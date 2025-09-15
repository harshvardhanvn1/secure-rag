# apps/db.py
import os
import psycopg
import uuid
from dotenv import load_dotenv

load_dotenv()
DSN = os.getenv("POSTGRES_DSN")

def get_conn():
    return psycopg.connect(DSN)

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

def insert_chunks(conn, doc_id, texts):
    ids = []
    with conn.cursor() as cur:
        for ord_i, red_text in enumerate(texts):
            cur.execute("""
                INSERT INTO chunk (doc_id, ord, redacted_text)
                VALUES (%s, %s, %s)
                RETURNING chunk_id;
            """, (doc_id, ord_i, red_text))
            ids.append(cur.fetchone()[0])
    conn.commit()
    return ids

def insert_embeddings(conn, chunk_ids, vectors, model_name: str):
    assert len(chunk_ids) == len(vectors)
    with conn.cursor() as cur:
        for cid, vec in zip(chunk_ids, vectors):
            dim = len(vec)
            placeholder = ",".join(["%s"] * dim)
            cur.execute(
                f"INSERT INTO chunk_embedding (chunk_id, embedding, model_name) "
                f"VALUES (%s, ARRAY[{placeholder}]::vector, %s) "
                f"ON CONFLICT (chunk_id) DO UPDATE "
                f"SET embedding = EXCLUDED.embedding, model_name = EXCLUDED.model_name;",
                (cid, *vec, model_name)
            )
    conn.commit()
