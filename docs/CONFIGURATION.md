# Configuration Contract

Configuration names are stable contracts. Credentials and sensitive resource identifiers must not be committed; approved non-secret development namespaces are recorded explicitly.

## Deployment topology

As of 2026-09-24, `dataexpertio_srini` remains the data workspace for all jobs,
pipelines, Unity Catalog data, SQL Warehouse queries, AI Search, Lakehouse Sync,
analytics, and Supervisor processing. Only the FastMCP and Flask runtimes will
be deployed with `Srini Free Edition`.

The split is planned but not yet implemented. App resources are workspace-local,
and a Free Edition forwarded user token cannot authorize paid-workspace SQL or
AI Search calls. The two apps will therefore use separate least-privilege OAuth
M2M identities created in the paid workspace for shared read-only data access.
The Free user token is retained only for same-workspace frontend-to-MCP calls
and trusted request identity. See
`docs/SPLIT_WORKSPACE_APP_DEPLOYMENT_PLAN.md`.

The development analytical namespace remains Unity Catalog `bootcamp_students.student_sri`. Lakebase uses a different classroom convention: all students share PostgreSQL schema `bootcamp_students`, and this application owns only tables whose base names end in `_srini`. Unity-Catalog-to-Lakebase synced graph tables live in PostgreSQL schema `bootcamp_cdc` and also end in `_srini`.

The verified development SQL compute is the serverless `Serverless Starter Warehouse`:

- Warehouse ID: `b15d3d6f837ba428`
- Workspace ID: `1352785079224954`
- Server: `dbc-7b106152-caf3.cloud.databricks.com`
- HTTP path: `/sql/1.0/warehouses/b15d3d6f837ba428`
- OAuth issuer: `https://dbc-7b106152-caf3.cloud.databricks.com/oidc`

Jobs and pipelines continue to use this warehouse in the data workspace. The
Free Edition apps cannot attach it as a local app resource; their paid-workspace
clients will use explicit host/warehouse settings plus app-specific OAuth M2M
credentials supplied only through Free Edition secret resources.

