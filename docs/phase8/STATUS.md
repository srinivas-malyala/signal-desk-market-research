# Phase 8 — Frontend Databricks App

Updated: 2026-09-24

| Unit | Status | Evidence | Remaining gate |
|---|---|---|---|
| 8.1 Flask shell and authentication | Render implementation locally accepted; deployment pending | Flask/Gunicorn retained; generic OIDC login/callback/logout; verified-email allowlist; secure bounded sessions; CSRF on writes; 60-second request-bound RS256 MCP assertions with MCP-session replay rejection; `$PORT`; public health; request IDs/security headers; Render ignores forwarded identity | Register OIDC redirect/client secrets, deploy to Render, and run authenticated/two-principal browser smoke tests |
| 8.2 Research and evidence workflow | Local implementation complete | Authenticated MCP routes support bounded performance, 2–5 ticker comparison, and hybrid filing/news evidence; UI exposes progress, empty/error/partial/rate-limit states, source links, context labels, as-of metadata, limitations, execution identity, and disclaimer | Deploy MCP/frontend and run the browser evidence-source acceptance flow |
| 8.3 Watchlists, notes, and reports | Local core workflow complete | Confirmed add/remove, note save, and report save use one authenticated idempotent MCP call; browser confirmation/cancel behavior and user-owned reload views are implemented; watchlist/news overview reads now use MCP and read-only overview no longer creates users | Deployed write/reload/two-user acceptance; note deletion requires a future versioned MCP delete contract because MCP 1.0 intentionally exposes only nine tools |
| 8.4 Usage analytics page | Render M2M implementation locally accepted; deployment pending | Bounded SQL Warehouse client reads five Phase 6 Gold datasets using the explicit frontend-specific M2M boundary; page shows contextual DAU, error rate, watchlist/save KPIs, exact usage/P95, source/freshness, service-principal execution, and empty/partial/stale/error states | Provision/grant the frontend M2M principal, deploy Phase 6/frontend, then prove a controlled MCP action appears with correct count and freshness |

## Local security contract

In Render mode, `/login` and `/oidc/callback` establish a bounded secure session
from a provider-verified email and subject; `/healthz` remains public. Every
application route requires that session, and every consequential request also
requires the session CSRF token. In retained Databricks compatibility mode, the
existing trusted proxy headers remain available. Render mode ignores those
headers. Missing, malformed, or partial identity receives a correlated `401`
before Lakebase or MCP access. Identity in JSON, query strings, form values, or
model arguments is never authoritative.

Every response, including authentication and dependency errors, receives a new
server-generated `X-Request-ID`, `Cache-Control: no-store`, a restrictive
Content Security Policy, HSTS, frame denial, MIME sniffing prevention, a
same-origin opener policy, a no-referrer policy, and disabled camera,
microphone, and geolocation permissions. Request bodies are capped at 32 KiB.
Unexpected failures return a generic message and retain only the request ID for
support correlation.

## MCP client boundary

`dashboard/mcp_client.py` defines the frontend watchlist contract independently
of FastMCP transport details. The current production adapter:

- requires an HTTPS `MCP_SERVER_URL`, allowing HTTP only for loopback testing;
- authenticates with either the retained Databricks bearer token or, in Render
  mode, a 60-second asymmetric signed identity assertion;
- forwards the frontend request ID as both HTTP correlation metadata and MCP metadata;
- enforces a 1–60 second timeout and a 256 KB response limit;
- maps invalid transport, response, configuration, and tool failures into safe
  typed exceptions; and
- always sends `confirmed=true` plus an 8–128 character idempotency key for
  watchlist writes.

For Render, the transport replaces the forwarded Databricks user bearer token
with a short-lived asymmetric JWT signed only by the frontend and verified by
MCP. The assertion binds issuer, audience, subject, email,
request ID, unique token ID, and an expiration of at most 60 seconds. Browser
tokens and OIDC client secrets will never cross the frontend-to-MCP boundary.

The browser generates one idempotency key per explicit add/remove/save action,
requires a visible confirmation, and displays correlated safe errors. Watchlist
and notable-news reads now use the authenticated MCP boundary. Saved-history
and sanitized-trace display remain bounded Lakebase reads until MCP gains a
versioned saved-history API; the read path no longer creates a user row.

## Research-screen design contract

The retained Flask app uses an analytic, stratified layout: bounded workflow
controls first, source/freshness-aware results second, then personal operational
state. Performance cards always show ticker, unit/window, as-of date, source,
and limitations. Comparisons share one time window. Evidence cards show source
type, ticker, date, context/similarity label, passage, and source URL. Loading,
empty, dependency error, partial comparison, stale/index-sync, and Massive
rolling-window states are visible text states rather than color alone. The
signed-in identity and authenticated-user execution disclosure remain visible.

## Local acceptance

Twenty-seven focused tests cover public health, missing email/token combinations,
body-supplied identity rejection, Jinja escaping, security headers, UUID request
IDs, invalid ticker/idempotency rejection, token/request-ID propagation into the
client abstraction, direct-write removal, dependency failure redaction, endpoint
TLS/configuration validation, confirmed MCP arguments, response size bounds,
oversized request rejection, and absence of forged forwarded identity headers.
They now also cover final-contract performance/comparison/evidence arguments,
input bounds, optional company context, and a distinct rate-limited response.
Confirmed note/report tests prove cancel/unconfirmed requests make no tool call,
and one accepted browser request maps to one idempotent MCP write.

The analytics client now uses a frontend-specific, least-privilege OAuth M2M
identity targeting the paid workspace in Render mode. All five
queries target fully qualified Gold tables, have hard row limits, and share a
256 KB response ceiling. The UI explicitly discloses service-principal query
execution because these are shared pseudonymous aggregates, not user-owned
operational rows. KPI cards include period context, source, and freshness;
exact tool counts and P95 latency use a table instead of an ornamental chart.

The complete local suite passes 231 tests and whole-repository lint. Render
packaging and identity/data-client refactors are implemented. OIDC registration,
paid-workspace M2M credentials/grants, Render-to-Lakebase/Databricks/Massive
connectivity, deployment, browser acceptance, and the final paid-service
readiness check remain gates. See `docs/RENDER_DEPLOYMENT_RUNBOOK.md`.
