ALTER TABLE {{table:assistant_action_proposals}} ADD COLUMN IF NOT EXISTS receipt JSONB;
ALTER TABLE {{table:assistant_action_proposals}} ADD COLUMN IF NOT EXISTS execution_error TEXT;
ALTER TABLE {{table:assistant_action_proposals}} ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ;
