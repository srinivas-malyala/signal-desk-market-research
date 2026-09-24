# Render deployment implementation plan

Updated: 2026-09-24

## Decision

Deploy the existing Flask frontend and FastMCP server as two separate Render Python web services.
Use Render Free while implementing and testing, then upgrade both
services to the smallest paid web-service plan for the final acceptance and
demo month. At current published pricing, the expected temporary hosting cost
is approximately $14 for that month.

All Spark jobs, Lakeflow pipelines, Unity Catalog tables, SQL Warehouse, AI
Search, Lakehouse Sync, analytics, and Supervisor processing remain in the
workspace selected by `dataexpertio_srini`. The existing Lakebase database and
`_srini` tables remain the operational store. No data is copied to Render.

This decision supersedes the proposed `Srini Free Edition` Databricks Apps
deployment in `docs/SPLIT_WORKSPACE_APP_DEPLOYMENT_PLAN.md`.

## Why two services

Keeping Flask and FastMCP separate preserves the existing trust and test
boundaries and avoids combining a WSGI frontend and ASGI MCP server during a
late deployment phase. It costs one additional small Render service during the
final month, but substantially reduces implementation and regression risk.

Render Free is acceptable for development, but both services can sleep after
inactivity and share the workspace's free instance-hour allowance. Upgrade both
before final acceptance so frontend-to-MCP calls do not encounter sequential
cold starts. Downgrade or suspend them after the capstone demonstration.

## Target architecture

```text
Browser
  -> Render Flask frontend
       -> OIDC login and secure session
       -> short-lived signed user assertion
       -> Render FastMCP service
            -> Lakebase (_srini operational state, audit, idempotency, quota)
            -> Massive API after Lakebase quota acquisition
            -> paid Databricks SQL and AI Search via MCP OAuth M2M identity
       -> paid Databricks Gold analytics via frontend OAuth M2M identity

Paid Databricks workspace (dataexpertio_srini)
  -> Jobs, pipelines, UC, SQL Warehouse, AI Search, Lakehouse Sync, analytics
  -> Supervisor -> UC HTTP/MCP connection -> Render FastMCP
```

Render is only the presentation/tool-serving plane. Paid Databricks remains the
governed data and processing plane.

## Authentication and trust model

### Browser to frontend

Use standards-based OIDC rather than passwords or a demo identity. The initial
provider may be Google because the current development identity is a Google
account, but the implementation must use generic configuration names:

- `OIDC_ISSUER_URL`
- `OIDC_CLIENT_ID`
- `OIDC_CLIENT_SECRET`
- `OIDC_REDIRECT_URI`
- `FLASK_SESSION_SECRET`
- optional `ALLOWED_USER_EMAILS` for a bounded capstone demo

The frontend must use state and nonce validation, secure/HTTP-only/SameSite
cookies, session rotation after login, CSRF protection on writes, bounded
session lifetime, and an explicit logout route. The authenticated OIDC subject
and verified email replace Databricks `X-Forwarded-*` headers on Render.

### Frontend to MCP

The frontend signs a short-lived asymmetric JWT for each MCP request. The
assertion contains only bounded claims:

- issuer and audience;
- stable OIDC subject and verified email;
- issued-at and expiry no more than 60 seconds apart;
- unique token ID; and
- request/correlation ID.

The frontend stores the private signing key; MCP receives only the public key.
MCP validates signature, issuer, audience, time bounds, and claim shape before
establishing trusted identity. It must ignore `X-Forwarded-Email`, tool
arguments, query parameters, and request bodies as identity sources when
`SIGNAL_DESK_IDENTITY_MODE=render`.

### Supervisor to MCP

Create a separate high-entropy machine bearer credential for the paid
workspace UC HTTP/MCP connection. MCP maps that credential to one fixed,
configured service subject; the model never supplies an email or owner. Rotate
the credential after acceptance. If UC HTTP connections support a compatible
OAuth flow for the deployed endpoint, prefer OAuth M2M over the static bearer
credential.

### Render to paid Databricks

Create two paid-workspace OAuth M2M service principals:

| Principal | Minimum access |
|---|---|
| MCP bridge | `CAN_USE` on the existing SQL Warehouse; `USE CATALOG`, `USE SCHEMA`, and `SELECT` on governed market tables; query access to the existing AI Search index/endpoint |
| Frontend analytics bridge | `CAN_USE` on the warehouse; `USE CATALOG`, `USE SCHEMA`, and `SELECT` only on the five Phase 6 Gold usage tables |

Do not share one OAuth secret between services. Render environment secrets hold
`DATA_WORKSPACE_CLIENT_ID` and `DATA_WORKSPACE_CLIENT_SECRET`; source, logs,
traces, and browser responses must never contain them.

## Render service definitions

Add a root `render.yaml` Blueprint containing two Python web services.

### MCP service

