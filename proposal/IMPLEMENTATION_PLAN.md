# Signal Desk Capstone Implementation Plan

## Purpose

The proposal describes Signal Desk as a brand-new capstone implementation. The execution plan, however, deliberately starts from the working code in this repository. Existing code is treated as an implementation accelerator—not as proof that a capstone requirement is already complete. Every retained component must be brought under the new contracts, security model, deployment model, and test suite.

This plan breaks that brownfield implementation into small, dependency-ordered units. Each unit produces a reviewable artifact, includes its own tests, and has an explicit exit criterion. A unit is complete only when its tests pass and its evidence is recorded.

> **Current deployment decision (2026-09-24):** Later budget and workspace
> constraints supersede the Databricks Apps hosting references retained in the
> original phase text below. Flask and FastMCP deploy as two Render Python web
> services from `render.yaml`; jobs, Spark pipelines, Unity Catalog, SQL
> Warehouse, AI Search, Lakebase Sync analytics, and Agent Bricks remain in the
> paid Databricks workspace. See `docs/adr/0006-render-application-tier.md` and
> `docs/RENDER_DEPLOYMENT_RUNBOOK.md` for the executable deployment contract.

The recommended implementation strategy is risk-first:

1. Validate free-tier Massive throughput and workspace capabilities before building around them.
2. Build the high-volume market pipeline before the agent or frontend.
3. Establish Lakebase ownership and identity boundaries before adding write tools.
4. Build the agent as independently testable tools before connecting Agent Bricks.
5. Add Lakebase CDF analytics before the final frontend so the UI consumes stable contracts.
6. Deploy and test a thin vertical slice before polishing the complete experience.

## Existing-code assessment and disposition

The repository already contains a useful research-agent prototype:

- a FastMCP server with nine retrieval and write tools;
- a `MassiveClient` with authentication, retries, and endpoints for ticker details, snapshots, bars, news, fundamentals, and filings;
- broker logic for performance, comparisons, company research, watchlists, notes, reports, semantic search, and notable updates;
- a Lakebase/Postgres schema and Python persistence helpers;
- an embedding ingestion job using MiniLM and pgvector;
- a Flask dashboard with watchlist, news, notes, reports, and tool-activity views;
- an agent system prompt, configuration examples, demo scenarios, app manifests, and three broker tests.

That foundation does **not** yet provide the required Spark/Lakeflow pipeline, grouped-market backfill, one-million-row certification, SEC ingestion pipeline, production Lakebase identity model, Lakebase CDF analytics, deployable Agent Bricks resources, reproducible Databricks bundle, or complete end-to-end test evidence.

| Existing asset | Disposition | Planned treatment |
|---|---|---|
| `mcp_server/massive_client.py` | Adapt | Preserve endpoint parsing, retry, and safe-error behavior; add the grouped daily endpoint, shared four-calls-per-minute limiter, correlation IDs, and fixtures. |
| `mcp_server/research_broker.py` | Refactor | Preserve validated calculations and tool behavior; split API, analytical, and repository concerns; trim requested date windows; fix article/ticker relationships and response bounds. |
| `mcp_server/stock_research_mcp_server.py` | Harden | Preserve FastMCP tool surface; derive user identity from trusted request context, sanitize traces, add confirmation/idempotency controls, and version contracts. |
| `mcp_server/schema.sql` | Migrate | Use the current model as migration version 1; add versioned upgrades for sessions, idempotency, tool events, CDF metadata, ownership, and indexes. |
| `mcp_server/lakebase.py` | Replace internally | Keep repository-facing behavior while replacing URL-secret, connection-per-operation access with an attached Lakebase Autoscaling resource, OAuth/SDK configuration, pooling, and transactions. |
| `jobs/ingest_research_embeddings.py` | Adapt | Retain the bundle entry point as a triggered managed Delta Sync operation; move canonical chunking to Spark and embedding/index lifecycle to Databricks AI Search. |
| `dashboard/app.py`, templates, and static assets | Extend | Preserve the Flask shell and useful operational views; move data access behind authenticated services and add research chat, evidence, analytics, and complete UI states. |
| Agent prompt, config, and demo scenarios | Adapt | Convert them into deployable Supervisor Agent/MCP configuration and a repeatable evaluation suite. |
| `app.yaml` files and `setup_secrets.py` | Replace configuration | Use attached resource references and explicit Databricks profiles; eliminate implicit-profile and raw connection-secret assumptions. |
| Spark/Lakeflow, SEC pipeline, CDF analytics, DAB, volume proof | New | Implement and test these because no equivalent currently exists in the repository. |

## Baseline-preservation rule

Before refactoring, capture the current public behavior with recorded Massive fixtures and a temporary Postgres test database. Regression tests will cover ticker validation, performance calculations, comparison ordering, watchlist add/remove semantics, note/report persistence, chunk creation, MCP response envelopes, and the existing dashboard routes. A reused component is credited as complete only after those tests pass against the revised implementation.

## Definition of done for every unit

Every implementation unit must include:

- source code and configuration committed to version control;
- unit or contract tests for normal, empty, invalid, and dependency-failure paths;
- no committed credentials, tokens, connection strings, or user data;
- structured logs with correlation IDs and safe error messages;
- updated documentation for new configuration or operational steps;
- reproducible commands for validation;
- an exit artifact, such as a passing test report, Delta query result, migration result, API response, screenshot, or deployment URL.

