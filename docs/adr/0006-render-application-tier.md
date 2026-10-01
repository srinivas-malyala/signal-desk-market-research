# ADR 0006: Render application tier and paid Databricks data plane

- Status: Accepted
- Date: 2026-09-24

Amended by ADR 0007 on 2026-09-29 for the staged Lakebase serving cutover.
Amended by owner decision on 2026-10-01: both Render services use
`dbx-ai-de-aug26`; no split-identity follow-up is tracked, and the paid Render
upgrade is deferred.

## Context

The selected paid Databricks workspace can run the capstone's jobs, pipelines,
Unity Catalog, SQL Warehouse, AI Search, Lakebase analytics, and Supervisor, but
budget policy does not allow it to host Databricks Apps. Free Edition was
considered for the two Python services, but cross-workspace identity and app
resource limitations make Render the lower-risk, lower-cost host.

## Decision

Deploy Flask and FastMCP as separate Render Python web services. Use Render Free
for the current acceptance and demo-readiness checkpoint; upgrade only after a
separate owner authorization. Keep all data and processing in the workspace selected explicitly by
`dataexpertio_srini`; Render stores no analytical copy.

Browser users authenticate to Flask through OIDC. Flask sends 60-second,
request-bound signed assertions to FastMCP. The Supervisor uses a separate
fixed machine credential. Flask and FastMCP use the owner-approved shared
workspace principal `dbx-ai-de-aug26` for bounded Databricks access. FastMCP moves to a
dedicated native Lakebase role and atomically published `_srini` serving tables
under ADR 0007.

The Databricks bundle manages only data-plane resources. `render.yaml` manages
the application tier and uses hash-pinned Linux/Python 3.11 dependency locks,
explicit secret placeholders, `$PORT` start commands, and health checks.

## Consequences

- Application deployment no longer depends on paid-workspace Databricks Apps
  entitlement or administrator-owned app secret bindings.
- A Lakebase runtime role, one shared workspace identity, one OIDC client, an
  assertion key pair, and a Supervisor credential must be provisioned before
  final live acceptance.
- Render Free cold starts require MCP-first/frontend-second warm-up before a
  live demo; no paid-tier claim is made.
- Clean-install and exact-command process checks can run locally and in CI
  without production credentials; end-to-end identity, data, and latency proof
  still requires deployed services.
