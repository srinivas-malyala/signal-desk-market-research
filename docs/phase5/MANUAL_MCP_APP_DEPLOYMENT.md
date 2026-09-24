# Manual deployment runbook — Signal Desk MCP app

Updated: 2026-09-24 Pacific

> **Superseded deployment target:** Do not execute this same-workspace runbook.
> Budget constraints now require FastMCP and Flask to run under
> `Srini Free Edition`, while data resources remain under
> `dataexpertio_srini`. This document is retained as historical evidence of the
> earlier blocked attempt. Use
> `docs/SPLIT_WORKSPACE_APP_DEPLOYMENT_PLAN.md` for the current sequence.

## Goal

Deploy the existing Signal Desk FastMCP service as the Databricks App
`signal-desk-mcp-dev` using the Databricks workspace UI.

This runbook is specific to the development workspace and the existing capstone
resources. Do not paste secret values, access tokens, or the Lakebase connection
URL into the application configuration.

## Deployment values

| Setting | Value |
|---|---|
| Workspace | `https://dbc-7b106152-caf3.cloud.databricks.com` |
| Workspace ID | `1352785079224954` |
| App name | `signal-desk-mcp-dev` |
| App description | `Signal Desk FastMCP retrieval and action service` |
| Existing workspace source folder | `/Workspace/Users/malyalasrinivas@gmail.com/.bundle/signal-desk-capstone/dev/files/mcp_server` |
| SQL warehouse ID | `b15d3d6f837ba428` |
| Unity Catalog namespace | `bootcamp_students.student_sri` |
| Lakebase application schema | `bootcamp_students` |
| Lakebase table suffix | `srini` |
| Lakebase graph schema | `bootcamp_cdc` |
| AI Search index | `bootcamp_students.student_sri.signal_desk_research_chunks_index` |

## Responsibility split

The recommended path is:

1. A workspace administrator creates the app and attaches its resources.
2. The administrator grants `CAN MANAGE` on the app to
   `malyalasrinivas@gmail.com`.
3. The student deploys the already-uploaded source folder and validates the app.

This avoids granting the student broad `MANAGE` access to the shared `massive`
and `database` secret scopes. Databricks requires the person adding a resource to
have management permission on both the app and the resource. Secret permissions
apply to the whole scope, not only the selected key.

## Part A — Administrator: create and configure the app

### 1. Open Databricks Apps

1. Sign in to the workspace.
2. Open the app switcher in the upper-left corner.
3. Select **Databricks Apps**.
4. Click **Create app**.
5. Select **Create a custom app**.

### 2. Enter the app identity

1. Set **Name** to `signal-desk-mcp-dev`.
2. Set **Description** to
   `Signal Desk FastMCP retrieval and action service`.
3. Click **Next: Configure Git**.
4. Skip Git configuration because this procedure deploys the existing workspace
   folder.
5. Click **Next: Configure**.

App names cannot be changed after creation. If an app with this name already
exists, open it and use **Edit** instead of creating a duplicate.

### 3. Add the two secret resources

In **App resources**, click **Add resource** for each row below. Choose resource
type **Secret** and use **Can read** for the app service principal.

| Custom resource key | Secret scope | Secret key | App permission |
|---|---|---|---|
| `massive-api-key` | `massive` | `api-key` | Can read |
| `lakebase-url` | `database` | `lakebase-url` | Can read |

Important:

- Enter the custom resource keys exactly as shown. The hyphens matter.
- Select the secrets; do not copy or display their values.
- **Can read** is sufficient for the app. Do not grant it Can write or Can
  manage.

### 4. Add the SQL warehouse resource

1. Click **Add resource**.
2. Select **SQL warehouse**.
3. Select warehouse `b15d3d6f837ba428`.
4. Set app permission to **Can use**.
5. Set the custom resource key to `sql-warehouse`.

### 5. Add the governed market tables

Add both as **Unity Catalog table** resources with **Select** permission.

| Custom resource key | Table |
|---|---|
| `silver-market-bars` | `bootcamp_students.student_sri.silver_market_bars` |
| `gold-stock-performance` | `bootcamp_students.student_sri.gold_stock_performance` |

The administrator or resource owner must have enough Unity Catalog authority for
Databricks to grant the app service principal `USE CATALOG`, `USE SCHEMA`, and
`SELECT` as required.

### 6. Add the AI Search index

1. Click **Add resource**.
2. Select **Vector search index** or **AI Search index**, depending on the label
   shown by the workspace UI.
3. Select
   `bootcamp_students.student_sri.signal_desk_research_chunks_index`.
