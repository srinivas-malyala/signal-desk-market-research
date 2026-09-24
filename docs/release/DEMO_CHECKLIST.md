# Signal Desk Capstone Demo Checklist

Updated: 2026-09-24

Do not mark a gate complete from local tests alone. Record sanitized run IDs,
table counts, timestamps, and screenshots; never capture secrets, tokens,
connection URLs, direct email values, or user-authored note/report bodies.

## A. Deployment gates

- [x] Renew OAuth for explicit profile `dataexpertio_srini`; confirmed
  `malyalasrinivas@gmail.com` on the intended workspace and passed strict
  development bundle validation on 2026-09-21.
- [x] Record the split-workspace decision: all processing/data resources remain
  under `dataexpertio_srini`; only FastMCP and Flask target
  `Srini Free Edition`.
- [ ] Renew OAuth for explicit profile `Srini Free Edition`; verify the intended
  Free workspace identity, Apps availability, secret support, and quota.
- [ ] Prove Free Edition app egress to the paid workspace and Lakebase; prove
  Massive HTTPS before enabling interactive fallback traffic.
- [ ] Create two separate least-privilege paid-workspace OAuth M2M identities,
  bind their credentials as distinct Free Edition app secrets, and pass positive
  plus forbidden-permission tests.
- [ ] Split data/app deployment surfaces and prove the paid plan contains no app
  changes while the Free plan contains no jobs, pipelines, paid-local warehouse,
  UC table, or AI Search creation.
- [x] Apply checksum migration `0005`; verified
  `bootcamp_students.massive_api_attempts_srini` and its time index exist, the
  ledger records `0005`, and a second migration pass applies nothing.
- [ ] Strictly validate/deploy the MCP app with `Srini Free Edition`; record app
  URL and deployment ID without recording credentials.
- [ ] Run the Phase 5 post-deployment harness: health, nine-tool discovery,
  governed retrieval, semantic retrieval, opt-in reversible write,
  idempotent retry, and sanitized trace/event reconciliation.
- [ ] Run simultaneous Job/MCP quota acceptance; prove acquisition five waits
  for the rolling window and no Massive request bypasses Lakebase.
- [ ] Configure the five Lakebase Lakehouse Sync histories in the UI.
- [ ] Deploy/run the activity analytics pipeline; reconcile a controlled write
  through Bronze, Silver, and Gold and record end-to-end latency.
- [ ] Prove a durable paid-workspace UC HTTP/MCP authentication flow to the Free
  MCP app without a personal token. If unsupported, implement and test the
  documented paid-workspace UC-function tool fallback for Supervisor.
- [ ] Deploy the Supervisor, wait for its serving endpoint to become online,
  capture all ten Phase 7 cases, and pass `tools/phase7_agent_eval.py`.
- [ ] Bind the same-workspace Free MCP app and deploy the frontend with
  `Srini Free Edition`; pass health, authenticated-route, security header, MCP
  request-ID, paid-analytics M2M, and safe-error smoke checks.
- [ ] Prove two real principals see isolated watchlists, notes, reports, and
  traces through the complete frontend → agent → MCP path.
- [ ] Restart both Free Edition apps immediately before final acceptance/demo;
  record readiness because Free Edition automatically stops apps after 24 hours.

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

- [ ] Re-run the full local test suite and Ruff; record totals and commit SHA.
- [ ] Run strict data-bundle validation with explicit profile
  `dataexpertio_srini` and strict app-deployment validation with explicit profile
  `Srini Free Edition`; inspect both plans for cross-target resources.
- [ ] Confirm data dictionary, tool/API reference, traceability matrix, status tracker, deployment guide, and diagram agree.
- [ ] Export final architecture diagram as PNG/JPEG and open it once for visual QA.
- [ ] Verify the repository and demo output contain no credentials or sensitive runtime artifacts.
