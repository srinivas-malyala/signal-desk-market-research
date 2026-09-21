# Phase 8 — Frontend Databricks App

Updated: 2026-09-21

| Unit | Status | Evidence | Remaining gate |
|---|---|---|---|
| 8.1 Flask shell and authentication | Local hardening complete | Flask/Gunicorn retained; demo identity removed; forwarded email and user token required; health remains public; request IDs and security headers cover success/error responses; template escaping and startup configuration tested | Restore `dataexpertio_srini` OAuth, rerun strict bundle validation, bind the deployed MCP URL/resource, deploy the frontend, and run authenticated service-principal/user smoke tests |
| 8.2 Research and evidence workflow | Pending | Existing overview shell retained | Add question workflow, agent status, evidence cards, as-of metadata, and complete UI states |
| 8.3 Watchlists, notes, and reports | In progress | Existing add/remove UX retained; watchlist writes now cross a typed MCP abstraction with explicit confirmation, per-action idempotency, user-token auth, response bounds, and safe failures | Deployed write/reload acceptance; add note/report actions and migrate remaining direct overview reads behind authenticated services |
| 8.4 Usage analytics page | Pending | Phase 6.2 Gold contracts implemented locally | Add warehouse-backed analytics UI after Phase 6 deployment |

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

The browser generates one idempotency key per explicit add/remove action and
displays correlated safe errors. The existing read-only overview still queries
Lakebase directly so the current shell remains functional; moving those reads
behind authenticated service APIs is explicitly pending rather than being
misreported as complete.

## Local acceptance

Eighteen focused tests cover public health, missing email/token combinations,
body-supplied identity rejection, Jinja escaping, security headers, UUID request
IDs, invalid ticker/idempotency rejection, token/request-ID propagation into the
client abstraction, direct-write removal, dependency failure redaction, endpoint
TLS/configuration validation, confirmed MCP arguments, response size bounds,
oversized request rejection, and absence of forged forwarded identity headers.

The complete local suite passes 178 tests and whole-repository lint. Strict
bundle validation was attempted on 2026-09-21 with the required
`dataexpertio_srini` profile but could not refresh its expired OAuth token; this
is recorded as an external authentication gate, not as a validation success or
an application defect.