## Test layers

| Layer | Purpose | Execution cadence |
|---|---|---|
| Unit | Pure functions, transformations, validation, calculations, rate limiting, and authorization decisions | Every change |
| Contract | Massive, SEC, MCP, Lakebase, CDF, and frontend request/response shapes using recorded fixtures | Every change |
| Local integration | Components with local Postgres/test doubles and captured API data | Every pull request |
| Databricks integration | Unity Catalog, Lakeflow, Lakebase, SQL warehouse, Agent Bricks, and app resources | At completion of the relevant unit |
| End-to-end | Authenticated research, evidence retrieval, write action, CDC propagation, and UI display | Every release candidate |
| Nonfunctional | Rate limit, volume, latency, security isolation, recovery, and cost checks | Before final demonstration |

## Target project structure after evolving this repository

```text
stock-market-research-agent-app-main/
├── databricks.yml
├── resources/
│   ├── market_ingestion.job.yml
│   ├── research_pipeline.pipeline.yml
│   ├── mcp_server.app.yml
│   └── frontend.app.yml
├── ingestion/                 # new shared Massive/SEC landing code
├── pipelines/                 # new Spark bronze/silver/gold pipeline code
│   ├── bronze/
│   ├── silver/
│   └── gold/
├── mcp_server/                # evolve the existing FastMCP service
│   ├── stock_research_mcp_server.py
│   ├── massive_client.py
│   ├── services/
│   ├── repositories/
│   └── migrations/
├── jobs/                      # evolve the existing embedding job
├── dashboard/                 # evolve the existing Flask Databricks App
├── agent/                     # evolve prompt/config/demo assets
├── shared/
│   ├── contracts/
│   └── observability/
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── integration/
│   └── e2e/
├── fixtures/
└── docs/
```

## Dependency map

```text
Foundation
  ├── Massive feasibility → market ingestion → bronze → silver → gold/1M proof
  ├── SEC feasibility → SEC ingestion → document transformations → embeddings
  ├── Lakebase provisioning → data access + identity → MCP retrieval/write tools
  └── CDF capability → CDF replication → usage analytics

Market + documents + Lakebase tools
  → Agent Bricks integration
  → Frontend research workflow
  → End-to-end deployment and hardening
```

## Unit disposition summary

| Units | Disposition | Existing-code basis |
|---|---|---|
| 0.1–0.2 | Adapt | Inventory the repository, capture behavior, and add missing quality gates around the current packages. |
| 0.3 | New/replace configuration | Replace manual manifests and setup with a Databricks bundle while retaining both app codebases. |
| 0.4 | New validation | Validate external/platform assumptions not proven by the prototype. |
| 1.1 | Adapt | Extend the current Massive client. |
| 1.2–1.3 | New | Add global checkpoints and market-wide raw landing. |
| 2.1–2.4 | New | Add Spark Bronze/Silver/Gold processing and million-row certification. |
| 3.1–3.3 | New | Add SEC acquisition and structured/unstructured transformations. |
| 4.1 | New platform bootstrap | Provision secure Lakebase ownership for the existing data model. |
| 4.2 | Migrate | Upgrade the current `schema.sql` without discarding data. |
| 4.3 | Refactor/replace internals | Preserve persistence behavior while replacing connection and identity handling. |
| 5.1–5.3 | Harden/refactor | Retain the FastMCP server and eight non-semantic tools under new contracts and security controls. |
| 5.4 | Adapt | Convert the current embedding job and semantic tool into an incremental deployable capability. |
| 6.1–6.2 | New | Add CDF replication and Delta usage analytics. |
| 7.1 | Adapt | Turn the current prompt/config/demo assets into deployed Agent Bricks resources and evaluations. |
| 7.2 | New security integration | Establish trusted identity through the full app-agent-MCP path. |
| 8.1–8.3 | Extend | Evolve the existing Flask dashboard and its current watchlist workflow. |
| 8.4 | New | Add the analytics page backed by Delta gold tables. |
| 9.1–9.4 | Integrate and prove | Package the retained and new components into a reproducible, tested capstone release. |

# Phase 0 — Decisions, scaffolding, and capability gates

## Unit 0.1 — Architecture decisions and contracts

**Goal:** Freeze the boundaries that other units depend on.

**Implement:**

- Architecture decision records for Flask, FastMCP, Lakebase Autoscaling, pgvector, Lakeflow Spark Declarative Pipelines, Unity Catalog, and two Databricks Apps.
- Inventory current routes, tools, database tables, environment variables, and response shapes; mark each as retain, change, or retire.
- Canonical ticker, trading-date, article, filing, research-chunk, agent-event, note, report, and error-envelope schemas.
- Data classification: public market data, user-owned content, identity metadata, and prohibited trace fields.
- Environment variables and resource keys without actual resource identifiers.

**Tests:**

- JSON/Pydantic schema validation for representative valid and invalid fixtures.
- Compatibility test that serialized contracts can be read by the ingestion, MCP, and frontend packages.
- Characterization tests that capture the existing broker, MCP, persistence, embedding-chunking, and Flask-route behavior before refactoring.

