# M5 user-bound execution

Status: locally implemented and verified, default-off; live rollout not performed.
M4 was pushed through 51f36e5. AI Search and paused schedules remain deferred.

## Implementation

- Migration 0009 adds receipt, safe execution-error and finished-at fields to
  existing suffix-owned proposals. No applied migration is edited.
- ASSISTANT_ACTIONS_ENABLED=false and ASSISTANT_EXECUTION_SCHEMA_READY=false
  default independently from chat/proposal flags. Enable only after migration 0009
  and explicit rollout authorization; disabling flags prevents new confirmations.
- Confirm accepts only confirmed=true and the stored payload_hash. Owner comes
  from existing OIDC/session lookup. No replacement arguments, keys, roles or
  receipts may be supplied. Storage revalidates the canonical immutable payload.
- Short locked claims commit before any MCP/network call. Active leases return
  execution-pending; saved receipts are replayed without a second write. Expired
  execution leases and outcome_unknown can be recovered ONLY by a fresh explicit
  authenticated confirmation with original payload/key. Pending expired drafts
  remain rejected. Recovery of an already-attempted write may outlive draft TTL;
  it is not autonomous authorization or an edited replacement action.
- UserWrites is shared by existing direct routes and chat. Each write and each
  MCP watchlist read mints a fresh browser-bound signed assertion; Supervisor/M2M
  credentials never execute these user-owned business mutations.
- All four types dispatch through existing MCP methods and their transactional
  ownership/idempotency enforcement. Report provenance is immutable proposal ID,
  hash and assistant origin, not a changing request ID (which would break retries).
- Success receipt fields are allowlisted and bounded. Transport/invalid-receipt
  errors are outcome_unknown, not falsely failed. Identity preparation before
  network is a known no-write failure. Terminal updates compare owner/lease/state
  and expiry; lost persistence acknowledgement returns uncertainty, never an
  automatic second write or a fresh key.
- Watchlist readback uses a new signed user MCP session; note/report readback
  queries saved ID AND authenticated user_id and compares exact stored arguments.
  A successful write with failed/mismatched readback is saved/verification-pending,
  not write-failed. Explicit retries of saved pending verification re-read only.
- Latest three owned saved-action receipts can enter labelled historical model
  context. IDs/action/verification only: no private keys, credentials or owner IDs.
  Receipts are application data, not permission for a new action.
- UI requires review checkbox and unedited argument preview before confirmation.
  Edits reset consent; revisions issue new immutable IDs/keys. Saved, pending
  verification, executing and unknown states reload from storage. Confirm controls
  stay disabled unless both action and execution-schema flags are enabled.

## Evidence

428 fast tests and 15 disposable PostgreSQL tests pass. Tests verify actual
existing signed-session/CSRF route boundary, distinct fresh write/read assertions,
stored payload/key dispatch, flags and replacement-argument rejection. Unit tests
cover all four actions, safe error classification, pending verification retry,
stable report provenance, private-context filtering and uncertain persistence.

PostgreSQL integration verifies owned claims, stale-token rejection, preserved
keys through expired lease recovery and durable receipt replay. A synthetic
business write commits one note then loses its reply; explicit recovery saves one
note total and verifies its exact body under the correct owner. No connection is
held over the MCP call; existing concurrency tests remain green.

Synthetic headless Chrome verifies checkbox gating, unsaved-edit denial, explicit
confirmation and saved receipt reload. No live account, MCP write or Lakebase
mutation is used. Node frame-parser, Ruff, credential scan, diff checks and local
service startup/health checks pass. No new dependency or infrastructure.

## Live acceptance still required (M6)

Before enabling actions: migrate/grant only intended suffix-owned objects; verify
M4 live typed-output serialization; use two real browser principals; exercise an
authorized reversible action with same-key retry/readback; verify unknown-outcome
recovery, latency/capacity and flag rollback through deployed Render services.
Pending proposal/receipt retention/legal-hold policy remains a rollout gate.
Transcript redaction never deletes action payloads, keys or receipts. There is no
unattended business-write recovery worker, no remote cancellation guarantee, and
no claim that unit/local PostgreSQL results prove production behavior.
