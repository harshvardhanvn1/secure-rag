-- Enable extensions (safe to re-run)
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS vector;    -- we'll need this later for embeddings

-- 1) Users
CREATE TABLE IF NOT EXISTS app_user (
  user_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email         TEXT UNIQUE NOT NULL,
  display_name  TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2) Documents (uploaded PDFs, etc.)
CREATE TABLE IF NOT EXISTS document (
  doc_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_user_id   UUID REFERENCES app_user(user_id) ON DELETE SET NULL,
  title           TEXT NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_active       BOOLEAN NOT NULL DEFAULT TRUE
);

-- 3) Per-document ACL (who can see what)
CREATE TABLE IF NOT EXISTS document_acl (
  doc_id    UUID NOT NULL REFERENCES document(doc_id) ON DELETE CASCADE,
  user_id   UUID NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
  role      TEXT NOT NULL CHECK (role IN ('owner','editor','viewer')),
  PRIMARY KEY (doc_id, user_id)
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_document_owner ON document(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_acl_user_doc ON document_acl(user_id, doc_id);