| Name | Component | Required when | Source |
|---|---|---|---|
| `MASSIVE_API_KEY` | feasibility/local ingestion | Live Massive calls | Local environment only |
| `MASSIVE_API_BASE_URL` | Massive clients | Optional test override | Environment; defaults to Massive API |
| `MASSIVE_RATE_LIMIT_STATE_PATH` | Massive clients | Shared request coordination | Writable state file; defaults to local `/tmp`, Volume control path in ingestion job |
| `MASSIVE_RATE_LIMIT_BACKEND` | Massive clients | Coordination selection | `process` for local/single-host use; deployed MCP and ingestion workloads explicitly use fail-closed `lakebase` |
| `MASSIVE_RATE_LIMIT_REQUESTER` | Massive clients | Sanitized quota audit label | Optional non-secret host/workload label, limited to 100 characters |
| derived `*_audit.jsonl` path | Massive certification | Every permitted physical API attempt | Credential-free append-only ledger beside the limiter state; never contains request headers or API keys |
| `SEC_USER_AGENT` | SEC ingestion | Live SEC calls | Identifying application/contact string |
| `sec/user-agent` | deployed SEC ingestion | When `SEC_USER_AGENT` is not set | Databricks secret containing the approved identifying contact; decoded only in memory |
| `USE_MOCK_BACKEND` | apps | Local development only | Literal `true`; deployed target must use `false` |
| `DATA_WORKSPACE_HOST` | frontend/MCP paid-data clients | Paid workspace API/SQL target | Non-secret environment value; `https://dbc-7b106152-caf3.cloud.databricks.com` |
| `DATA_WORKSPACE_WAREHOUSE_ID` | frontend/MCP paid-data clients | Existing paid serverless SQL Warehouse | Non-secret environment value; `b15d3d6f837ba428` |
| `DATA_WORKSPACE_CLIENT_ID` | frontend/MCP paid-data clients | App-specific OAuth M2M client in paid workspace | Separate Free Edition secret per app; never shared between apps |
| `DATA_WORKSPACE_CLIENT_SECRET` | frontend/MCP paid-data clients | App-specific OAuth M2M secret in paid workspace | Separate Free Edition secret per app; never committed or logged |
| `DATABRICKS_WAREHOUSE_ID` | jobs/local acceptance | Same-workspace Delta SQL access | Existing paid-workspace runtime or explicit local environment; no longer a Free app resource |
| `DATABRICKS_CATALOG` | MCP retrieval | Governed market tables | Non-secret environment value; `bootcamp_students` |
| `DATABRICKS_SCHEMA` | MCP retrieval | Governed market tables | Non-secret environment value; `student_sri` |
| `SIGNAL_DESK_VECTOR_SEARCH_INDEX` | MCP retrieval/index sync | Managed research index | Non-secret full name; `bootcamp_students.student_sri.signal_desk_research_chunks_index` |
| `PGHOST`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGPORT` | MCP operational store | Future migration to an attached Lakebase Autoscaling resource | Not used by the current shared classroom URL; never logged |
| `LAKEBASE_URL` | MCP/frontend local override | Explicit local-only connection override | Runtime environment only; PostgreSQL URL with `sslmode=require` |
| `LAKEBASE_SECRET_SCOPE` | MCP/frontend | Deployed Lakebase connection | Defaults to admin-managed scope `database` |
| `LAKEBASE_SECRET_KEY` | MCP/frontend | Deployed Lakebase connection | Defaults to admin-managed key `lakebase-url` |
| `SIGNAL_DESK_SCHEMA` | MCP/frontend | Lakebase operational schema | Non-secret environment value; `bootcamp_students` |
| `SIGNAL_DESK_TABLE_SUFFIX` | MCP/frontend/migrations | Per-student Lakebase table namespace | Non-secret lowercase identifier; `srini` |
| `SIGNAL_DESK_GRAPH_SCHEMA` | MCP/frontend/CDF reads | Lakebase schema containing replicated graph tables | Non-secret environment value; `bootcamp_cdc` |
| `lakebase_table_suffix` | Activity analytics bundle | Resolves Lakehouse Sync history names for shared-schema source tables | Bundle variable; development value `srini` |
| `MCP_SERVER_URL` | frontend write service | Watchlist and later research/action tool calls | HTTPS URL resolved from the same Free Edition MCP app resource; deployed binding remains a Phase 8 gate |
| `MCP_TIMEOUT_SECONDS` | frontend write service | Optional MCP timeout override | Integer 1–60; defaults to 20 seconds |
| `RAW_VOLUME_PATH` | ingestion/pipeline | Raw file landing | Bundle-derived `/Volumes/...` path |

## Planned Free Edition app resource keys

| App | Key | Resource | Permission intent |
|---|---|---|---|
| MCP | `lakebase-url` | Free Edition secret containing the existing Lakebase URL | Read; app accesses only `_srini` tables |
| MCP | `massive-api-key` | Free Edition secret containing the existing Massive key | Read |
| MCP | `data-workspace-client-id` | MCP-specific paid-workspace OAuth client ID | Read/protected injection |
| MCP | `data-workspace-client-secret` | MCP-specific paid-workspace OAuth client secret | Read |
| Frontend | `lakebase-url` | Free Edition secret containing the existing Lakebase URL | Read; bounded `_srini` reads only |
| Frontend | `data-workspace-client-id` | Frontend-specific paid-workspace OAuth client ID | Read/protected injection |
| Frontend | `data-workspace-client-secret` | Frontend-specific paid-workspace OAuth client secret | Read |
| Frontend | `mcp-app` | Same-workspace Free Edition FastMCP app | Can use; resolve URL without hardcoding |

The Free app manifests must not declare the paid SQL warehouse, paid Unity
Catalog tables, or paid AI Search index as local app resources. Those resources
remain governed in `dataexpertio_srini` and are reached only through the
least-privilege bridge identities after the egress and M2M acceptance gates.

The complete PostgreSQL URL remains protected by Databricks secrets. A separate
Free Edition secret binding must be created for each app without displaying or
committing the value. The deployed helpers receive `LAKEBASE_URL` from
`valueFrom` and never log or persist it; direct access is conditional on the
Free Edition Lakebase TLS egress proof.

Connections must validate that both shared schemas exist, but must not create, drop, or claim ownership of either schema. Every operational table reference is fully qualified as `bootcamp_students.<base_table>_srini`; setting only a search path is insufficient because it does not enforce the required suffix. Replicated graph objects are referenced as `bootcamp_cdc.<base_table>_srini`. Dynamic schema, base-table, and suffix components must be allowlisted and identifier-validated before SQL composition.

Migration `0005` adds `bootcamp_students.massive_api_attempts_srini`. Deployed
MCP and Massive ingestion callers serialize acquisitions with a Lakebase
transaction advisory lock and use the database clock to enforce at most four
physical attempts in any rolling 60-second window across hosts. If Lakebase is
unavailable, callers refuse the external API request; they never fall back to
an uncoordinated local allowance.

All operational SQL and migrations resolve through an allowlisted table registry and target only fully qualified `_srini` objects. `setup_secrets.py` must not be used for deployment because the administrator already owns secret provisioning.
