# Render deployment implementation plan

Updated: 2026-10-07

> **Final deployed outcome:** ADR 0007 moved operational state and market reads
> to Lakebase, but the evaluated Lakebase research FTS path was not promoted
> because Recall@5 was 0.7843 against the 0.85 minimum. Research therefore
> remains on the accepted Databricks AI Search v2 index, and both Render services
> retain the owner-approved shared `dbx-ai-de-aug26` workspace identity. The
> Lakebase-only plan is retained as evaluation history, not the current runtime.

## Implementation status

Units 1–7 are implemented and accepted on the deployed two-service Render
architecture: `$PORT`/health behavior, data-bundle separation, generic OIDC,
secure sessions/CSRF, signed frontend identity, fixed Supervisor identity,
Lakebase serving, AI Search research retrieval, Gold analytics, and confirmed
actions. The current local suite passes 285 tests; the release evidence also
records Ruff, reproducibility, credential-scan, public-health, two-principal,
cross-host quota, and Supervisor 10/10 acceptance.

Strict post-change validation of the data-only bundle passed on 2026-09-24 with
explicit profile `dataexpertio_srini`, authenticated as
`malyalasrinivas@gmail.com`. An `invalid_client` failure encountered during the
initial cutover was historical and has been resolved; the final Render services
use the owner-approved shared M2M identity. Operational procedures remain in
`docs/RENDER_DEPLOYMENT_RUNBOOK.md`.

## Decision

Deploy the existing Flask frontend and FastMCP server as two separate Render Python web services.
Use Render Free for implementation, acceptance, and the current demo-readiness
checkpoint. A paid upgrade remains an owner-controlled optional change and was
explicitly deferred on 2026-10-01. Pre-warm MCP and frontend before a live demo.

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
inactivity and share the workspace's free instance-hour allowance. The owner
deferred a paid upgrade after final acceptance; pre-warm MCP and then frontend
before a live demonstration. Suspend them after the capstone demonstration when
they are no longer needed.

## Target architecture

