-- Chunks we index (store only redacted text)
CREATE TABLE IF NOT EXISTS chunk (
  chunk_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  doc_id          UUID NOT NULL REFERENCES document(doc_id) ON DELETE CASCADE,
  ord             INTEGER NOT NULL,            -- order in the doc
  redacted_text   TEXT NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Embeddings for each chunk (adjust dim later to your model)
CREATE TABLE IF NOT EXISTS chunk_embedding (
  chunk_id    UUID PRIMARY KEY REFERENCES chunk(chunk_id) ON DELETE CASCADE,
  embedding   VECTOR(1536) NOT NULL,           -- e.g., OpenAI text-embedding-3-small
  model_name  TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_chunk_doc ON chunk(doc_id, ord);

-- Vector index (build after you have some data; it's fine to create now)
CREATE INDEX IF NOT EXISTS idx_chunk_embedding_vec
ON chunk_embedding
USING ivfflat (embedding vector_l2_ops)
WITH (lists = 100);

