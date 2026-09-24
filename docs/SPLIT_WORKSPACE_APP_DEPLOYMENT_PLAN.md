# Split-workspace Databricks Apps deployment plan

Updated: 2026-09-24

## Decision

Keep all data engineering, analytics, Lakehouse Sync, Unity Catalog, SQL
Warehouse, AI Search, and Supervisor workloads in the workspace selected by
`dataexpertio_srini`. Deploy only the FastMCP and Flask Databricks Apps in the
workspace selected by `Srini Free Edition`.

This is feasible only after cross-workspace connectivity and authentication are
proved. It is not a deployment-profile substitution: Databricks App resources,
the app service principal, and forwarded user OAuth tokens are scoped to the
workspace that hosts the app. The existing app manifests therefore cannot bind
the Free Edition apps directly to the paid workspace's warehouse, Unity Catalog
tables, AI Search index, or secrets.

## Confirmed facts and open gates

| Item | Status | Consequence |
|---|---|---|
| Paid data workspace | Verified | `dataexpertio_srini` authenticates as `malyalasrinivas@gmail.com`; existing data resources remain unchanged. |
| Free Edition app capacity | Supported by current Databricks limits | Two apps fit within the three-app account limit. Apps stop after at most 24 hours and must be restarted for a demo. |
| Free Edition profile | Authentication gate | The cached token for `Srini Free Edition` was invalid on 2026-09-24; reauthentication is required before inventory or validation. |
| Cross-workspace user OAuth | Not supported | The Free Edition `X-Forwarded-Access-Token` must never be sent to the paid workspace SQL Warehouse or AI Search APIs. |
| Cross-workspace app authorization | Requires implementation | Each Free Edition app needs a separate least-privilege OAuth M2M service principal in the paid workspace. Do not share one client secret between the apps. |
| Free Edition outbound network | Unverified, high risk | Free Edition restricts outbound internet access. Prove HTTPS access to the paid workspace and Massive plus PostgreSQL access to Lakebase before refactoring or deploying the full apps. |
| Lakebase | Endpoint already verified from local/paid execution | Reuse the same `_srini` tables and quota ledger only if the Free Edition app can reach the PostgreSQL endpoint over TLS. |
| Paid Supervisor to Free MCP | Unverified, high risk | Prove a governed HTTP/MCP connection can obtain a token accepted by the Free Edition app. If Free Edition cannot host the required machine identity, implement equivalent paid-workspace UC function tools for the Supervisor instead of using a temporary personal token. |

## Target architecture

```text
Browser user
  -> Flask app (Srini Free Edition)
       -> FastMCP app (Srini Free Edition), forwarding the Free-workspace user token
            -> Lakebase PostgreSQL (_srini operational tables and rate ledger)
            -> Massive API (only after Lakebase quota acquisition)
            -> paid data workspace SQL + AI Search via MCP-specific OAuth M2M identity
       -> paid data workspace usage Gold tables via frontend-specific OAuth M2M identity

Paid data workspace
  -> Jobs, Spark pipelines, UC tables, SQL Warehouse, AI Search, Lakehouse Sync,
     activity analytics, and Supervisor remain here
  -> Supervisor -> governed UC HTTP/MCP connection -> Free Edition FastMCP app
     only if the cross-workspace app authentication proof passes
```

The browser and frontend-to-MCP path retains user identity because both apps are
in the same Free Edition workspace. Paid data reads use service identity and are
shared-data reads; Lakebase writes continue to use the trusted forwarded email
for row ownership, confirmation, idempotency, and audit attribution. The UI and
trace documentation must disclose this split execution model.

## Required implementation changes

### Deployment boundary

- Keep the existing data-plane bundle on `dataexpertio_srini`.
- Remove the two `.app.yml` resources from that bundle's deployment surface so
  a normal data deployment can never try to create an app there.
- Create an independent Free Edition app deployment configuration or a
  deterministic direct-CLI deployment workflow for `dashboard/` and
  `mcp_server/`. Every command must specify `--profile "Srini Free Edition"`.
- Validate the data bundle against `dataexpertio_srini` and the app deployment
  configuration against `Srini Free Edition` independently.
- Bind the frontend to the MCP app as a same-workspace Databricks app resource
  where supported; retain user-token forwarding so the MCP receives trusted
  end-user identity.

### Data-plane authentication

