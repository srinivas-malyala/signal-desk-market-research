# Assistant rollout and recovery runbook

Status: M2 prepared and locally verified; no application deployment or live
migration performed. Live operations require explicit rollout authority and a
user-selected Databricks profile. AI Search recovery remains deferred.

## Implemented M2 configuration

| Setting | Default / bounds |
|---|---|
| SIGNAL_DESK_SUPERVISOR_ENDPOINT | Required by client; embedded endpoint name, never browser input |
| ASSISTANT_ENABLED | false; gates chat APIs and template/assets |
| ASSISTANT_PROPOSALS_ENABLED | false; gates draft creation/review routes and UI |
| ASSISTANT_PROPOSALS_SCHEMA_READY | false; requires migration 0008 after 0006/0007 |
| ASSISTANT_ACTIONS_ENABLED | false; enables explicit user-bound confirmations |
| ASSISTANT_EXECUTION_SCHEMA_READY | false; requires migration 0009 |
| FRONTEND_WORKER_TIMEOUT_SECONDS | 240; 240–600, validated at Gunicorn startup |
| ASSISTANT_SCHEMA_READY | false; enable only after migrations 0006 and 0007 |
| ASSISTANT_RECOVERY_ENABLED | false; starts post-fork startup/periodic recovery |
| ASSISTANT_RECOVERY_INTERVAL_SECONDS | 60; 10–3600 |
| ASSISTANT_RECOVERY_BATCH_SIZE | 100; 1–1000 |
| ASSISTANT_RETENTION_ENABLED | false; requires recovery and schema readiness |
| ASSISTANT_RETENTION_DAYS | 30; 1–3650; user selected preparation of 30 days |

Model deadline 180 seconds, lease 210 seconds, 20 history messages, 4,000-character
question and 24,000-byte assembled content are code bounds, not environment knobs.
M5 implements guarded confirmation execution, disabled by default. Proposal TTL
remains a fixed 30-minute bound. No action flag or migration was enabled live.
When enabled, API reads and writes also require ASSISTANT_SCHEMA_READY=true.

Reuse DATA_WORKSPACE_HOST/CLIENT_ID/CLIENT_SECRET through shared auth. Frontend
principal requires CAN_QUERY on the embedded endpoint. Keep embedded MCP bearer
credential separate from browser-user assertions and the standalone token.
Never put secrets or connection URLs in logs, YAML or prompts.

## Deployment sequence (requires separate approval)

1. Record commit/baseline and preserve unrelated working-tree changes.
2. Run local acceptance, fresh locked installs and exact service startup checks.
3. Apply migrations 0006 and 0007 with the existing checksum-protected MCP runner.
   Verify only configured suffix-owned objects and intended role grants changed.
   Do not use frontend startup to apply DDL; set schema readiness only afterward.
4. Deploy frontend with recovery/retention and future chat/action flags disabled.
   Prepared Blueprint loads dashboard/gunicorn.conf.py; no live timeout change
   has occurred merely by editing the repository.
5. Enable recovery and schema-ready flags only after schema verification.
   Confirm count-only maintenance logs and bounded queries; no model retries.
6. Deploy M3 research routes/UI disabled first; pilot with two authenticated users.
   Verify OIDC/CSRF, persistence, ownership and real streamed POST through Render.
7. Measure proxy buffering, first-response/total latency, worker/thread/pool
   capacity and browser disconnects. A 240-second Gunicorn timeout does not prove
   Render permits the same request duration. SSE heartbeats are not proof either.
8. Review a retention count preview and backups. Only with separate approval set
   ASSISTANT_RETENTION_ENABLED=true. Monitor redacted counts, not transcripts.
9. Enable M4/M5 actions only after immutable proposal, user identity, retry and
   readback gates pass. AI Search citation gate remains required for full release.
10. Expand after M6 acceptance; update deployment evidence and user documentation.

Do not silently change paid plans or add a queue. If deployed streaming capacity
is insufficient, prepare durable execution for review before general rollout.

## Generation recovery

Owned reload reconciles expired runs for that conversation; new submissions also
reconcile leases. Internal reconcile_expired(limit=100) returns counts only and
never resumes model research or executes business writes. Gunicorn post_worker_init
starts a daemon immediately and periodically only when flags permit; worker_exit
stops it. No pre-fork threads/connections or public maintenance API.
SQL batches use SKIP LOCKED, five-second statement and one-second lock timeouts.

Run leases are fixed; stale completion cannot overwrite expiry. Model transport
has four slots per process; abandoned readers retain slots until actual exit.
Repository capacity is four across all workers. Local four-client tests held no
database connections during model waits and rejected a fifth user. Investigate
sustained capacity errors; do not automatically retry or raise limits.

Terminal database persistence errors do not report saved/completed success.
Do not retry an uncertain commit: reload/duplicate submission reads actual state.
If a worker died before persistence, lease expiry labels the run interrupted.
Response stopping is local; guaranteed remote cancellation is not supported.

## Prepared 30-day retention policy

User approved preparing automatic age-based retention, not live enablement.
redact_expired_transcripts() defaults to a read-only count preview. Application
clears message content and sets redacted_at for terminal runs whose finished_at
is older than 30 days; active/recent runs are untouched. Counts represent messages,
not conversations. Explicit apply and the default-off retention flag are required.

IDs, ownership, submission hashes and run states remain for duplicate safety.
Old conversation titles become Research only when no live/recent run exists;
title updates are separately bounded. Reload exposes redaction timestamps.
Empty/redacted turns are excluded from Supervisor history. Redaction is irreversible
in the active database; backups may retain content under a separate policy.
This is not a secure-erasure guarantee. Disable retention immediately on unexpected
results; restoring content requires an authorized backup restoration procedure.

Business notes/reports are not transcripts and are not changed. M4/M5 must define
separate proposal/receipt retention and legal-hold requirements before rollout.
No automatic removal of keys, receipts or foreign-key origins is authorized.
Transcripts are not synchronized to Gold and remain excluded from ordinary logs.

## Observability and rollback

Log IDs, safe categories, counts and durations, not transcripts/tool payloads or
connection strings. Distinguish service research identity from browser attribution.
Add M3 request-level metrics rather than treating existing MCP metrics as chat proof.

Disable future action/chat flags, then disable retention/recovery as appropriate.
Drain active work; retain additive schema, hashes, receipts and ownership metadata.
No automatic destructive down migration. Flag rollback cannot reverse committed
writes or redacted text. Verify existing health/auth/direct workflows afterward.
