# ADR 0006: Render application tier and paid Databricks data plane

- Status: Accepted
- Date: 2026-09-24

Amended by ADR 0007 on 2026-09-29: the MCP's Databricks OAuth M2M runtime
identity is replaced through a staged Lakebase-only serving cutover. The
frontend analytics identity remains a separate concern.

## Context

The selected paid Databricks workspace can run the capstone's jobs, pipelines,
Unity Catalog, SQL Warehouse, AI Search, Lakebase analytics, and Supervisor, but
budget policy does not allow it to host Databricks Apps. Free Edition was
considered for the two Python services, but cross-workspace identity and app
resource limitations make Render the lower-risk, lower-cost host.

## Decision

Deploy Flask and FastMCP as separate Render Python web services. Use Render Free
for development and the smallest paid tier for final acceptance and the demo
month. Keep all data and processing in the workspace selected explicitly by
`dataexpertio_srini`; Render stores no analytical copy.

Browser users authenticate to Flask through OIDC. Flask sends 60-second,
request-bound signed assertions to FastMCP. The Supervisor uses a separate
fixed machine credential. Flask retains a separate least-privilege Databricks
identity for Gold analytics until a follow-on decision. FastMCP moves to a
dedicated native Lakebase role and atomically published `_srini` serving tables
under ADR 0007.

The Databricks bundle manages only data-plane resources. `render.yaml` manages
the application tier and uses hash-pinned Linux/Python 3.11 dependency locks,
explicit secret placeholders, `$PORT` start commands, and health checks.

## Consequences

- Application deployment no longer depends on paid-workspace Databricks Apps
  entitlement or administrator-owned app secret bindings.
- A Lakebase runtime role, one frontend analytics identity, one OIDC client, an
  assertion key pair, and a Supervisor credential must be provisioned before
  final live acceptance.
- Render Free cold starts are acceptable for development but not final demo
  acceptance; both services are temporarily upgraded for that window.
- Clean-install and exact-command process checks can run locally and in CI
  without production credentials; end-to-end identity, data, and latency proof
  still requires deployed services.