**Exit criterion:** Contract fixtures and ADRs are reviewed; no open architectural decision blocks the scaffold.

## Unit 0.2 — Repository, quality tooling, and CI

**Goal:** Put the existing repository—not an empty scaffold—under repeatable quality gates.

**Implement:**

- Preserve the current `mcp_server`, `jobs`, `dashboard`, and `agent` packages while adding shared contracts, new ingestion/pipeline packages, dependency locking, formatting, linting, type checking, pytest configuration, coverage, and secret scanning.
- Separate unit, contract, integration, and end-to-end test markers.
- Mock backend switches for local development.

**Tests:**

- CI runs against the existing source plus the new scaffolding.
- Existing broker tests continue to pass; add at least one test for each currently untested package and an intentionally excluded integration test.

**Exit criterion:** A clean checkout can install dependencies and pass the fast test suite with one documented command.

## Unit 0.3 — Databricks bundle foundation

**Goal:** Establish repeatable dev/prod resource definitions before application logic.

**Implement:**

- `databricks.yml` with parameterized catalog, schema, volume, warehouse, application names, and deployment targets.
- Convert the two existing manually deployed Databricks Apps and the embedding script into initial bundle resources; add new resource stubs for market ingestion and the Lakeflow pipeline.
- Least-privilege permission plan and bootstrap checklist for resources not fully managed by the bundle.

**Tests:**

- `databricks bundle validate --strict --target dev` using the user-selected profile.
- Path-resolution test for all source and resource files.
- Configuration scan proving no hardcoded workspace URL, token, secret, branch, or database ID.

**Exit criterion:** The bundle validates in the chosen development workspace. No profile is selected automatically; the user must choose one before execution.

## Unit 0.4 — External-service and platform feasibility spike

**Goal:** Retire the highest-risk assumptions before full implementation.

**Implement:**

- Call the Massive Daily Market Summary for five recent trading dates with `include_otc=true` using the free key.
- Record returned row counts, response size, latency, and error/rate-limit headers without storing the key.
- Retrieve one Massive news response, one SEC submission, and one SEC Company Facts response.
- Verify Lakebase Autoscaling and Lakebase CDF availability in the selected workspace.
- Verify the workspace can deploy a minimal Databricks App and create a Lakeflow pipeline.

**Tests:**

- Confirm the grouped endpoint returns market-wide records and requires one request per date.
- Confirm five calls remain within the documented free allowance.
- Project the number of trading dates required for one million distinct rows using observed counts.
- Insert, update, and delete a disposable Lakebase row and verify whether CDF can capture it.

**Exit criterion:** A short feasibility report records observed counts and confirms the primary approach. If Lakebase CDF is unavailable, formally select the allowed Lakeflow event-pipeline fallback before continuing.

# Phase 1 — Massive market ingestion

## Unit 1.1 — Shared Massive client and global rate limiter

**Goal:** Guarantee that all use of the free key stays below five calls per minute.

**Implement:**

- Extend the existing `MassiveClient`, retaining its authentication, timeout, retry/backoff, safe-error, and response parsing behavior while adding response validation and request correlation IDs.
- Process-safe shared queue limited to four requests per rolling minute.
- `Retry-After` handling, bounded retries, jitter, metrics, and test-clock injection.
- Add the missing Daily Market Summary method; keep and regression-test the existing custom-bars, ticker-overview, snapshot, news, fundamentals, and filing methods.

**Tests:**

- Virtual-clock test proves no more than four requests are released in any rolling minute.
- Concurrent caller test proves ingestion and agent requests share the same allowance.
- 401, 403, 404, 429, timeout, malformed JSON, and empty-result tests.
- Verify logs and exceptions never expose the API key.
- Recorded-fixture compatibility tests prove existing broker-facing methods keep their agreed response shapes.

**Exit criterion:** Deterministic tests prove the limiter cannot exceed four calls per minute under concurrency or retries.

## Unit 1.2 — Trading calendar and checkpoint store

**Goal:** Make the historical load resumable and idempotent.

**Implement:**

- Generate eligible weekdays within the free two-year history; treat empty holiday responses as completed no-data dates.
- Checkpoint states: pending, in-progress, completed, no-data, retryable-failure, terminal-failure.
- Record request ID, landing path, row count, checksum, attempt count, and timestamps.

**Tests:**

- Weekend, holiday, duplicate date, resume-after-failure, corrupt checkpoint, and stale in-progress tests.
- Idempotency test proves a completed date is not fetched again unless explicitly requested.

**Exit criterion:** A simulated interrupted 20-date backfill resumes without duplicate API calls or duplicate landed files.

## Unit 1.3 — Raw market landing job

**Goal:** Land replayable, immutable Massive responses in a Unity Catalog Volume.

**Implement:**

- Lakeflow Job task that fetches one grouped response per date with `adjusted=true` and `include_otc=true`.
- Write one atomic JSON file plus manifest per trading date.
- Parameters for start date, end date, maximum dates, and stop-after-row-estimate.
- Structured job metrics for calls, rows, bytes, elapsed time, retries, and failures.

**Tests:**

- Local fixture test and a live two-date development run.
- Atomic-write test proves partial files are not treated as complete.
- Replay test reads landed files without contacting Massive.

