# Phase 5 Status — MCP agent tools and semantic research

Updated: 2026-09-11

| Unit | Status | Evidence | Remaining gate |
|---|---|---|---|
| 5.0 Retrieval design | Complete | ADR 0005 records section-aware parent/child chunking, Qwen3 embeddings, Delta Sync AI Search, hybrid retrieval, provenance, and evaluation targets | None |
| 5.1 Service and observability | Local implementation complete | Nine tool names retained; health route, correlation IDs, contract versions, structured completion logs, fail-closed trusted identity, pseudonymous bounded traces, and agent session/events pass tests | Deployed health, trace-failure, and cross-principal proof |
| 5.2 Retrieval tools | Local implementation complete | Historical performance prefers bounded parameterized Silver/Gold SQL, Massive is a rate-limited fallback/on-demand source, requested windows are trimmed, sector is not invented, reads do not create state, and news uses a many-to-many bridge | Workspace known-answer and entitlement/freshness acceptance |
| 5.3 Action tools | Local implementation complete | Watchlist/note/report writes require confirmation and transactional idempotency; different-payload key reuse fails; trusted request identity owns writes; rollback and bounded-input tests pass | Apply migration 0004 and prove two principals through deployed MCP |
| 5.4 Semantic retrieval | Workspace acceptance in progress | Canonical chunks plus standard endpoint, triggered Qwen3 Delta Sync hybrid index, filtered/reranked SDK search, parent deduplication, provenance, on-behalf-of-user token support, post-refresh sync job, restored OAuth, and strict bundle validation | Workspace provision/sync/live evaluation |

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

## Workspace acceptance

The selected profile is `dataexpertio_srini`. OAuth was restored on 2026-09-11
and the authenticated identity is `malyalasrinivas@gmail.com`. Strict bundle
validation passes after changing the Vector Search endpoint permission to the
supported `CAN_USE` level. No committed code contains a token, Massive key, SEC
contact, or Lakebase URL.

Remaining workspace acceptance is: apply Lakebase migration 0004, provision the
endpoint/index and sync job, run the 50+ case retrieval set, deploy MCP, and
exercise two authenticated principals plus retry/trace checks.
