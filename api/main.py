# api/main.py
from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Tuple, Dict
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
import io
import re

from pypdf import PdfReader

from apps.db import (
    get_conn, ensure_user, create_or_get_document,
    delete_document_chunks, insert_chunks, insert_embeddings,
    grant_owner, insert_retrieval_trace
)
from apps.embeddings import embed_texts, EMBEDDING_MODEL
from ingest.pii import redact_and_report

app = FastAPI(title="Secure-RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ "http://localhost:5173",  # dev
    "http://localhost:3000", # docker prod
    ],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- auth ----------
async def get_current_user(authorization: str = Header(None)) -> Tuple[UUID, str]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    email = authorization.replace("Bearer ", "").strip()
    if not email:
        raise HTTPException(status_code=401, detail="Empty email token")

    with get_conn() as conn:
        user_id = ensure_user(conn, email=email, display_name=email)
        conn.commit()
    return user_id, email

class LoginRequest(BaseModel):
    email: str

@app.post("/login")
def login(req: LoginRequest):
    if not req.email.strip():
        raise HTTPException(status_code=400, detail="Email required")
    return {"token": req.email.strip()}

# ---------- health ----------
@app.get("/healthz")
def health():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
    return {"ok": True, "model": EMBEDDING_MODEL}

# ---------- models ----------
class IngestRequest(BaseModel):
    title: str
    text: str
    source_key: Optional[str] = None

class IngestResponse(BaseModel):
    doc_id: UUID
    chunks: int
    status: str

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5

class SearchHit(BaseModel):
    rank: int
    chunk_id: UUID
    score: float         # cosine similarity
    title: str
    snippet: str

class SearchResponse(BaseModel):
    hits: List[SearchHit]
    trace_id: Optional[int] = None

# Security stats models
class RedactionSummaryRow(BaseModel):
    entity_type: str
    total: int

class SecurityStats(BaseModel):
    totals: List[RedactionSummaryRow]
    last_7d: List[RedactionSummaryRow]
    last_24h: List[RedactionSummaryRow]

class SecurityRunRow(BaseModel):
    run_id: int
    created_at: datetime
    notes: Optional[str]
    micro_precision: float
    micro_recall: float
    micro_f1: float

# ---------- simple chunker ----------
_SENT_SPLIT = re.compile(r"(?<=[\.!?])\s+|\n{2,}")

def simple_sent_chunk(text: str, max_len: int = 800) -> List[str]:
    parts = [p.strip() for p in _SENT_SPLIT.split(text) if p.strip()]
    chunks: List[str] = []
    buf = ""
    for p in parts:
        if not buf:
            buf = p
        elif len(buf) + 1 + len(p) <= max_len:
            buf = f"{buf} {p}"
        else:
            chunks.append(buf)
            buf = p
    if buf:
        chunks.append(buf)
    return chunks

# ---------- helper: redaction log insert ----------
def _insert_redaction_counts(conn, doc_id: UUID, chunk_id: UUID, counts: Dict[str, int]) -> None:
    if not counts:
        return
    rows = [(doc_id, chunk_id, et, cnt) for et, cnt in counts.items() if cnt > 0]
    if not rows:
        return
    with conn.cursor() as cur:
        cur.executemany("""
            INSERT INTO redaction_log (doc_id, chunk_id, entity_type, count)
            VALUES (%s, %s, %s, %s);
        """, rows)

# ---------- JSON ingest ----------
@app.post("/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest, current: Tuple[UUID, str] = Depends(get_current_user)):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Empty text")

    user_id, _ = current
    title = req.title.strip() or "Untitled"
    source_key = (req.source_key or f"manual/{title.lower().replace(' ', '-')}" )

    chunks_plain = simple_sent_chunk(req.text, max_len=800)

    # Redact + collect entity counts per chunk
    redacted_list: List[str] = []
    counts_list: List[Dict[str, int]] = []
    for c in chunks_plain:
        rc, counts = redact_and_report(c)
        redacted_list.append(rc)
        counts_list.append(counts)

    if not redacted_list:
        raise HTTPException(400, detail="No usable content")

    with get_conn() as conn:
        doc_id, is_new = create_or_get_document(conn, owner_user_id=user_id, title=title, source_key=source_key)
        # replace existing chunks/embeddings for this doc_id
        delete_document_chunks(conn, doc_id)
        chunk_ids = insert_chunks(conn, doc_id, redacted_list)
        vecs = embed_texts(redacted_list)
        insert_embeddings(conn, chunk_ids=chunk_ids, vectors=vecs, model_name=EMBEDDING_MODEL)
        grant_owner(conn, doc_id, user_id)

        # log PII counts per chunk
        for chunk_id, counts in zip(chunk_ids, counts_list):
            _insert_redaction_counts(conn, doc_id, chunk_id, counts)

        conn.commit()

    return IngestResponse(doc_id=doc_id, chunks=len(chunk_ids), status=("created" if is_new else "replaced"))

# ---------- File ingest ----------
@app.post("/ingest_file", response_model=IngestResponse)
async def ingest_file(file: UploadFile = File(...), current: Tuple[UUID, str] = Depends(get_current_user)):
    name = file.filename or "upload"
    fn_lower = name.lower()

    data = await file.read()
    content_type = (file.content_type or "").lower()
    full_text = ""

    if fn_lower.endswith(".pdf") or "pdf" in content_type:
        reader = PdfReader(io.BytesIO(data))
        full_text = "\n".join((page.extract_text() or "") for page in reader.pages)
    elif fn_lower.endswith(".txt") or content_type.startswith("text/"):
        full_text = data.decode("utf-8", errors="ignore")
    else:
        raise HTTPException(status_code=400, detail="Only .pdf and .txt supported for now")

    if not full_text.strip():
        raise HTTPException(400, detail="No text extracted")

    req = IngestRequest(title=name, text=full_text, source_key=f"upload/{fn_lower.replace(' ', '-')}")
    return ingest(req, current)