- Root/source: `mcp_server/` plus explicitly packaged shared modules.
- Build: install the locked MCP requirements.
- Start: production ASGI command bound to `0.0.0.0:$PORT`.
- Health check: `/health`.
- Secrets: Lakebase URL, Massive key, MCP Databricks M2M credentials, frontend
  assertion public key, and Supervisor machine credential.
- Non-secrets: paid workspace host, warehouse ID, UC namespace, AI Search index,
  identity mode, contract version, and rate-limit requester.

### Frontend service

- Root/source: `dashboard/` plus explicitly packaged shared modules.
- Build: install the locked dashboard requirements.
- Start: Gunicorn bound to `0.0.0.0:$PORT`.
- Health check: `/healthz`.
- Secrets: Lakebase URL, frontend Databricks M2M credentials, OIDC client
  secret, Flask session secret, and assertion private key.
- Non-secrets: MCP HTTPS URL, OIDC issuer/client ID/redirect URI, paid workspace
  host/warehouse/UC namespace, analytics freshness threshold, and identity mode.

Blueprint entries must declare secret variables with `sync: false`; no secret
value belongs in `render.yaml`.

## Required code changes

### Shared runtime configuration

- Extend the runtime contract with `SIGNAL_DESK_HOSTING=local|databricks|render`
  and fail closed for unsupported or incomplete modes.
- Add a paid-workspace OAuth client factory shared by the MCP and frontend SQL
  adapters without sharing credentials.
- Redact the new credential/configuration names from logs and error responses.

### MCP

- Replace Databricks-only forwarded-header middleware with a pluggable trusted
  identity provider; retain the current provider for local regression tests.
- Add Render JWT verification and fixed Supervisor machine identity.
- Refactor `lakehouse_market.py` and `research_search.py` to use explicit paid
  workspace OAuth M2M clients, never a browser token.
- Bind the production ASGI server to Render's `$PORT`.
- Keep Lakebase writes, confirmations, idempotency, pseudonymous traces, and the
  cross-host Massive limiter unchanged.

### Frontend

- Add OIDC login/callback/logout and secure server-side identity context.
- Replace the requirement for Databricks forwarded headers in Render mode.
- Sign a short-lived user assertion for every MCP request.
- Refactor `analytics_client.py` to use the frontend-specific paid-workspace
  OAuth M2M identity.
- Add CSRF enforcement for every consequential browser write.
- Bind Gunicorn to `$PORT` and retain all security/request-ID headers.
- Update execution disclosures: user identity comes from OIDC, shared data reads
  execute as least-privilege Databricks service principals, and writes are owned
  by the authenticated user in Lakebase.

### Databricks deployment boundary

- Keep the root DAB for data-plane resources under `dataexpertio_srini`.
- Exclude `resources/*.app.yml` from the active root bundle include surface so
  a routine bundle deploy cannot create Databricks Apps.
- Retain the old app YAML only as historical/reference configuration or remove
  it after Render acceptance.
- Add regression tests that the paid bundle contains no active app resources.

## Independently testable implementation sequence

### Unit 0 — branch and plan

- Work only on `codex/render-app-deployment`.
- Preserve the last verified paid data-plane commit as the rollback base.

Acceptance: clean branch and committed Render plan/tracker checkpoint.

### Unit 1 — packaging and local process compatibility

1. Inventory imports for each app and create deterministic service build
   contexts without copying credentials or test artifacts.
2. Add `$PORT` support and production start commands.
3. Add/verify public liveness endpoints that do not touch dependencies.
4. Run both services locally with dependency calls mocked.

Acceptance: both processes start independently, pass health checks, and stop
cleanly; build contexts contain no repository metadata or credentials.

### Unit 2 — paid-workspace M2M client boundary

1. Implement the explicit OAuth M2M client factory.
2. Refactor MCP SQL, MCP AI Search, and frontend analytics clients.
3. Add positive, missing-secret, wrong-host, wrong-scope, timeout, and redaction
   tests.
4. Provision separate service principals and grant least privilege.

Acceptance: bounded `SELECT 1`, known-answer market retrieval, AI Search query,
and Gold analytics query succeed with the intended principal; cross-principal
and write attempts fail.

### Unit 3 — Render identity and request security

1. Implement generic OIDC login/session/logout for Flask.
2. Implement short-lived asymmetric assertions from frontend to MCP.
3. Implement MCP validation and fixed Supervisor machine identity.
4. Add CSRF protection and preserve idempotency/request IDs.

Acceptance: valid two-user flows pass; expired, replayed, wrong-audience,
tampered, missing, body-supplied, and forwarded-header identities fail closed.

### Unit 4 — Render Blueprint and deployment separation

1. Add `render.yaml` with both services and secret placeholders only.
2. Exclude Databricks App resources from the active data bundle.
3. Add static tests for start commands, ports, health paths, secret placeholders,
   and absence of Databricks Apps from the data plan.
4. Run strict data-bundle validation with `dataexpertio_srini`.

Acceptance: Render definitions validate; the Databricks deployment plan changes
no app resource and retains all jobs/pipelines/data resources.