Introduce an explicit client factory for the paid workspace rather than using
ambient `Config()` or the Free Edition user token:

| Variable | Purpose | Handling |
|---|---|---|
| `DATA_WORKSPACE_HOST` | Paid workspace host | Non-secret environment value |
| `DATA_WORKSPACE_WAREHOUSE_ID` | Existing serverless warehouse | Non-secret environment value |
| `DATA_WORKSPACE_CLIENT_ID` | App-specific paid-workspace OAuth client | Free Edition secret resource or protected configuration |
| `DATA_WORKSPACE_CLIENT_SECRET` | App-specific paid-workspace OAuth secret | Free Edition secret resource only |
| `SIGNAL_DESK_VECTOR_SEARCH_INDEX` | Existing paid-workspace AI Search index | Non-secret environment value |

- `mcp_server/lakehouse_market.py` must use the MCP bridge identity for SQL.
- `mcp_server/research_search.py` must use the MCP bridge identity for AI
  Search. It must no longer interpret a Free Edition user token as a paid
  workspace credential.
- `dashboard/analytics_client.py` must use the frontend bridge identity for the
  paid SQL Warehouse instead of the Free app's ambient service principal.
- Tests must prove host selection, OAuth M2M configuration, credential
  separation, no token logging, and rejection of missing/partial configuration.

The MCP bridge principal needs only warehouse use, read access to the market
tables, and AI Search query access. The frontend bridge principal needs only
warehouse use and read access to the five Gold activity tables. Neither needs
Unity Catalog write access.

### Free Edition secrets and external services

Create Free Edition secret resources for each app without copying values into
source or documentation:

- MCP: Massive API key, Lakebase URL, MCP paid-workspace client ID/secret.
- Frontend: Lakebase URL, frontend paid-workspace client ID/secret.

The direct Lakebase URL remains the shared operational data path. This preserves
existing `_srini` ownership, CDC sources, idempotency records, and the
cross-host Massive quota ledger. If the Free Edition egress probe cannot reach
Lakebase, stop: duplicating the operational database in Free Edition would break
CDC, identity isolation, and cross-host rate coordination.

### Identity and authorization

- Trust only Free Edition proxy headers for the signed-in browser identity.
- Forward the Free Edition user token only from frontend to MCP in the same
  workspace.
- Never forward that token to `dataexpertio_srini`; official Databricks
  guidance states it is scoped to the app's workspace.
- Use distinct paid-workspace M2M identities for MCP and frontend shared-data
  reads.
- Continue enforcing user ownership in Lakebase from the trusted email, and
  continue pseudonymizing analytics/traces.
- Grant demo users `CAN USE` on both Free Edition apps. Grant management only to
  the deployer.

## Implementation and test sequence

Each unit is independently stoppable and testable. Do not proceed past a failed
gate.

### Unit 1 — Free Edition preflight

1. Renew OAuth for `Srini Free Edition`.
2. Verify the expected user, workspace host, Apps availability, app quota,
   secret support, and existing resources.
3. Record only sanitized metadata.

Acceptance: explicit-profile identity and read-only Apps inventory succeed.

### Unit 2 — outbound connectivity spike

Deploy a minimal temporary probe or add a non-secret diagnostic command that
tests DNS/TCP/TLS only for:

- `dbc-7b106152-caf3.cloud.databricks.com:443`;
- the configured Lakebase host on port 5432; and
- the Massive API host on port 443.

Do not print credentials or send a Massive request during this probe.

Acceptance: paid-workspace HTTPS and Lakebase TLS succeed. Massive HTTPS is
required only for interactive fallback and the cross-host quota test. If Free
Edition blocks egress, complete LinkedIn verification if available and retry;
otherwise use the Render deployment fallback allowed by the capstone.

### Unit 3 — paid-workspace bridge identities

1. Have the paid-workspace administrator create two OAuth M2M service
   principals, one per app.
2. Grant the MCP identity only SQL/market/AI Search read permissions.
3. Grant the frontend identity only SQL/Gold analytics read permissions.
4. Store credentials as separate Free Edition secrets and verify them with a
   bounded `SELECT 1`/index metadata call without disclosure.

Acceptance: each identity can perform only its intended read and fails the
other app's or any write permission checks.

### Unit 4 — client refactor and local tests

