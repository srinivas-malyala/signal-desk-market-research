# Configuration Contract

Configuration names are stable contracts. Values shown here are examples only; credentials and workspace resource identifiers must not be committed.

| Name | Component | Required when | Source |
|---|---|---|---|
| `MASSIVE_API_KEY` | feasibility/local ingestion | Live Massive calls | Local environment only |
| `MASSIVE_API_BASE_URL` | Massive clients | Optional test override | Environment; defaults to Massive API |
| `SEC_USER_AGENT` | SEC ingestion | Live SEC calls | Identifying application/contact string |
| `USE_MOCK_BACKEND` | apps | Local development only | Literal `true`; deployed target must use `false` |
| `DATABRICKS_WAREHOUSE_ID` | frontend/MCP analytics | Delta SQL access | App resource `valueFrom` |
| `PGHOST`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGPORT` | MCP operational store | Deployed Lakebase access | Attached `postgres` resource; never logged |
| `SIGNAL_DESK_SCHEMA` | MCP | Lakebase schema selection | Non-secret environment value |
| `RAW_VOLUME_PATH` | ingestion/pipeline | Raw file landing | Bundle-derived `/Volumes/...` path |

## Required Databricks app resource keys

| App | Key | Resource | Permission intent |
|---|---|---|---|
| MCP | `postgres` | Lakebase Autoscaling branch/database | Can connect and create; app owns its schema |
| MCP | `massive-api-key` | Secret | Read |
| MCP | `sql-warehouse` | SQL warehouse | Can use |
| Frontend | `mcp-connection` | UC/external MCP connection or service endpoint | Use/query only |
| Frontend | `sql-warehouse` | SQL warehouse | Can use |

The current URL-secret variables (`LAKEBASE_URL`, `LAKEBASE_SECRET_SCOPE`, and `LAKEBASE_SECRET_KEY`) are compatibility-only and are retired by Phase 4. `setup_secrets.py` must not be used for a deployment because it selects credentials implicitly.
