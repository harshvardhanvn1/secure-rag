DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND indexname='idx_chunk_embedding_vec'
  ) THEN
    CREATE INDEX idx_chunk_embedding_vec
      ON chunk_embedding USING ivfflat (embedding) WITH (lists = 100);
  END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_retrieval_trace_created_at
  ON retrieval_trace(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_retrieval_trace_hit_chunk
  ON retrieval_trace_hit(chunk_id);