1. Add a fail-closed paid-workspace client factory.
2. Refactor MCP SQL and AI Search adapters.
3. Refactor frontend analytics SQL.
4. Preserve the same-workspace frontend-to-MCP user-token path.
5. Update configuration, security disclosures, unit tests, and smoke harnesses.

Acceptance: full local tests and Ruff pass; tests demonstrate that the Free
user token never reaches paid-workspace clients.

### Unit 5 — split deployment configuration

1. Separate the data and app deployment surfaces.
2. Replace Free app references to paid-local warehouse/table/index resources
   with the new secret/non-secret cross-workspace contract.
3. Add the same-workspace MCP app binding to the frontend.
4. Strictly validate each deployment configuration with its explicit profile.

Acceptance: the data plan contains no app create/update, and the Free Edition
plan contains no jobs, pipelines, paid warehouse, paid UC table, or paid AI
Search resource creation.

### Unit 6 — deploy and accept FastMCP

Deploy MCP first. Run health, nine-tool discovery, governed SQL retrieval,
semantic retrieval, reversible write/idempotency, trace reconciliation,
two-principal isolation, and simultaneous paid Job/Free MCP quota acceptance.

Acceptance: all prepared Phase 5 tests pass and the fifth shared Massive
acquisition waits for the rolling-window slot.

### Unit 7 — deploy and accept Flask frontend

Bind the MCP app, deploy the frontend, then run authenticated browser, security
header, request-ID, research/evidence, action/reload, analytics, failure-state,
and two-principal tests.

Acceptance: a controlled action reaches Lakebase and later appears in the paid
workspace Phase 6 Gold analytics screen with measured freshness.

### Unit 8 — paid Supervisor integration

Attempt a governed paid-workspace UC HTTP/MCP connection to the Free MCP app
using a durable supported OAuth flow. Never use a committed or long-lived
personal token.

Acceptance: all ten captured Phase 7 cases pass with identity and confirmation
evidence. If durable cross-account app authentication is unavailable in Free
Edition, implement the same nine contracts as paid-workspace governed UC
function tools for the Supervisor while retaining the Free MCP service for the
frontend.

### Unit 9 — release operations

- Restart both Free Edition apps immediately before acceptance/demo because
  Free Edition apps automatically stop after 24 hours.
- Capture sanitized deployment IDs, URLs, timestamps, and evidence.
- Update the architecture diagram to show the two workspaces and M2M bridge.
- Re-run all tests, strict validations, and the release checklist.

## Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| Free Edition egress blocks paid workspace, Lakebase, or Massive | Critical | Run Unit 2 first; use LinkedIn verification if available; fall back to Render rather than duplicating data. |
| Loss of paid-workspace per-user UC enforcement | High | Use read-only, least-privilege app-specific M2M principals; retain Lakebase ownership enforcement and disclose shared-data execution. |
| Supervisor cannot authenticate to Free MCP durably | High | Prove before Supervisor deployment; fall back to paid-workspace UC function tools, not a personal bearer token. |
| Free apps stop after 24 hours | Medium | Add restart/readiness steps to the demo runbook and monitor both apps before the demo. |
| Bundle accidentally deploys resources to the wrong workspace | High | Separate deployment surfaces and require explicit profiles plus plan-content tests. |
| Shared Massive free-plan budget is exceeded across workspaces | High | Keep the already-applied Lakebase transaction-lock ledger and complete simultaneous Job/MCP acceptance before enabling fallback traffic. |
| Credential duplication across app hosts | High | Use separate OAuth clients per app, Free Edition secret resources, rotation, bounded scopes, and no credential output. |

## Rollback

The data plane does not move. If any Free Edition gate fails, stop/delete only
the two Free Edition app deployments and revoke their two paid-workspace OAuth
secrets. Existing jobs, pipelines, UC data, AI Search, Lakebase tables,
migrations, and CDC configuration remain untouched. Do not drop or recreate
Lakebase schemas or `_srini` tables.

## Authoritative references

- [Databricks Apps authorization](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth)
- [Databricks App resources](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/resources)
- [Databricks app-to-app resources](https://docs.databricks.com/gcp/en/dev-tools/databricks-apps/apps-resource)
- [Calling a Databricks App with OAuth](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/connect-local)
- [Databricks Free Edition limitations](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations)
- [Databricks Apps networking](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/networking)
- [Unity Catalog HTTP connections and OAuth](https://docs.databricks.com/aws/en/query-federation/http)
