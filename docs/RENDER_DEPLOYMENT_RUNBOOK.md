# Render deployment runbook

Updated: 2026-09-29

This runbook deploys only the Flask frontend and FastMCP service to Render. All
jobs, pipelines, Unity Catalog data, SQL Warehouse, AI Search, Lakehouse Sync,
analytics, and Supervisor processing remain in the Databricks workspace selected
by `dataexpertio_srini`.

The MCP follows `docs/LAKEBASE_ONLY_MCP_SERVING_PLAN.md`: Databricks continues
to build governed data, but request-time MCP reads move to atomically published
Lakebase serving tables. SQL Warehouse and AI Search remain rollback paths until
the independent market and research gates pass.

Never paste a secret into a command, commit, screenshot, build log, or evidence
file. Enter secrets only through the Render dashboard or another approved secret
manager. Record sanitized service URLs, deployment IDs, timestamps, and test
results only.

## 0. Reproduce the service builds locally

The Blueprint installs hash-pinned Linux/Python 3.11 dependency locks. Regenerate
them only after intentionally editing the corresponding input requirement file:

```bash
uv pip compile mcp_server/requirements.txt --python-version 3.11 --python-platform x86_64-unknown-linux-gnu --generate-hashes --output-file mcp_server/requirements.lock
uv pip compile dashboard/requirements.txt --python-version 3.11 --python-platform x86_64-unknown-linux-gnu --generate-hashes --output-file dashboard/requirements.lock
```

Run the same automated checks used by CI before creating a Blueprint deployment:

```bash
uv run python tools/check_render_reproducibility.py --clean-install --process-smoke
```

This validates the two-service/secret contract, installs both locks into fresh
Python 3.11 environments, imports their runtime modules, starts the exact
Blueprint commands, and probes `/health` and `/healthz`. The local MCP process
smoke sets `SIGNAL_DESK_RUN_MIGRATIONS=false` because it has no deployment
database; the Blueprint explicitly sets it to `true`.

## 1. Renew and validate the data workspace

Completed on 2026-09-24: the explicit profile authenticated as
`malyalasrinivas@gmail.com`, and strict validation of the data-only development
bundle passed. Re-run these commands if the credential expires or the bundle
changes:

```bash
databricks auth login --host https://dbc-7b106152-caf3.cloud.databricks.com --profile dataexpertio_srini
databricks bundle validate --strict -t dev --profile dataexpertio_srini
```

On 2026-09-29, `dataexpertio_srini` was reauthenticated and strict validation
passed. Continue to use `--profile dataexpertio_srini` on every Databricks
command.

Inspect the resolved plan and confirm it contains no `apps` resources. The
active bundle includes only job, pipeline, storage, and AI Search definitions;
the historical `resources/*.app.yml` files are no longer included.

## 2. Discover and prepare Lakebase serving

Do not start with a workspace-admin request. First discover the exact Lakebase
project, branch, endpoint, database, registered catalog, and
current permissions using the reauthenticated profile. Discover CLI syntax
before issuing commands:

```bash
databricks postgres -h
databricks postgres list-projects -h
databricks postgres get-synced-table -h
```

CLI v1.12.1 has no synced-table list command. Inventory known synced-table
resource names from repository/bundle state and Catalog Explorer, then verify
each with `get-synced-table`.

Follow Gates 0–3 in `docs/LAKEBASE_ONLY_MCP_SERVING_PLAN.md` to publish one
narrow market serving Delta table, atomically copy it and
`research_search_documents` into shared PostgreSQL schema `bootcamp_students`
as `market_history_serving_srini` and `research_documents_serving_srini`, add
bounded query indexes, and reconcile keys/counts/freshness.

Create or select a native PostgreSQL runtime role with only:

- database `CONNECT`;
- existing operational-table DML required by MCP;
- shared-schema `USAGE`; and
- serving-table `SELECT`.

Do not grant `databricks_superuser`, `CREATEDB`, `CREATEROLE`, or broad schema
ownership. Run one permitted read and deliberately forbidden DDL/write checks.
If discovery exposes a missing permission, request only that exact one-time
project or Unity Catalog grant.

Gate 0 found that the existing secret maps to shared project
`summer-bootcamp-2026-v2`; the selected user cannot read its ACL and no Lakebase
UC catalog is registered. The classroom decision is to use that project without
requesting an admin grant: setup creates only persistent `_srini` tables in the
existing shared PostgreSQL schema, and the manual publisher uses session-local
staging plus an atomic transaction. Do not add these serving tables to the five
history tables allowlisted by the activity pipeline, and do not confuse that
Lakebase-to-UC `bootcamp_cdc` namespace with the separate PostgreSQL
`bootcamp_cdc` graph destination. The frontend Gold analytics credential
remains separate and must never be reused by MCP.

## 3. Register browser OIDC

Google OpenID Connect is the accepted provider for the capstone. Follow the
provider registration and secret-entry checklist in
`docs/RENDER_OIDC_PREPARATION.md`. Register a confidential Web application
client with this exact final callback URL:

```text
https://signal-desk-frontend-s88i.onrender.com/oidc/callback
```

