# Lakebase-only MCP serving plan

Updated: 2026-09-29

## Objective

Remove the Render MCP service's runtime dependency on a Databricks workspace
OAuth M2M client. The MCP must serve operational actions, historical market
reads, attributable research retrieval, audit events, and Massive quota
coordination through its existing TLS PostgreSQL connection to Lakebase.

This is an incremental serving-plane change, not a data-platform migration.
Jobs, Lakeflow pipelines, Unity Catalog, Lakehouse Sync, and the accepted AI
Search index remain in `dataexpertio_srini`. They continue to produce and govern
the source data. Only the MCP's request-time read path moves to Lakebase.

## Current evidence and constraint

- Render already uses `LAKEBASE_URL` successfully for migrations, action state,
  rate limiting, idempotency, and bounded trace/event records.
- The remaining MCP failures occur before SQL Warehouse and AI Search calls
  because the configured paid-workspace M2M client returns `invalid_client`.
- `dataexpertio_srini` is the selected profile for this work and was
  reauthenticated on 2026-09-29.
- The existing secret resolves to shared project `summer-bootcamp-2026-v2`,
  branch `production`, endpoint `primary`, and database `databricks_postgres`.
  The project is owned by another user. The selected identity can list it but
  cannot read its ACL, and no Lakebase UC catalog is currently registered.
- The secret currently connects as broad native role `student`; the final MCP
  runtime must not retain that role.
- `market_history_serving` was published with 1,255,489 unique keys and zero
  reconciliation difference. The existing research source has 393 unique
  chunks. Both serving sources have CDF and row tracking enabled.

## Decision principles

1. Preserve the accepted source-of-truth pipelines and current AI Search index.
2. Add serving copies; do not redirect or mutate existing operational tables.
3. Use the classroom's shared PostgreSQL schema `bootcamp_students`; every
   persistent application-owned serving table must end in `_srini`.
4. Put every new read path behind an explicit backend feature flag.
5. Cut over one capability at a time, with known-answer and rollback tests.
6. Do not call PostgreSQL full-text search semantic retrieval. The existing
   `semantic_research` contract can move only after the 51-case evaluation is
   rerun and the documented thresholds pass.
7. Do not delete the SQL Warehouse or AI Search resources during this project.

## Target architecture

```text
Browser -> Render Flask -> signed assertion -> Render FastMCP
                                              |-> Lakebase operational schema
                                              |-> Lakebase bootcamp_students
                                              |     |-> market_history_serving_srini
                                              |     `-> research_documents_serving_srini
                                              `-> Massive API after Lakebase quota acquisition

dataexpertio_srini
  Jobs/Lakeflow/Unity Catalog
      |-> curated market serving Delta table ----\
      `-> research_search_documents --------------> atomic direct publisher

