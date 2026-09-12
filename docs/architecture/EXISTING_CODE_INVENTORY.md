# Existing Code Inventory

Status: Phase 0 baseline, 2026-09-10

The capstone proposal presents Signal Desk as a new solution. Implementation starts from this prototype and treats every retained component as code that must be revalidated, secured, and deployed through the capstone architecture.

## Runtime components

| Component | Current behavior | Phase 0 decision | Later owner |
|---|---|---|---|
| `mcp_server/stock_research_mcp_server.py` | FastMCP HTTP server with nine tools and database traces | Retain tool names; characterize responses; harden identity and tracing | Phase 5 |
| `mcp_server/research_broker.py` | Massive orchestration, calculations, SQL, and persistence | Retain verified calculations; separate API, service, and repository boundaries | Phases 4–5 |
| `mcp_server/massive_client.py` | Authenticated REST calls, retries, pagination, ticker endpoints | Extend; add grouped daily endpoint and one shared limiter | Phase 1 |
| `mcp_server/lakebase.py` | URL secret, new psycopg2 connection per operation, schema execution | Preserve call surface temporarily; replace internals with attached Autoscaling Lakebase and pooling | Phase 4 |
| `mcp_server/migrations/*.sql` | Versioned operational, agent, and CDC-ready tables plus pgvector | Render only allowlisted, fully qualified `_srini` tables and checksum every applied version | Phase 4 |
| `jobs/ingest_research_embeddings.py` | Originally chunked four source types, embedded with MiniLM, and upserted pgvector | Retain its bundle entry point only as a managed Delta Sync trigger; Spark now owns chunks and AI Search owns embeddings | Phase 5 |
| `dashboard/app.py` | Flask overview and watchlist CRUD with direct Lakebase access | Retain UI shell/routes; remove demo identity and direct database sharing | Phase 8 |
| `agent/*` | Prompt, configuration example, and manual demo scenarios | Convert into deployable Supervisor Agent configuration and evaluations | Phase 7 |
| `setup_secrets.py` | Writes Massive and Lakebase URL secrets with implicit CLI profile | Retire before deployment; use explicit profile and attached resources | Phases 0, 4, 9 |

## Existing public MCP tool surface

| Tool | Type | Current authority/data source | Decision |
|---|---|---|---|
| `get_stock_performance` | Read | Massive plus Lakebase cache | Retain contract; bound period and payload |
| `get_company_research` | Read | Massive plus Lakebase cache | Retain; add SEC-backed evidence |
| `compare_stocks` | Read | Calls performance tool per ticker | Retain; move historical analytics to Delta |
| `get_watchlist` | Read/write-on-read | Model-supplied email; creates user/list | Retain visible behavior; remove writes from read path and trust request identity |
| `update_watchlist` | Write | Model-supplied email | Retain; add trusted identity, confirmation, and idempotency |
| `save_research_note` | Write | Model-supplied email | Retain; add trusted identity, confirmation, and idempotency |
| `save_analysis_report` | Write | Model-supplied email | Retain; add trusted identity, confirmation, and idempotency |
| `semantic_research` | Read | Originally Lakebase pgvector | Retain tool name; move to managed hybrid AI Search with provenance and filters |
| `get_notable_updates` | Read/update | Reads activity and updates last visit | Retain; make the state change explicit and identity-bound |

## Known baseline risks

- `user_email` is controlled by the model rather than bound to forwarded identity.
- The dashboard falls back to `demo@example.com` when identity is absent.
- Traces may persist complete parameters and complete tool results.
- Market data is fetched ticker-by-ticker; no market-wide backfill or global free-tier limiter exists.
- The requested lookback window can include extra days from the fetch buffer.
- News is modeled with one ticker per article rather than a many-to-many relationship.
- Company sector and industry are both populated from the same SIC description.
- Database helpers open one connection and transaction per call or row.
- Deployment is manual and depends on URL secrets and implicit profile selection.
- There is no Spark/Lakeflow, SEC, Lakebase-to-Delta analytics, or million-row proof.

## Baseline test obligations

Before a module is refactored, tests must record its relevant behavior using deterministic fixtures. At minimum: ticker validation, price return calculation, comparison input bounds, Massive pagination, HTTP error mapping, watchlist semantics, note/report response shapes, chunk boundaries, the nine MCP tool names, dashboard health/index/watchlist routes, and safe configuration rules.