```text
Browser
  -> Render Flask frontend
       -> OIDC login and secure session
       -> short-lived signed user assertion
       -> Render FastMCP service
            -> Lakebase (_srini operational state, audit, idempotency, quota)
            -> Massive API after Lakebase quota acquisition
            -> Lakebase serving tables for bounded market reads
            -> Databricks AI Search v2 for accepted research retrieval
       -> paid Databricks Gold analytics via the shared OAuth M2M identity

Paid Databricks workspace (dataexpertio_srini)
  -> Jobs, pipelines, UC, SQL Warehouse, AI Search, Lakehouse Sync, analytics
  -> triggered Unity Catalog-to-Lakebase serving-table synchronization
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

### Render services to Lakebase and paid Databricks

Both Render services use `LAKEBASE_URL` for bounded operational or serving
access. Market retrieval is Lakebase-primary. Research remains on Databricks AI
Search because the Lakebase FTS candidate failed its promotion threshold, so
the MCP retains workspace credentials. The frontend uses the same workspace
identity for the five bounded Gold analytics reads.

The owner approved shared use of the `dbx-ai-de-aug26` OAuth M2M identity by MCP
and frontend for this capstone. The current classroom Lakebase `student` role is
broader than the production ideal; allowlisted identifiers, `_srini` ownership
predicates, and bounded queries are the accepted capstone boundary. A dedicated
least-privilege native database role remains production hardening.

| Principal | Minimum access |
|---|---|
| MCP runtime | Shared `dbx-ai-de-aug26` workspace identity for AI Search plus bounded Lakebase access to owned `_srini` operational and market-serving tables |
| Frontend analytics bridge | Shared `dbx-ai-de-aug26` identity with `CAN_USE` on the warehouse and bounded reads of the five Phase 6 Gold usage objects; Lakebase access for user-owned history |

Source, logs, traces, and browser responses must never contain the Lakebase URL,
native password, frontend OAuth credential, or generated tokens.

## Render service definitions

Add a root `render.yaml` Blueprint containing two Python web services.

### MCP service

- Root/source: `mcp_server/` plus explicitly packaged shared modules.
- Build: install the locked MCP requirements.
- Start: production ASGI command bound to `0.0.0.0:$PORT`.
- Health check: `/health`.
- Secrets: Lakebase URL, Massive key, shared workspace M2M credentials,
  frontend assertion public key, and Supervisor machine credential.
- Non-secrets: serving backend flags, identity mode, contract version,
  rate-limit requester, workspace host, and accepted AI Search v2 index.

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
- Keep paid-workspace authentication isolated to the frontend analytics client;
  do not share its credentials with MCP.
- Redact the new credential/configuration names from logs and error responses.

### MCP

- Replace Databricks-only forwarded-header middleware with a pluggable trusted
  identity provider; retain the current provider for local regression tests.
- Add Render JWT verification and fixed Supervisor machine identity.
- Add feature-flagged Lakebase adapters for `lakehouse_market.py` and
  `research_search.py`; preserve the current implementations as rollback paths
  until their independent acceptance gates pass.
- Bind the production ASGI server to Render's `$PORT`.
- Keep Lakebase writes, confirmations, idempotency, pseudonymous traces, and the
  cross-host Massive limiter unchanged.

### Frontend

- Add OIDC login/callback/logout and secure server-side identity context.
- Replace the requirement for Databricks forwarded headers in Render mode.
- Sign a short-lived user assertion for every MCP request.
- Refactor `analytics_client.py` to use the explicit paid-workspace OAuth M2M
  identity; the owner later accepted `dbx-ai-de-aug26` for both services.
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

### Unit 2 — Lakebase serving boundary

1. Reauthenticate `dataexpertio_srini` and discover the exact Lakebase project,
   branch, database, catalog, and permissions.
2. Publish one narrow market serving Delta table and atomically copy it plus
   `research_search_documents` into shared PostgreSQL schema
   `bootcamp_students`, using only `_srini` target names.
3. Add least-privilege PostgreSQL grants and query indexes.
4. Implement feature-flagged MCP adapters; keep frontend analytics isolated.
5. Add positive, missing-secret, wrong-role, timeout, staleness, injection, and
   redaction tests.

Acceptance result: bounded market parity succeeded without workspace OAuth,
serving copies reconciled to Delta, and forbidden PostgreSQL writes failed.
Research did not cut over because the complete 51-case Lakebase FTS evaluation
missed the Recall@5 promotion threshold; AI Search remains deployed.

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

- Lakebase operational and serving-table TLS/PostgreSQL access;
- market known-answer parity and research retrieval quality;
- Massive HTTPS without consuming an unnecessary API request; and
- dependency installation/build behavior.

Acceptance: every required outbound path succeeds, no secret appears in logs or
responses, and the Lakebase market request path makes no workspace OAuth call. If
Lakebase requires an allowlist, use Render's documented regional outbound
ranges.

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

### Unit 9 — final demo window

1. Keep both Render services on Free unless the owner separately authorizes an
   upgrade; pre-warm MCP first and frontend second.
2. Re-run health, end-to-end, security, quota, CDC latency, and performance
   acceptance after any later tier change.
3. Reconfirm the exported architecture diagram against the live deployment IDs and URLs.
4. Record sanitized URLs, deploy IDs, commit SHA, timestamps, and test totals.
5. After submission/demo, suspend, downgrade, or delete the Render services and
   revoke/rotate all deployment credentials.

Acceptance: the complete non-paid release checklist passes on the exact
deployed commits; any paid-tier evidence remains explicitly deferred.

## Cost and budget controls

| Stage | Services | Expected hosting cost |
|---|---|---|
| Development | Two Render Free web services | $0, subject to sleep and shared free hours |
| Optional owner-authorized paid window | Two smallest paid web services | Approximately $14 total at current $7/service pricing; currently deferred |
| After demo | Suspend/downgrade/delete | Return to $0 when services are no longer needed |

Lakebase market serving removes request-time SQL Warehouse consumption from the
market path. Research continues to consume Databricks AI Search because the FTS
candidate did not meet the quality gate; pipelines and triggered syncs also
continue to consume Databricks resources. Use bounded PostgreSQL reads,
triggered synchronization, hard limits, short timeouts, and explicit freshness
checks.

## Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| Render Free double cold start breaks acceptance timeouts | High | Warm MCP first and frontend second before the demo; upgrade only with separate owner authorization. |
| Replacing Databricks proxy identity introduces impersonation risk | Critical | OIDC plus short-lived asymmetric assertions; ignore all model/body/header identity claims; negative tests. |
| Public MCP endpoint is abused | High | Mandatory auth except health, bounded payloads, rate limits, no CORS, safe errors, and separate browser/Supervisor trust paths. |
| Lakebase runtime role is broader than the production ideal | High | Accepted for the classroom capstone with allowlists and ownership predicates; create a dedicated native role before production use. |
| PostgreSQL retrieval is weaker than accepted AI Search | High | Keep AI Search as the deployed research backend; Lakebase FTS remains unpromoted after the failed 51-case quality gate. |
| Managed synced-table setup needs a missing grant | Medium | Use the verified shared-schema PostgreSQL path and atomic direct publisher; do not broaden project permissions. |
| Lakebase is exposed to broad Render egress ranges | High | Require TLS, existing ownership predicates, bounded pools, and identifier allowlists; add a least-privilege database role before production and use network allowlisting where practical. |
| 512 MB service memory is insufficient | Medium | Measure peak memory during the Free spike; upgrade compute only if evidence requires it. |
| Two-service cost persists after demo | Medium | Add dated teardown/rotation checklist and suspend immediately after final evidence capture. |
| Data bundle still contains active Databricks App resources | High | Exclude app YAML from active includes and test the resolved deployment plan. |

## Rollback

Render is stateless. A failed Lakebase adapter is rolled back by restoring its
backend feature flag and redeploying the previous Render commit. Do not delete
the serving or operational `_srini` tables, Unity Catalog
tables, jobs, pipelines, SQL Warehouse, AI Search, or Lakehouse Sync during the
observation period. The paid data-plane rollback base remains commit `43c1951`.

## Authoritative references

- [Render pricing](https://render.com/pricing)
- [Render Free limitations](https://render.com/docs/free)
- [Render Flask deployment](https://render.com/docs/deploy-flask)
- [Render web services and environment secrets](https://render.com/docs/web-services)
- [Render health checks](https://render.com/docs/health-checks)
- [Render outbound IP ranges](https://render.com/docs/outbound-ip-addresses)
- [Databricks Apps cross-workspace authorization constraint](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth)
- [Databricks OAuth M2M authentication](https://docs.databricks.com/aws/en/dev-tools/cli/authentication)
- [Lakebase synced tables](https://docs.databricks.com/aws/en/oltp/projects/sync-tables)
- [Lakebase authentication](https://docs.databricks.com/aws/en/oltp/projects/authentication)
- [Unity Catalog HTTP connections](https://docs.databricks.com/aws/en/query-federation/http)