**Exit criterion:** A checkpointed 10-date pilot lands valid manifests and can be rerun with zero duplicate requests.

# Phase 2 — Spark market pipeline and volume proof

## Unit 2.1 — Bronze market streaming table

**Goal:** Incrementally ingest raw landed responses into Delta.

**Implement:**

- Auto Loader streaming read from the raw market path.
- Explode the `results` array into one record per security/date.
- Preserve raw payload fields, request ID, source path, ingestion time, and rescued data.
- Expectations for source path, ticker, timestamp, and request ID.

**Tests:**

- PySpark transformation tests using valid, empty, duplicated, malformed, and schema-drift fixtures.
- Pipeline development run proves new files are processed once.

**Exit criterion:** Bronze row counts reconcile exactly to the sum of result counts in completed manifests.

## Unit 2.2 — Silver market bars

**Goal:** Produce a trustworthy analytical market table.

**Implement:**

- Normalize ticker, trading date, OHLC, VWAP, volume, transaction count, and OTC flag.
- Deduplicate on `(ticker, trading_date)` using deterministic ingestion ordering.
- Quarantine invalid prices, negative volume, inconsistent high/low, and null keys.
- Add company/reference enrichment only when it does not drop price records.

**Tests:**

- Unit tests for OHLC rules, normalization, duplicates, missing optional fields, and quarantine routing.
- Reconciliation: accepted plus quarantined equals Bronze input.
- Uniqueness test for `(ticker, trading_date)`.

**Exit criterion:** Silver passes all expectations and reconciliation queries on the 10-date pilot.

## Unit 2.3 — Gold market analytics

**Goal:** Publish stable datasets for the agent and frontend.

**Implement:**

- Materialized views for returns, rolling volatility, period high/low, volume change, peer comparison, and data coverage.
- Preserve ticker, sector, industry, period, source freshness, and data-quality dimensions.
- SQL warehouse access contract for bounded agent and frontend queries.

**Tests:**

- Known-answer tests on a small deterministic price series.
- Weekend/holiday gaps, split-adjusted data, insufficient history, zero prior close, and incomparable period tests.
- Query plans and response-size checks for representative requests.

**Exit criterion:** Known-answer calculations pass and the SQL warehouse returns a bounded peer comparison result.

## Unit 2.4 — Full backfill and one-million-row certification

**Goal:** Prove the Volume requirement using the Massive free plan.

**Implement:**

- Start with the observed pilot density (about 16,593 rows per response), target 1.1 million raw rows for margin, and permit at most 252 dates in the initial run. The checkpointed job stops fetching once the raw target is reached and can resume with a higher target if measured Silver distinct rows do not yet exceed one million.
- Record every permitted physical attempt in a credential-free append-only audit ledger; all retries still pass through the shared four-calls-per-rolling-minute limiter.
- Persist a certification report with API-call count, elapsed API time, row counts by layer, duplicates, quarantined rows, date range, and exact distinct-key count.
- Orchestrate immutable landing, incremental pipeline refresh, and strict Silver certification as separate dependent tasks.

**Tests:**

- Assert the measured distinct count exceeds 1,000,000.
- Assert actual request timing never exceeded the configured limit.
- Rerun a completed subset and prove the Delta count does not change.
- Sample reconciliation from raw manifest through Bronze and Silver.

**Exit criterion:** A saved Delta certification record and run output certify more than one million distinct market rows with no rate-limit violation.

# Phase 3 — SEC and unstructured-data pipeline

## Unit 3.1 — SEC client and raw landing

**Goal:** Acquire authoritative filing and XBRL data responsibly.

**Implement:**

- SEC client with compliant identifying User-Agent, bounded concurrency, retry/backoff, and caching.
- Submissions, Company Facts, and selected 10-K/10-Q/8-K document retrieval.
- Raw landing manifests with CIK, accession number, filing type, filing date, URL, checksum, and content type.
- Store changing submissions and Company Facts as content-addressed snapshots; treat accession-keyed filing documents as immutable and fail closed on checksum changes.

**Tests:**

- Recorded-fixture tests for submissions, XBRL facts, HTML, amendments, missing documents, and SEC error pages.
- Development integration for two companies and multiple filing types.
- Idempotency and checksum-change tests.

**Exit criterion:** Two companies have replayable submissions, facts, and filing documents with complete provenance.

## Unit 3.2 — Silver companies, facts, filings, and article relationships

**Goal:** Normalize structured and semi-structured research data.

**Implement:**

- Company and CIK mapping.
- XBRL fact normalization with taxonomy, unit, period, form, filed date, and accession.
- Filing metadata table and many-to-many article/ticker bridge.
- Expectations for accession uniqueness, valid source URL, CIK format, and required dates.
- Enrich market analytics with SEC SIC industry peers without dropping market rows that lack company reference data.

**Tests:**

- Fiscal-year variation, amended filings, duplicate facts, multiple units, multiple tickers per article, and missing CIK tests.
- Referential-integrity checks between companies, filings, facts, news, and ticker bridges.

**Exit criterion:** Structured research tables pass integrity tests for the selected demonstration companies.

## Unit 3.3 — Document parsing and research chunks

**Goal:** Turn unstructured content into inspectable retrieval units.

