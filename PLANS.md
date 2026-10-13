# Embedded Supervisor implementation plan

Updated: 2026-10-12, America/Los_Angeles.
Current state: M0 local spike and standalone live protocol baseline verified.
Active milestone: M2 locally verified; M1 citation/index recovery deferred by user.
Live update: user deployed MCP, created the governed embedded service and attached
it to the separate Supervisor in the UI. Comparison and proposal tests succeeded;
semantic search failed because its index is missing. See LIVE_STATUS.md; do not
create a duplicate Supervisor or unpause the index-dependent refresh job.
Selected live profile: `dataexpertio_srini` (user selected 2026-10-12).
Live operations update: all three scheduled jobs owned by the deployed `dev`
bundle are paused as of 2026-10-12; the remaining eight jobs are manual-only.
The three bundle schedule declarations are also `PAUSED` to prevent redeployment
from re-enabling them.

## Working documents

- `AGENTS.md`: contributor rules and identity invariants.
- `GOALS.md`: scope and release definition.
- `docs/assistant/CONTEXT.md`: existing code and proposed module map.
- `docs/assistant/CONTRACTS.md`: API, persistence, events, and recovery.
- `docs/assistant/DECISIONS.md`: decisions and unresolved platform questions.
- `docs/assistant/VERIFICATION.md`: tests and acceptance matrix.
- `docs/assistant/DEPLOYMENT.md`: configuration, rollout, rollback.

## Milestone tracker

| Milestone | Status | Depends on | Exit gate | Evidence |
|---|---|---|---|---|
| M0 Protocol/design spike | Partially verified | None | Embedded proposal/citation and permission proof still pending | `docs/assistant/M0_FINDINGS.md`; 18 targeted tests pass |
| M1 Restricted embedded agent | Locally verified; live gate pending | M0 | Four research tools accessible; forbidden direct calls rejected | `docs/assistant/M1_FINDINGS.md`; 27 tests pass |
| M2 Persistence and backend | Locally complete; deployment not performed | M0 | Isolation, bounded history, run leases, deduplication, adapter tests pass | 75 targeted tests, 11 PostgreSQL tests, locked installs/startup verified; default-off recovery and 30-day retention prepared |
| M3 Research chat | Not started | M1, M2 | Multi-turn streamed research works through deployed infrastructure | Pending |
| M4 Proposal lifecycle | Not started | M2, M3 | Immutable previews, edits, expiry, dismissal, confirmation pass | Pending |
| M5 User-bound execution | Not started | M4 | Ownership, stable retry, ambiguous-outcome recovery, readback pass | Pending |
| M6 Acceptance and rollout | Not started | M1–M5 | G1–G8 and rollback gates pass | Pending |

## M0 — Verify contracts and implementation constraints

- Inspect current endpoint schema with the user-selected Databricks profile.
- Capture sanitized research, comparison, multi-turn, failure, and proposal examples.
- Determine visible text/citation/tool-result event shapes. Do not assume token
  deltas, structured-output parameters, or previous-response continuation support.
- Prove a non-mutating typed proposal tool returns arguments through the endpoint;
  otherwise verify a strict versioned response envelope. Fail closed on bad output.
- Verify restricted MCP endpoint mounting and credential policy using the installed
  FastMCP version. Record the selected design and startup implications.
- Establish who applies migrations and where recovery runs after worker death.
- Record unresolved requirements and evidence in DECISIONS.md before dependent work.

## M1 — Restricted Supervisor and MCP surface

Local implementation is complete. Separate HTTP identity/surface, four research
tools and four pure proposal formatters, prompt/specification, evaluation cases,
and default-off Render configuration are verified. Next: deploy the MCP build
with separate secrets, provision the embedded Supervisor, and close live gates.
No Render connection/CLI was available; no live provisioning is claimed.

- Add dedicated embedded credentials and identity kind; keep the existing identity.
- Expose and enforce only four research tools on the restricted MCP surface.
- Reject user-state reads/writes even when callers manually construct tool calls.
- Add embedded prompt/config alongside existing agent files; use proposal instructions
  and bounded user context, with no user identity in model arguments.
- Provision a separate governed connection and Supervisor only within authorized
  deployment scope. Keep endpoint/resource identifiers in protected configuration
  or non-secret deployment records, never hardcoded application logic.
- Add routing/grounding examples and adversarial write-denial evaluation cases.

