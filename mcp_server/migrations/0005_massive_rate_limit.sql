CREATE TABLE IF NOT EXISTS {{table:massive_api_attempts}} (
  attempt_id UUID PRIMARY KEY,
  acquired_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
  requester TEXT NOT NULL CHECK(length(requester) BETWEEN 1 AND 100),
  contract_version SMALLINT NOT NULL DEFAULT 1 CHECK(contract_version = 1)
);
CREATE INDEX IF NOT EXISTS {{index:idx_massive_attempts_time}}
  ON {{table:massive_api_attempts}}(acquired_at DESC);
