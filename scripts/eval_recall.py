import json
import requests
import psycopg
import os

API_URL = os.getenv("API_URL", "http://localhost:8000")
DSN = os.getenv("POSTGRES_DSN")

def eval_recall(gold_path, user_email="alice@example.com"):
    with open(gold_path) as f:
        gold = json.load(f)

    results = []
    with psycopg.connect(DSN) as conn:
        for item in gold:
            query = item["query"]
            gold_chunks = set(item["gold_chunks"])
            top_k = item.get("top_k", 5)

            r = requests.post(
                f"{API_URL}/search",
                headers={"X-User-Email": user_email, "Content-Type": "application/json"},
                json={"query": query, "top_k": top_k},
            )
            r.raise_for_status()
            resp = r.json()
            trace_id = resp["trace_id"]
            hits = [h["chunk_id"] for h in resp["hits"]]

            recall = 1.0 if gold_chunks.intersection(hits) else 0.0
            results.append((query, recall))

            # save to DB
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO retrieval_eval (trace_id, query_text, gold_chunks, top_k, hits, recall_at_k)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """, (trace_id, query, list(gold_chunks), top_k, hits, recall))
            conn.commit()

    avg = sum(r for _, r in results) / len(results)
    print(f"Recall@K: {avg:.2f}")
    for q, r in results:
        print(f"{q:40s} {r}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python scripts/eval_recall.py gold.json")
        sys.exit(1)
    eval_recall(sys.argv[1])
