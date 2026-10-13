CREATE UNIQUE INDEX IF NOT EXISTS {{index:idx_assistant_message_origin}}
  ON {{table:assistant_messages}}(id,run_id,conversation_id,user_id);
CREATE TABLE IF NOT EXISTS {{table:assistant_action_proposals}} (
  id UUID PRIMARY KEY,
  user_id BIGINT NOT NULL,
  run_id UUID NOT NULL,
  conversation_id UUID NOT NULL,
  origin_message_id UUID NOT NULL,
  payload JSONB NOT NULL CHECK(jsonb_typeof(payload)='object'),
  payload_hash TEXT NOT NULL CHECK(length(payload_hash)=64),
  idempotency_key TEXT NOT NULL UNIQUE,
  state TEXT NOT NULL CHECK(state IN ('pending','dismissed','expired','superseded','executing','succeeded','failed','outcome_unknown')),
  revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0),
  parent_id UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
  expires_at TIMESTAMPTZ NOT NULL,
  lease_token UUID,
  lease_until TIMESTAMPTZ,
  CHECK(state<>'executing' OR (lease_token IS NOT NULL AND lease_until IS NOT NULL)),
  FOREIGN KEY(run_id,conversation_id,user_id) REFERENCES {{table:assistant_runs}}(id,conversation_id,user_id),
  FOREIGN KEY(origin_message_id,run_id,conversation_id,user_id)
    REFERENCES {{table:assistant_messages}}(id,run_id,conversation_id,user_id),
  UNIQUE(id,run_id,conversation_id,user_id),
  FOREIGN KEY(parent_id,run_id,conversation_id,user_id)
    REFERENCES {{table:assistant_action_proposals}}(id,run_id,conversation_id,user_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS {{index:idx_assistant_proposal_initial}}
  ON {{table:assistant_action_proposals}}(run_id,payload_hash) WHERE parent_id IS NULL;
