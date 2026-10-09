# Signal Desk Evidence Manifest

## Submission links

- Live application: https://signal-desk-frontend-s88i.onrender.com/
- Public MCP service: https://signal-desk-mcp.onrender.com/
- Source repository: https://github.com/srinivas-malyala/signal-desk-market-research

## Rubric evidence map

| Rubric category | Primary implementation | Verification evidence |
|---|---|---|
| Spark data pipeline | `pipelines/market_bars_classified.py`, `pipelines/silver_market_bars.py`, `pipelines/silver_market_quarantine.py`, `pipelines/silver_research_chunks.py`, `pipelines/silver_sec_facts.py` | `docs/IMPLEMENTATION_STATUS.md`, `docs/release/REQUIREMENTS_TRACEABILITY.md`, pipeline resources under `resources/` |
| Third-party API integration | `mcp_server/massive_client.py`, `ingestion/market_backfill.py`, `ingestion/sec_client.py`, `ingestion/article_landing.py` | Shared rate-limit ledger migration `mcp_server/migrations/0005_massive_rate_limit.sql`; acceptance details in `docs/IMPLEMENTATION_STATUS.md` |
| Lakebase data model | `mcp_server/migrations/0001_operational_core.sql` through `0005_massive_rate_limit.sql`, `mcp_server/lakebase.py` | Schema and isolation evidence in `docs/phase4/STATUS.md` and `docs/release/REQUIREMENTS_TRACEABILITY.md` |
| Action-taking AI agent | `mcp_server/stock_research_mcp_server.py`, `mcp_server/action_service.py`, `agent/system_prompt.md`, `agent/agent_bricks_config.yaml` | `tools/phase7_agent_eval.py`, `agent/evaluations.json`, 10 of 10 deployed Supervisor cases in `docs/IMPLEMENTATION_STATUS.md` |
| Analytics pipeline | `pipelines/bronze_lakebase_changes.py`, `pipelines/silver_agent_activity.py`, all `pipelines/gold_*` analytics modules | `resources/activity_analytics.pipeline.yml`, `tools/phase6_cdf_acceptance.py`, live analytics screenshot |
| Frontend and core workflow | `dashboard/app.py`, `dashboard/templates/index.html`, `dashboard/static/app.js`, `dashboard/static/styles.css` | Live authenticated screenshots and frontend tests under `tests/test_dashboard_*` and `tests/test_render_frontend_routes.py` |
| Deployed application | `render.yaml`, `docs/RENDER_DEPLOYMENT_RUNBOOK.md`, `docs/RENDER_OIDC_PREPARATION.md` | Live Render deployment screenshot and accessible application URL |
| Big Data Volume | Market pipeline and serving publisher | 1,255,677 Bronze rows, 1,255,489 unique Silver rows, and 188 deterministic quarantines |
| Big Data Variety | SEC filings, article text, XBRL facts, JSON source payloads, OHLCV data | 507 traceable research chunks in the accepted bounded corpus and a 393-row searchable canonical serving corpus |

## Screenshot inventory

- `screenshots/app-research.png` — authenticated research workflow and attributable evidence cards
- `screenshots/app-watchlist-signals.png` — user-owned watchlist, signals, notes, and reports
- `screenshots/app-usage-analytics.png` — Gold metrics and tool latency table
- `screenshots/render-live-deployment.png` — Live Render MCP service and successful deploy history

## Current deterministic verification

Executed locally on October 7, 2026:

```text
281 passed, 2 dependency deprecation warnings
Ruff: All checks passed
```

The warnings come from Authlib imports used by FastMCP dependencies and do not represent failed tests.