4. Set app permission to **Can select**.
5. Set the custom resource key to `research-index`.

Databricks should automatically grant the app service principal `USE CATALOG`,
`USE SCHEMA`, and `SELECT` when the person adding the index has sufficient
privileges.

### 7. Configure user authorization

The MCP server uses the forwarded Databricks identity and can issue SQL and AI
Search requests on behalf of the signed-in user.

Under **User authorization**, add only these additional API scopes:

- `sql`
- `vector-search`

Keep the default identity scopes. Do not add unrelated scopes such as files,
jobs, model serving, or app management.

### 8. Create the app and delegate app management

1. Click **Create app**.
2. Wait for the app object and its dedicated service principal to be created.
3. On the app overview page, click **Share**.
4. Add `malyalasrinivas@gmail.com` with **CAN MANAGE**.
5. Give ordinary app users **CAN USE**, not CAN MANAGE.

At this point the app exists but may not yet be deployed.

## Part B — Student: verify the source folder

The latest MCP source is already present at:

```text
/Workspace/Users/malyalasrinivas@gmail.com/.bundle/signal-desk-capstone/dev/files/mcp_server
```

In **Workspace**, open that folder and confirm it contains at least:

- `app.yaml`
- `stock_research_mcp_server.py`
- `requirements.txt`
- `lakebase.py`
- `research_broker.py`
- `research_search.py`
- `action_service.py`
- `lakehouse_market.py`
- `massive_client.py`
- `audit.py`
- the `migrations` directory

Do not select the parent `files` directory. The selected source folder must have
`app.yaml` and `requirements.txt` at its root.

### Expected `app.yaml`

Open `app.yaml` and verify that its resource references match the keys configured
above:

```yaml
command: ["python", "stock_research_mcp_server.py"]
env:
  - name: DATABRICKS_WAREHOUSE_ID
    valueFrom: sql-warehouse
  - name: MASSIVE_API_KEY
    valueFrom: massive-api-key
  - name: LAKEBASE_URL
    valueFrom: lakebase-url
  - name: SIGNAL_DESK_SCHEMA
    value: bootcamp_students
  - name: SIGNAL_DESK_TABLE_SUFFIX
    value: srini
  - name: SIGNAL_DESK_GRAPH_SCHEMA
    value: bootcamp_cdc
  - name: SIGNAL_DESK_VECTOR_SEARCH_INDEX
    valueFrom: research-index
  - name: DATABRICKS_CATALOG
    value: bootcamp_students
  - name: DATABRICKS_SCHEMA
    value: student_sri
```

Do not replace any `valueFrom` entry with a secret value or resource ID.

### Expected Python dependencies

Confirm `requirements.txt` includes:

```text
fastmcp>=2.12,<3
requests>=2.32,<3
urllib3>=2.2,<3
databricks-sdk>=0.81,<1
psycopg2-binary>=2.9,<3
```

`psycopg2-binary` is required for the Lakebase connection.

## Part C — Student: deploy from the workspace folder

1. Open **Databricks Apps**.
2. Select `signal-desk-mcp-dev`.
3. Confirm that the overview page shows all six resources:
   two secrets, one SQL warehouse, two Unity Catalog tables, and one AI Search
   index.
4. Click **Deploy**.
5. Select **From workspace folder**.
6. Choose:

   ```text
   /Workspace/Users/malyalasrinivas@gmail.com/.bundle/signal-desk-capstone/dev/files/mcp_server
   ```

7. Click **Select**.
8. Review the source path and click **Deploy**.
9. Wait for dependency installation and application startup to finish. Do not
   close the page while it is still building.

The deployment is successful only when the app reports a running state. Creating
the app object alone is not a completed deployment.

## Part D — Verify the deployment

### 1. Check deployment status and logs

On the app overview page:

1. Confirm the app status is **Running**.
2. Open the latest deployment details.
3. Inspect both system and application logs.
4. Confirm dependency installation succeeded.
5. Confirm there is no missing resource, permission, import, or Lakebase startup
   error.

Never paste raw environment-variable values into a support message or screenshot.

### 2. Test the health route

1. Click the app URL.
2. Complete the Databricks consent prompt if shown.
3. Append `/health` to the app URL.
4. Confirm the response is:

```json
{
  "status": "ok",
  "service": "stock-market-research",
  "contract_version": "1.0"
}
```

The exact JSON spacing may differ.

### 3. Confirm resource injection without exposing values

On the app environment/configuration page, verify that these environment names
exist:

- `DATABRICKS_WAREHOUSE_ID`
- `MASSIVE_API_KEY`
- `LAKEBASE_URL`
- `SIGNAL_DESK_VECTOR_SEARCH_INDEX`
- `DATABRICKS_CATALOG`
- `DATABRICKS_SCHEMA`

The secret-backed variables should remain resource references. Do not reveal or
copy their resolved values.

### 4. Record acceptance evidence

Record only non-sensitive evidence:

- App name and URL.
- Deployment ID and completion time.
- Running status.
- Health response status.
- Service-principal identifier.
- Resource keys and permission levels, without secret values.
- Any sanitized error code and message.

## Troubleshooting

### Cannot add `massive-api-key` or `lakebase-url`

Cause: the person adding the resource lacks management permission on the secret
scope.

Recommended resolution: ask the secret-scope administrator to add the resource
to the app. Avoid granting broad scope management unless the administrator accepts
that access.

Alternative administrator action, when explicitly approved:

```bash
databricks secrets put-acl massive malyalasrinivas@gmail.com MANAGE --profile dataexpertio_srini
databricks secrets put-acl database malyalasrinivas@gmail.com MANAGE --profile dataexpertio_srini
```

`MANAGE` applies to the complete secret scope. If it is granted only to perform
the binding, the administrator should decide whether and when to reduce it after
deployment.

### AI Search index cannot be added

The person adding it must be able to grant the app service principal access to
the parent catalog, schema, and index. Ask the Unity Catalog owner or metastore
administrator to add this resource.

### App builds but does not start

Check the application logs for the first exception. Common causes are:

- A resource key does not exactly match `app.yaml`.
- `psycopg2-binary` was omitted from `requirements.txt`.
- The source folder was selected one directory too high or too low.
- The app service principal cannot read the Lakebase or Massive secret scope.
- The Lakebase migration cannot use the shared schema or `_srini` tables.
- The server cannot reach the SQL warehouse or AI Search index.

Correct the configuration and click **Deploy** again. Do not create a second app
for a routine deployment failure.

### Health returns 404

Confirm the URL ends with `/health`, the latest source folder was deployed, and
`stock_research_mcp_server.py` contains the FastMCP custom health route.

### Health returns 502 or the app stops

Inspect the app logs. A 502 normally means the process did not bind successfully
or exited during startup. The first startup action applies Lakebase migrations,
so a Lakebase permission or connectivity error can stop the service before the
health route becomes available.

## Optional CLI verification

The UI steps above are sufficient. After deployment, the following read-only
commands provide reproducible status and logs:

```bash
databricks apps get signal-desk-mcp-dev --profile dataexpertio_srini
databricks apps logs signal-desk-mcp-dev --profile dataexpertio_srini
```

## Automated post-deployment acceptance

After the app is running and the signed-in user has completed any Databricks
authorization consent prompt, install the locked MCP development extra if needed:

```bash
UV_CACHE_DIR=.uv-cache uv sync --extra mcp --extra dashboard
```

Run the read-only gate first:

```bash
.venv/bin/python tools/phase5_mcp_smoke.py \
  --profile dataexpertio_srini \
  --app-name signal-desk-mcp-dev \
  --output build/phase5/mcp_smoke_readonly.json
```

This verifies the health response, all nine tool contracts, governed market
retrieval, semantic retrieval with provenance, and Lakebase trace/event
reconciliation. It authenticates through the selected Databricks profile and
does not construct forwarded identity headers.

Only after the read-only gate passes, run the reversible action gate:

```bash
.venv/bin/python tools/phase5_mcp_smoke.py \
  --profile dataexpertio_srini \
  --app-name signal-desk-mcp-dev \
  --exercise-writes \
  --output build/phase5/mcp_smoke_write.json
```

The write gate selects an ETF ticker not already present in the Primary
watchlist, performs a confirmed add, repeats the exact idempotency key, proves
that the same key with changed parameters is rejected, and removes the ticker
with a new key. Cleanup is attempted from a `finally` path even when the replay
or conflict request fails.

The reports contain counts, status, correlation evidence, and public market
metadata only. They never include the OAuth token, secret values, Lakebase URL,
user email, or raw idempotency keys.

## Official references

- [Create a custom Databricks app](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/create-custom-app)
- [Deploy a Databricks app](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/deploy)
- [Add resources to a Databricks app](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/resources)
- [Add a secret resource](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/secrets)
- [Add an AI Search index resource](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/vector-search)
- [Configure app authorization](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth)
- [Configure app permissions](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/permissions)
