# apps/db.py
import os
import psycopg
import uuid
from typing import List, Tuple, Optional
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


def create_or_get_document(conn, owner_user_id: int, title: str, source_key: str) -> Tuple[int, bool]:
    """
    Idempotent document creation.
    Returns (doc_id, is_new)
    """
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO document (owner_user_id, title, source_key, created_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (source_key) DO NOTHING
            RETURNING doc_id;
        """, (owner_user_id, title, source_key))
        row = cur.fetchone()
        if row:
            return row[0], True  # created new

        # fetch existing doc_id; keep title fresh if it changed
        cur.execute("SELECT doc_id, title FROM document WHERE source_key = %s;", (source_key,))
        fetched = cur.fetchone()
        if not fetched:
            raise RuntimeError("create_or_get_document: neither inserted nor found existing row")
        doc_id, existing_title = fetched
        if existing_title != title:
            cur.execute("UPDATE document SET title = %s WHERE doc_id = %s;", (title, doc_id))
        return doc_id, False  # reused existing


def delete_document_chunks(conn, doc_id: int) -> None:
    """
    Remove all chunks & embeddings for a given document.
    """
    with conn.cursor() as cur:
        cur.execute("""
            DELETE FROM chunk_embedding
            WHERE chunk_id IN (SELECT chunk_id FROM chunk WHERE doc_id = %s);
        """, (doc_id,))
        cur.execute("DELETE FROM chunk WHERE doc_id = %s;", (doc_id,))

    
def insert_retrieval_trace(conn, user_id, query_text: str, top_k: int, hits):
    """
    hits: list of (chunk_id, score) ordered by rank
    Returns trace_id
    """
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO retrieval_trace (user_id, query_text, top_k, created_at)
            VALUES (%s, %s, %s, NOW())
            RETURNING trace_id;
        """, (user_id, query_text, top_k))
        trace_id = cur.fetchone()[0]

        for rank, (cid, score) in enumerate(hits, start=1):
            cur.execute("""
                INSERT INTO retrieval_trace_hit (trace_id, rank, chunk_id, score)
                VALUES (%s, %s, %s, %s);
            """, (trace_id, rank, cid, score))

    return trace_id
