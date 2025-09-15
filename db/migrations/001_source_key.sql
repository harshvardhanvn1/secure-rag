-- 001_source_key.sql

-- 1) add source_key for idempotent ingest
ALTER TABLE document
  ADD COLUMN IF NOT EXISTS source_key TEXT;

-- make it unique (safe if already unique)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname = 'public'
      AND indexname = 'uq_document_source_key'
  ) THEN
    ALTER TABLE document
      ADD CONSTRAINT uq_document_source_key UNIQUE (source_key);
  END IF;
END$$;

-- quick backfill so existing rows have something unique
UPDATE document
SET source_key = LOWER(REGEXP_REPLACE(title, '\s+', '-', 'g')) || '-' || doc_id
WHERE source_key IS NULL;
