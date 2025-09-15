# api/main.py

import os
from typing import List, Optional, Tuple
from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File
from pydantic import BaseModel, Field
from uuid import UUID
from pypdf import PdfReader
import io

from apps.db import (
    get_conn,
    ensure_user,
    create_or_get_document,
    delete_document_chunks,
    insert_chunks,
    insert_embeddings,
    grant_owner,
    insert_retrieval_trace  # ensure this is imported
)
from apps.embeddings import embed_texts, EMBEDDING_MODEL, EMBEDDING_DIM
from ingest.pii import redact_text


# --- auth stub dependency ---
async def get_current_user(x_user_email: str = Header(None)) -> Tuple[UUID, str]:
    """
    Stub for current user: read from header X-User-Email, create or fetch.
    Returns (user_id, email).
    """
    if not x_user_email:
        raise HTTPException(status_code=401, detail="X-User-Email header required")
    with get_conn() as conn:
        user_id = ensure_user(conn, email=x_user_email, display_name=x_user_email)
        conn.commit()
    return user_id, x_user_email


# --- request/response models ---
class IngestRequest(BaseModel):
    title: str = Field(..., description="Document title shown in UI")
    text: str = Field(..., description="Raw cleaned text")
    source_key: Optional[str] = Field(None, description="Stable key to make re-ingest replace old content (optional)")


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
    trace_id: Optional[int] = None   # optional trace id


app = FastAPI(title="Secure-RAG API (with trace logging + ACL)")


@app.get("/healthz")
def health():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
    return {"ok": True, "model": EMBEDDING_MODEL}


@app.post("/ingest")
def ingest(
    req: IngestRequest,
    current: Tuple[UUID, str] = Depends(get_current_user)
):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Empty text")

    user_id, user_email = current

    with get_conn() as conn:
        # idempotent creation or reuse
        source_key = req.source_key or f"adhoc/{req.title.lower().replace(' ', '-')}"
        doc_id, is_new = create_or_get_document(conn, owner_user_id=user_id, title=req.title, source_key=source_key)
        if not is_new:
            delete_document_chunks(conn, doc_id)

        # chunking + redaction
        CHUNK_SIZE = 800
        chunks = [req.text[i : i + CHUNK_SIZE] for i in range(0, len(req.text), CHUNK_SIZE)]
        redacted = [redact_text(c) for c in chunks]

        # insert chunks & embeddings
        chunk_ids = insert_chunks(conn, doc_id, redacted)
        vecs = embed_texts(redacted)
        insert_embeddings(conn, chunk_ids=chunk_ids, vectors=vecs, model_name=EMBEDDING_MODEL)

        # grant owner
        grant_owner(conn, doc_id, user_id)

        conn.commit()

    return {
        "doc_id": doc_id,
        "chunks": len(chunk_ids),
        "status": "replaced" if not is_new else "created"
    }

@app.post("/ingest_file")
def ingest_file(
    file: UploadFile = File(...),
    current: tuple[UUID, str] = Depends(get_current_user)
):
    name = file.filename or "upload"
    fn_lower = name.lower()

    # read bytes once
    data = file.file.read()

    # figure out text based on extension / content-type
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

    # reuse your existing JSON ingest pipeline
    req = IngestRequest(
        title=name,
        text=full_text,
        source_key=f"upload/{fn_lower.replace(' ', '-')}"
    )
    return ingest(req, current)

@app.post("/search", response_model=SearchResponse)
def search(
    req: SearchRequest,
    current: Tuple[UUID, str] = Depends(get_current_user)
):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Empty query")

    user_id, user_email = current
    qvec = embed_texts([req.query])[0]

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT c.chunk_id, d.title, c.redacted_text,
                       (ce.embedding <-> %s::vector({EMBEDDING_DIM})) AS score
                FROM chunk_embedding ce
                JOIN chunk c ON c.chunk_id = ce.chunk_id
                JOIN document d ON d.doc_id = c.doc_id
                JOIN document_acl da ON da.doc_id = d.doc_id
                WHERE ce.model_name = %s
                  AND da.user_id = %s
                ORDER BY ce.embedding <-> %s::vector({EMBEDDING_DIM})
                LIMIT %s;
            """, (qvec, EMBEDDING_MODEL, user_id, qvec, req.top_k))
            rows = cur.fetchall()

    # prepare hits for response and for trace
    resp_hits: List[SearchHit] = []
    trace_hits: List[Tuple[UUID, float]] = []  # (chunk_id, score)
    for i, (chunk_id, title, text, score) in enumerate(rows, start=1):
        snippet = (text[:320] + "…") if len(text) > 320 else text
        resp_hits.append(SearchHit(
            rank=i,
            chunk_id=chunk_id,
            score=float(score),
            title=title,
            snippet=snippet
        ))
        trace_hits.append((chunk_id, float(score)))

    # log trace
    with get_conn() as trace_conn:
        trace_id = insert_retrieval_trace(trace_conn, user_id, req.query, req.top_k, trace_hits)
        trace_conn.commit()

    return SearchResponse(hits=resp_hits, trace_id=trace_id)
