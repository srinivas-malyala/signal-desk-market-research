# Capstone Requirements Traceability

Updated: 2026-09-21

Status vocabulary: **workspace verified** means evidence exists in the target
workspace; **local accepted** means deterministic implementation tests pass but
the deployment-dependent proof is outstanding; **blocked externally** names an
admin/UI prerequisite rather than claiming completion.

| Required component | Implementation evidence | Verification evidence | Current status / remaining proof |
|---|---|---|---|
| Spark data pipeline | Separate market and research Lakeflow Spark Declarative Pipelines normalize Massive, SEC, article, and document data into Bronze/Silver/Gold tables. | Market update reconciled 1,255,677 Bronze rows to 1,255,489 Silver keys + 188 quarantines; research update reconciled 2 companies, 12 filings, 57,806 facts, 86 articles, 549 links, and 507 traceable chunks. | Workspace verified. |
| Third-party API | Massive Stocks REST plus SEC EDGAR/data.sec.gov with secret/contact handling, immutable landing, rate controls, retries, and caching. | Massive volume run stayed at measured maximum four attempts per rolling minute; SEC/article cached rerun made zero external calls. | Workspace verified; Lakebase cross-host limiter migration/live concurrency proof remains before interactive traffic. |
| Lakebase data model | Shared schema `bootcamp_students`, allowlisted `_srini` operational tables, checksum migrations, pooling, ownership-scoped SQL, idempotent writes, and CDC replica identity. | PostgreSQL 17+, all 16 tables owned by the connected role, five idempotent migrations, quota-ledger table/index, and two-user isolation verified in workspace. | Workspace verified; simultaneous Job/MCP quota acceptance remains part of the third-party API deployment proof. |
| Action-taking AI agent | MCP 1.0 exposes six retrieval and three confirmed write tools; Agent prompt/config has ten executable evaluation fixtures. | Local action tests cover confirmation, idempotency, rollback, ownership, bounded audit and forbidden writes; deterministic Phase 7 trace evaluator passes fixture validation. | Local accepted; MCP/UC connection/Supervisor deployment and live captured-trace evaluation blocked by admin MCP deployment tasks. |
| Analytics pipeline | Lakehouse Sync histories feed normalized Bronze CDC, privacy-safe deduplicated Silver activity, and five Gold metric families. | Synthetic insert/update/delete/preimage/duplicate/late/null/error/privacy sequence reconciles known aggregates. | Phase 6.2 local accepted; UI-only Lakehouse Sync, pipeline deployment, controlled live change, and latency measurement pending. |
| Frontend | Existing Flask/Gunicorn app is retained; trusted identity, fail-closed routes, request IDs, security headers, and a bounded MCP client are implemented. | Route/client/security tests pass without demo identity or forged forwarded headers. | Local hardening accepted; frontend and MCP bindings/deployment plus research/evidence/actions/analytics UI remain. |
| Deployed application | Bundle defines separate frontend and MCP Databricks Apps and their least-privilege resources. | OAuth was renewed and strict development bundle validation passed on 2026-09-21; the earlier failed MCP creation left no partial app. | Blocked externally: admin secret-resource binding/management, then MCP and frontend deployment acceptance. |
| Two Big Data Vs | **Volume:** market dataset exceeds 1M unique rows. **Variety:** structured OHLCV/XBRL, semi-structured JSON, and unstructured filing/news text. | 1,255,489 unique Silver market keys; filing/article document pipeline and 393-row searchable canonical corpus verified. | Workspace verified for Volume and Variety. High velocity is not required; CDC latency will be measured but not used as a completion claim yet. |

## Proposal deliverables

| Deliverable | Artifact | Status |
|---|---|---|
| Data-source and technology integration writeup | `proposal/CAPSTONE_PROPOSAL.md` | Complete and aligned to a brand-new implementation narrative. |
| Architecture diagram | `proposal/signal-desk-capstone-architecture.png` and SVG source | Complete; re-export if the architecture source changes before submission. |

Detailed phase evidence and external gates are maintained in
`docs/IMPLEMENTATION_STATUS.md`; this matrix is the concise submission map.
