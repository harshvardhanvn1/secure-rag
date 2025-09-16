from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Tuple
from pydantic import BaseModel
from uuid import UUID
import io
from pypdf import PdfReader

from apps.db import (
    get_conn, ensure_user, create_or_get_document,
    delete_document_chunks, insert_chunks, insert_embeddings,
    grant_owner, insert_retrieval_trace
)
from apps.embeddings import embed_texts, EMBEDDING_MODEL, EMBEDDING_DIM
from ingest.pii import redact_text

app = FastAPI(title="Secure-RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- auth stub ---
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
    # stub token = just email
    return {"token": req.email}



# --- request/response models ---
class IngestRequest(BaseModel):
    title: str
    text: str
    source_key: Optional[str] = None


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class SearchHit(BaseModel):
    rank: int
    chunk_id: UUID
    score: float
    title: str
    snippet: str


class SearchResponse(BaseModel):
    hits: List[SearchHit]
    trace_id: Optional[int] = None


# --- health check ---
@app.get("/healthz")
def health():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
    return {"ok": True, "model": EMBEDDING_MODEL}


# --- JSON ingest ---
@app.post("/ingest")
def ingest(req: IngestRequest, current: Tuple[UUID, str] = Depends(get_current_user)):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Empty text")

    user_id, _ = current

    with get_conn() as conn:
        source_key = req.source_key or f"adhoc/{req.title.lower().replace(' ', '-')}"
        doc_id, is_new = create_or_get_document(conn, owner_user_id=user_id, title=req.title, source_key=source_key)
        if not is_new:
            delete_document_chunks(conn, doc_id)

        CHUNK_SIZE = 800
        chunks = [req.text[i:i+CHUNK_SIZE] for i in range(0, len(req.text), CHUNK_SIZE)]
        redacted = [redact_text(c) for c in chunks]

        chunk_ids = insert_chunks(conn, doc_id, redacted)
        vecs = embed_texts(redacted)
        insert_embeddings(conn, chunk_ids=chunk_ids, vectors=vecs, model_name=EMBEDDING_MODEL)

        grant_owner(conn, doc_id, user_id)
        conn.commit()

    return {"doc_id": doc_id, "chunks": len(chunk_ids), "status": "replaced" if not is_new else "created"}


# --- File ingest ---
@app.post("/ingest_file")
async def ingest_file(file: UploadFile = File(...), current: Tuple[UUID, str] = Depends(get_current_user)):
    name = file.filename or "upload"
    fn_lower = name.lower()

    data = await file.read()  # async read

    content_type = (file.content_type or "").lower()
    full_text = ""

    if fn_lower.endswith(".pdf") or "pdf" in content_type:
        reader = PdfReader(io.BytesIO(data))
        full_text = "\n".join((page.extract_text() or "") for page in reader.pages)
    elif fn_lower.endswith(".txt") or content_type.startswith("text/"):
        full_text = data.decode("utf-8", errors="ignore")
    else:
        raise HTTPException(400, detail="Only .pdf and .txt supported for now")

    if not full_text.strip():
        raise HTTPException(400, detail="No text extracted")

    req = IngestRequest(title=name, text=full_text, source_key=f"upload/{fn_lower.replace(' ', '-')}")
    return ingest(req, current)


# --- Search ---
@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest, current: Tuple[UUID, str] = Depends(get_current_user)):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Empty query")

    user_id, _ = current
    qvec = embed_texts([req.query])[0]

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT c.chunk_id, d.title, c.redacted_text,
                    (1 - (ce.embedding <=> %s::vector({EMBEDDING_DIM}))) AS score
                FROM chunk_embedding ce
                JOIN chunk c ON c.chunk_id = ce.chunk_id
                JOIN document d ON d.doc_id = c.doc_id
                JOIN document_acl da ON da.doc_id = d.doc_id
                WHERE ce.model_name = %s
                AND da.user_id = %s
                ORDER BY ce.embedding <=> %s::vector({EMBEDDING_DIM})
                LIMIT %s;
            """, (qvec, EMBEDDING_MODEL, user_id, qvec, req.top_k))
            rows = cur.fetchall()


    resp_hits = []
    trace_hits = []
    for i, (chunk_id, title, text, score) in enumerate(rows, start=1):
        snippet = (text[:320] + "…") if len(text) > 320 else text
        resp_hits.append(SearchHit(
            rank=i,
            chunk_id=chunk_id,
            score=float(score),  # cosine similarity
            title=title,
            snippet=snippet
        ))
        trace_hits.append((chunk_id, float(score)))


    with get_conn() as trace_conn:
        trace_id = insert_retrieval_trace(trace_conn, user_id, req.query, req.top_k, trace_hits)
        trace_conn.commit()

    return SearchResponse(hits=resp_hits, trace_id=trace_id)
