# Capstone Implementation Status

Updated: 2026-09-10

This is the living tracker for implementation progress and external gates. A unit is complete only when its code and deterministic tests pass; workspace-dependent proof is listed separately.

| Phase | Status | Completed | Pending or external gate |
|---|---|---|---|
| 0 — Foundation | Substantially complete | Architecture/contracts, quality tooling, bundle, Unity Catalog and warehouse validation, Massive and SEC feasibility; first selective development deployment completed | Lakebase live CRUD/CDF check |
| 1 — Massive ingestion | Deployed; workspace pilot pending | 1.1 rate-safe client; 1.2 atomic checkpoints; 1.3 immutable landing; two-date live local pilot landed 33,186 rows and reran with zero API calls; managed Volume and ingestion job deployed selectively | Run the workspace pilot; validate Volume locks/atomic replace; cross-host limiter coordination after Lakebase access |
| 2 — Spark market pipeline | Implemented locally; workspace proof pending | Auto Loader Bronze + manifests; deterministic Silver + quarantine; Gold performance, broad-market peer, and coverage datasets; rate-attempt ledger; orchestrated measured certification | Deploy/run pipeline; reconcile 10-date pilot; execute bounded backfill; persist passing >1M-row certification; add sector/industry enrichment after Phase 3 reference data |
| 3 — SEC pipeline | Implemented locally; workspace proof pending | Identified/rate-limited SEC client; immutable submissions, Company Facts, and selected filings; dynamic XBRL normalization; company/filing/article relationships; HTML section extraction; deterministic chunks; Gold research catalog | Provision `sec/user-agent`; deploy and run two-company refresh; inspect pipeline expectations and reconciliation; retain live evidence |
| 4 — Lakebase | Blocked externally | Provisional student DSN and `student_sri` schema contract | Usable password, CRUD proof, versioned migrations, pooling, and identity isolation |
| 5 — MCP agent tools | Prototype available | Existing retrieval/write tools characterized | Production contracts, safe traces, confirmation, repository boundaries, and semantic retrieval |
| 6 — CDF analytics | Pending | Architecture selected | Lakebase change feed, Silver activity, and Gold usage metrics |
| 7 — Agent integration | Prototype assets available | Prompt and configuration inventoried | Deployed supervisor, MCP connection, evaluation, and identity propagation |
| 8 — Frontend | Prototype available | Existing Flask routes and core writes characterized | Authenticated research workflow, evidence UX, analytics page, and production states |
| 9 — Release | Pending | Strict development bundle validation | Deployment, end-to-end acceptance, security/performance proof, documentation, and demo |

## Active sequence

1. Run and reconcile the deployed Phase 1 two-date idempotency pilot.
2. Split the shared pipeline resource into independently deployable market and research pipelines.
3. Deploy and test the Phase 2 market pipeline, then execute the bounded market-volume certification.
4. Provision the approved SEC identifying contact as runtime secret `sec/user-agent` without committing it.
5. Deploy and run the Phase 3 two-company research refresh and inspect SEC/chunk reconciliation datasets.
6. Finalize cross-host rate coordination before enabling interactive Massive traffic.

## Current external inputs

- Databricks profile: `dataexpertio_srini` — verified.
- Unity Catalog: `bootcamp_students.student_sri` — verified.
- SQL warehouse: `b15d3d6f837ba428` — verified serverless access.
- Massive key: Databricks secret `massive/api-key` — verified without disclosure.
- SEC identifying contact — verified live and retained only at runtime.
- Lakebase: approved provisional host/role/database/schema contract; usable password pending.

## Workspace deployment evidence

- 2026-09-10 — Selectively deployed managed Volume `bootcamp_students.student_sri.signal_desk_raw` and development job `market_ingestion` (job ID `591105044211834`).
- 2026-09-10 — First workspace pilot run `998731877059605` failed before any API request because the serverless Python task did not define `__file__`; runtime entry-point compatibility is being corrected before the pilot is retried.
- 2026-09-10 — Corrected all Spark Python entry points to support the Databricks-provided `filename` runtime and added a regression check; 40 Phase 1/configuration tests and lint pass locally.
- Lakebase-dependent applications and `research_embeddings`, plus all Phase 2/3 jobs and pipelines, remained undeployed at this milestone.
