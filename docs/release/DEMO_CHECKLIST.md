# Signal Desk Capstone Demo Checklist

Updated: 2026-09-25

Do not mark a gate complete from local tests alone. Record sanitized run IDs,
table counts, timestamps, and screenshots; never capture secrets, tokens,
connection URLs, direct email values, or user-authored note/report bodies.

## A. Deployment gates

- [x] Renew OAuth for explicit profile `dataexpertio_srini`; confirmed
  `malyalasrinivas@gmail.com` on the intended workspace and passed strict
  development bundle validation on 2026-09-21.
- [x] Record the Render decision: all processing/data resources remain under
  `dataexpertio_srini`; only FastMCP and Flask move to two Render web services.
- [x] Add the two-service `render.yaml`; validate build/start commands, `$PORT`,
  health checks, Linux/Python 3.11 hash-pinned clean installs, exact-command
  local process starts, and `sync: false` secret placeholders without deploying
  data resources from Render.
- [ ] Prove Render egress to the paid workspace and Lakebase; Lakebase and
  Massive HTTPS are verified, but paid-workspace SQL/AI Search still fail with
  M2M `invalid_client`.
- [ ] Create two separate least-privilege paid-workspace OAuth M2M identities,
  store their credentials as distinct Render service secrets, and pass positive
  plus forbidden-permission tests.
- [ ] Register the browser OIDC client; prove secure sessions, CSRF, logout, and
  tampered/expired/missing short-lived MCP assertion rejection.
- [x] Select Google OIDC, fix the Render callback contract, generate a local-only
  3072-bit assertion key pair plus session/Supervisor secrets, record only their
  fingerprints, and prepare the per-service secret-entry checklist. Google
  client registration remains the external action in the item above.
- [x] Split data/app deployment surfaces and prove the paid DAB configuration contains no
  app changes while the Render Blueprint contains no jobs, pipelines, warehouse,
  UC table, or AI Search creation.
- [x] Apply checksum migration `0005`; verified
  `bootcamp_students.massive_api_attempts_srini` and its time index exist, the
  ledger records `0005`, and a second migration pass applies nothing.
- [x] Deploy the MCP service on Render Free; `https://signal-desk-mcp.onrender.com`
  is live and the accepted Supervisor-token deployment is `dep-darca5p7lnhs73cr1nig`.
- [ ] Run the Phase 5 post-deployment harness: health, nine-tool discovery,
  governed retrieval, semantic retrieval, opt-in reversible write,
  idempotent retry, and sanitized trace/event reconciliation.
- [ ] Run simultaneous Job/MCP quota acceptance; prove acquisition five waits
  for the rolling window and no Massive request bypasses Lakebase.
- [x] Configure the five Lakebase Lakehouse Sync histories in the UI.
- [x] Deploy/run the activity analytics pipeline; the controlled sequence
  reconciled 34 Bronze rows to 26 effective Silver rows and exact Gold metrics;
  maximum reported source latency was 85 seconds.
- [ ] Prove a durable paid-workspace UC HTTP/MCP authentication flow to the
  Render MCP service using a separate machine credential or supported OAuth M2M
  flow, never a personal token or model-supplied identity.
- [ ] Deploy the Supervisor, wait for its serving endpoint to become online,
  capture all ten Phase 7 cases, and pass `tools/phase7_agent_eval.py`.
- [ ] Deploy the frontend on Render Free with OIDC and signed MCP assertions;
  health, login/callback/session, security headers, fail-closed routes, and the
  signed MCP boundary pass. Paid-analytics M2M and the authenticated workflow
  still require acceptance.
- [ ] Prove two real principals see isolated watchlists, notes, reports, and
  traces through the complete frontend → agent → MCP path.
- [ ] Upgrade both Render services to the smallest paid tier for the final
  acceptance/demo month; record readiness and verify that no cold start affects
  the five-minute workflow. The planned runtime budget is approximately $14.

## B. Five-minute core workflow

- [ ] Open the authenticated frontend; show the request ID without exposing a token.
- [ ] Ask for AAPL 30-day performance; point out ticker, lookback, source and as-of date.
- [ ] Compare two companies on one shared window; show bounded, like-for-like data.
- [ ] Ask a filing/news thesis question; open an evidence card with title, type, URL and date.
- [ ] Request a watchlist add. Demonstrate that the agent asks for confirmation before writing.
- [ ] Confirm once; show the updated watchlist. Retry the exact idempotency key and show no duplicate.
- [ ] Save one confirmed research note or report; show ownership-bound persistence without displaying sensitive text in analytics.
- [ ] Show the corresponding pseudonymous Silver activity and Gold usage metric after sync.

## C. Big Data and engineering proof

- [ ] Query `gold_market_data_coverage`; show 81 complete dates.
- [ ] Show 1,255,489 unique Silver `(ticker,trading_date)` rows and 188 quarantines from 1,255,677 Bronze rows.
- [ ] Show structured market/XBRL data, semi-structured source JSON, and unstructured filing/news chunks.
- [ ] Show a cached ingestion rerun with zero external API calls.
- [ ] Show the cross-host Massive ledger without revealing request details or credentials.
- [ ] Show a source URL/content hash for retrieved research and explain why semantic evidence does not supply exact financial values.

## D. Negative and recovery checks

- [ ] Invalid ticker returns a safe correction and no invented company/price.
- [ ] Plan-restricted fundamentals are labeled unavailable, never zero.
- [ ] Missing identity fails closed; no demo identity fallback exists.
- [ ] Unconfirmed note/report/watchlist request makes no write call.
- [ ] Corrupt/unavailable limiter state prevents the external Massive call.
- [ ] Analytics contains no direct email, token, API key, connection URL, or authored research body.
- [ ] Cleanup all disposable acceptance users, memberships, notes, and reports; retain only sanitized evidence.

## E. Submission package

- [x] Re-run the full local test suite and Ruff; 241 tests and Ruff pass after
  the live Render diagnostic checkpoint (`9b3b176`).
- [x] Run strict data-bundle validation with explicit profile
  `dataexpertio_srini`; validate the Render Blueprint and inspect both deployment
  surfaces for cross-target resources. Data-only validation passed on 2026-09-24.
- [x] Confirm the current data dictionary, tool/API reference, traceability
  matrix, status tracker, Render deployment guide, proposal, and diagram agree
  on the split-host deployment contract.
- [x] Export the final architecture diagram as an 1800×1120 PNG and open it for
  visual QA; retain the editable SVG source alongside it.
- [x] Verify tracked repository files and sanitized acceptance output contain no
  credentials or sensitive runtime artifacts; `tools/check_no_secrets.py`
  passes and generated credentials remain under ignored `build/render-secrets`.
