# Phase 5 Status — MCP agent tools and semantic research

Updated: 2026-09-30

| Unit | Status | Evidence | Remaining gate |
|---|---|---|---|
| 5.0 Retrieval design | Complete | ADR 0005 records section-aware parent/child chunking, Qwen3 embeddings, Delta Sync AI Search, hybrid retrieval, provenance, and evaluation targets | None |
| 5.1 Service and observability | Render deployment accepted | `https://signal-desk-mcp.onrender.com` is live; health, unauthenticated rejection, Supervisor authentication, nine-tool discovery, Lakebase market reads, semantic research, Massive fallback, correlation IDs, and bounded trace/event reconciliation passed | None for MCP deployment; Supervisor evaluation is Phase 7 |
| 5.2 Retrieval tools | Workspace accepted | Historical performance uses a bounded parameterized Silver/Gold SQL read; a live AAPL known-answer reconciled 9 rows, 0.24% return, two-day freshness, safe free-plan snapshot denial, and one Massive attempt; requested windows are trimmed, sector is not invented, reads do not create user state, and news uses a many-to-many bridge | None for the current workspace dataset |
| 5.3 Action tools | Deployed acceptance complete | Watchlist/note/report writes require confirmation and transactional idempotency; exact replay returns the stored result; changed-payload reuse fails; two real principals proved ownership isolation through the authenticated UI; exact cleanup passed | None for the accepted action workflow |
| 5.4 Semantic retrieval | Workspace accepted | Canonical chunks plus CDF Delta serving-table publisher, ready standard endpoint, triggered Qwen3 Delta Sync hybrid index with 393 rows, filtered/reranked SDK search, parent deduplication, provenance, and a passing 51-case live evaluation | None for the current workspace corpus |

## Accepted implementation sequence

1. Replace duplicate character chunking with the canonical Spark-owned contract.
2. Provision the standard Vector Search endpoint and Delta Sync index through the
   bundle, using `databricks-qwen3-embedding-0-6b`.
3. Refactor semantic search to the managed index with filters and provenance.
4. Harden trusted identity, confirmations, idempotency, and bounded audit events.
5. Run local contracts and retrieval metrics, then deploy and run workspace gates.

## Implementation evidence

- 2026-09-11 — Replaced duplicate character-window behavior in the research
  pipeline with deterministic filing-section parent/child chunks. Articles use a
  separately bounded profile; contextual embedding text and faithful retrieval
  text are persisted independently. Twelve document and pipeline contract tests
  plus focused lint pass.
- 2026-09-11 — Replaced the MiniLM/pgvector runtime path with a DAB-managed
  standard endpoint and triggered Delta Sync hybrid index using Qwen3 0.6B.
  Added bounded filter/rerank/parent-expansion search, a post-pipeline sync task,
  and on-behalf-of-user SDK authentication. Thirty-five focused tests and lint
  pass. Strict bundle parsing reached the workspace-auth visitor and stopped only
  because `dataexpertio_srini` has no cached OAuth credentials.
- 2026-09-11 — Removed model-supplied `user_email` from every user-scoped MCP
  signature. Consequential writes now require `confirmed=true` and an
  8–128-character idempotency key, reserve/store the key in the same transaction
  as the write, reject key reuse with changed parameters, and roll back as one
  unit. Watchlist reads no longer create users or lists.
- 2026-09-11 — Added a health route, request correlation IDs, contract versions,
  structured safe completion logs, pseudonymous trace subjects, bounded trace
  summaries, and Lakebase agent session/tool events. Note/report bodies, source
  context, access tokens, idempotency values, and large result arrays are not
  retained in traces.
- 2026-09-11 — Historical performance now prefers a parameterized, 370-row-bounded
  SQL Warehouse read joining governed Silver bars to Gold performance and falls
  back explicitly to the shared rate-limited Massive client. Requested calendar
  windows are trimmed, actual trading periods are reported, sector is left null
  rather than copied from SIC industry, and migration 0004 adds the operational
  article/ticker bridge.
