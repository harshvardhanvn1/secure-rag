-- 003_fix_trace_user_id_type.sql

-- Drop the existing faulty tables if you just created them and have no data
DROP TABLE IF EXISTS retrieval_trace_hit;
DROP TABLE IF EXISTS retrieval_trace;

-- Recreate with matching types
CREATE TABLE IF NOT EXISTS retrieval_trace (
  trace_id     BIGSERIAL PRIMARY KEY,
  user_id      UUID REFERENCES app_user(user_id),
  query_text   TEXT NOT NULL,
  top_k        INT NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS retrieval_trace_hit (
  trace_id   BIGINT REFERENCES retrieval_trace(trace_id) ON DELETE CASCADE,
  rank       INT    NOT NULL,
  chunk_id   UUID REFERENCES chunk(chunk_id) ON DELETE CASCADE,
  score      DOUBLE PRECISION NOT NULL,
  PRIMARY KEY (trace_id, rank)
);

CREATE INDEX IF NOT EXISTS idx_retrieval_trace_created_at ON retrieval_trace(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_retrieval_trace_hit_chunk ON retrieval_trace_hit(chunk_id);
