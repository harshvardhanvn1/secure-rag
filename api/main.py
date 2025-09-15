# api/main.py
import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from uuid import UUID


from apps.db import get_conn, ensure_user, create_or_get_document, delete_document_chunks, insert_chunks, insert_embeddings
from apps.embeddings import embed_texts, EMBEDDING_MODEL, EMBEDDING_DIM
from ingest.pii import redact_text

# --- models ---
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

# --- app ---
app = FastAPI(title="Secure-RAG API (minimal)")

@app.get("/healthz")
def health():
    # minimal check that DB is reachable
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
    return {"ok": True, "model": EMBEDDING_MODEL}

@app.post("/ingest")
def ingest(req: IngestRequest):
    if not req.text.strip():
        raise HTTPException(400, "Empty text")

    # pick a basic source_key if not provided (safe default)
    source_key = req.source_key or f"adhoc/{req.title.lower().replace(' ', '-')}"
    with get_conn() as conn:
        user_id = ensure_user(conn, email="demo@local", display_name="Demo User")
        doc_id, is_new = create_or_get_document(conn, owner_user_id=user_id, title=req.title, source_key=source_key)
        if not is_new:
            # keep idempotent ingest (cheap & predictable)
            delete_document_chunks(conn, doc_id)

        # naive chunking (same as your bulk_ingest)
        text = req.text
        CHUNK_SIZE = 800
        chunks = [text[i:i+CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]

        # PII redaction
        redacted = [redact_text(c) for c in chunks]

        # insert chunks
        chunk_ids = insert_chunks(conn, doc_id, redacted)


        # embed
        vecs = embed_texts(redacted)
        insert_embeddings(conn, chunk_ids=chunk_ids, vectors=vecs, model_name=EMBEDDING_MODEL)

        conn.commit()
        return {"doc_id": doc_id, "chunks": len(chunk_ids), "status": "replaced" if not is_new else "created"}

@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    if not req.query.strip():
        raise HTTPException(400, "Empty query")

    qvec = embed_texts([req.query])[0]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT c.chunk_id, d.title, c.redacted_text,
                       (ce.embedding <-> %s::vector({EMBEDDING_DIM})) AS score
                FROM chunk_embedding ce
                JOIN chunk c ON c.chunk_id = ce.chunk_id
                JOIN document d ON d.doc_id = c.doc_id
                WHERE ce.model_name = %s
                ORDER BY ce.embedding <-> %s::vector({EMBEDDING_DIM})
                LIMIT %s;
            """, (qvec, EMBEDDING_MODEL, qvec, req.top_k))
            rows = cur.fetchall()

    hits = []
    for i, (chunk_id, title, text, score) in enumerate(rows, start=1):
        snippet = (text[:320] + "…") if len(text) > 320 else text
        hits.append(SearchHit(
            rank=i,
            chunk_id=chunk_id,
            score=float(score),
            title=title,
            snippet=snippet
        ))

    return SearchResponse(hits=hits)
