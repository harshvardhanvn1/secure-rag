-- Users
CREATE TABLE IF NOT EXISTS app_user (
  user_id      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  email        TEXT UNIQUE NOT NULL,
  display_name TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Documents
CREATE TABLE IF NOT EXISTS document (
  doc_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  owner_user_id  UUID REFERENCES app_user(user_id),
  title          TEXT NOT NULL,
  source_key     TEXT UNIQUE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ACL
CREATE TABLE IF NOT EXISTS document_acl (
  doc_id  UUID REFERENCES document(doc_id) ON DELETE CASCADE,
  user_id UUID REFERENCES app_user(user_id) ON DELETE CASCADE,
  role    TEXT NOT NULL CHECK (role IN ('owner','viewer')),
  PRIMARY KEY (doc_id, user_id)
);

-- Chunks
CREATE TABLE IF NOT EXISTS chunk (
  chunk_id      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  doc_id        UUID REFERENCES document(doc_id) ON DELETE CASCADE,
  ord           INT NOT NULL,
  redacted_text TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Embeddings
CREATE TABLE IF NOT EXISTS chunk_embedding (
  chunk_id    UUID PRIMARY KEY REFERENCES chunk(chunk_id) ON DELETE CASCADE,
  embedding   vector(768) NOT NULL,  -- <-- set fixed dim
  model_name  TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Retrieval trace (UUID FKs)
CREATE TABLE IF NOT EXISTS retrieval_trace (
  trace_id   BIGSERIAL PRIMARY KEY,
  user_id    UUID REFERENCES app_user(user_id),
  query_text TEXT NOT NULL,
  top_k      INT  NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS retrieval_trace_hit (
  trace_id BIGINT REFERENCES retrieval_trace(trace_id) ON DELETE CASCADE,
  rank     INT NOT NULL,
  chunk_id UUID REFERENCES chunk(chunk_id) ON DELETE CASCADE,
  score    DOUBLE PRECISION NOT NULL,
  PRIMARY KEY (trace_id, rank)
);
