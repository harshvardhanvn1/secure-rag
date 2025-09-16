import beir
from beir import util
from beir.datasets.data_loader import GenericDataLoader
import requests
import json
import os

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
USER_EMAIL = os.getenv("USER_EMAIL")  # must be set

if not USER_EMAIL:
    raise RuntimeError("USER_EMAIL not set. Run: export USER_EMAIL='your-real-login-email'")

def main():
    dataset = "nq"
    url = f"https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/{dataset}.zip"
    data_path = util.download_and_unzip(url, "datasets")
    corpus, queries, qrels = GenericDataLoader(data_folder=data_path).load(split="test")

    print(f"Loaded {len(corpus)} docs, {len(queries)} queries")

    gold = []
    headers = {"Authorization": f"Bearer {USER_EMAIL}", "Content-Type": "application/json"}

    corpus_items = list(corpus.items())[:100]
    queries_items = list(queries.items())[:20]

    doc_id_map = {}

    # Ingest documents
    for doc_id, doc in corpus_items:
        text = f"{doc['title']}\n\n{doc['text']}" if doc.get("title") else doc["text"]
        res = requests.post(
            f"{API_URL}/ingest",
            headers=headers,
            json={"title": f"beir-{doc_id}", "text": text},
            timeout=60,
        )
        res.raise_for_status()
        resp = res.json()
        doc_id_map[doc_id] = resp["doc_id"]

    # Build gold.json
    for qid, query in queries_items:
        relevant_docs = list(qrels.get(qid, {}).keys())
        mapped = [doc_id_map[d] for d in relevant_docs if d in doc_id_map]
        if not mapped:
            continue
        gold.append({
            "query": query,
            "gold_doc_ids": mapped,
            "top_k": 5
        })

    out_path = "samples/beir_gold.json"
    os.makedirs("samples", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(gold, f, indent=2)

    print(f"Wrote {len(gold)} queries to {out_path}")
    print("Now run:")
    print(f"  export POSTGRES_DSN='postgresql://postgres:postgres@localhost:5433/securerag'")
    print(f"  export API_URL={API_URL}")
    print(f"  export USER_EMAIL={USER_EMAIL}")
    print(f"  python scripts/eval_recall.py {out_path}")

if __name__ == "__main__":
    main()