# ---------- Search ----------
@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest, current: Tuple[UUID, str] = Depends(get_current_user)):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Empty query")

    user_id, _ = current
    [qvec] = embed_texts([req.query])

    dim = len(qvec)
    placeholder = ",".join(["%s"] * dim)

    sql = f"""
    WITH q AS (
      SELECT ARRAY[{placeholder}]::vector AS v
    )
    SELECT
      c.chunk_id,
      -- convert L2 distance to cosine similarity for unit vectors: cos = 1 - (d^2)/2
      (1.0 - ((emb.embedding <-> q.v) * (emb.embedding <-> q.v)) / 2.0) AS score,
      d.title,
      CASE
        WHEN length(c.redacted_text) > 400 THEN substring(c.redacted_text for 400) || '…'
        ELSE c.redacted_text
      END AS snippet,
      (emb.embedding <-> q.v) AS dist
    FROM chunk_embedding emb
    JOIN chunk c ON c.chunk_id = emb.chunk_id
    JOIN document d ON d.doc_id = c.doc_id
    LEFT JOIN document_acl a ON a.doc_id = d.doc_id
    JOIN q ON TRUE
    WHERE d.owner_user_id = %s OR a.user_id = %s
    ORDER BY dist ASC
    LIMIT %s;
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (*qvec, user_id, user_id, req.top_k))
            rows = cur.fetchall()

    resp_hits: List[SearchHit] = []
    trace_hits = []
    for i, (chunk_id, score, title, snippet, _dist) in enumerate(rows, start=1):
        resp_hits.append(SearchHit(
            rank=i,
            chunk_id=chunk_id,
            score=float(score),
            title=title,
            snippet=snippet
        ))
        trace_hits.append((chunk_id, float(score)))

    with get_conn() as trace_conn:
        trace_id = insert_retrieval_trace(trace_conn, user_id, req.query, req.top_k, trace_hits)
        trace_conn.commit()

    return SearchResponse(hits=resp_hits, trace_id=trace_id)

# ---------- Leaderboard (Recall@K) ----------
class LeaderboardRow(BaseModel):
    eval_id: int
    trace_id: int
    query_text: str
    top_k: int
    recall_at_k: float
    hits: List[UUID]
    gold_chunks: List[UUID]
    created_at: datetime

class LeaderboardSummary(BaseModel):
    avg_recall: Optional[float] = None
    n_evals: int = 0
    last_eval_at: Optional[datetime] = None

class LeaderboardResponse(BaseModel):
    summary: LeaderboardSummary
    rows: List[LeaderboardRow]

@app.get("/leaderboard", response_model=LeaderboardResponse)
def leaderboard(current: Tuple[UUID, str] = Depends(get_current_user), limit: int = 200):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(AVG(recall_at_k), 0.0)::float, COUNT(*), MAX(created_at)
                FROM retrieval_eval;
            """)
            avg_recall, n_evals, last_eval_at = cur.fetchone() or (0.0, 0, None)

            cur.execute("""
                SELECT eval_id, trace_id, query_text, gold_chunks, top_k, hits, recall_at_k, created_at
                FROM retrieval_eval
                ORDER BY created_at DESC
                LIMIT %s;
            """, (limit,))
            rows = cur.fetchall()

    out_rows = [
        LeaderboardRow(
            eval_id=r[0],
            trace_id=r[1],
            query_text=r[2],
            gold_chunks=r[3],
            top_k=r[4],
            hits=r[5],
            recall_at_k=float(r[6]),
            created_at=r[7],
        ) for r in rows
    ]
    return LeaderboardResponse(
        summary=LeaderboardSummary(
            avg_recall=(float(avg_recall) if avg_recall is not None else None),
            n_evals=int(n_evals or 0),
            last_eval_at=last_eval_at
        ),
        rows=out_rows
    )

# ---------- Security stats ----------
@app.get("/security_stats", response_model=SecurityStats)
def security_stats(current: Tuple[UUID, str] = Depends(get_current_user)):
    def _fetch_rows(where: str = "", params: tuple = ()) -> List[RedactionSummaryRow]:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT entity_type, COALESCE(SUM(count),0)::bigint
                    FROM redaction_log
                    {where}
                    GROUP BY entity_type
                    ORDER BY entity_type;
                """, params)
                rows = cur.fetchall()
        return [RedactionSummaryRow(entity_type=r[0], total=int(r[1])) for r in rows]

    totals = _fetch_rows()
    last_7d = _fetch_rows("WHERE created_at >= now() - interval '7 days'")
    last_24h = _fetch_rows("WHERE created_at >= now() - interval '24 hours'")
    return SecurityStats(totals=totals, last_7d=last_7d, last_24h=last_24h)

@app.get("/security_runs", response_model=List[SecurityRunRow])
def security_runs(current: Tuple[UUID, str] = Depends(get_current_user), limit: int = Query(20, ge=1, le=200)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT r.run_id, r.created_at, r.notes,
                       o.micro_precision, o.micro_recall, o.micro_f1
                FROM pii_eval_run r
                JOIN pii_eval_overall o USING (run_id)
                ORDER BY r.created_at DESC
                LIMIT %s;
            """, (limit,))
            rows = cur.fetchall()
    out = [
        SecurityRunRow(
            run_id=r[0], created_at=r[1], notes=r[2],
            micro_precision=float(r[3]), micro_recall=float(r[4]), micro_f1=float(r[5])
        )
        for r in rows
    ]
    return out
