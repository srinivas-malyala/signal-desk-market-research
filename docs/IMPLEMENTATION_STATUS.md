# Capstone Implementation Status

Updated: 2026-09-11

This is the living tracker for implementation progress and external gates. A unit is complete only when its code and deterministic tests pass; workspace-dependent proof is listed separately.

| Phase | Status | Completed | Pending or external gate |
|---|---|---|---|
| 0 — Foundation | Substantially complete | Architecture/contracts, quality tooling, bundle, Unity Catalog and warehouse validation, Massive and SEC feasibility; first selective development deployment completed | Lakebase live CRUD/CDF check |
| 1 — Massive ingestion | Workspace pilot complete | 1.1 rate-safe client; 1.2 atomic checkpoints; 1.3 immutable landing; managed Volume and ingestion job deployed; 10-date workspace pilot reconciled 149,051 rows and identical rerun made zero API calls | Cross-host limiter coordination after Lakebase access |
| 2 — Spark market pipeline | Workspace acceptance complete | Dedicated deployed market pipeline; 81 manifest dates and 1,255,677 Bronze rows reconcile to 1,255,489 unique Silver rows plus 188 deterministic quarantines; measured free-plan maximum is 4 attempts per rolling minute; Gold coverage and persisted certification passed | None for the volume-certification workflow |
| 3 — SEC pipeline | Workspace acceptance complete | Dedicated deployed research pipeline; two-company landing and cached rerun completed; 2 companies, 12 filings, 57,806 facts, 86 articles, 549 article/ticker links, and 507 traceable chunks with zero integrity violations; cached rerun made no external calls | None for the bounded two-company workflow |
| 4 — Lakebase | Local implementation complete; workspace proof pending | Admin-managed secret verified; all runtime SQL uses strict `_srini` table registry; checksum-protected migrations, CDC replica identity, bounded stale-safe pools, rollback behavior, and app secret resources validate locally | Verify live permissions, apply migrations, run CRUD, and prove isolation |
| 5 — MCP agent tools | Prototype available | Existing retrieval/write tools characterized | Production contracts, safe traces, confirmation, repository boundaries, and semantic retrieval |
| 6 — CDF analytics | Pending | Architecture selected | Lakebase change feed, Silver activity, and Gold usage metrics |
| 7 — Agent integration | Prototype assets available | Prompt and configuration inventoried | Deployed supervisor, MCP connection, evaluation, and identity propagation |
| 8 — Frontend | Prototype available | Existing Flask routes and core writes characterized | Authenticated research workflow, evidence UX, analytics page, and production states |
| 9 — Release | Pending | Strict development bundle validation | Deployment, end-to-end acceptance, security/performance proof, documentation, and demo |

## Active sequence

1. Refactor Phase 4 operational SQL and migrations for bootcamp_students.<table>_srini.
2. Verify Lakebase connectivity, schema/table permissions, and disposable CRUD through the admin-managed secret.
3. Implement CDF replication into bootcamp_cdc and resume agent/frontend integration.
4. Finalize cross-host rate coordination before enabling interactive Massive traffic.

## Current external inputs

- Databricks profile: `dataexpertio_srini` — verified.
- Unity Catalog: `bootcamp_students.student_sri` — verified.
- SQL warehouse: `b15d3d6f837ba428` — verified serverless access.
- Massive key: Databricks secret `massive/api-key` — verified without disclosure.
- SEC identifying contact — verified live and retained only at runtime.
- Lakebase: database/lakebase-url secret is provisioned and key-only verified; shared schema bootcamp_students, table suffix _srini, and graph schema bootcamp_cdc are confirmed.

## Workspace deployment evidence

