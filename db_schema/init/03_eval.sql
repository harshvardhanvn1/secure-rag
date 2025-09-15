CREATE TABLE IF NOT EXISTS retrieval_eval (
  eval_id     BIGSERIAL PRIMARY KEY,
  trace_id    BIGINT REFERENCES retrieval_trace(trace_id) ON DELETE CASCADE,
  query_text  TEXT NOT NULL,
  gold_chunks UUID[] NOT NULL,
  top_k       INT NOT NULL,
  hits        UUID[] NOT NULL,
  recall_at_k FLOAT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
