import os, re, uuid, time
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
import psycopg
from pii import redact_text

# Load env
load_dotenv()
DSN = os.getenv("POSTGRES_DSN")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1536"))

PROVIDER = os.getenv("EMBEDDING_PROVIDER", "hf")
HF_MODEL = os.getenv("HF_MODEL", "sentence-transformers/all-mpnet-base-v2")
HF_DIM = int(os.getenv("HF_DIM", "768"))

local_model = None
if PROVIDER == "hf":
    from sentence_transformers import SentenceTransformer
    local_model = SentenceTransformer(HF_MODEL)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

try:
    from openai import OpenAI
    openai_client: Optional[OpenAI] = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
except ImportError as e:
    print("⚠️ Failed to import openai package:", e)
    openai_client = None


# --- tiny helpers (student-level, simple and readable) ---

def simple_sent_chunk(text: str, max_len: int = 500):
    """Split by sentence-ish separators; merge small ones up to ~max_len."""
    parts = re.split(r'(?<=[\.\!\?])\s+', text.strip())
    chunks, buf = [], ""
    for p in parts:
        if not p:
            continue
        if len(buf) + 1 + len(p) <= max_len:
            buf = (buf + " " + p).strip()
        else:
            if buf: chunks.append(buf)
            buf = p
    if buf: chunks.append(buf)
    # add ord numbers upstream
    return [c.strip() for c in chunks if c.strip()]

# def fake_redact(text: str) -> str:
#     """Very basic redaction: emails → [EMAIL], digits that look like phone → [PHONE]."""
#     t = re.sub(r'[\w\.-]+@[\w\.-]+', '[EMAIL]', text)
#     t = re.sub(r'\b(?:\+?\d[\d\-\s]{7,}\d)\b', '[PHONE]', t)
#     return t

def ensure_user(conn, email: str, display_name: str) -> uuid.UUID:
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO app_user (email, display_name)
            VALUES (%s, %s)
            ON CONFLICT (email) DO UPDATE SET display_name=EXCLUDED.display_name
            RETURNING user_id;
        """, (email, display_name))
        return cur.fetchone()[0]

def create_document(conn, owner_user_id, title: str) -> uuid.UUID:
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO document (owner_user_id, title)
            VALUES (%s, %s)
            RETURNING doc_id;
        """, (owner_user_id, title))
        return cur.fetchone()[0]

def grant_owner(conn, doc_id, user_id):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO document_acl (doc_id, user_id, role)
            VALUES (%s, %s, 'owner')
            ON CONFLICT (doc_id, user_id) DO UPDATE SET role='owner';
        """, (doc_id, user_id))

# def insert_chunks_and_zero_embeddings(conn, doc_id, texts):
#     """Insert chunks and a zero vector for each (placeholder)."""
#     with conn.cursor() as cur:
#         for ord_i, red_text in enumerate(texts):
#             cur.execute("""
#                 INSERT INTO chunk (doc_id, ord, redacted_text)
#                 VALUES (%s, %s, %s)
#                 RETURNING chunk_id;
#             """, (doc_id, ord_i, red_text))
#             chunk_id = cur.fetchone()[0]

#             # Build a zero vector of required dim in SQL
#             cur.execute(f"""
#                 INSERT INTO chunk_embedding (chunk_id, embedding, model_name)
#                 VALUES (%s, array_fill(0.0::float4, ARRAY[{EMBEDDING_DIM}])::vector, %s);
#             """, (chunk_id, 'placeholder'))
#     conn.commit()

def insert_chunks(conn, doc_id, texts):
    chunk_ids = []
    with conn.cursor() as cur:
        for ord_i, red_text in enumerate(texts):
            cur.execute("""
                INSERT INTO chunk (doc_id, ord, redacted_text)
                VALUES (%s, %s, %s)
                RETURNING chunk_id;
            """, (doc_id, ord_i, red_text))
            chunk_ids.append(cur.fetchone()[0])
    conn.commit()
    return chunk_ids

def insert_embeddings(conn, chunk_ids: List[str], vectors: List[List[float]]):
    assert len(chunk_ids) == len(vectors)
    with conn.cursor() as cur:
        for cid, vec in zip(chunk_ids, vectors):
            # psycopg will adapt Python lists to Postgres arrays; cast to vector
            dim = len(vec)
            placeholder = ",".join(["%s"] * dim)
            cur.execute(
                f"INSERT INTO chunk_embedding (chunk_id, embedding, model_name) "
                f"VALUES (%s, ARRAY[{placeholder}]::vector, %s) "
                f"ON CONFLICT (chunk_id) DO UPDATE SET embedding = EXCLUDED.embedding, model_name = EXCLUDED.model_name;",
                (cid, *vec, EMBEDDING_MODEL)
            )
    conn.commit()


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Return one embedding per text.
    - OpenAI if provider=openai and key present
    - HuggingFace local model if provider=hf
    - Fallback: zeros
    """
    if PROVIDER == "openai" and openai_client:
        resp = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
        return [d.embedding for d in resp.data]

    if PROVIDER == "hf" and local_model:
        return local_model.encode(texts, normalize_embeddings=True).tolist()

    # Final fallback: zeros
    dim = HF_DIM if PROVIDER == "hf" else EMBEDDING_DIM
    return [[0.0] * dim for _ in texts]


def main():
    src = Path("samples/sample_policy.txt")
    if not src.exists():
        raise SystemExit(f"Missing file: {src}")

    text = src.read_text(encoding="utf-8")
    chunks = simple_sent_chunk(text)
    redacted = [redact_text(c) for c in chunks]

    print(f"Read {len(chunks)} chunks; after redaction: {len(redacted)}")

    with psycopg.connect(DSN) as conn:
        conn.execute("SET TIME ZONE 'UTC';")
        user_id = ensure_user(conn, "alice@example.com", "Alice")
        doc_id = create_document(conn, user_id, f"Sample Policy ({int(time.time())})")
        grant_owner(conn, doc_id, user_id)

        chunk_ids = insert_chunks(conn, doc_id, redacted)
        vectors = embed_texts(redacted)  # real if key present, else zeros
        insert_embeddings(conn, chunk_ids, vectors)

    print(f"Ingestion complete (embeddings: {PROVIDER})")



if __name__ == "__main__":
    main()