- 2026-09-10 — Selectively deployed managed Volume `bootcamp_students.student_sri.signal_desk_raw` and development job `market_ingestion` (job ID `591105044211834`).
- 2026-09-10 — First workspace pilot run `998731877059605` failed before any API request because the serverless Python task did not define `__file__`; runtime entry-point compatibility is being corrected before the pilot is retried.
- 2026-09-10 — Corrected all Spark Python entry points to support the Databricks-provided `filename` runtime and added a regression check; 40 Phase 1/configuration tests and lint pass locally.
- 2026-09-10 — Replaced in-place limiter state mutation and JSONL append with a separate lock, atomic state replacement, and immutable per-acquisition audit files compatible with UC Volumes. Certification retains the first legacy audit event; 44 affected tests and lint pass.
- 2026-09-10 — Redeployed only `jobs.market_ingestion` with the Volume-safe limiter; the already-created managed Volume was left intact.
- 2026-09-10 — Retry run `281427550011155` proved secret access and immutable landing for 2026-09-08 (16,710 rows from one call), then exposed an `OSError` when the limiter attempted a second mutation of its Volume-hosted state/audit files. Job retries consumed zero further API calls. The limiter is being converted to atomic state replacement plus immutable per-attempt audit objects.
- 2026-09-10 — Redeployed the corrected `market_ingestion` job selectively; the managed Volume was preserved.
- 2026-09-10 — Workspace run `335002703842351` passed the full 10-date pilot: 149,051 available rows, nine data dates, one no-data date, no retries, and no failures. It skipped two prior checkpoints and landed the remaining 115,865 rows with eight calls.
- 2026-09-10 — Removed `SystemExit(0)` from successful Spark Python entry-point execution while retaining nonzero failure exits; 44 affected tests and lint pass. This prevents successful notebook-style tasks from being reported as internal errors.
- 2026-09-10 — Explicitly redeployed the finalized `market_ingestion` job; no other bundle resource changed.
- 2026-09-10 — Idempotency run `809484306892540` succeeded with 149,051 available rows, all 10 dates skipped, and zero API attempts, bytes, retries, or failures.
- 2026-09-10 — Split the catch-all Spark resource into explicit `market_pipeline` and `research_pipeline` graphs. Market-volume orchestration now references only `market_pipeline`; 33 focused tests, lint, and strict development bundle validation pass.
- 2026-09-10 — The first selective `market_pipeline` deployment was rejected before creation because this workspace API disallows single-asterisk library globs. The resources are being converted to explicit per-file entries; no pipeline or table was created by the failed request.
- 2026-09-10 — Replaced wildcard groups with explicit per-file pipeline libraries and selectively deployed `market_pipeline` as pipeline ID `6d6d9a79-3b5d-4fca-af6d-61765d0aae60`. The research pipeline and Lakebase-dependent resources remained undeployed.
- 2026-09-10 — First update `dcb6b56c-1b58-49a1-be6c-fb5520187f9a` failed during flow analysis before table writes because Massive fields `T` (ticker) and `t` (timestamp) are distinct but Spark resolved them case-insensitively. The market pipeline must enable case-sensitive field resolution to preserve both source values.
- 2026-09-10 — Enabled `spark.sql.caseSensitive` for the market pipeline only, preserving both Massive fields; 19 Phase 2 configuration/source/analytics tests and lint pass.
- 2026-09-10 — Redeployed `market_pipeline` with the field-resolution correction; no Phase 3 or Lakebase-dependent resource was deployed.
- 2026-09-10 — Update `a84ba60e-92cf-4d97-8d98-6b244432c706` completed all nine flows and reconciled 149,051 manifest/Bronze rows, but quarantined all rows as `schema_rescued`. Warehouse inspection isolated the rescued value to the omitted top-level Massive `count` field; the Bronze response schema now captures it.
- 2026-09-10 — The Massive envelope schema correction passes 20 Phase 2 source/configuration/analytics tests and lint.
- 2026-09-10 — Deployed the corrected market pipeline. Reprocessing the 10-date development tables now requires an explicitly approved full refresh because Auto Loader has already checkpointed those files.
- 2026-09-10 — With explicit approval, full-refresh update `ca1bbd17-bab5-40d8-a05b-6bf248d03f15` rebuilt only the development `market_pipeline` tables and reached `COMPLETED`; immutable Volume files were not changed.
- 2026-09-10 — Warehouse verification passed: 10 `MATCH` dates and 149,051 manifest/Bronze rows; 149,031 unique Silver rows plus 20 `duplicate_ticker_date` quarantines; zero duplicate Silver keys; 10 `COMPLETE` Gold coverage dates from 2026-08-27 through 2026-09-09; bounded Gold performance query succeeded.
- 2026-09-10 — Created the Databricks-backed `sec` secret scope for the approved SEC identifying contact; the contact value remains uncommitted.
- 2026-09-10 — Provisioned and key-only verified `sec/user-agent`; the secret value was not read back or written to repository files.
- 2026-09-10 — Phase 3 pre-deployment gate passed: 34 SEC/article/document/configuration tests and lint succeeded locally.
- 2026-09-10 — Selectively deployed Phase 3: SEC job `380855220996785`, article job `129689732201837`, research pipeline `82ec186f-f38e-4ebe-b121-0b1faeea946d`, and refresh job `321391048242098`. Both applications and `research_embeddings` remained undeployed.
- 2026-09-10 — Two-company Phase 3 orchestrator run `562225890540150` reached `TERMINATED SUCCESS`; sanitized child metrics and pipeline reconciliation are being retained as the remaining acceptance evidence.
- 2026-09-10 — Run `562225890540150` landed 2 submissions, 2 Company Facts snapshots, 12 filing documents, and 100 article query results using 16 SEC and 2 Massive attempts with zero retries/failures. Research update `e8dac8a4-a967-4aff-948e-f4fa5d7af170` completed.
- 2026-09-10 — Warehouse reconciliation passed: 2 companies, 12 unique filings, 57,806 unique facts, zero orphan CIKs, 507 chunks across 98 sources, zero duplicate/untraceable chunks, 86 distinct articles, 549 article/ticker links, and bounded industry/Gold queries succeeded.
- 2026-09-10 — Phase 3 cache/idempotency orchestrator run `892606879283451` reached `TERMINATED SUCCESS`. Article task run `1114483094003228` reused 2 cached queries with zero API calls/HTTP attempts; SEC task run `57407285384248` reused 4 structured requests and 12 filing documents with zero HTTP attempts. Incremental research update `fcff5d1b-fced-48c5-9d32-1e4be504bdbd` completed.
- 2026-09-10 — Strict bundle validation passed and the Lakebase-independent `market_volume_backfill` orchestration was selectively deployed as job `356134100996112`; its default bounds are 252 dates and a 1.1M raw-row stop target.
- 2026-09-10 — Bounded >1M-row certification run `748482763142265` started with the default limits.
- 2026-09-10 — The landing stage completed successfully: 71 API dates produced 1,106,626 newly available raw rows and 116,806,780 landed bytes, with 2 no-data dates, zero retries, and zero failures. The managed Volume now contains 81 market-date partitions including the earlier pilot.
- 2026-09-10 — Market pipeline update a854185a-a1c8-4edc-b887-115998831964 completed incrementally. Orchestrator run 748482763142265 and all three tasks reached TERMINATED SUCCESS.
- 2026-09-10 — Persisted certification status is PASSED: 1,255,677 manifest/Bronze rows reconcile to 1,255,489 distinct Silver keys plus 188 quarantined rows; zero duplicate Silver keys; 81 dates from 2025-09-23 through 2026-09-09; 83 audited API attempts with an observed maximum of 4 in any rolling minute. Independent warehouse statement 01f1ad75-a4ec-18b6-b06a-f495785e1152 confirmed the layer counts.
- 2026-09-11 — Admin-managed Lakebase secret database/lakebase-url was key-only verified without reading its value. Phase 4 now targets shared schema bootcamp_students with all application tables suffixed _srini; CDF-synced graph tables use bootcamp_cdc and the same suffix. Existing private-schema SQL must be refactored before deployment.
- 2026-09-11 — Phase 4 namespace/migration unit passed 14 focused tests and lint: strict table/index allowlists, `_srini` qualification, three checksum-protected migrations, shared-schema validation without schema DDL, secret decoding, bounded pooling, rollback, and explicit pool shutdown are implemented.
- 2026-09-11 — Refactored all Flask, MCP broker, trace, and embedding SQL through the allowlisted `_srini` table registry; removed obsolete unversioned `schema.sql`; added stale-connection replacement and rollback tests. Forty-one focused tests and lint pass, and bundle validation confirms both apps receive the admin-managed Lakebase secret resource.
- Lakebase-dependent applications and `research_embeddings` remain undeployed.
