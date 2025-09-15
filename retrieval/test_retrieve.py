# retrieval/test_retrieve.py
import sys
from typing import List, Tuple
from apps import db
from apps.embeddings import embed_texts, EMBEDDING_MODEL

def search(query: str, k: int = 5) -> List[Tuple[str, float, str]]:
    """
    Return top-k: (doc_title, distance, snippet)
    """
    # 1) embed query
    [qvec] = embed_texts([query])

    sql = """
    WITH q AS (
      SELECT ARRAY[%s]::vector AS v
    )
    SELECT d.title,
           (ce.embedding <-> q.v) AS distance,
           c.redacted_text
    FROM q
    JOIN chunk_embedding ce ON true
    JOIN chunk c ON c.chunk_id = ce.chunk_id
    JOIN document d ON d.doc_id = c.doc_id
    ORDER BY ce.embedding <-> q.v
    LIMIT %s;
    """

    # 2) run ANN search
    rows = []
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            # flatten qvec into params
            params = (*qvec, k)
            # build placeholder list for vector dims
            ph = ",".join(["%s"] * len(qvec))
            cur.execute(sql.replace("%s", ph, 1), params)  # replace first %s with dim placeholders
            rows = cur.fetchall()

    # rows: [(title, distance, text), ...]
    return rows

def main():
    if len(sys.argv) < 2:
        print("Usage: PYTHONPATH=. python retrieval/test_retrieve.py \"your question\" [k]")
        sys.exit(1)

    query = sys.argv[1]
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    print(f"Model: {EMBEDDING_MODEL}")
    print(f"Query: {query}\n")

    results = search(query, k=k)
    for i, (title, dist, text) in enumerate(results, 1):
        snippet = (text[:180] + "…") if len(text) > 200 else text
        print(f"{i:>2}. {title} | dist={dist:.4f}\n    {snippet}\n")

if __name__ == "__main__":
    main()