The committed issuer is `https://accounts.google.com`. Enter the resulting
client ID and client secret only in the frontend Render service. Use
`ALLOWED_USER_EMAILS` during the bounded demonstration to restrict access to
named test accounts.

## 4. Generate application-only credentials

Generate one RSA key pair, a Flask session secret, and a separate high-entropy
Supervisor machine credential with `tools/generate_render_credentials.py`.
Generated values live only in ignored `build/render-secrets/`; the generator
prints fingerprints but no secret values. Re-running it validates the existing
set without overwriting it. Store the private key only in the frontend service
and the public key only in the MCP service. Never reuse OIDC, Lakebase, or
frontend analytics credentials.

Required secret ownership:

| Secret | MCP | Frontend |
|---|---:|---:|
| `LAKEBASE_URL` | Yes | Yes |
| `MASSIVE_API_KEY` | Yes | No |
| MCP Databricks `DATA_WORKSPACE_CLIENT_ID/SECRET` | Rollback window only; remove after Gate 4 | No |
| Frontend Databricks `DATA_WORKSPACE_CLIENT_ID/SECRET` | No | Yes |
| `FRONTEND_ASSERTION_PUBLIC_KEY` | Yes | No |
| `FRONTEND_ASSERTION_PRIVATE_KEY` | No | Yes |
| `MCP_SUPERVISOR_TOKEN`, `MCP_SUPERVISOR_SUBJECT` | Yes | No |
| OIDC settings and `FLASK_SESSION_SECRET` | No | Yes |
| `MCP_SERVER_URL` | No | Yes |

## 5. Create the Render Blueprint

Connect
[`srinivas-malyala/signal-desk-market-research`](https://github.com/srinivas-malyala/signal-desk-market-research)
and select branch `codex/render-app-deployment`, which is currently the GitHub
default branch. Create a Blueprint from the root `render.yaml`. Confirm that
Render proposes exactly two Python web services and no database:

- `signal-desk-mcp`
- `signal-desk-frontend`

Keep both services on the Free plan during the connectivity spike. Enter every
`sync: false` value through the Render dashboard. For the frontend, set
`MCP_SERVER_URL` to the final MCP HTTPS service URL and set the OIDC redirect URI
to the exact callback registered with the provider.

## 6. Deploy and accept MCP first

Deploy `signal-desk-mcp`. A successful build is not sufficient; verify the
public dependency-free health route and the authenticated tool path.

Deploy the market backend first. Canary it against the accepted AAPL known
answer, then cut over only after exact parity. Deploy the research backend only
after the complete 51-case evaluation passes all existing quality, provenance,
and filter thresholds. Keep backend identity in sanitized result metadata.

Run the read-only acceptance harness with the machine credential supplied only
through the shell environment:

```bash
python tools/phase5_mcp_smoke.py \
  --url https://<mcp-service>.onrender.com \
  --output build/phase5/render-mcp-readonly.json
```

The harness reads `MCP_SUPERVISOR_TOKEN` from the environment by default. Add
`--exercise-writes` only when disposable Lakebase writes and guaranteed cleanup
are approved. Then run simultaneous Job/MCP Massive quota acceptance and prove
that acquisition five waits for the shared Lakebase rolling-window slot.

## 7. Deploy and accept the frontend

Deploy `signal-desk-frontend`, then run the sanitized unauthenticated preflight:

```bash
python tools/render_acceptance.py \
  --mcp-url https://<mcp-service>.onrender.com \
  --frontend-url https://<frontend-service>.onrender.com \
  --output build/phase9/render-preflight.json
```

In a browser, sign in with two real permitted principals and verify:

1. research, comparison, and source-linked evidence;
2. confirmed watchlist, note, and report writes;
3. reload of user-owned state with no cross-user visibility;
4. analytics empty/partial/stale/error states;
5. expired/tampered/missing identity and missing CSRF rejection; and
6. one controlled action reaching Phase 6 Gold with measured freshness.

## 8. Connect the Supervisor

Create the paid-workspace governed HTTP/MCP connection to the Render MCP URL.
Use the separate Supervisor machine credential or a compatible administrator-
approved OAuth M2M mechanism. Never use a personal token or expose the machine
credential to the model. Deploy the Supervisor, capture all ten evaluation
fixtures, and run:

```bash
python tools/phase7_agent_eval.py --results /path/to/sanitized-results.json
```

## 9. Final paid demo window and teardown

Before final acceptance, upgrade both services to the smallest paid plan and
repeat all health, security, workflow, quota, CDC freshness, and performance
checks. The expected temporary hosting cost is approximately $14 at the planned
pricing. Record the exact commit SHA used for both deployments.

After the demonstration, suspend, downgrade, or delete both Render services and
rotate/revoke the Lakebase runtime password, any remaining frontend Databricks
credential, OIDC secret, assertion key pair, and Supervisor credential. Do not
delete Lakebase serving/operational `_srini` tables,
Unity Catalog resources, jobs, pipelines, SQL Warehouse, or AI Search resources
until a separately approved cleanup after the rollback observation period.
