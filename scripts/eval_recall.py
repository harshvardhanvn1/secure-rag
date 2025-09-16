import sys
import json
import requests
import psycopg
import os

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
USER_EMAIL = os.getenv("USER_EMAIL")
if not USER_EMAIL:
    raise RuntimeError("USER_EMAIL not set. export USER_EMAIL='your-real-login-email'")

def get_dsn():
    dsn = os.getenv("POSTGRES_DSN")
    if not dsn:
        raise RuntimeError(
            "POSTGRES_DSN not set.\n"
            "Examples:\n"
            "  export POSTGRES_DSN='postgresql://postgres:postgres@localhost:5433/securerag'  # host machine\n"
            "  export POSTGRES_DSN='postgresql://postgres:postgres@db:5432/securerag'        # inside compose network"
        )
    return dsn

def eval_recall(gold_path):
    DSN = get_dsn()

    with open(gold_path, "r") as f:
        gold = json.load(f)

    results = []

    with psycopg.connect(DSN) as conn:
        for item in gold:
            query = item["query"]
            top_k = item.get("top_k", 5)

            # Normalize golds
            gold_chunks = {str(gc).lower() for gc in item.get("gold_chunks", [])}
            gold_doc_ids = {str(d).lower() for d in item.get("gold_doc_ids", [])}

            if gold_doc_ids and not gold_chunks:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT c.chunk_id
                        FROM chunk c
                        WHERE c.doc_id = ANY(%s)
                    """, (list(gold_doc_ids),))
                    gold_chunks = {str(row[0]).lower() for row in cur.fetchall()}

            # Run search
            r = requests.post(
                f"{API_URL}/search",
                headers={"Authorization": f"Bearer {USER_EMAIL}", "Content-Type": "application/json"},
                json={"query": query, "top_k": top_k},
                timeout=60,
            )
            r.raise_for_status()
            data = r.json()
            trace_id = data.get("trace_id")
            hits = [str(h["chunk_id"]).lower() for h in data.get("hits", [])]

            # Compute recall@k
            hit_set = set(hits)
            recall = 1.0 if (gold_chunks & hit_set) else 0.0

            results.append((query, recall))

            # Persist in retrieval_eval
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
