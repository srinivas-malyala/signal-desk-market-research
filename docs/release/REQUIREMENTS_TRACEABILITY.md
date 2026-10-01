# Capstone Requirements Traceability

Updated: 2026-10-01

Status vocabulary: **workspace verified** means evidence exists in the target
workspace; **deployed accepted** means the relevant live workflow and its
deterministic checks pass; **deferred by owner** identifies an intentionally
unperformed change rather than a release failure.

| Required component | Implementation evidence | Verification evidence | Current status / remaining proof |
|---|---|---|---|
| Spark data pipeline | Separate market and research Lakeflow Spark Declarative Pipelines normalize Massive, SEC, article, and document data into Bronze/Silver/Gold tables. | Market update reconciled 1,255,677 Bronze rows to 1,255,489 Silver keys + 188 quarantines; research update reconciled 2 companies, 12 filings, 57,806 facts, 86 articles, 549 links, and 507 traceable chunks. | Workspace verified. |
| Third-party API | Massive Stocks REST plus SEC EDGAR/data.sec.gov with secret/contact handling, immutable landing, rate controls, retries, and caching. | Live cross-host acceptance produced four Render MCP plus one Job attempt, exactly five Lakebase ledger rows, a maximum rolling count of four, and a 60.225-second wait for attempt five; SEC/article cached rerun made zero external calls. | Workspace and deployed shared-quota workflow verified. |
| Lakebase data model | Shared schema `bootcamp_students`, allowlisted `_srini` operational tables, checksum migrations, pooling, ownership-scoped SQL, idempotent writes, and CDC replica identity. | PostgreSQL 17+, all 16 tables owned by the connected role, five idempotent migrations, shared quota ledger, and deployed two-real-principal UI isolation plus exact cleanup. | Workspace and deployed action isolation verified for the capstone. |
| Action-taking AI agent | MCP 1.0 exposes six retrieval and three confirmed write tools; Agent prompt/config has ten executable evaluation fixtures. | Deployed actions pass confirmation, exact replay, changed-payload rejection, ownership isolation, cleanup, and bounded audit; the governed Supervisor evaluation passes 10/10. | Deployed accepted. |
| Analytics pipeline | Lakehouse Sync histories feed normalized Bronze CDC, privacy-safe deduplicated Silver activity, and five Gold metric families. | Five histories are enabled/queryable; a self-cleaning 18-event sequence reconciled 34 Bronze and 26 effective Silver rows to exact Gold metrics with maximum reported source latency of 85 seconds. | Workspace verified. |
| Frontend | Existing Flask/Gunicorn app is retained; trusted identity, fail-closed routes, request IDs, security headers, fresh per-session assertions, and bounded MCP/warehouse clients are implemented. | All five Gold reads and controlled 32.34-second CDC refresh passed through the authenticated UI; two permitted Google principals proved isolated watchlists, notes, reports, and traces. | Deployed accepted under the owner-approved shared M2M principal. |
| Deployed application | FastMCP and Flask are deployed as two Render web services; governed processing remains in Databricks; Lakebase serves market/operational state while AI Search serves accepted semantic research. | Public health, market and semantic reads, reversible/idempotent actions, cross-host quota, Gold analytics, CDC freshness, two-principal isolation, READY Supervisor, and 10/10 evaluation pass. | Free-tier release checkpoint accepted; paid upgrade deferred by owner. |
| Two Big Data Vs | **Volume:** market dataset exceeds 1M unique rows. **Variety:** structured OHLCV/XBRL, semi-structured JSON, and unstructured filing/news text. | 1,255,489 unique Silver market keys; filing/article document pipeline and 393-row searchable canonical corpus verified. | Workspace verified for Volume and Variety. High velocity is not required; CDC latency will be measured but not used as a completion claim yet. |

## Proposal deliverables

| Deliverable | Artifact | Status |
|---|---|---|
| Data-source and technology integration writeup | `proposal/CAPSTONE_PROPOSAL.md` | Complete and aligned to a brand-new implementation narrative. |
| Architecture diagram | `proposal/signal-desk-capstone-architecture.png` and SVG source | Complete; re-exported at 1800×1120 and visually verified on 2026-10-01 after the shared-principal decision. |

Detailed phase evidence and external gates are maintained in
`docs/IMPLEMENTATION_STATUS.md`; this matrix is the concise submission map.