## M2 — Conversation backend and Supervisor adapter

Implemented migration 0006, owned repository, shared claims/capacity, fixed leases,
deduplication, reconciliation, generation orchestration and trusted snapshots.
Transport bounds caller waiting to 180 seconds, including blocked authentication,
POST and slow-drip reads, using four bounded daemon readers per process. Timed-out
readers retain slots until they really exit; remote cancellation is not guaranteed.
75 targeted tests and 11 disposable PostgreSQL tests pass. Default-off recovery
hooks, 30-day transcript retention and minimum 240-second worker configuration
are implemented; four-client threaded-pool capacity, process death and uncertain
commit handling verified locally. No public routes, live migrations or deployment.
Actual Render stream measurement belongs to M3/M6; trusted execution receipts
remain M5 work. AI Search and its paused refresh schedule remain deferred.

- Add a new migration after verifying the next unused sequence number; update
  frontend/MCP table registries and migration tests. Add owner/index/FK constraints.
- Implement repository access with ownership predicates on every route and query.
- Implement shared run leases, submission deduplication, expired-run reconciliation.
- Add Supervisor client with SDK-managed M2M authentication, streaming parser,
  total deadline, bounded buffers, redaction, and deterministic error categories.
- Build history only from server-owned completed records and trusted app receipts.
  Bound context; label user context snapshots with timestamps and origin.
- Release database connections before network waits; persist terminal outcomes.

## M3 — Research chat and sources

- Add Flask blueprint/service routes and streamed POST response with existing
  OIDC/CSRF controls; keep route registration changes small in app.py.
- Add separate JS/CSS/template components, conversation reload, progress, and stop.
- Support sanitized citations only when observed tool metadata substantiates them.
- Persist interrupted content distinctly; withhold proposals until completion.
- Verify buffering, timeouts, disconnects, worker capacity, and accessibility.

## M4 — Proposal lifecycle

- Define discriminated schemas for four action types; reject extras and identity.
- Validate content against existing MCP bounds, normalize, hash, and store it.
- Render exact preview, edit, confirm, dismiss, expiry, and execution-result states.
- Edits supersede the old proposal; requests confirm by ID and matching hash only.
- Atomically claim proposals, bind them to owner and originating message, and
  disallow proposal generation from incomplete or failed responses.

## M5 — Execute as browser user

- Extract reusable write service helpers from existing routes without internal HTTP.
- Mint a fresh user assertion for each downstream MCP session. Use one stable
  server-generated idempotency key per immutable proposal.
- Never hold a proposal row lock/database transaction across the MCP network call.
- Recover claims with leases; retry exact payload/key after ambiguous outcome.
- Persist receipts and verify affected state through the user-bound read path.
- If write succeeds but readback fails, report saved/readback pending accurately.
- Keep confirmation payload and receipt separate from Supervisor-generated prose.

## M6 — Verify, stage, and release

- Complete targeted tests, full fast suite, secret scan, changed-module lint, and
  locked service install/startup checks. Fix dependency-extra/CI scope gaps in scope.
- Run two-principal acceptance and restricted-credential denial tests.
- Measure concurrency and first-response/total latency; decide web streaming versus
  durable queue from evidence. Do not change paid infrastructure without authorization.
- Deploy disabled first, pilot research only, then enable confirmed actions.
- Exercise flag rollback; retain additive schema and data.
- Update existing configuration/runbook/handoff only after implementation/deployment
  facts change. Record commit, dates, settings, results, and remaining limitations.

## Per-milestone handoff template

Latest handoff: M1 implements separate credentials, default-off restricted MCP
mount, four research tools, four pure typed candidate tools, and embedded agent
instructions/specification/evaluation examples. 27 M1 tests and startup smoke
pass; full fast suite is 321 passed with one existing paused-schedule mismatch.
Next: obtain Render deployment access, deploy the restricted MCP build, provision
the separate embedded Supervisor using dataexpertio_srini, and close M0's live
proposal/citation gates. No live deployment or grant has occurred. See
M1_FINDINGS.md; M0_FINDINGS.md retains the protocol baseline.

```text
Milestone/status:
Changed files:
Verified behavior and commands:
Evidence paths (sanitized):
Decisions accepted or changed:
Unverified assumptions/blockers:
Next concrete task:
Deployment state and authorization scope:
```
