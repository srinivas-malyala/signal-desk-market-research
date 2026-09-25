# Configuration Contract

Configuration names are stable contracts. Credentials and sensitive resource identifiers must not be committed; approved non-secret development namespaces are recorded explicitly.

## Deployment topology

As of 2026-09-24, `dataexpertio_srini` remains the data workspace for all jobs,
pipelines, Unity Catalog data, SQL Warehouse queries, AI Search, Lakehouse Sync,
analytics, and Supervisor processing. Only the FastMCP and Flask runtimes will
be deployed as two separate Render web services.

The Render split is implemented locally but not yet deployed. Browser users authenticate
to Flask through generic OIDC. Flask sends MCP a short-lived asymmetric signed
identity assertion, not the browser's OIDC token. Each Render service uses a
separate least-privilege OAuth M2M identity created in the paid workspace for
shared read-only data access. The Supervisor uses a separate machine credential
or supported OAuth M2M flow and is mapped to a fixed server-side identity. See
`docs/RENDER_DEPLOYMENT_PLAN.md`.

The development analytical namespace remains Unity Catalog `bootcamp_students.student_sri`. Lakebase uses a different classroom convention: all students share PostgreSQL schema `bootcamp_students`, and this application owns only tables whose base names end in `_srini`. Unity-Catalog-to-Lakebase synced graph tables live in PostgreSQL schema `bootcamp_cdc` and also end in `_srini`.

The verified development SQL compute is the serverless `Serverless Starter Warehouse`:

- Warehouse ID: `b15d3d6f837ba428`
- Workspace ID: `1352785079224954`
- Server: `dbc-7b106152-caf3.cloud.databricks.com`
- HTTP path: `/sql/1.0/warehouses/b15d3d6f837ba428`
- OAuth issuer: `https://dbc-7b106152-caf3.cloud.databricks.com/oidc`

Jobs and pipelines continue to use this warehouse in the data workspace. The
Render services use explicit host/warehouse settings plus service-specific
OAuth M2M credentials supplied only through Render secret environment values.

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
| `DATA_WORKSPACE_CLIENT_ID` | frontend/MCP paid-data clients | Service-specific OAuth M2M client in paid workspace | Separate Render secret per service; never shared between services |
| `DATA_WORKSPACE_CLIENT_SECRET` | frontend/MCP paid-data clients | Service-specific OAuth M2M secret in paid workspace | Separate Render secret per service; never committed or logged |
| `DATABRICKS_WAREHOUSE_ID` | jobs/local acceptance | Same-workspace Delta SQL access | Existing paid-workspace runtime or explicit local environment; not a Render resource |
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
| `MCP_SERVER_URL` | frontend write service | Watchlist and later research/action tool calls | Render MCP HTTPS URL; deployed binding remains a Phase 8 gate |
| `MCP_TIMEOUT_SECONDS` | frontend write service | Optional MCP timeout override | Integer 1–60; defaults to 20 seconds |
| `SIGNAL_DESK_HOSTING` | MCP/frontend | Select deployed host behavior | Literal `render` in both Render services |
| `SIGNAL_DESK_IDENTITY_MODE` | MCP/frontend | Select deployed identity provider | `oidc_session` for frontend; `signed_assertion` for MCP |
| `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_REDIRECT_URI` | frontend | Browser sign-in | Provider registration; client secret stored only as a Render secret |
| `FLASK_SESSION_SECRET` | frontend | Encrypted/signed server session | High-entropy Render secret; rotate after acceptance if exposed |
| `FRONTEND_ASSERTION_PRIVATE_KEY` | frontend | Sign short-lived MCP identity assertions | Render secret available only to frontend |
| `FRONTEND_ASSERTION_PUBLIC_KEY` | MCP | Verify frontend identity assertions | Render environment value; no private material |
| `MCP_SUPERVISOR_TOKEN` | MCP/Supervisor connection | Authenticate non-browser Supervisor calls | Separate high-entropy secret or replace with supported OAuth M2M; never exposed to the model |
| `MCP_SUPERVISOR_SUBJECT` | MCP | Fixed audit identity for Supervisor actions | Non-secret allowlisted subject; never accepted from tool arguments |
| `RAW_VOLUME_PATH` | ingestion/pipeline | Raw file landing | Bundle-derived `/Volumes/...` path |

## Planned Render environment contract

| Service | Secret/value | Purpose | Permission intent |
|---|---|---|---|
| MCP | `LAKEBASE_URL`, `MASSIVE_API_KEY` | Operational store and bounded external fallback | Read/write only `_srini` tables; Massive calls use the shared quota ledger |
| MCP | `DATA_WORKSPACE_CLIENT_ID`, `DATA_WORKSPACE_CLIENT_SECRET` | Paid SQL and AI Search access | MCP-specific least-privilege read identity |
| MCP | `FRONTEND_ASSERTION_PUBLIC_KEY`, `MCP_SUPERVISOR_TOKEN` | Verify frontend users and authenticate Supervisor | Verification/machine auth only |
| Frontend | `LAKEBASE_URL` | Bounded user history reads | Read only permitted `_srini` objects and user-owned rows |
| Frontend | `DATA_WORKSPACE_CLIENT_ID`, `DATA_WORKSPACE_CLIENT_SECRET` | Paid Gold analytics access | Frontend-specific least-privilege read identity |
| Frontend | OIDC settings, `FLASK_SESSION_SECRET` | Browser authentication/session | Frontend only |
| Frontend | `FRONTEND_ASSERTION_PRIVATE_KEY`, `MCP_SERVER_URL` | Authenticated MCP calls | Signing key available only to frontend; HTTPS URL is non-secret |

The planned `render.yaml` will declare both services and non-secret defaults.
Every secret field must use `sync: false`; no secret value may appear in the
Blueprint, repository, build output, or logs. The Render services must not
assume Databricks app resources or ambient `Config()` credentials. Paid SQL,
Unity Catalog, and AI Search resources remain governed in
`dataexpertio_srini` and are reached only through the least-privilege M2M
identities after positive and negative permission tests.

The complete PostgreSQL URL remains protected. Jobs in Databricks continue to
retrieve it from the administrator-owned `database/lakebase-url` secret;
Render receives the same connection URL through a protected service-specific
secret value without displaying, committing, logging, or persisting it. Direct
access is conditional on the Render-to-Lakebase TLS connectivity spike.

Connections must validate that both shared schemas exist, but must not create, drop, or claim ownership of either schema. Every operational table reference is fully qualified as `bootcamp_students.<base_table>_srini`; setting only a search path is insufficient because it does not enforce the required suffix. Replicated graph objects are referenced as `bootcamp_cdc.<base_table>_srini`. Dynamic schema, base-table, and suffix components must be allowlisted and identifier-validated before SQL composition.

Migration `0005` adds `bootcamp_students.massive_api_attempts_srini`. Deployed
MCP and Massive ingestion callers serialize acquisitions with a Lakebase
transaction advisory lock and use the database clock to enforce at most four
physical attempts in any rolling 60-second window across hosts. If Lakebase is
unavailable, callers refuse the external API request; they never fall back to
an uncoordinated local allowance.

All operational SQL and migrations resolve through an allowlisted table registry and target only fully qualified `_srini` objects. `setup_secrets.py` must not be used for deployment because the administrator already owns secret provisioning.
