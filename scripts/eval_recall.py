import sys
import json
import requests
import psycopg
import os

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

def get_dsn():
    dsn = os.getenv("POSTGRES_DSN")
    if not dsn:
        raise RuntimeError("POSTGRES_DSN not set. Run: export POSTGRES_DSN='postgresql://postgres:postgres@localhost:5433/securerag'")
    return dsn

def eval_recall(gold_path, user_email="alice@example.com"):
    DSN = get_dsn()
    with open(gold_path) as f:
        gold = json.load(f)

    results = []
    with psycopg.connect(DSN) as conn:
        for item in gold:
            query = item["query"]
            top_k = item.get("top_k", 5)

            # Support chunk IDs or doc IDs
            gold_chunks = set(item.get("gold_chunks", []))
            gold_doc_ids = set(item.get("gold_doc_ids", []))
            if gold_doc_ids and not gold_chunks:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT c.chunk_id
                        FROM chunk c
                        WHERE c.doc_id = ANY(%s)
                    """, (list(gold_doc_ids),))
                    gold_chunks = {row[0] for row in cur.fetchall()}

            r = requests.post(
                f"{API_URL}/search",
                headers={"X-User-Email": user_email, "Content-Type": "application/json"},
                json={"query": query, "top_k": top_k},
            )
            r.raise_for_status()
            resp = r.json()
            trace_id = resp["trace_id"]
            hits = [h["chunk_id"] for h in resp["hits"]]

            recall = 1.0 if set(hits).intersection(gold_chunks) else 0.0
            results.append((query, recall))

            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO retrieval_eval (trace_id, query_text, gold_chunks, top_k, hits, recall_at_k)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """, (trace_id, query, list(gold_chunks), top_k, hits, recall))
        conn.commit()

    avg = sum(r for _, r in results) / max(1, len(results))
    print(f"Recall@K: {avg:.2f}")
    for q, r in results:
        print(f"{q:40s} {r}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/eval_recall.py samples/gold.json")
        sys.exit(1)
    eval_recall(sys.argv[1])
