# Signal Desk Capstone Demo Checklist

Updated: 2026-10-01

Do not mark a gate complete from local tests alone. Record sanitized run IDs,
table counts, timestamps, and screenshots; never capture secrets, tokens,
connection URLs, direct email values, or user-authored note/report bodies.

## A. Deployment gates

- [x] Renew OAuth for explicit profile `dataexpertio_srini`; confirmed
  `malyalasrinivas@gmail.com` on the intended workspace and passed strict
  development bundle validation on 2026-09-21.
- [x] Reauthenticate `dataexpertio_srini` and complete ADR 0007 Gate 0 discovery
  without recording credentials. The existing secret maps to shared project
  `summer-bootcamp-2026-v2`; no Lakebase UC catalog is registered.
- [x] Record the Render decision: all processing/data resources remain under
  `dataexpertio_srini`; only FastMCP and Flask move to two Render web services.
- [x] Add the two-service `render.yaml`; validate build/start commands, `$PORT`,
  health checks, Linux/Python 3.11 hash-pinned clean installs, exact-command
  local process starts, and `sync: false` secret placeholders without deploying
  data resources from Render.
- [x] Create suffix-isolated Lakebase market and research serving targets in
  shared PostgreSQL schema `bootcamp_students`; only
  `market_history_serving_srini` and `research_documents_serving_srini` were
  created, both empty after setup.
- [x] Populate the Lakebase serving copies: 1,255,489 market rows and 393
  research rows, zero duplicate keys, expected primary/query indexes.
- [x] Record the accepted shared-classroom runtime constraint: application
  allowlists, ownership predicates, confirmation/idempotency, and two-real-
  principal isolation are the capstone boundary; no broader grant was added.
- [x] Publish and reconcile
  `bootcamp_students.student_sri.market_history_serving`: 1,255,489 source and
  target rows, zero duplicate `(ticker,trading_date)` keys, CDF and row tracking
  enabled.
- [x] Prove local market known-answer parity: the latest three AAPL rows matched
  UC on dates, OHLC, return, volatility, request ID, and freshness.
- [x] Do not promote Lakebase FTS: its 51-case Recall@5 was 0.7843 versus the
  0.85 minimum (MRR/nDCG 0.7843; zero provenance/filter failures). Keep AI
  Search active and retain the MCP workspace credential until an accepted
  research path replaces it. Track frontend Gold analytics separately.
- [x] Register the browser OIDC client; prove secure sessions, CSRF, logout, and
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
- [x] Run the Phase 5 post-deployment harness: health, nine-tool discovery,
  governed retrieval, semantic retrieval, opt-in reversible write,
  idempotent retry, and sanitized trace/event reconciliation.
- [x] Run simultaneous Job/MCP quota acceptance; prove acquisition five waits
  for the rolling window and no Massive request bypasses Lakebase.
- [x] Configure the five Lakebase Lakehouse Sync histories in the UI.
- [x] Deploy/run the activity analytics pipeline; the controlled sequence
  reconciled 34 Bronze rows to 26 effective Silver rows and exact Gold metrics;
  maximum reported source latency was 85 seconds.
- [x] Prove a durable paid-workspace UC HTTP/MCP authentication flow to the
  Render MCP service using a separate machine credential or supported OAuth M2M
  flow, never a personal token or model-supplied identity.
- [x] Deploy the Supervisor, wait for its serving endpoint to become online,
  capture all ten Phase 7 cases, and pass `tools/phase7_agent_eval.py`.
- [x] Deploy the frontend on Render Free with OIDC and signed MCP assertions;
  health, login/callback/session, security headers, fail-closed routes, and the
  signed MCP boundary, five Gold reads, controlled CDC refresh, and
  authenticated workflow pass under the approved shared-MCP-principal
  exception.
- [x] Prove two real principals see isolated watchlists, notes, reports, and
  traces through the complete frontend → agent → MCP path.
- [ ] Upgrade both Render services to the smallest paid tier. Explicitly
  deferred by owner instruction on 2026-10-01; both services remain verified
  on Free and must be pre-warmed before the demo. No paid-tier change was made.

## B. Five-minute core workflow

- [x] Open the authenticated frontend; show the request ID without exposing a token.
- [x] Ask for AAPL 30-day performance; point out ticker, lookback, source and as-of date.
- [x] Compare two companies on one shared window; show bounded, like-for-like data.
- [x] Ask a filing/news thesis question; open an evidence card with title, type, URL and date.
- [x] Request a watchlist add. Demonstrate that the agent asks for confirmation before writing.
- [x] Confirm once; show the updated watchlist. Retry the exact idempotency key and show no duplicate.
- [x] Save one confirmed research note or report; show ownership-bound persistence without displaying sensitive text in analytics.
- [x] Show the corresponding pseudonymous Silver activity and Gold usage metric after sync.

## C. Big Data and engineering proof

- [x] Query `gold_market_data_coverage`; show 81 complete dates.
- [x] Show 1,255,489 unique Silver `(ticker,trading_date)` rows and 188 quarantines from 1,255,677 Bronze rows.
- [x] Show structured market/XBRL data, semi-structured source JSON, and unstructured filing/news chunks.
- [x] Show a cached ingestion rerun with zero external API calls.
- [x] Show the cross-host Massive ledger without revealing request details or credentials.
- [x] Show a source URL/content hash for retrieved research and explain why semantic evidence does not supply exact financial values.

## D. Negative and recovery checks

- [x] Invalid ticker returns a safe correction and no invented company/price.
- [x] Plan-restricted fundamentals are labeled unavailable, never zero.
- [x] Missing identity fails closed; no demo identity fallback exists.
- [x] Unconfirmed note/report/watchlist request makes no write call.
- [x] Corrupt/unavailable limiter state prevents the external Massive call.
- [x] Analytics contains no direct email, token, API key, connection URL, or authored research body.
- [x] Cleanup all disposable acceptance notes, reports, tickers, empty
  watchlists, and idempotency records; retain users plus sanitized traces,
  quota rows, and evidence.

## E. Submission package

- [x] Re-run the full local test suite and Ruff; 266 tests and Ruff pass at the
  2026-10-01 P6 release checkpoint.
- [x] Run strict data-bundle validation with explicit profile
  `dataexpertio_srini`; validate the Render Blueprint and inspect both deployment
  surfaces for cross-target resources. Target `dev` and Render reproducibility
  validation passed on 2026-10-01.
- [x] Confirm the current data dictionary, tool/API reference, traceability
  matrix, status tracker, Render deployment guide, proposal, and diagram agree
  on the split-host deployment contract.
- [x] Export the final architecture diagram as an 1800×1120 PNG and open it for
  visual QA; retain the editable SVG source alongside it.
- [x] Verify tracked repository files and sanitized acceptance output contain no
  credentials or sensitive runtime artifacts; `tools/check_no_secrets.py`
  passes and generated credentials remain under ignored `build/render-secrets`.
- [x] Verify both public health endpoints return 200, both Render services are
  Live on Free, the Supervisor endpoint is READY, and the 10/10 evaluation
  remains green. Evidence: ignored
  `build/acceptance/p6-release-readiness-2026-10-01.json`.