**Implement:**

- HTML-to-text normalization, selected section extraction, boilerplate removal, chunking, overlap, content hashes, and provenance.
- Stable chunk IDs based on source, accession/article ID, content hash, and index.
- Gold research catalog with source type, ticker, title, filing/article date, URL, and freshness.
- Reconciliation datasets that fail on duplicate chunk IDs, duplicate source indexes, or missing provenance.

**Tests:**

- Golden-file tests for HTML tables, malformed HTML, Unicode, empty sections, repeated boilerplate, and chunk boundaries.
- Reprocessing unchanged content produces identical IDs; changed content produces new hashes.

**Exit criterion:** Every chunk can be traced back to a source URL and exact filing/article identity.

# Phase 4 — Lakebase operational foundation

## Unit 4.1 — Lakebase connection and shared-table ownership bootstrap

**Goal:** Establish a safe operational database before application writes.

**Implement:**

- Use the administrator-managed `database/lakebase-url` secret without exposing the decoded connection URL.
- Use the existing shared PostgreSQL schema `bootcamp_students`; never create or drop the shared schema.
- Namespace every application object with the `_srini` suffix and document which role owns those tables.
- Frontend will not connect directly to the operational schema; it will use authenticated service APIs, avoiding cross-service-principal ownership conflicts.

**Tests:**

- Connectivity, SSL, PostgreSQL version, shared-schema permission, and create/read/update/delete smoke tests.
- Identifier-allowlist and two-user scoped-write tests prevent cross-student table names and cross-user mutations.

**Exit criterion:** All Signal Desk objects are fully qualified `_srini` tables in the shared schema, disposable CRUD cleans up, and wrong-owner mutations affect zero rows.

## Unit 4.2 — Lakebase migrations and relational model

**Goal:** Create versioned operational tables and constraints.

**Implement:**

- Adopt the existing operational model as checksum-protected migration version 1, rendering fully qualified `_srini` objects rather than running unversioned SQL.
- Add versioned migrations for agent sessions, tool events, idempotency records, CDF-safe metadata, multi-ticker article relationships, and any missing ownership/status fields.
- Foreign keys, uniqueness, cascade behavior, timestamps, indexes, status checks, and bounded payload columns.
- Seed only non-sensitive development reference data.

**Tests:**

- Apply migrations to an empty `_srini` namespace and apply again idempotently; reject changed checksums for already-applied versions.
- Constraint, rollback, cascade, index-existence, and transaction tests.
- Data-preservation test compares counts and representative user records before and after the upgrade.

**Exit criterion:** Fresh and upgrade migrations pass; the schema matches a generated data dictionary.

## Unit 4.3 — Data access layer, pooling, and identity enforcement

**Goal:** Make every operational query safe and user-scoped.

**Implement:**

- Replace the internals of the existing `lakebase.py` connection-per-operation helpers with attached-resource/OAuth configuration, an SSL connection pool, bounded size, transient retries, and transaction helpers.
- Extract the SQL currently embedded in `research_broker.py` into repositories for users, watchlists, notes, reports, sessions, and tool events while preserving tested behavior.
- Trusted identity adapter derived from Databricks forwarded identity; remove user identity from model-controlled tool parameters.
- Ownership filter on every user-data read, update, and delete.

**Tests:**

- Transaction rollback, pool exhaustion, reconnect, SQL injection, invalid identity, and absent-header tests.
- Two-user isolation suite proves one user cannot read, modify, or delete another user's data.
- Compatibility tests prove existing watchlist, note, and report records remain readable after the repository refactor.

**Exit criterion:** All repository tests and the two-user isolation suite pass.

# Phase 5 — MCP agent tools and semantic research

## Unit 5.1 — FastMCP server shell and observability

**Goal:** Provide a stable, traceable tool service before implementing business tools.

**Implement:**

- Harden the existing FastMCP server and middleware with a health endpoint, trusted request context, correlation IDs, structured logs, safe error envelope, timeouts, and a sanitized trace writer.
- Trace only bounded metadata; exclude tokens, credentials, full note bodies, full reports, and oversized market responses.
- Contract version for each tool response.

**Tests:**

- Tool success, validation failure, dependency failure, timeout, trace failure, and oversized-result tests.
- Verify tracing failures never change tool results and secrets never appear in logs.
- Regression test all nine existing tool registrations and their public names before adding or retiring any tool.

**Exit criterion:** A sample tool call produces a safe response and bounded Lakebase audit event.

## Unit 5.2 — Retrieval tools

**Goal:** Implement evidence retrieval independently of agent orchestration.

**Implement:**

- Refactor the existing `get_stock_performance`, `compare_stocks`, `get_company_research`, `get_watchlist`, and `get_notable_updates` implementations behind the new service/repository boundaries.
- Query Delta gold tables for historical analytics and use Massive only for entitled on-demand end-of-day data through the shared limiter.
- Include source, ticker, requested period, actual period, as-of time, freshness, and limitations.
- Correct known prototype gaps: trim bars to the requested window, bound response sizes, separate sector/industry mapping, and represent news-to-ticker as many-to-many.

**Tests:**

- Known-answer calculations, invalid ticker, partial company data, missing fundamentals, no news, rate-limited API, and stale cache tests.
- Contract tests ensure no tool invents or silently substitutes missing values.

