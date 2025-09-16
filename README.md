# Secure-RAG  
**Chat with private PDFs — with PII redaction, per-doc ACL, retrieval traces, and evaluation leaderboard.**

---

## Project Overview
Secure-RAG is a private Retrieval-Augmented Generation (RAG) system designed for **regulated documents**.  
Unlike generic RAG demos, Secure-RAG focuses on **security and accountability**:

- **PII Redaction**: All text is processed using [Microsoft Presidio](https://github.com/microsoft/presidio) before embedding.  
- **Per-Document Access Control**: Each document is tied to the uploading user’s email. Queries are filtered to return only documents that the user is authorized to access.  
- **Retrieval Traces**: Every search query and its retrieved results are logged in the database.  
- **Evaluation Leaderboard**: Supports both retrieval quality (Recall@K) and redaction quality (PII precision/recall).  

---

## Technology Stack and Rationale

This system integrates modern, open-source technologies carefully selected for their academic robustness and industry relevance:  

- **FastAPI**: A high-performance, asynchronous web framework that provides clean API contracts and is increasingly adopted in both research and production environments.  
- **Postgres 16 + pgvector**: PostgreSQL provides a reliable relational backbone, while the `pgvector` extension enables efficient approximate nearest neighbor (ANN) search for embeddings. This combination allows for both structured queries and vector retrieval.  
- **Presidio + spaCy**: Presidio, supported by spaCy’s NLP pipeline, is a mature and extensible framework for detecting and anonymizing personally identifiable information (PII). Its modular architecture makes it suitable for research and compliance-focused use cases.  
- **Sentence-Transformers (all-mpnet-base-v2)**: This model provides high-quality, open-source embeddings (768-dimensional), balancing accuracy with computational efficiency, making it suitable for both prototyping and large-scale evaluations.  
- **React + Vite + TailwindCSS**: This modern frontend stack offers rapid development, hot reloading, and a minimalistic yet effective styling framework, well-aligned with best practices for interactive systems research.  
- **Docker Compose**: Ensures reproducibility and simplifies environment setup by encapsulating database, API, and frontend components. This allows for portability across development and production environments.  

---

## Architecture

```
            ┌───────────┐
Upload PDF →│  Ingest   │──┐
            └───────────┘  │
                │           │
                ▼           │
         [Presidio Redaction]
                │
                ▼
     [Embeddings via SBERT] 
                │
                ▼
    Store in Postgres + pgvector
                │
────────────────┼─────────────────
                │
                ▼
          User Search Query
                │
                ▼
   ANN Search (ACL-filtered hits)
                │
                ▼
    Return hits + log in retrieval_trace
```

---

## Setup & Run

### 1. Clone repo & install dependencies
```bash
git clone <your_repo>
cd Secure-RAG
```

### 2. Run with Docker (full-stack)
```bash
./scripts/dev_up.sh
```

- **UI** → [http://localhost:3000](http://localhost:3000)  
- **API** → [http://localhost:8000](http://localhost:8000)  
- **DB** → `postgresql://postgres:postgres@localhost:5433/securerag`  

### 3. Run in dev mode (hot reload frontend)
```bash
# Start DB + API in docker
docker compose up db securerag-api

# Run frontend locally
cd web
npm install
npm run dev  # → http://localhost:5173
```

---

## Features

### Login
- Enter your email → stored as `Authorization: Bearer <email>` header.  
- All subsequent requests are scoped to that identity.  

### Ingest
- Upload `.pdf` or `.txt` or paste raw text.  
- PII redacted before embedding.  
- Stored in `document`, `chunk`, `chunk_embedding`, and ACL tables.  

### Search
- Enter a query → ANN search in `pgvector`.  
- ACL ensures only your docs are retrieved.  
- Results + scores logged in `retrieval_trace`.  

---

## Leaderboard: Retrieval Eval (Recall@K)

It supports measuring retrieval quality with **Recall@K**.

### Schema
Evaluations stored in:
```sql
TABLE retrieval_eval (
    trace_id UUID REFERENCES retrieval_trace(trace_id),
    query_text TEXT,
    gold_chunks UUID[],
    top_k INT,
    hits UUID[],
    recall_at_k FLOAT
);
```

### (A) Run Evaluation with Gold File
1. Prepare a gold file, e.g. `samples/beir_gold.json`:
   ```json
   [
     {
       "query": "what is non controlling interest on balance sheet",
       "gold_chunks": ["3cadfa68-0718-48af-b097-96b79c094874"],
       "top_k": 5
     }
   ]
   ```

2. Run:
   ```bash
   export POSTGRES_DSN='postgresql://postgres:postgres@localhost:5433/securerag'
   export API_URL=http://127.0.0.1:8000
   export USER_EMAIL=hnagar1@asu.edu

   python scripts/eval_recall.py samples/beir_gold.json
   ```

3. Results appear in terminal and are stored in DB:
   ```
   Recall@K: 0.67
   what is non controlling interest on balance sheet   1.0
   ```

### (B) Recreate BEIR Pipeline
There is also provide a small pipeline to load BEIR-style evaluation data:  
- **`scripts/load_beir_sample.py`**: maps BEIR doc IDs to ingested chunk IDs.  
- **`samples/beir_gold.json`**: gold query–answer mappings.  
- Run `eval_recall.py` afterwards to compute Recall@K.  

This pipeline ensures reproducibility of results across runs.  

---

## 🛡️ Security Eval: PII Redaction

To evaluate Presidio’s ability to correctly redact sensitive info.

### Schema
Evaluations stored in:
```sql
TABLE pii_eval_run (
    run_id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT now(),
    notes TEXT
);

TABLE pii_eval_result (
    run_id UUID REFERENCES pii_eval_run(run_id),
    text TEXT,
    gold_entities JSONB,
    detected_entities JSONB,
    precision FLOAT,
    recall FLOAT,
    f1 FLOAT
);
```

### (A) Run Synthetic Eval
```bash
export POSTGRES_DSN='postgresql://postgres:postgres@localhost:5433/securerag'
python -m scripts.synthetic_pii_eval
```

This generates synthetic text with names, phones, emails, and SSNs using `faker`, runs Presidio, and computes **micro-precision / recall / F1**.  

Example output:
```
Synthetic PII eval complete.
Micro-Precision: 0.995  Micro-Recall: 0.947  Micro-F1: 0.971
```

### (B) Recreate Results
- The evaluation logic is contained in `scripts/synthetic_pii_eval.py`.  
- It generates synthetic samples and compares Presidio’s detection results against the known ground truth.  
- By rerunning the script, you can reproduce the reported metrics.  

---

## 📖 Summary
- Secure-RAG is not just another “Chat with your PDF” system.  
- It is **secure, auditable, and measurable**.  
- With one integrated stack, you obtain:  
  - PII Redaction  
  - Access Control  
  - Retrieval Logging  
  - Retrieval Leaderboard (Recall@K)  
  - PII Security Evaluation  

This project demonstrates the design and implementation of a RAG system that balances **practical functionality** with **rigorous evaluation**.  
