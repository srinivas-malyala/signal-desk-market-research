# Signal Desk Tool and API Reference

Updated: 2026-09-21  
MCP contract version: `1.0`

The FastMCP service exposes streamable HTTP at `/mcp` and an unauthenticated
health probe at `GET /health`. Tool requests obtain identity and the user OAuth
token only from the Databricks request context. `user_email` is never a tool
argument. Each tool response includes `contract_version` and `correlation_id`;
errors use `status: error`, a bounded `error_code`, and a safe `message`.

## Retrieval tools

### `get_stock_performance`

- Inputs: `ticker: str`; `lookback_days: int = 30` (2–365 calendar days).
- Returns: bounded governed daily bars, latest OHLCV, period return/high/low,
  source and `as_of`. Governed Lakehouse history is preferred; the shared
  rate-limited Massive daily-aggregate path is the explicit fallback.
- No user row is created by a read.

### `get_company_research`

- Inputs: `ticker: str`; `news_limit: int = 10` (1–50);
  `include_fundamentals: bool = true`.
- Returns: normalized company profile, recent many-to-many news, SEC filing
  links, and available reported fundamentals with provenance.
- Entitlement or missing-data errors remain unavailable; they are never zero.

### `compare_stocks`

- Inputs: `tickers: list[str]` (2–5); `lookback_days: int = 30`.
- Returns: like-for-like price, return, high and low for one shared window and
  as-of basis.

### `get_watchlist`

- Inputs: `watchlist_name: str = "Primary"`.
- Returns: the authenticated user's membership and latest locally stored
  company/price facts. Ownership is enforced server-side.

### `semantic_research`

- Inputs: `query: str`; `top_k: int = 5` (1–5); optional `tickers`,
  `source_types` (`filing`/`article`), inclusive `start_date`, and `end_date`.
- Returns: parent-deduplicated, attributable SEC/news passages from the managed
  hybrid Delta Sync index, including source type/ID/URL/date, ticker and score.
- Semantic text is supporting context, not proof of an exact financial value.

### `get_notable_updates`

- Inputs: `move_threshold_percent: float = 5.0`;
  `mark_visited: bool = false`.
- Returns: locally synced qualifying watchlist moves and articles since the
  stored comparison time. The agent keeps `mark_visited=false` unless the user
  explicitly asks to advance the marker.

## Confirmed action tools

All writes are scoped to trusted request identity, transactional, bounded, and
audited. The same idempotency key may be reused only for an exact retry.

### `update_watchlist`

- Inputs: `ticker`; `action` exactly `add` or `remove`;
  `watchlist_name = "Primary"`; `confirmed`; `idempotency_key` (8–128 safe
  characters).
- Effect: creates/removes one authenticated-user membership and returns the
  resulting watchlist. `confirmed` must be true.

### `save_research_note`

- Inputs: `ticker`, `title`, `note_text`, optional `thesis_tags`, `confirmed`,
  and `idempotency_key`.
- Effect: inserts one authenticated-user note and returns its ID/time.
  Drafting or discussing a note does not authorize this call.

### `save_analysis_report`

- Inputs: `title`, `thesis`, `tickers`, `report_text`, optional
  `source_context`, `confirmed`, and `idempotency_key`.
- Effect: inserts one authenticated-user report and returns its ID/time.

## External source APIs

| Provider | Implemented use | Identification/authentication | Safety and budget |
|---|---|---|---|
| Massive Stocks REST | Grouped daily market summary, ticker details, daily aggregates, news, and plan-dependent financial/reference endpoints | Bearer key from `massive/api-key`; never placed in URL or logs | Every physical attempt, including retry, passes a rolling limiter. Deployed paths use the fail-closed Lakebase coordinator capped at four attempts per 60 seconds across hosts. |
| SEC EDGAR/data.sec.gov | Submissions, Company Facts, and filing documents | Required identifying `User-Agent` from `sec/user-agent`; configured contact is `malyala.de@gmail.com` | Bounded company/form/document scope, cached immutable landing, retries and checksums; no scraping without identification. |

Raw source payloads land immutably before Spark normalization. Credentials,
OAuth tokens, request authorization headers, Lakebase URLs, and user-authored
research bodies are excluded from logs and analytics events.

