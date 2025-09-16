-- PII redaction event counts per chunk (produced during ingestion)
CREATE TABLE IF NOT EXISTS redaction_log (
  log_id       BIGSERIAL PRIMARY KEY,
  doc_id       UUID NOT NULL REFERENCES document(doc_id) ON DELETE CASCADE,
  chunk_id     UUID NOT NULL REFERENCES chunk(chunk_id) ON DELETE CASCADE,
  entity_type  TEXT NOT NULL,              -- e.g., PERSON, EMAIL_ADDRESS, PHONE_NUMBER, US_SSN
  count        INTEGER NOT NULL DEFAULT 0,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS redaction_log_doc_idx   ON redaction_log(doc_id);
CREATE INDEX IF NOT EXISTS redaction_log_chunk_idx ON redaction_log(chunk_id);
CREATE INDEX IF NOT EXISTS redaction_log_type_idx  ON redaction_log(entity_type);

-- Synthetic/benchmark PII evaluation runs (precision/recall/F1)
CREATE TABLE IF NOT EXISTS pii_eval_run (
  run_id     BIGSERIAL PRIMARY KEY,
  notes      TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Per-entity metrics for a run
CREATE TABLE IF NOT EXISTS pii_eval_entity_metrics (
  run_id     BIGINT NOT NULL REFERENCES pii_eval_run(run_id) ON DELETE CASCADE,
  entity_type TEXT NOT NULL,
  tp         INTEGER NOT NULL,
  fp         INTEGER NOT NULL,
  fn         INTEGER NOT NULL,
  precision  DOUBLE PRECISION NOT NULL,
  recall     DOUBLE PRECISION NOT NULL,
  f1         DOUBLE PRECISION NOT NULL,
  PRIMARY KEY (run_id, entity_type)
);

-- Overall micro-averaged metrics for a run
CREATE TABLE IF NOT EXISTS pii_eval_overall (
  run_id          BIGINT PRIMARY KEY REFERENCES pii_eval_run(run_id) ON DELETE CASCADE,
  micro_precision DOUBLE PRECISION NOT NULL,
  micro_recall    DOUBLE PRECISION NOT NULL,
  micro_f1        DOUBLE PRECISION NOT NULL
);