Existing SQL Warehouse and AI Search remain available as rollback paths only.
```

At the final MCP cutover, Render requires `LAKEBASE_URL`, `MASSIVE_API_KEY`, the
frontend assertion public key, and the Supervisor credential. The MCP no longer
requires `DATA_WORKSPACE_CLIENT_ID`, `DATA_WORKSPACE_CLIENT_SECRET`,
`DATA_WORKSPACE_WAREHOUSE_ID`, or a Vector Search index name.

## Serving datasets

### Historical market data

Create one curated Unity Catalog serving table with exactly the bounded fields
currently returned by `lakehouse_market.fetch_market_bars`:

- `(ticker, trading_date)` primary key;
- OHLCV, VWAP, and transaction count;
- daily return and 20-day annualized volatility;
- source request ID and source freshness timestamp.

The source publisher joins the accepted Silver and Gold sources in Databricks,
MERGEs into a regular Delta table, enables Change Data Feed and row tracking,
and reconciles source/target counts. Because the shared project has no
registered Lakebase UC catalog and this identity lacks the project permission
needed to create managed synced tables, a manually triggered job streams that
narrow source into session-local PostgreSQL temporary tables. It validates
counts and keys, then transactionally replaces
`bootcamp_students.market_history_serving_srini`. A failed publish rolls back to
the prior visible copy. The MCP performs no broad OLAP aggregation in Lakebase.

### Research documents

Publish the existing regular Delta table
`bootcamp_students.student_sri.research_search_documents` into
`bootcamp_students.research_documents_serving_srini`, keyed by `chunk_id`.
Preserve passage, parent context, source metadata, tickers, dates, URLs, and
content hashes in the same atomic transaction as market history.

The first implementation uses an expression GIN index over
`to_tsvector(...)` rather than adding a generated column. Metadata filters, parent
deduplication, maximum candidates, result limits, and provenance stay aligned
with the current MCP contract.

Full-text retrieval is a deployment spike, not automatic acceptance of the
`semantic_research` tool. Promotion requires the existing 51-case evaluation to
pass its committed Recall@5, MRR, nDCG, provenance, and filter thresholds. If it
does not, retain AI Search as the production backend while evaluating the
existing 384-dimensional MiniLM/pgvector compatibility path. A local model is
acceptable only if Render memory, cold start, licensing, and quality gates pass.

## Authentication and authorization

- Continue using direct PostgreSQL over TLS with `sslmode=require`.
- Prefer a dedicated native Postgres password role for the Render MCP because
  it does not require hourly workspace token exchange.
- Grant only `CONNECT`, shared-schema `USAGE`, `SELECT` on the two `_srini`
  serving tables, and
  the existing minimum DML permissions on MCP-owned operational tables.
- Do not grant `databricks_superuser`, `CREATEDB`, `CREATEROLE`, or broad schema
  ownership to the runtime role.
- Store the URL only in Render secret configuration and rotate the password
  after acceptance.
- The one-time setup and manually triggered publisher deployment use the interactive
  `dataexpertio_srini` identity. It is not a runtime dependency.

Creating or managing a native role still requires suitable Lakebase project
permissions. Serving-table setup needs only the already verified PostgreSQL
`CREATE` privilege in the shared schema; the direct publisher avoids a new
project-owner or workspace-admin dependency.

## Feature flags and rollback

Introduce explicit backend selection:

```text
SIGNAL_DESK_MARKET_BACKEND=databricks|lakebase
SIGNAL_DESK_RESEARCH_BACKEND=databricks|lakebase_fts|lakebase_pgvector
```

Defaults remain `databricks` until the corresponding acceptance gate passes.
Each Lakebase adapter must fail closed; it must not silently switch to Massive
or another research backend. The existing documented Massive fallback for
entitled daily aggregates remains an explicit tool result.

Rollback is an environment-variable change plus a Render redeploy. Do not drop
serving tables, existing AI Search resources, or source
Delta tables during acceptance. Remove them only in a separately approved
cleanup after a stable observation period.

## Independently testable sequence

### Gate 0 — authenticate and discover

Status: complete on 2026-09-29. The findings are recorded under **Current
evidence and constraint**. The classroom convention selects the existing shared
project and PostgreSQL schema `bootcamp_students`, with ownership isolated by
the `_srini` suffix.

1. Reauthenticate the chosen profile:

   ```bash
   databricks auth login --host https://dbc-7b106152-caf3.cloud.databricks.com --profile dataexpertio_srini
   ```

2. Discover command shapes before use:

   ```bash
   databricks postgres -h
   databricks postgres list-projects -h
   databricks postgres get-synced-table -h
   ```

3. List the existing project, branch, endpoint, database, registered Lakebase
   catalog, and current principal using only `--profile dataexpertio_srini`.
   CLI v1.12.1 has no synced-table list command: inventory known synced-table
   resource names from repository/bundle state and Catalog Explorer, then verify
   each with `get-synced-table`.
4. Verify source schemas, primary keys, CDF, row tracking, and source row counts.
5. Record sanitized identifiers and permissions; never record tokens, URLs with
   credentials, or secret values.

Acceptance: exact resources and permissions are known, and any missing
permission is named precisely.

### Gate 1 — create suffix-isolated shared-schema targets

1. Use existing PostgreSQL schema `bootcamp_students`; do not create or own the
   shared schema.
2. Create only `market_history_serving_srini` and
   `research_documents_serving_srini`, plus their application-query indexes.
3. Publish through session-local temporary tables and one atomic PostgreSQL
   transaction; never drop or overwrite another student's table.
4. Reconcile Unity Catalog and PostgreSQL counts, keys, null handling, and
   freshness.
5. Keep the publisher manual until parity, freshness, and cost are accepted.

Status: complete on 2026-09-29. Job `310994468355420`, run
`193161163752168`, atomically published 1,255,489 market rows and 393 research
rows. Both tables have zero duplicate keys and all expected primary/query
indexes. Attempt 0 encountered a transient serverless native-driver `SIGABRT`;
the platform retry completed successfully without a partial commit.

This new path is separate from both established sync directions:

- Lakebase-to-Unity-Catalog Lakehouse Sync still maps PostgreSQL
  `bootcamp_students` to UC `bootcamp_students.bootcamp_cdc` and produces
  `lb_<postgres_table>_history`. The activity pipeline continues to read only
  its five allowlisted `_srini` histories; the serving tables are not added.
- Unity-Catalog-to-Lakebase graph tables still land in PostgreSQL schema
  `bootcamp_cdc` and end in `_srini`. The equal `bootcamp_cdc` label does not
  make the two directions or namespaces interchangeable.

Acceptance: serving copies are complete and existing operational/source objects
are unchanged.

### Gate 2 — implement the market adapter

1. Add a parameterized Lakebase market query bounded to one ticker, at most 370
   rows, and the requested date interval.
2. Preserve numeric normalization and the current response contract.
3. Add unit, injection, timeout, empty-result, staleness, and source-label tests.
4. Run the accepted AAPL known answer against both backends and compare rows,
   dates, return, high, low, and freshness.
5. Deploy with the Databricks backend default, canary Lakebase, then cut over.

Acceptance: exact known-answer parity and no workspace OAuth call from the
Lakebase request path.

Status: local live parity passed for the three latest AAPL rows (dates, OHLC,
return, volatility, request ID, and freshness matched the UC source exactly).
Deployed backend cutover and no-workspace-call evidence remain pending.

### Gate 3 — implement and evaluate research retrieval

1. Add bounded PostgreSQL full-text candidate retrieval with all current filters
   and provenance fields.
2. Keep the backend identity visible in result metadata and traces.
3. Run deterministic adapter tests and the complete 51-case live evaluation.
4. Promote `lakebase_fts` only if every existing threshold passes. Otherwise,
   keep AI Search active and run a separately measured pgvector experiment.
5. Measure Render peak memory and cold-start behavior before considering a local
   embedding model.

Acceptance: the deployed backend passes the existing quality and safety gates;
otherwise there is no semantic cutover.

Status: evaluated on 2026-09-29. The 51-case Lakebase FTS run had Recall@5
0.7843, MRR 0.7843, nDCG@5 0.7843, zero provenance failures, and zero filter
violations. It failed the committed Recall@5 >= 0.85 threshold, so
`SIGNAL_DESK_RESEARCH_BACKEND` remains `databricks`; AI Search remains the
accepted production and rollback backend.

### Gate 4 — remove MCP workspace credentials

1. Run the full read-only MCP harness, reversible-write/idempotency gate,
   simultaneous quota gate, and trace/event reconciliation on Lakebase backends.
2. Prove outbound MCP traffic no longer includes workspace OAuth, SQL Warehouse,
   or AI Search calls.
3. Remove the MCP-only Databricks credential variables from `render.yaml` and
   Render after rollback validation.
4. Keep frontend analytics credentials as a separately tracked concern; they
   are not reused by MCP.

Acceptance: all nine MCP tools pass without MCP workspace credentials.

### Gate 5 — final evidence and cleanup decision

1. Repeat two-real-principal isolation and Supervisor evaluations.
2. Observe at least one normal source refresh and verify publisher freshness.
3. Update the architecture diagram, data dictionary, tool reference, status,
   traceability matrix, and demo checklist with measured results.
4. Decide separately whether to retain or clean up the dormant SQL/AI Search
   rollback resources.

Acceptance: the release package describes the deployed path exactly and retains
sanitized evidence.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Managed synced-table creation needs a permission the user lacks | Use the verified shared-schema PostgreSQL path and atomic direct publisher; no new admin grant is required. |
| Whole-market replication is unnecessarily large | Publish one narrow, indexed serving table rather than syncing multiple broad Silver/Gold tables. |
| Sync lag makes results stale | Return source freshness, set an explicit threshold, and fail visibly when exceeded. |
| PostgreSQL search quality regresses | Preserve AI Search, rerun all 51 cases, and prohibit semantic cutover on threshold failure. |
| Native password has broad access | Create a dedicated role, least-privilege grants, TLS, secret storage, rotation, and negative permission tests. |
| Publisher consumes too many connections | Stream over one PostgreSQL connection from one manually triggered job and measure duration before scheduling. |
| A serving-table change harms operational data | Use session-local staging, one transaction, suffix-isolated targets, feature flags, and environment-only rollback. |

## Non-goals

- Replacing Unity Catalog as the governed source of truth.
- Deleting the accepted AI Search index or SQL Warehouse.
- Moving pipelines or Supervisor processing to Render.
- Claiming lexical retrieval is semantic without evaluation evidence.
- Solving the frontend Gold-analytics runtime path in the MCP cutover. That can
  use the same serving pattern later, but it has separate permissions and tests.
