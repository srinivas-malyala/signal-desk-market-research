# Signal Desk Data Dictionary

Updated: 2026-09-21

This dictionary describes the implemented development model. Unity Catalog
analytics live in `bootcamp_students.student_sri`. Lakebase operational tables
live in shared PostgreSQL schema `bootcamp_students` and are isolated with the
suffix `_srini`. No application owns the shared schema itself.

## Lakebase operational model

| Base table (physical suffix `_srini`) | Grain and key | Important fields | Data classification / purpose |
|---|---|---|---|
| `users` | One application user; `id`, unique `email` | `display_name`, `last_visit_at`, timestamps | Direct identity; ownership root. Never publish email to analytics. |
| `watchlists` | One named list per user; `id`, unique `(user_id,name)` | `is_default`, `created_at` | User-owned operational state. |
| `watchlist_tickers` | One ticker membership; `(watchlist_id,ticker)` | `added_at`, `last_viewed_at` | CDC source; no direct identity column. |
| `companies` | One ticker; `ticker` | profile, industry, exchange, market cap, filing fields, `payload`, `synced_at` | Cached public reference data. Missing values remain null. |
| `price_snapshots` | One ticker/capture; `id`, unique `(ticker,captured_at)` | OHLCV, previous close, changes, source `payload` | Cached public market data. |
| `news_articles` | One source article; `id` | title, description, URL, publisher, publication time, `payload` | Public/semi-structured source data; legacy `ticker` retained for compatibility. |
| `news_article_tickers` | One article/ticker relation; `(article_id,ticker)` | per-ticker sentiment fields, `linked_at` | Many-to-many article coverage; CDC-ready. |
| `research_notes` | One saved note; `id` | `user_id`, ticker, title, `note_text`, tags, timestamps | Sensitive user-authored content; CDC analytics excludes text. |
| `analysis_reports` | One saved report; `id` | `user_id`, title, thesis, tickers, `report_text`, source context | Sensitive user-authored content; CDC analytics excludes text. |
| `research_embeddings` | One legacy embedding record; `id` | source identity, ticker, chunk, hash, vector(384), model | Retained compatibility store; managed AI Search uses Delta documents instead. |
| `stock_research_mcp_traces` | One MCP tool invocation; `trace_id` | session, tool, bounded parameters/result, pseudonymous user, status, duration | Sanitized operational audit; no token, secret, or authored body. |
| `agent_sessions` | One agent session; `session_id` | `user_id`, status, created/last-activity times | CDC source for session activity. |
| `agent_tool_events` | One tool event; `event_id` | session/user, tool, action, status, duration, bounded metadata | Primary CDC source for usage analytics. |
| `idempotency_records` | One write result per user/operation/key; `(user_id,operation_name,idempotency_key)` | response `result`, `created_at` | Prevents duplicate confirmed writes and detects key reuse. |
| `massive_api_attempts` | One permitted physical Massive attempt; `attempt_id` | database-clock `acquired_at`, bounded requester label, contract version | Cross-host free-plan quota ledger; physical name `bootcamp_students.massive_api_attempts_srini`; contains no URL, query, header, or key. Migration `0005` is applied and idempotency-verified. |
| `schema_migrations` | One applied migration version; `version` | SHA-256 checksum, `applied_at` | Detects mutation of already-applied migrations. |

`watchlist_tickers`, `research_notes`, `analysis_reports`, `agent_sessions`,
`agent_tool_events`, and `news_article_tickers` use `REPLICA IDENTITY FULL`.
The first five are the selected Lakebase-to-Unity-Catalog change sources.

## Lakehouse market and research model

| Dataset | Grain | Key fields and role |
|---|---|---|
| `bronze_market_daily` | One raw Massive security/day row | Raw ticker fields, source request/date, rescue data. |
| `bronze_market_manifests` | One landed response manifest/date | Row/byte counts, checksum, request metadata, landing time. |
| `silver_market_bars` | One valid `(ticker,trading_date)` | Typed OHLCV, transaction count, OTC flag, source request. |
| `silver_market_quarantine` | One rejected source row | Original identifiers and deterministic rejection reason. |
| `gold_stock_performance` | One ticker/trading date | Daily return, volume change, trailing-20 volatility/range/volume. |
| `gold_market_peer_comparison` | One ticker/trading date | Market-relative return, percentile, peer count. |
| `gold_market_data_coverage` | One source date | Manifest/Bronze/Silver/quarantine reconciliation and acceptance rate. |
| `silver_sec_companies` | One normalized SEC company snapshot | CIK, ticker, SIC/industry and source freshness. |
| `silver_sec_facts` | One normalized SEC Company Fact observation | CIK, taxonomy, concept, unit, period/form/accession provenance. |
| `silver_sec_filings` | One SEC filing | CIK/accession/form/date, document URL/text provenance. |
| `silver_research_articles` | One normalized Massive news article | Article metadata, source URL/date, body/description and provenance. |
| `silver_article_tickers` | One article/ticker relation | Per-ticker relationship and source insight metadata. |
| `silver_research_chunks` | One section-aware child chunk | Stable chunk/parent/source IDs, retrieval and embedding text, ticker/date/URL/hash. |
| `research_search_documents` | One publishable chunk | Regular CDF-enabled Delta source for the managed hybrid AI Search index. |
| `gold_research_catalog` | One article or filing source | Tickers, date, URL, content hash, chunk count and indexed characters. |
| `gold_industry_peer_comparison` | One ticker/industry/date | Industry-relative return, percentile, and peer count. |

The measured workspace volume is 1,255,677 Bronze market rows, resolving to
1,255,489 unique Silver `(ticker,trading_date)` rows and 188 deterministic
quarantines across 81 manifest dates.

## Lakebase CDC analytics model

Lakehouse Sync is expected to create append-only history tables named
`bootcamp_students.bootcamp_students.lb_<base>_srini_history` for the five
selected operational sources. The Phase 6 pipeline outputs remain in
`bootcamp_students.student_sri`.

| Dataset | Grain | Published fields / privacy rule |
|---|---|---|
| `bronze_lakebase_changes` | One normalized row-level change | Change ID, source/key, PostgreSQL LSN/XID/order, sync/event times, pseudonym, session/tool/status/duration/action. |
| `silver_agent_activity` | One deduplicated effective insert/update/delete | Adds activity date and source latency; direct email and authored note/report text are absent. |
| `gold_daily_active_researchers` | One activity date | Pseudonymous researcher and invocation counts plus freshness. |
| `gold_tool_usage_latency` | One date/tool | Invocation/success/error/null-duration counts, average/p50/p95 latency and freshness. |
| `gold_agent_error_rate` | One activity date | Invocation count, error count/rate and freshness. |
| `gold_watchlist_changes` | One date/action | Watchlist change count and freshness. |
| `gold_research_saves` | One date/research type/action | Note/report change and researcher counts without authored content. |

Change types are `insert`, `update_preimage`, `update_postimage`, and `delete`;
Silver retains only effective `insert`, `update_postimage`, and `delete` rows.
