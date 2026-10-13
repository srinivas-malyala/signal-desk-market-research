# M2 local implementation status

## Trusted snapshot increment

Added owner-scoped `watchlist_snapshot()` repository query for Primary, with a
database timestamp and maximum 50 tickers. `assistant_context.py` normalizes
tickers and forwards only membership, timestamp and application origin; unknown
fields (including owner/credentials) are discarded. The generation service
accepts an optional server-injected provider, not browser context. History budget
includes snapshot UTF-8 bytes. No system-role authority or permission to write
is derived from the snapshot. M3 must inject the repository provider explicitly.
Execution-receipt context remains deferred until trusted M5 receipts exist.

52 targeted local tests pass; prior five PostgreSQL integration tests remain
valid for the earlier storage increment (new snapshot query not yet integration
tested). Strict transport cancellation remains pending. No live changes.

## PostgreSQL verification update

Docker Desktop became available. Five real integration tests passed against an
isolated localhost PostgreSQL 18 container using an existing local image:
owner-scoped reads/claims/finalization and roundtrip, simultaneous duplicate
submissions producing one run, simultaneous same-owner capacity claims,
expired-lease reconciliation rejecting stale completion, and composite ownership
foreign-key denial. Migration 0006 DDL was applied twice in each fresh test schema.
Tests removed only UUID-named fixture schemas; the disposable container/data
volume was removed afterward. No Lakebase connection or mutation occurred.

Reproduce with disposable local PostgreSQL and
`ASSISTANT_TEST_POSTGRES_PORT=<localhost-port> .venv/bin/pytest tests/test_assistant_postgres.py`.
Tests skip if the explicit test port is absent. They never consume LAKEBASE_URL.
Strict deadline cancellation, trusted context and broader backend acceptance
remain pending; M2 is not complete. Earlier Docker-unavailable notes below are
historical and superseded by this verification.

Latest verification: 50 targeted tests pass after malformed upstream shape,
generator disconnect and safe failure-persistence coverage. Changed-file Ruff
passes. Local PostgreSQL integration is blocked: postgres/initdb are absent from
PATH and Docker CLI cannot connect because its daemon socket is absent. No live
database fallback was attempted. Start Docker Desktop or supply a disposable
local PostgreSQL instance before running genuine constraint/concurrency tests.
Strict wall-clock cancellation remains unimplemented; do not enable production
chat on the basis of the current between-frame deadline checks.

M2 is in progress, not complete. AI Search recovery was deferred by the user.

Implemented bounded server-owned completed-turn history, a production-independent
SSE parser, and synchronous authenticated transport. The transport uses the
existing SDK authentication helper; on Render that is explicit OAuth M2M. Endpoint
comes from `SIGNAL_DESK_SUPERVISOR_ENDPOINT`, never from browser input. Set the
embedded endpoint `mas-94a8ed23-endpoint` only when later enabling the integration.

Bounds: 4,000-character question, 20 history messages, 24,000 UTF-8 content bytes,
2 MB stream, 256 KB frame, 100 KB text. Incomplete frames and bare EOF do not
verify completion. Failure overrides terminal success. Tool payloads are not
rendered publicly; no candidate becomes an executable proposal here.

Transport disables redirects and automatic application retries, closes responses,
uses 10-second connection and 15-second socket-inactivity timeouts, and checks a
180-second elapsed limit between received lines. This is not yet a strict
wall-clock watchdog against slow-drip traffic. Completed text-only responses
remain available through ResponseState.final_text for later orchestration.

17 targeted tests and changed-file Ruff pass. No live invocation, migration,
database write, deployment, or index change performed. Databricks Python SDK
guidance informed auth reuse and synchronous Flask transport.

Remaining before M2 completion: additive storage migration/registries, owner-scoped
repository and pagination, shared leases/capacity, deduplication, expired-worker
reconciliation, orchestration with database release before streaming, trusted
context/receipt assembly, malformed-event hardening, strict deadline enforcement,
and database-backed concurrency/isolation tests. Chat routes/UI are later work.

## Persistence increment

Migration `0006_assistant_conversations.sql` adds suffix-owned conversations,
runs and messages, composite ownership foreign keys, unique submission IDs,
and a partial unique active-run index per owner. Registries and migration
rendering tests are updated. Proposal storage is deferred to M4, rather than
creating an unused executable-action table now.

`assistant_repository.py` provides owner-scoped creation, cursor pagination,
bounded history reads, submission fingerprint/deduplication, capacity checks,
210-second generation leases, expired-run reconciliation during new claims,
and lease-token/expiry compare-and-set completion. The fixed namespaced
transaction advisory lock serializes only brief claims; no lock/connection is
held during model transport. Reconciliation updates run metadata across owners
but returns no cross-owner transcript data. Leases are fixed-duration rather
than renewed; strict transport termination before lease expiry remains required.

`assistant_service.py` coordinates generation and terminal persistence, handles
duplicate submissions without invoking the model, and records interrupted
generations on generator close. It is an internal backend primitive, not a
public route/SSE schema. Trusted context/receipts and proposal extraction remain
unimplemented. No business-write execution is exposed.

41 targeted tests pass (history/transport/protocol, mocked repository/service,
and migration/schema rendering). Mocks verify queries and control flow, NOT
real PostgreSQL constraints, rollback, concurrency or isolation. A disposable
PostgreSQL integration test is still required; no migration has been applied.

The remaining list above is historical; migration, registries, repository and
basic orchestration now exist. Outstanding: database integration proof,
strict wall-clock cancellation, malformed-event hardening, trusted context,
operational recovery/retention policy and complete backend acceptance.