- 2026-09-11 — Added a retrieval evaluation CLI with Recall@5, MRR, nDCG,
  provenance completeness, and filter-violation metrics. Two fixture-backed smoke
  labels validate the harness; live acceptance intentionally requires at least 50
  workspace labels. Whole-repository lint and 145 tests pass.
- 2026-09-11 — Selectively deployed the research pipeline and completed graph
  validation update `ca094e65-f38e-4ebe-b121-0b1faeea946d` plus chunk refresh
  `56c5df46-e1a8-4d14-bd93-d467aadb554e`. SQL Warehouse reconciliation found
  393 complete chunks from 98 sources (86 articles and 12 filings), with zero
  duplicate chunk IDs, duplicate source indexes, or untraceable chunks.
- 2026-09-11 — Applied checksum-protected Lakebase migration `0004` using the
  admin-managed `database/lakebase-url` secret. All 15 expected `_srini` tables
  are present and owned by the current database role, the second apply was empty,
  five CDC tables have full replica identity, and disposable owner-isolation CRUD
  passed with complete cleanup.
- 2026-09-11 — The first index create proved this workspace rejects a Lakeflow
  materialized view as the direct source. Added a separately testable Spark
  publisher that incrementally MERGEs canonical chunks into the regular,
  CDF-enabled `research_search_documents` Delta table. After replacing a
  serverless-incompatible `SystemExit(0)` entry point, run `255439151353917`
  reconciled 393 source and target rows with zero duplicate chunk IDs.
- 2026-09-11 — Provisioned standard endpoint `signal-desk-research-dev` and the
  triggered Delta Sync index. Sync job run `52577799192254` succeeded, and the
  ready index reports 393 indexed rows. The DAB plan preserves the existing index
  rather than proposing recreation.
- 2026-09-11 — Corrected the live reranker request contract and ran the committed
  51-case workspace evaluation. Recall@5 is 1.0000, MRR is 0.9902, nDCG@5 is
  0.9928, with zero provenance failures or filter violations. Focused regression
  tests and lint pass. Detailed evidence is retained in
  `docs/phase5/WORKSPACE_ACCEPTANCE_FINDINGS.md`.
- 2026-09-11 — Selective MCP app deployment was rejected before app creation:
  the deploying user lacks the permission required to attach the administrator-owned
  `massive-api-key` resource. The same user cannot inspect the `massive` or
  `database` scope ACLs. An administrator must grant the deployer `MANAGE` on
  both secret resources or perform an equivalent administrator-managed binding.
  No partial `signal-desk-mcp-dev` app remains.
- 2026-09-11 — Added a sanitized Phase 5.2 workspace acceptance runner and a
  post-deployment MCP harness. The latter is read-only by default, never forges
  forwarded identity headers, and requires `--exercise-writes` before it tests a
  confirmed watchlist add, exact idempotent replay, changed-payload rejection,
  and cleanup in a `finally` path. It also reconciles correlation IDs across
  bounded trace and agent-event records.
- 2026-09-11 — Live Phase 5.2 acceptance passed for AAPL. Two independent
  warehouse reads reconciled 9 rows through 2026-09-09, the calculated 30-day
  return matched at 0.24%, staleness was 2 days against a 7-day maximum, and the
  unavailable free-plan snapshot degraded to the documented daily-aggregate
  fallback after 1 physical Massive attempt against the 4-attempt budget.
- 2026-09-25 — Deployed the MCP service on Render. Public health and
  unauthenticated rejection pass; the Supervisor credential authenticates;
  all nine tools are discoverable; and both read attempts produced matching,
  bounded Lakebase trace and agent-event rows with redacted idempotency fields.
  The read-only gate remains failed for two precise configuration reasons: AI
  Search reports `invalid_client` for the current paid-workspace M2M identity,
  and the governed market fallback reports missing ambient credentials because
  `MASSIVE_API_KEY` has not yet been entered on Render. The reversible write
  gate was intentionally not run while retrieval is red.
