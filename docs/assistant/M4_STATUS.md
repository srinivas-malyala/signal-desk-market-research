# M4 proposal review implementation

Status: locally implemented; live tool-output acceptance remains pending.
M3 commits were pushed through a9410de. No M4 deployment or live migration.
AI Search and scheduled jobs remain deferred/paused.

## Implemented

- Migration 0008 adds suffix-owned assistant_action_proposals, composite origin
  and revision ownership foreign keys, normalized JSON payload/hash, expiry,
  revision lineage, stable private idempotency keys and execution-claim leases.
  Existing migrations are unchanged. Root candidate deduplication does not prevent
  revising back to previous text with a new revision/key.
- Only completed owned runs with persisted, unredacted assistant messages can
  produce proposals. Strict schemas cover add/remove Primary, notes and reports.
- Adapter accepts matched function_call/function_call_output records for the four
  proposal formatter names, a bounded JSON-string output and exact non-executed
  envelope. It never extracts proposals from prose, unmatched outputs or browser
  arguments. At most four candidates per response. Unsupported shapes fail closed.
  Exact live endpoint serialization still requires a sanitized capture/test.
- Candidates are stored only after verified response completion and successful
  answer persistence. Failed/interrupted streams cannot create drafts. Browser
  proposal events contain IDs only; previews are fetched from owned storage.
- Lists, exact previews, expiry, dismissal and revisions use owner/hash/state
  checks. Revision atomically supersedes its parent and issues a new ID/key/hash.
- Internal claim is transaction-bound, owner/hash/expiry checked and single-use,
  with a 120-second lease. No HTTP route calls it yet. Expired execution leases
  must not be blindly retried; outcome recovery belongs to M5.
- Default-off ASSISTANT_PROPOSALS_ENABLED and ASSISTANT_PROPOSALS_SCHEMA_READY.
  Schema readiness requires migration 0008, separately from M2/M3 readiness.
- UI shows plain-text exact JSON, editable argument JSON, revision/state/hash,
  expiry, dismissal and a review checkbox. Confirm stays disabled and explains M5.
  Direct confirm requests require auth/CSRF/owned matching draft and return HTTP
  501 execution_not_available. Nothing is executed or recorded as succeeded.
- Only revise requests receive a bounded 512 KB body allowance; other request
  bounds remain unchanged. Model fields and identities cannot alter ownership.

## Evidence

413 fast tests pass; 13 PostgreSQL integration tests pass. New storage tests
cover incomplete-origin denial, owner isolation, root deduplication, revision
invalidation, edit-back with fresh key, dismissal, expiry and concurrent one-claim.
Three Node framing tests pass. Synthetic headless Chrome verifies preview,
revision, dismissal, disabled confirmation alongside M3 stream/reload/stop and
mobile layout. Changed-module Ruff, secret scan, diff and startup checks pass.
All databases/browser fixtures are local and disposable, not live platform proof.

## Remaining before M4 release / M5

Verify live matched tool-output serialization on the existing embedded Supervisor,
including all four types, malformed candidates and final/failed streams. No live
capture is claimed here. Apply migration/grants and enable flags only with rollout
approval. Business writes, confirmed execution, receipts, readback, uncertain
outcome recovery and execution-result UI are M5 work. Proposal/receipt retention
must be defined separately before action rollout; transcript redaction does not
redact proposal payloads. AI Search citation acceptance remains deferred.
