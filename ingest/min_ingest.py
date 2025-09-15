import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import re, time
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
import psycopg

from ingest.pii import redact_text

from apps import db
from apps.embeddings import embed_texts, EMBEDDING_MODEL, EMBEDDING_DIM


load_dotenv()


def simple_sent_chunk(text: str, max_len: int = 500):
    """Split into rough sentence chunks of ~max_len chars."""
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
    return [c.strip() for c in chunks if c.strip()]

def main():
    src = Path("samples/sample_policy.txt")
    if not src.exists():
        raise SystemExit(f"Missing file: {src}")

    text = src.read_text(encoding="utf-8")
    chunks = simple_sent_chunk(text)
    redacted = [redact_text(c) for c in chunks]

    print(f"Read {len(chunks)} chunks; after redaction: {len(redacted)}")

    with db.get_conn() as conn:
        conn.execute("SET TIME ZONE 'UTC';")
        user_id = db.ensure_user(conn, "alice@example.com", "Alice")
        doc_id = db.create_document(conn, user_id, f"Sample Policy ({int(time.time())})")
        db.grant_owner(conn, doc_id, user_id)

        chunk_ids = db.insert_chunks(conn, doc_id, redacted)
        vectors = embed_texts(redacted)
        db.insert_embeddings(conn, chunk_ids, vectors, EMBEDDING_MODEL)

    print("Ingestion complete")


if __name__ == "__main__":
    main()
