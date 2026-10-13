# M2 backend acceptance status

Status: locally implemented and verified, 2026-10-12. Not deployed.
AI Search and its dependent paused refresh schedule remain deferred by the user.

## Implemented scope

- Migration 0006: suffix-owned conversations, runs and messages, composite
  ownership foreign keys, unique submissions and one active generation per user.
- Migration 0007: additive message/title redaction markers. No applied migration
  was edited. Both migrations applied twice in each disposable integration schema.
- Owner-scoped repository with pagination, completed-turn history, shared capacity,
  duplicate payload hashes, fixed leases and compare-and-set terminal persistence.
- Trusted, dated Primary-watchlist snapshot, restricted to 50 normalized tickers.
  Credentials and model-supplied identity never enter context.
- Bounded Supervisor transport: 180-second caller deadline, 15-second socket idle
  timeout, four daemon readers per process and one-event queue. Late events cannot
  mutate expired response state. Abandoned readers retain capacity until real exit.
- Internal generation lifecycle closes upstream streams on disconnect, persists
  before announcing completion, sanitizes storage errors and does not retry an
  uncertain commit. Durable reload/duplicate reads determine the actual outcome.
- Owner reload and new submissions reconcile expired leases. Default-off Gunicorn
  post-fork maintenance runs immediately and periodically using bounded SKIP LOCKED
  batches, five-second statement timeout and one-second lock timeout.
- Prepared Gunicorn config defaults to 240 seconds (allowed 240–600), above the
  180-second generation deadline and 210-second lease. No live setting was changed.
- User-selected 30-day transcript retention policy prepared, disabled by default.
  Preview returns counts; explicit application clears terminal transcript text
  while preserving IDs, hashes and metadata for duplicate safety. Conversation
  titles are reset only when the entire conversation is old and has no live run.
  It does not delete saved notes/reports or business-action records.
- CI installs both dashboard/MCP extras, lints new backend modules and defines a
  disposable PostgreSQL integration job. Hosted GitHub CI has not run locally.

## Verification evidence

75 targeted backend/runtime/repository/schema tests pass.
11 real PostgreSQL 18 integration tests pass:

1. Owner isolation and terminal roundtrip.
2. Concurrent duplicate submissions create one run.
3. Lease expiry rejects stale finalization.
4. Simultaneous owner-capacity claims and transaction rollback.
5. Composite ownership foreign-key denial.
6. Primary snapshot ownership, timestamp and 50-ticker bounds.
7. Owned reload/maintenance recovery leaves live runs unchanged.
8. Retention preview/redaction bounds, repeatability and preserved duplicate keys.
9. Four simultaneous generations with a real five-connection threaded pool.
   Each model wait held zero database connections; fifth user was rejected.
   Observed local sample: maximum four checked-out connections, total 0.023 seconds.
   Model transport was a deterministic stub, not a live latency benchmark.
10. Abrupt child-process exit after claim; expiry recovers without regeneration.
11. Lost terminal commit acknowledgement: safe public error, saved run found by
    duplicate/reload without an extra assistant message.

Full fast suite: 380 passed, one known deferred schedule assertion failed
(expects UNPAUSED; index-dependent job intentionally remains PAUSED).
Changed-module Ruff, credential scan, diff checks, fresh hash-locked service
installs and both exact Blueprint startup/health smoke checks pass.
Disposable database schemas/container are cleaned up; no live Lakebase access.

## Configuration and rollout boundary

ASSISTANT_RECOVERY_ENABLED=false and ASSISTANT_SCHEMA_READY=false are Blueprint
defaults. Only after an authorized migration through the checksum runner may the
schema-ready and recovery flags be enabled. ASSISTANT_RETENTION_ENABLED=false;
the user approved preparing 30 days, not enabling live redaction. Review preview
and backup policy before separate deployment approval. Maintenance runs per
Gunicorn worker; PostgreSQL coordinates claims/recovery across processes.

No chat routes, UI, public maintenance endpoint, proposal execution or live
migration is introduced by M2. Trusted execution receipts belong to M5.
See DEPLOYMENT.md for settings and rollout/rollback instructions.

## Remaining external acceptance (M3/M6, not local backend proof)

Actual Render buffering, request-duration limits, first-response latency and
production worker/pool capacity must be measured with the M3 routes. Local tests
do not establish these. Guaranteed remote cancellation is not provided.
Schema/role grants, migration deployment, two real browser users and retention
enablement require explicit rollout scope. M4/M5 must separately govern proposal,
receipt and legal-hold retention before any business-write release.
