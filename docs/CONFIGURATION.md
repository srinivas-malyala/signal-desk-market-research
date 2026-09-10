# Configuration Contract

Configuration names are stable contracts. Credentials and sensitive resource identifiers must not be committed; approved non-secret development namespaces are recorded explicitly.

The development analytical namespace is Unity Catalog `bootcamp_students.student_sri`. The operational PostgreSQL schema is also named `student_sri`, but it is a separate namespace inside Lakebase; the shared name does not imply shared storage.

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
| `SEC_USER_AGENT` | SEC ingestion | Live SEC calls | Identifying application/contact string |
| `USE_MOCK_BACKEND` | apps | Local development only | Literal `true`; deployed target must use `false` |
| `DATABRICKS_WAREHOUSE_ID` | frontend/MCP analytics | Delta SQL access | App resource `valueFrom` |
| `PGHOST`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGPORT` | MCP operational store | Future attached Lakebase access | Attached `postgres` resource; never logged |
| `LAKEBASE_URL` | MCP/frontend compatibility path | Student connection-string access | Runtime secret; PostgreSQL URL with `sslmode=require` |
| `SIGNAL_DESK_SCHEMA` | MCP/frontend | Lakebase schema selection | Non-secret environment value; provisional value `student_sri` |
| `RAW_VOLUME_PATH` | ingestion/pipeline | Raw file landing | Bundle-derived `/Volumes/...` path |

## Required Databricks app resource keys

| App | Key | Resource | Permission intent |
|---|---|---|---|
| MCP | `postgres` | Lakebase Autoscaling branch/database | Can connect and create; app owns its schema |
| MCP | `massive-api-key` | Secret | Read |
| MCP | `sql-warehouse` | SQL warehouse | Can use |
| Frontend | `mcp-connection` | UC/external MCP connection or service endpoint | Use/query only |
| Frontend | `sql-warehouse` | SQL warehouse | Can use |

Until the final Lakebase project resource is available, both apps accept a runtime-only URL assembled from this approved contract:

```text
host=ep-odd-union-d1792avs.database.us-west-2.cloud.databricks.com
database=databricks_postgres
user=student
password=<runtime-secret>
sslmode=require
```

The password and complete URL must remain in a secret or runtime environment. Every connection validates `SIGNAL_DESK_SCHEMA`, verifies that it exists, and then sets its session search path to `student_sri,public`; application tables therefore resolve in the student schema rather than `public`. The schema is assumed to be pre-created and must be owned by, or grant create/read/write privileges to, the `student` role. A missing schema fails the connection instead of falling back to `public`.

The URL-secret variables (`LAKEBASE_URL`, `LAKEBASE_SECRET_SCOPE`, and `LAKEBASE_SECRET_KEY`) remain a compatibility path and can be retired when an Autoscaling Lakebase project is attached in Phase 4. `setup_secrets.py` must not be used for a deployment because it selects credentials implicitly.