### Unit 5 — Render Free connectivity spike

Deploy MCP first on Render Free and test only sanitized outcomes for:

- paid Databricks workspace OAuth/token acquisition and SQL;
- AI Search;
- Lakebase TLS/PostgreSQL;
- Massive HTTPS without consuming an unnecessary API request; and
- dependency installation/build behavior.

Acceptance: every required outbound path succeeds, and no secret appears in
logs or responses. If Lakebase or Databricks requires an allowlist, use Render's
documented regional outbound ranges.

### Unit 6 — MCP deployment acceptance

Run health, nine-tool discovery, known-answer/freshness, semantic retrieval,
reversible confirmed writes, exact idempotent replay, changed-payload rejection,
bounded trace reconciliation, and simultaneous paid Job/Render MCP quota tests.

Acceptance: the prepared Phase 5 harness passes and acquisition five waits for
the shared Lakebase rolling-window slot.

### Unit 7 — frontend deployment acceptance

Deploy the frontend on Render Free, configure OIDC redirect URLs, then run
browser accessibility/security, research/evidence, confirmations, saved-history
reload, analytics, failure states, and two-real-principal isolation.

Acceptance: one controlled action is owned by the correct Lakebase user and
later appears in Phase 6 Gold analytics with measured freshness.

### Unit 8 — Supervisor integration

Create the paid-workspace UC HTTP/MCP connection to Render using the separate
machine credential or supported OAuth M2M. Deploy the Supervisor and capture
all ten Phase 7 evaluation cases.

Acceptance: deterministic evaluation passes; the model cannot select or forge
an owner identity; confirmations and idempotency remain enforced by MCP.

### Unit 9 — final paid demo window

1. Upgrade both Render services to the smallest paid plan.
2. Re-run health, end-to-end, security, quota, CDC latency, and performance
   acceptance without cold starts.
3. Update and export the architecture diagram.
4. Record sanitized URLs, deploy IDs, commit SHA, timestamps, and test totals.
5. After submission/demo, suspend, downgrade, or delete the Render services and
   revoke/rotate all deployment credentials.

Acceptance: the complete release checklist passes on the exact deployed commit.

## Cost and budget controls

| Stage | Services | Expected hosting cost |
|---|---|---|
| Development | Two Render Free web services | $0, subject to sleep and shared free hours |
| Final acceptance/demo month | Two smallest paid web services | Approximately $14 total at current $7/service pricing |
| After demo | Suspend/downgrade/delete | Return to $0 when services are no longer needed |

Render hosting does not eliminate paid Databricks query consumption. Continue
bounded SQL, hard row limits, short timeouts, no polling, stale-result caching,
and Lakebase reuse so the app does not create unnecessary warehouse or AI
Search activity.

## Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| Render Free double cold start breaks acceptance timeouts | High | MCP-first deployment and warm-up during development; upgrade both services for final acceptance. |
| Replacing Databricks proxy identity introduces impersonation risk | Critical | OIDC plus short-lived asymmetric assertions; ignore all model/body/header identity claims; negative tests. |
| Public MCP endpoint is abused | High | Mandatory auth except health, bounded payloads, rate limits, no CORS, safe errors, Render/UC credentials separated. |
| Paid workspace M2M principals are overprivileged | High | Separate principals, explicit grants, negative permission tests, credential rotation after demo. |
| Lakebase is exposed to broad Render egress ranges | High | Require TLS, least-privilege database role, existing ownership predicates, bounded pools; use allowlisting where practical. |
| 512 MB service memory is insufficient | Medium | Measure peak memory during the Free spike; upgrade compute only if evidence requires it. |
| Two-service cost persists after demo | Medium | Add dated teardown/rotation checklist and suspend immediately after final evidence capture. |
| Data bundle still contains active Databricks App resources | High | Exclude app YAML from active includes and test the resolved deployment plan. |

## Rollback

Render is stateless. A failed deployment is rolled back to the previous Render
commit or both services are suspended. Revoke the two paid-workspace OAuth
secrets and the Supervisor credential. Do not modify or delete Lakebase schemas,
`_srini` tables, Unity Catalog tables, jobs, pipelines, AI Search, or Lakehouse
Sync. The paid data-plane rollback base remains commit `43c1951`.

## Authoritative references

- [Render pricing](https://render.com/pricing)
- [Render Free limitations](https://render.com/docs/free)
- [Render Flask deployment](https://render.com/docs/deploy-flask)
- [Render web services and environment secrets](https://render.com/docs/web-services)
- [Render health checks](https://render.com/docs/health-checks)
- [Render outbound IP ranges](https://render.com/docs/outbound-ip-addresses)
- [Databricks Apps cross-workspace authorization constraint](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth)
- [Databricks OAuth M2M authentication](https://docs.databricks.com/aws/en/dev-tools/cli/authentication)
- [Unity Catalog HTTP connections](https://docs.databricks.com/aws/en/query-federation/http)