**Exit criterion:** Retrieval tools pass contracts and return evidence-grounded answers for the demonstration tickers.

## Unit 5.3 — Action tools

**Goal:** Satisfy the meaningful-write requirement safely.

**Implement:**

- Retain and harden the existing `update_watchlist`, `save_research_note`, and `save_analysis_report` tools; add `delete_research_note` only if it supports the final workflow.
- Confirmation token or explicit-confirmation field for consequential writes.
- Idempotency key for retries and ownership enforcement from trusted identity.
- Remove model-supplied `user_email` as an authority source while preserving it temporarily only in versioned compatibility adapters if required during migration.

**Tests:**

- Add/remove, duplicate add, repeated retry, invalid action, absent confirmation, rollback, and delete-not-owned tests.
- Two-user end-to-end isolation test through MCP rather than direct repositories.

**Exit criterion:** A confirmed tool call creates or changes one user-owned record exactly once; unauthorized writes fail.

## Unit 5.4 — Embeddings and semantic retrieval

**Goal:** Retrieve relevant filing and news passages with inspectable provenance.

**Implement:**

- Replace duplicate character-window chunking with one section-aware Spark contract: 500-token child passages (650 maximum, 75 overlap), 1,600-token parents, and separate contextual embedding text from faithful retrieval text.
- Enable Change Data Feed and row tracking on the canonical Delta chunk table, then maintain a triggered managed Delta Sync Vector Search index.
- Use `databricks-qwen3-embedding-0-6b` at 1,024 dimensions; retain GTE as a measured fallback and MiniLM only as an evaluation baseline.
- Refactor `semantic_research` for hybrid retrieval, reranking, ticker/source/date filters, bounded top-k, parent expansion, and explicit score/provenance.
- Continue to use structured SEC Company Facts, rather than semantic search, for exact financial values.

**Tests:**

- Chunk-to-index reconciliation, unchanged-content incremental sync, model-version migration, empty index, filtered retrieval, and service failure tests.
- Labeled retrieval set measuring Recall@k, MRR, nDCG, provenance completeness, and filter correctness.
- Regression fixtures verify that the current company/news chunk text remains discoverable after the job refactor.

**Exit criterion:** Retrieval evaluation meets the documented target and every result exposes source provenance.

# Phase 6 — Lakebase CDF and usage analytics

## Unit 6.1 — Lakebase CDF replication

**Goal:** Capture operational inserts, updates, and deletes in Unity Catalog Delta tables.

**Implement:**

- Enable required Postgres replica identity/change capture on watchlist, notes, reports, sessions, and tool-event tables.
- Configure CDF destination tables and document the workspace bootstrap procedure.
- Preserve `_pg_change_type`, timestamp, LSN, transaction ID, and source table.

**Tests:**

- For each selected table, insert, update, and delete a uniquely labeled test record.
- Verify all three events appear in Delta in correct order and measure propagation latency.
- Verify note/report bodies are excluded or masked from analytics destinations where appropriate.

**Exit criterion:** A recorded test demonstrates ordered row-level changes in Delta. If CDF is unavailable, the approved Lakeflow event-table fallback is implemented and documented.

## Unit 6.2 — Silver activity and gold usage metrics

**Goal:** Turn operational changes into safe analytics.

**Implement:**

- Streaming table for normalized Lakebase changes.
- Silver agent activity with stable user pseudonym, session, tool, status, duration, and action type.
- Materialized views for daily active researchers, tool usage/latency, agent error rate, watchlist changes, and research saves.
- Freshness and source fields for every metric.

**Tests:**

- Known event sequences produce known aggregates.
- Insert/update/delete semantics, duplicates, late events, null duration, and masked identity tests.
- End-to-end latency measurement from Lakebase commit to gold metric.

**Exit criterion:** Gold metrics reconcile to a controlled test sequence and expose no user-authored research text.

# Phase 7 — Agent Bricks integration

## Unit 7.1 — Supervisor Agent and MCP connection

**Goal:** Connect the tested tools to the conversational agent.

**Implement:**

- Start from the existing `agent/system_prompt.md`, agent configuration, and demo scenarios; reconcile them with the final versioned MCP contracts.
- Deploy Supervisor Agent instructions, an external MCP connection through the supported Databricks connection mechanism, and accurate tool descriptions.
- Retain and test the existing grounding rules for evidence, as-of dates, missing data, confirmations, and financial-advice limitations.
- Convert the existing example questions into executable evaluations for price, comparison, filing evidence, watchlist mutation, and saved research.

**Tests:**

- Wait for endpoint readiness, then run deterministic evaluation scenarios.
- Verify expected tool selection and parameter alignment.
- Verify write tools are not called without confirmation.
- Verify invalid ticker and unavailable-data answers do not hallucinate.

**Exit criterion:** All evaluation scenarios pass and the trace proves correct tool routing.

## Unit 7.2 — Agent identity propagation

**Goal:** Prove the conversational path preserves authenticated user ownership.

**Implement:**

- Define the trusted identity handoff from Databricks App to Supervisor Agent to MCP server.
- If forwarded user identity is not available across the full chain, implement a short-lived signed internal identity assertion validated by the MCP server; never trust a plain model-supplied email.

