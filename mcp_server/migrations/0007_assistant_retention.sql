-- Keep message IDs and run deduplication metadata when transcript text expires.
ALTER TABLE {{table:assistant_messages}}
  ADD COLUMN IF NOT EXISTS redacted_at TIMESTAMPTZ;
ALTER TABLE {{table:assistant_conversations}}
  ADD COLUMN IF NOT EXISTS title_redacted_at TIMESTAMPTZ;
