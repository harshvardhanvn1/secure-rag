import time
from pathlib import Path

from apps import db
from apps.embeddings import embed_texts, EMBEDDING_MODEL
from ingest.pii import redact_text
from ingest.min_ingest import simple_sent_chunk  # reuse existing chunker

CLEAN_DIR = Path("data/sec/clean")

def ingest_one_file(conn, path: Path, owner_email="alice@example.com", owner_name="Alice"):
    raw = path.read_text(encoding="utf-8", errors="ignore")
    chunks = simple_sent_chunk(raw, max_len=800)
    redacted = [redact_text(c) for c in chunks]

    user_id = db.ensure_user(conn, owner_email, owner_name)
    title = path.stem.replace("_", " ")
    doc_id = db.create_document(conn, user_id, f"{title} ({int(time.time())})")
    db.grant_owner(conn, doc_id, user_id)

    chunk_ids = []
    with conn.cursor() as cur:
        for ord_i, txt in enumerate(redacted):
            cur.execute(
                "INSERT INTO chunk (doc_id, ord, redacted_text) VALUES (%s, %s, %s) RETURNING chunk_id;",
                (doc_id, ord_i, txt),
            )
            chunk_ids.append(cur.fetchone()[0])
    conn.commit()

    vectors = embed_texts(redacted)
    with conn.cursor() as cur:
        for cid, vec in zip(chunk_ids, vectors):
            placeholder = ",".join(["%s"] * len(vec))
            cur.execute(
                f"""
                INSERT INTO chunk_embedding (chunk_id, embedding, model_name)
                VALUES (%s, ARRAY[{placeholder}]::vector, %s)
                ON CONFLICT (chunk_id) DO UPDATE
                  SET embedding = EXCLUDED.embedding, model_name = EXCLUDED.model_name;
                """,
                (cid, *vec, EMBEDDING_MODEL),
            )
    conn.commit()
    return doc_id, len(redacted)

def main():
    paths = sorted(CLEAN_DIR.glob("*.txt"))
    if not paths:
        raise SystemExit(f"No files found in {CLEAN_DIR}. Run scripts/clean_sec.py first.")
    with db.get_conn() as conn:
        conn.execute("SET TIME ZONE 'UTC';")
        totals = []
        for p in paths:
            doc_id, n = ingest_one_file(conn, p)
            print(f"{p.name}: {n} chunks → doc_id={doc_id}")
            totals.append(n)
        print(f"\nAll done. Files: {len(paths)}, total chunks: {sum(totals)}")

if __name__ == "__main__":
    main()