**Tests:**

- Two authenticated users invoke the same read/write tools and receive isolated data.
- Tampered, expired, missing, and replayed identity assertions fail safely.

**Exit criterion:** Identity is cryptographically or platform-verifiably bound to every user-scoped tool call.

# Phase 8 — Frontend Databricks App

## Unit 8.1 — Flask app shell and authentication

**Goal:** Deploy a minimal authenticated frontend early.

**Implement:**

- Retain the existing Flask/Gunicorn application, visual styling, templates, and working overview/watchlist routes as the starting shell.
- Replace demo-user fallback and direct connection-secret assumptions with attached `app.yaml` resource references using `valueFrom`, SDK `Config()`, health endpoint, request IDs, and required authenticated identity.
- Extend the current navigation and pages to Research, Watchlist, Saved Research, and Usage Analytics; preserve existing news, notes, reports, and activity views where they still fit.
- Route operational access through authenticated service APIs instead of sharing the Lakebase schema directly between app service principals.

**Tests:**

- Flask route tests, missing identity, health check, security headers, template escaping, and startup configuration tests.
- Deploy smoke test with the app service principal and attached resources.
- Snapshot/DOM regression tests cover the existing overview and watchlist flows before visual changes.

**Exit criterion:** Authenticated user can open the deployed shell and health monitoring reports ready.

## Unit 8.2 — Research and evidence workflow

**Goal:** Deliver the primary user workflow as a vertical slice.

**Implement:**

- Research question input and agent response streaming/status.
- Add company performance and peer comparison views to the existing dashboard rather than creating a second frontend.
- Evidence cards with source, URL, date, ticker, similarity/context label, and as-of time.
- Loading, empty, error, partial, stale, and rate-limited states.

**Tests:**

- Mocked UI/API tests for all required states.
- Browser test: ask a question, observe agent status, inspect evidence, and open a source.
- Accessibility checks for keyboard navigation, labels, focus, and color-independent status.

**Exit criterion:** A deployed user can complete an evidence-grounded company research question without using a separate interface.

## Unit 8.3 — Watchlists, notes, and reports

**Goal:** Expose the action-taking workflow in the frontend.

**Implement:**

- Preserve the existing watchlist list/add/remove workflow; route it through hardened APIs and add note save/delete and report save actions.
- Confirmation interface before writes and clear success/error feedback.
- User-owned saved-research history.

**Tests:**

- Browser tests for add, duplicate add, remove, save, retry, cancel, delete, and permission failure.
- Verify one UI action maps to one idempotent MCP write.
- Regression test confirms the existing add/remove form behavior and persisted watchlist data survive the transition.

**Exit criterion:** A user can research a ticker, add it to a watchlist, save a note, reload, and see the persisted result.

## Unit 8.4 — Usage analytics page

**Goal:** Demonstrate the operational-to-analytical pipeline.

**Implement:**

- KPI context for period, unit, comparison, freshness, and source.
- Tool usage/latency table or chart, error-rate view, active-user metric, and write-activity metric.
- SQL warehouse queries against gold usage tables; no direct analytical scan against Lakebase.

**Tests:**

- Known test sequence renders expected values.
- Loading, no-data, partial-refresh, stale, query-error, and large-result guard tests.
- Freshness matches the latest processed CDF timestamp.

**Exit criterion:** A controlled MCP action appears in the analytics page with correct count and freshness.

# Phase 9 — Deployment, evaluation, and capstone proof

## Unit 9.1 — Complete bundle deployment

**Goal:** Make development and production deployments reproducible.

**Implement:**

- Final DAB resources replace the existing manual deployment steps for the embedding job, MCP app, and frontend app and add the new ingestion job and Spark pipeline.
- Parameterized dev/prod targets, permissions, resource keys, schedules, retries, timeouts, and notifications.
- Separate documented bootstrap for Lakebase project/branch/database, CDF, secrets, and Agent Bricks where automation is unavailable.

**Tests:**

- Strict bundle validation.
- Clean development deployment from a fresh checkout.
- Start pipeline/job/apps and verify status/logs.
- Configuration-diff review between dev and prod.

**Exit criterion:** A fresh operator can deploy the complete dev environment using the runbook without editing source files.

## Unit 9.2 — End-to-end acceptance suite

**Goal:** Prove every capstone requirement in one repeatable suite.

**Implement and test:**

1. Verify more than one million distinct market rows in Silver Delta.
2. Run a Spark transformation and show Bronze/Silver/Gold lineage and quality results.
3. Retrieve Massive and SEC evidence for a company.
4. Ask the agent a grounded price/document question.
5. Perform a confirmed watchlist or research-note write.
6. Verify the record in Lakebase.
7. Verify the change in the Delta CDF history.
8. Verify the corresponding gold usage metric.
9. Verify the frontend displays the saved result and analytics update.

**Exit criterion:** The suite produces a timestamped evidence packet with query results, tool trace IDs, pipeline run IDs, and screenshots.

## Unit 9.3 — Security, recovery, and performance hardening

**Goal:** Demonstrate responsible operation, not only a happy-path demo.

**Implement:**

