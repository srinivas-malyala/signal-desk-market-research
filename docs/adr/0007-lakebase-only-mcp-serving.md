# ADR 0007: Lakebase-only MCP runtime serving

Status: Accepted for staged implementation

Date: 2026-09-29

## Context

The Render FastMCP service already reaches Lakebase directly and uses it for
operational state, idempotency, audit events, and cross-host Massive quota
coordination. Historical market retrieval and managed research search still use
a paid-workspace OAuth M2M client. That client currently fails with
`invalid_client`, and provisioning or repairing it is waiting on a workspace
administrator.

The application needs a route that permits implementation and acceptance to
continue without replacing the governed Databricks data-processing plane or
discarding the accepted AI Search baseline.

## Decision

Adopt an incremental Lakebase-only runtime serving path for MCP:

- publish narrow curated Delta serving tables from the accepted pipelines;
- use an atomic, manually triggered direct publisher to create PostgreSQL
  serving copies in shared schema `bootcamp_students`, with every persistent
  target ending in `_srini`;
- query historical market data directly through the existing Lakebase pool;
- evaluate PostgreSQL full-text retrieval over synchronized research documents;
- retain AI Search until the full 51-case retrieval suite proves that a
  Lakebase backend meets the existing quality thresholds; and
- remove MCP workspace credentials only after all nine tools pass deployed
  acceptance with the Lakebase backends.

Backend feature flags and suffix-isolated serving tables make the change reversible.
The SQL Warehouse and AI Search resources remain intact as rollback paths during
the observation period.

## Consequences

Positive:

- MCP request handling no longer needs a workspace OAuth token after cutover.
- The already working Lakebase security, pooling, audit, and quota boundary is
  reused.
- Serving queries become low-latency indexed PostgreSQL lookups.
- The change can be accepted and rolled back one capability at a time.

Negative:

- Curated data exists in both Delta and Lakebase, with measurable synchronization
  lag and additional serving-resource cost.
- PostgreSQL full-text search is not equivalent to Qwen3 hybrid AI Search.
- The direct publisher streams 1.25 million market rows through one job-driver
  connection; its duration and source freshness must be measured before any
  schedule is enabled.
- Frontend Gold analytics retains a Databricks credential dependency. The owner
  accepted sharing `dbx-ai-de-aug26` with MCP on 2026-10-01, so no credential-
  split follow-up is tracked.

## Rejected alternatives

- Lakebase Data API: it requires Databricks OAuth bearer tokens and therefore
  does not eliminate the blocking runtime identity.
- Personal access or user OAuth tokens in Render: unsuitable for durable
  production machine authentication.
- Immediate restoration of MiniLM/pgvector: potentially viable, but it reverses
  the accepted managed-search design and adds Render memory/cold-start risk.
- Massive-only retrieval: removes governed historical and attributable research
  guarantees.
- Immediate deletion of SQL/AI Search resources: removes the safest rollback
  before Lakebase parity is proved.
- Managed Lakebase synced tables in the shared project: no Lakebase UC catalog
  is registered and the selected identity lacks the necessary project-level
  permission. The direct publisher uses existing PostgreSQL privileges and
  session-local staging instead.

The serving path does not alter either classroom sync direction. PostgreSQL
`bootcamp_students` still publishes history into UC
`bootcamp_students.bootcamp_cdc`, where the activity pipeline reads only five
allowlisted `_srini` histories. UC-to-Lakebase graph tables still use PostgreSQL
schema `bootcamp_cdc` and `_srini` names.

## Execution

The authoritative gates, acceptance criteria, rollback, and permission
discovery steps are in `docs/LAKEBASE_ONLY_MCP_SERVING_PLAN.md`.

On 2026-09-29 the direct publisher populated 1,255,489 market rows and 393
research rows with zero duplicate keys, and a three-row AAPL parity sample
matched UC exactly. The 51-case Lakebase FTS evaluation did not pass promotion:
Recall@5 was 0.7843 against the 0.85 minimum (MRR and nDCG@5 were 0.7843, with
zero provenance and filter failures). Therefore this ADR currently authorizes
Lakebase market canary work but does not authorize research cutover or removal
of the MCP workspace credential; AI Search remains active.