- 2026-09-25 — Copied the existing `massive/api-key` value directly from the
  Databricks secret scope into the Render MCP environment without displaying or
  committing it. Deployment `dep-darfbsh42hec73agvkrg` succeeded. The repeated
  read-only gate returned successful AAPL fallback data through 2026-09-24 and
  again reconciled both bounded trace/event pairs. The remaining retrieval
  failure is the paid-workspace M2M `invalid_client` response for governed SQL
  and AI Search; writes remain intentionally gated.
- 2026-09-28 — Hardened MCP production diagnostics after Render exposed only
  HTTP access records for the M2M failure. Error completions now emit a
  searchable warning-level JSON event with UTC timestamp, tool, correlation ID,
  duration, bounded application error code, error type, and an allowlisted OAuth
  dependency code such as `invalid_client`. Raw exception messages, credentials,
  tokens, and unknown error strings are never logged. Commit `030c14a` was
  deployed as Render deployment `dep-dati35mgekts73atrl8g`; the authenticated
  read-only smoke test produced a searchable `semantic_research` event with
  `dependency_error_code=invalid_client`, dependency-authentication type,
  correlation ID, duration, and timestamp, with no raw OAuth message or secret.
  The full local suite passes 243 tests, repository-wide Ruff, and the tracked-file
  credential scan.

## Workspace acceptance

The data profile remains `dataexpertio_srini`; its authenticated identity is
`malyalasrinivas@gmail.com`, and all SQL, Unity Catalog, AI Search, Lakebase
analytics, and agent processing remain there. As of 2026-09-24, only the MCP
and Flask app runtimes will move to Render.

The earlier Databricks App secret-binding and Free Edition paths are superseded.
The Render MCP process is deployed and its transport, machine authentication,
tool contract, Massive fallback, and audit path are accepted. Remaining
acceptance follows ADR 0007: sync narrow market and research serving tables into
Lakebase, prove market parity, promote a Lakebase research backend only after
the existing 51-case thresholds pass, then remove MCP workspace credentials and
exercise reversible action/idempotency, simultaneous-quota, Supervisor, and
two-real-principal isolation gates. SQL Warehouse and AI Search remain rollback
paths during acceptance.

The prior same-workspace UI procedure in
`docs/phase5/MANUAL_MCP_APP_DEPLOYMENT.md` is retained as historical context
but must not be executed. The current sequence is in
`docs/RENDER_DEPLOYMENT_PLAN.md`.

On 2026-09-29, `dataexpertio_srini` was reauthenticated and Gate 0 completed.
The existing secret maps to shared project `summer-bootcamp-2026-v2`; the user
cannot read its ACL and no Lakebase UC catalog is registered. A feature-flagged
Lakebase adapter now passes local tests, and the new CDF-enabled
`market_history_serving` Delta table reconciles 1,255,489 source and target rows
with zero duplicate keys. The classroom convention selected the shared project
and PostgreSQL schema `bootcamp_students`, isolated by `_srini` table names.
The manually triggered atomic publisher populated 1,255,489 market rows and 393
research rows with zero duplicate keys. The latest three AAPL rows match UC
exactly. The 51-case Lakebase FTS evaluation achieved Recall@5/MRR/nDCG 0.7843
with zero provenance or filter failures, but failed the 0.85 Recall@5 minimum;
research therefore remains on the accepted AI Search backend. Neither existing
`bootcamp_cdc` sync direction was changed.

On 2026-09-30, the opt-in write harness passed the deployed action gate,
including confirmation, exact replay, changed-payload rejection, cleanup, and
bounded trace/event reconciliation. Shared recursive result serialization
ensures watchlist, note, and report timestamps can be persisted in the
idempotency record; commit `357da4c` reached Live as deployment
`dep-dauop049v7es73ad0khg`. Two permitted Google principals then each created
one watchlist ticker, note, and report through the deployed authenticated UI and
saw only their own data and traces. The sanitized cleanup harness removed every
disposable operational and idempotency row while retaining audit and quota
evidence.
