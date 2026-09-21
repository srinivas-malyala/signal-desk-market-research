# Configuration Contract

Configuration names are stable contracts. Credentials and sensitive resource identifiers must not be committed; approved non-secret development namespaces are recorded explicitly.

The development analytical namespace remains Unity Catalog `bootcamp_students.student_sri`. Lakebase uses a different classroom convention: all students share PostgreSQL schema `bootcamp_students`, and this application owns only tables whose base names end in `_srini`. Unity-Catalog-to-Lakebase synced graph tables live in PostgreSQL schema `bootcamp_cdc` and also end in `_srini`.

The verified development SQL compute is the serverless `Serverless Starter Warehouse`:

- Warehouse ID: `b15d3d6f837ba428`
- Workspace ID: `1352785079224954`
- Server: `dbc-7b106152-caf3.cloud.databricks.com`
- HTTP path: `/sql/1.0/warehouses/b15d3d6f837ba428`
- OAuth issuer: `https://dbc-7b106152-caf3.cloud.databricks.com/oidc`

Both Databricks Apps receive `DATABRICKS_WAREHOUSE_ID` from an attached `sql-warehouse` resource with `CAN_USE`. Authentication remains Databricks-managed; no JDBC credential or OAuth token is stored in source.

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
| `DATABRICKS_WAREHOUSE_ID` | frontend/MCP analytics | Delta SQL access | App resource `valueFrom` |
| `DATABRICKS_CATALOG` | MCP retrieval | Governed market tables | Non-secret environment value; `bootcamp_students` |
| `DATABRICKS_SCHEMA` | MCP retrieval | Governed market tables | Non-secret environment value; `student_sri` |
| `SIGNAL_DESK_VECTOR_SEARCH_INDEX` | MCP retrieval/index sync | Managed research index | Non-secret full name; `bootcamp_students.student_sri.signal_desk_research_chunks_index` |
| `PGHOST`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGPORT` | MCP operational store | Future attached Lakebase access | Attached `postgres` resource; never logged |
| `LAKEBASE_URL` | MCP/frontend local override | Explicit local-only connection override | Runtime environment only; PostgreSQL URL with `sslmode=require` |
| `LAKEBASE_SECRET_SCOPE` | MCP/frontend | Deployed Lakebase connection | Defaults to admin-managed scope `database` |
| `LAKEBASE_SECRET_KEY` | MCP/frontend | Deployed Lakebase connection | Defaults to admin-managed key `lakebase-url` |
| `SIGNAL_DESK_SCHEMA` | MCP/frontend | Lakebase operational schema | Non-secret environment value; `bootcamp_students` |
| `SIGNAL_DESK_TABLE_SUFFIX` | MCP/frontend/migrations | Per-student Lakebase table namespace | Non-secret lowercase identifier; `srini` |
| `SIGNAL_DESK_GRAPH_SCHEMA` | MCP/frontend/CDF reads | Lakebase schema containing replicated graph tables | Non-secret environment value; `bootcamp_cdc` |
| `lakebase_table_suffix` | Activity analytics bundle | Resolves Lakehouse Sync history names for shared-schema source tables | Bundle variable; development value `srini` |
| `MCP_SERVER_URL` | frontend write service | Watchlist and later research/action tool calls | HTTPS MCP Databricks App URL; deployed binding remains a Phase 8 gate |
| `MCP_TIMEOUT_SECONDS` | frontend write service | Optional MCP timeout override | Integer 1–60; defaults to 20 seconds |
| `RAW_VOLUME_PATH` | ingestion/pipeline | Raw file landing | Bundle-derived `/Volumes/...` path |

## Required Databricks app resource keys

| App | Key | Resource | Permission intent |
|---|---|---|---|
| MCP | `lakebase-url` | Admin-managed Lakebase URL secret | Can read; app accesses only `_srini` tables |
| MCP | `massive-api-key` | Secret | Read |
| MCP | `sql-warehouse` | SQL warehouse | Can use |
| MCP | `silver-market-bars` | Unity Catalog table | Select |
| MCP | `gold-stock-performance` | Unity Catalog table | Select |
| Frontend | `mcp-connection` | UC/external MCP connection or service endpoint | Use/query only |
| Frontend | `sql-warehouse` | SQL warehouse | Can use |

The complete PostgreSQL URL is stored only in Databricks secret `database/lakebase-url`. The deployed helpers fetch the secret with `WorkspaceClient`, Base64-decode it in memory, and never log or persist it. `LAKEBASE_URL` remains an explicit local-test override only.

Connections must validate that both shared schemas exist, but must not create, drop, or claim ownership of either schema. Every operational table reference is fully qualified as `bootcamp_students.<base_table>_srini`; setting only a search path is insufficient because it does not enforce the required suffix. Replicated graph objects are referenced as `bootcamp_cdc.<base_table>_srini`. Dynamic schema, base-table, and suffix components must be allowlisted and identifier-validated before SQL composition.

Migration `0005` adds `bootcamp_students.massive_api_attempts_srini`. Deployed
MCP and Massive ingestion callers serialize acquisitions with a Lakebase
transaction advisory lock and use the database clock to enforce at most four
physical attempts in any rolling 60-second window across hosts. If Lakebase is
unavailable, callers refuse the external API request; they never fall back to
an uncoordinated local allowance.

All operational SQL and migrations resolve through an allowlisted table registry and target only fully qualified `_srini` objects. `setup_secrets.py` must not be used for deployment because the administrator already owns secret provisioning.
