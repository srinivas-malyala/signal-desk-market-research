CREATE TABLE IF NOT EXISTS {{table:agent_sessions}} (
  session_id UUID PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES {{table:users}}(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'completed', 'failed')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_activity_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS {{table:agent_tool_events}} (
  event_id BIGSERIAL PRIMARY KEY,
  session_id UUID REFERENCES {{table:agent_sessions}}(session_id) ON DELETE SET NULL,
  user_id BIGINT REFERENCES {{table:users}}(id) ON DELETE SET NULL,
  tool_name TEXT NOT NULL,
  action_type TEXT NOT NULL CHECK(action_type IN ('retrieve', 'create', 'update', 'delete')),
  status TEXT NOT NULL CHECK(status IN ('success', 'error')),
  duration_ms INTEGER CHECK(duration_ms IS NULL OR duration_ms >= 0),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS {{index:idx_agent_events_time}}
  ON {{table:agent_tool_events}}(created_at DESC);

CREATE TABLE IF NOT EXISTS {{table:idempotency_records}} (
  user_id BIGINT NOT NULL REFERENCES {{table:users}}(id) ON DELETE CASCADE,
  operation_name TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  result JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(user_id, operation_name, idempotency_key)
);
