CREATE TABLE IF NOT EXISTS {{table:assistant_conversations}} (
  id UUID PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES {{table:users}}(id) ON DELETE CASCADE,
  title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 200),
  created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(id, user_id)
);
CREATE INDEX IF NOT EXISTS {{index:idx_assistant_conversations_owner}}
  ON {{table:assistant_conversations}}(user_id, created_at DESC, id);
CREATE TABLE IF NOT EXISTS {{table:assistant_runs}} (
  id UUID PRIMARY KEY,
  conversation_id UUID NOT NULL,
  user_id BIGINT NOT NULL,
  client_message_id UUID NOT NULL,
  payload_hash TEXT NOT NULL CHECK(length(payload_hash)=64),
  state TEXT NOT NULL CHECK(state IN ('running','completed','failed','interrupted')),
  lease_token UUID NOT NULL,
  lease_until TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
  finished_at TIMESTAMPTZ,
  error_code TEXT,
  FOREIGN KEY(conversation_id,user_id) REFERENCES {{table:assistant_conversations}}(id,user_id) ON DELETE CASCADE,
  UNIQUE(conversation_id,client_message_id),
  UNIQUE(id,conversation_id,user_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS {{index:idx_assistant_runs_owner_active}}
  ON {{table:assistant_runs}}(user_id) WHERE state='running';
CREATE INDEX IF NOT EXISTS {{index:idx_assistant_runs_active}}
  ON {{table:assistant_runs}}(lease_until) WHERE state='running';
CREATE TABLE IF NOT EXISTS {{table:assistant_messages}} (
  id UUID PRIMARY KEY,
  run_id UUID NOT NULL,
  conversation_id UUID NOT NULL,
  user_id BIGINT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('user','assistant')),
  content TEXT NOT NULL CHECK(octet_length(content)<=100000),
  created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
  FOREIGN KEY(run_id,conversation_id,user_id) REFERENCES {{table:assistant_runs}}(id,conversation_id,user_id) ON DELETE CASCADE,
  UNIQUE(run_id,role)
);
