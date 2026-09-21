# Phase 8 — Frontend Databricks App

Updated: 2026-09-21

| Unit | Status | Evidence | Remaining gate |
|---|---|---|---|
| 8.1 Flask shell and authentication | Local hardening complete; bundle validated | Flask/Gunicorn retained; demo identity removed; forwarded email and user token required; health remains public; request IDs and security headers cover success/error responses; template escaping and startup configuration tested; renewed OAuth identity and strict development bundle validation verified | Bind the deployed MCP URL/resource, deploy the frontend, and run authenticated service-principal/user smoke tests |
| 8.2 Research and evidence workflow | Local implementation complete | Authenticated MCP routes support bounded performance, 2–5 ticker comparison, and hybrid filing/news evidence; UI exposes progress, empty/error/partial/rate-limit states, source links, context labels, as-of metadata, limitations, execution identity, and disclaimer | Deploy MCP/frontend and run the browser evidence-source acceptance flow |
| 8.3 Watchlists, notes, and reports | Local core workflow complete | Confirmed add/remove, note save, and report save use one authenticated idempotent MCP call; browser confirmation/cancel behavior and user-owned reload views are implemented; watchlist/news overview reads now use MCP and read-only overview no longer creates users | Deployed write/reload/two-user acceptance; note deletion requires a future versioned MCP delete contract because MCP 1.0 intentionally exposes only nine tools |
| 8.4 Usage analytics page | Local implementation complete | Bounded app-auth SQL Warehouse client reads five Phase 6 Gold datasets; page shows contextual DAU, error rate, watchlist and save KPIs, exact tool usage/P95 table, source/freshness, service-principal execution, and empty/partial/stale/error states | Deploy Phase 6 pipeline and frontend, then prove a controlled MCP action appears with correct count and measured freshness |

## Local security contract

Every route except `/healthz` requires both `X-Forwarded-Email` and
`X-Forwarded-Access-Token`, which Databricks Apps supplies at the trusted proxy
boundary when user authorization is enabled. Missing, malformed, or partial
identity receives a correlated `401` response before Lakebase or MCP access.
Identity in JSON, query strings, or form values is never authoritative.

Every response, including authentication and dependency errors, receives a new
server-generated `X-Request-ID`, `Cache-Control: no-store`, a restrictive
Content Security Policy, HSTS, frame denial, MIME sniffing prevention, a
same-origin opener policy, a no-referrer policy, and disabled camera,
microphone, and geolocation permissions. Request bodies are capped at 32 KiB.
Unexpected failures return a generic message and retain only the request ID for
support correlation.

## MCP client boundary

`dashboard/mcp_client.py` defines the frontend watchlist contract independently
of FastMCP transport details. The production adapter:

- requires an HTTPS `MCP_SERVER_URL`, allowing HTTP only for loopback testing;
- authenticates with the forwarded user bearer token and never constructs
  forwarded identity headers;
- forwards the frontend request ID as MCP metadata;
- enforces a 1–60 second timeout and a 256 KB response limit;
- maps invalid transport, response, configuration, and tool failures into safe
  typed exceptions; and
- always sends `confirmed=true` plus an 8–128 character idempotency key for
  watchlist writes.

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

The analytics client uses SDK `Config()` for Databricks App service-principal
authentication and the warehouse ID supplied through `valueFrom`. All five
queries target fully qualified Gold tables, have hard row limits, and share a
256 KB response ceiling. The UI explicitly discloses service-principal query
execution because these are shared pseudonymous aggregates, not user-owned
operational rows. KPI cards include period context, source, and freshness;
exact tool counts and P95 latency use a table instead of an ornamental chart.

The complete local suite passes 207 tests and whole-repository lint. On
2026-09-21, OAuth for the required `dataexpertio_srini` profile was renewed,
the active identity was verified as `malyalasrinivas@gmail.com`, and strict
development bundle validation passed. Deployment still depends on the
administrator-managed MCP secret-resource binding.