- Retention/redaction policy, database backup/branch strategy, failed-job recovery, checkpoint replay, and dependency timeout behavior.
- Query bounds, payload limits, connection-pool limits, and application rate limits.
- Operational dashboard/runbook for failures.

**Tests:**

- Cross-user access attempt, forged identity, injection, oversized payload, API outage, Lakebase restart, CDF delay, partial file, and interrupted backfill.
- Measure frontend response time, tool latency, CDF-to-gold latency, and pipeline duration against documented targets.

**Exit criterion:** No critical security issue remains; recovery procedures are demonstrated for at least one ingestion and one database failure.

## Unit 9.4 — Final evaluation, documentation, and demo

**Goal:** Package the implementation for capstone review.

**Implement:**

- README, architecture, data dictionary, API/tool reference, deployment runbook, testing guide, limitations, and cost/rate-limit notes.
- Update the current README/manual setup guidance so it points to the reproducible bundle workflow; retain useful troubleshooting and demo material after verifying it.
- Agent evaluation results and retrieval-quality sample.
- Five-to-ten-minute demo script with preflight checks and fallback screenshots.
- Requirement traceability matrix linking each rubric item to code, test, and demonstration evidence.

**Tests:**

- A person other than the implementer follows the setup and demo runbook.
- Link, command, configuration, and screenshot verification.

**Exit criterion:** Every rubric requirement has an implementation artifact, passing test, and demonstration step.

# Recommended milestone sequence

| Milestone | Units | Demonstrable outcome |
|---|---|---|
| M1 — Baseline and feasibility | 0.1–0.4 | Existing behavior captured; reuse decisions documented; workspace, Massive free tier, SEC, app, pipeline, and CDF assumptions verified |
| M2 — Big Data proof | 1.1–2.4 | Rate-safe ingestion and more than one million processed market rows |
| M3 — Variety pipeline | 3.1–3.3 | SEC facts and unstructured filing chunks in governed tables |
| M4 — Operational core | 4.1–5.4 | Secure Lakebase model plus tested retrieval, action, and semantic tools |
| M5 — Analytics | 6.1–6.2 | Lakebase changes transformed into gold usage metrics |
| M6 — Agent and UI | 7.1–8.4 | Authenticated end-to-end research and write workflow in a Databricks App |
| M7 — Release | 9.1–9.4 | Repeatable deployment, acceptance evidence, hardening, and final demo |

# Requirement traceability

| Capstone requirement | Primary implementation units | Proof |
|---|---|---|
| Spark data pipeline | 2.1–2.4, 3.2–3.3 | Lakeflow run, lineage, expectations, and row reconciliation |
| Third-party API | 0.4, 1.1–1.3, 3.1 | Massive and SEC contract/integration evidence |
| Lakebase data model | 4.1–4.3 | Migrations, data dictionary, CRUD and isolation tests |
| Action-taking AI agent | 5.1–5.3, 7.1–7.2 | Grounded retrieval plus confirmed persistent write |
| Analytics pipeline | 6.1–6.2 | Lakebase change appears in Delta and gold metric |
| Frontend | 8.1–8.4 | Browser acceptance workflow |
| Deployed application | 9.1–9.2 | Running Databricks App URL and deployment evidence |
| Volume | 2.4 | More than one million distinct market rows |
| Variety | 3.1–3.3 | Structured, JSON, and unstructured content processed |

# Recommended execution discipline

- Implement one numbered unit per pull request whenever practical.
- Refactor only after characterization tests capture the behavior being retained; do not perform a wholesale rewrite of working modules.
- Keep database changes forward-only and test upgrades from the repository's current `schema.sql` with preserved data.
- Do not start the full backfill until the 10-date pilot and rate-limit tests pass.
- Do not expose write tools until identity isolation tests pass.
- Do not build analytics UI against provisional SQL; freeze and test gold contracts first.
- Deploy thin app shells early so service-principal ownership and resource permissions fail early rather than at the end.
- Keep recorded external API fixtures small and scrubbed of credentials.
- Save capstone evidence continuously instead of reconstructing it during the final week.

# Existing-code completion map

This map prevents “already present” from being confused with “capstone complete.”

| Current capability | First unit that modifies it | Unit that proves it complete |
|---|---:|---:|
| Massive REST client | 1.1 | 2.4 for rate-safe million-row ingestion |
| Price/research/comparison broker logic | 5.2 | 9.2 for grounded end-to-end retrieval |
| Watchlist/note/report writes | 4.2–5.3 | 9.2 for identity-bound action plus analytics propagation |
| Postgres/Lakebase schema | 4.1–4.3 | 6.1 and 9.2 for secure CRUD and CDF |
| FastMCP server and traces | 5.1–5.3 | 7.1–7.2 for agent routing and identity |
| Embedding script and semantic search | 5.4 | 9.2 for evidence retrieval with provenance |
| Flask dashboard | 8.1–8.4 | 9.2 for deployed core workflow |
| Prompt/config/demo assets | 7.1 | 9.2 and 9.4 for evaluated, deployable agent |
| Manual app manifests/setup | 0.3 and 9.1 | 9.1 for clean reproducible deployment |
| Spark, SEC, CDF analytics, volume proof | New in 1.3–3.3 and 6.1–6.2 | 9.2 for integrated capstone evidence |
