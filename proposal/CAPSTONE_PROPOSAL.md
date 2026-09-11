# Capstone Project Proposal

## Signal Desk: Agentic Equity Research and Market Intelligence Platform

### Project summary

Signal Desk will be a new, evidence-grounded stock-market research application built on Databricks. It will help a user investigate public companies, compare market performance, search company filings and financial news, maintain a personal watchlist, and save research notes or reports. The capstone will be presented, designed, implemented, tested, and deployed as a greenfield system with its own data contracts, pipelines, database schema, agent tools, user interface, and infrastructure configuration.

The capstone includes the components required for a production-oriented data application: a PySpark ingestion and transformation pipeline, over one million historical market rows in Delta, SEC filing ingestion, Lakebase Change Data Feed for operational analytics, a unified research interface, and repeatable Databricks deployment.

The result will answer questions such as:

- How has a company performed over a selected period, and how does it compare with peers?
- What recent news, SEC filings, and financial facts support or challenge an investment thesis?
- Which companies and themes is the user actively researching?
- Which agent tools are most frequently used, slow, or error-prone?
- How do watchlists and research activity change over time?

This system provides research support only; it will not execute trades or provide personalized investment advice.

## 1. Data sources and integration plan

### Massive Stocks API

Massive will be the principal third-party market-data API. The application will use:

- **Daily Market Summary** for market-wide OHLC, volume, and VWAP data for all U.S. stocks on each trading date.
- **Custom Aggregate Bars and the latest entitled daily aggregates** for on-demand company price research.
- **Ticker Reference and Company Overview** for company names, exchanges, industry classifications, CIK identifiers, and market capitalization.
- **Ticker News** for article metadata, descriptions, related tickers, publisher information, source URLs, and sentiment fields.

Massive provides REST, WebSocket, and flat-file access to U.S. stock data. The capstone MVP will use REST endpoints because they integrate naturally with the Python ingestion stack and make historical backfills reproducible. API keys will be stored as Databricks secrets or attached secret resources and will never be committed to source control.

### Massive free-plan feasibility and rate-limit design

The project will be implemented against the **Stocks Basic free plan**. As of August 29, 2026, Massive lists this plan as providing all U.S. stock tickers, 100% market coverage, end-of-day data, two years of history, and **five API calls per minute**. The project will not depend on paid-only snapshots, WebSockets, flat files, trades, quotes, or real-time data.

The million-row backfill will use the Daily Market Summary endpoint with `include_otc=true` instead of issuing one request per ticker. One request for a trading date returns daily OHLC, volume, and VWAP records for the U.S. market. The implementation will therefore need approximately 252 API requests for one trading year, not more than one million API requests. PySpark will explode each response's `results` array into one Delta row per security and trading date.

All Massive requests will pass through a shared, single-worker rate limiter configured for **four calls per minute**, leaving headroom below the free-plan limit. The backfill will issue at most one request every 15 seconds, honor `Retry-After` on HTTP 429 responses, apply exponential backoff for transient failures, and checkpoint every successfully landed trading date. At four calls per minute, 252 dates take approximately 63 minutes of API time. Interactive agent requests will use the same queue so the API key cannot exceed its aggregate allowance.

The initial target is 252 recent trading dates. At a conservative average of 5,000 returned U.S. securities per date, this produces approximately 1,260,000 market rows. The job will compute the actual distinct `(ticker, trading_date)` count after each batch and, if necessary, continue farther back within the free plan's two-year history until the validated Delta row count exceeds 1,000,000. Across approximately 504 trading dates, the two-year window needs an average of only 1,985 returned securities per date to exceed one million rows. Completion will be based on the measured Delta count rather than the estimate.

Official documentation:

- [Massive Stocks API overview](https://massive.com/docs/rest/stocks/overview)
- [Massive Stocks pricing and free-plan limits](https://massive.com/pricing?product=stocks)
- [Massive Daily Market Summary](https://massive.com/docs/rest/stocks/aggregates/daily-market-summary)
- [Massive Custom Aggregate Bars](https://massive.com/docs/rest/stocks/aggregates/custom-bars)
- [Massive Ticker News](https://massive.com/docs/rest/stocks/news)

### SEC EDGAR APIs

SEC EDGAR will add authoritative regulatory and financial-reporting data:

- The **Submissions API** will provide filing metadata for 10-K, 10-Q, and 8-K filings.
- The **Company Facts API** will provide structured XBRL facts such as revenue, assets, liabilities, and net income.
- Filing HTML or text documents will supply unstructured content for section extraction, chunking, and semantic research.

The SEC APIs do not require an API key, but ingestion will identify the application with a compliant User-Agent, respect SEC access policies, and use bulk archives for large backfills where appropriate.

Official documentation: [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)

### Application-generated operational data

The frontend and AI agent will generate transactional data in Lakebase:

- users and authenticated identities;
- watchlists and watchlist membership changes;
- saved research notes and reports;
- agent sessions, tool calls, parameters, latency, status, and safe result metadata;
- user visit timestamps and application events.

This data is essential both to the application workflow and to the usage-analytics requirement.

## 2. Spark data pipeline

A scheduled Lakeflow Job will call Massive and SEC endpoints and land raw responses in a Unity Catalog Volume. The Massive portion will use the centralized four-calls-per-minute queue and date checkpoints described above. A Lakeflow Spark Declarative Pipeline, written primarily in Python using PySpark, will implement a medallion design.

### Bronze layer

- `bronze_market_daily`: raw market-wide daily records from Massive.
- `bronze_company_reference`: raw ticker and company profile JSON.
- `bronze_news`: raw news and sentiment JSON.
- `bronze_sec_submissions`: raw filing indexes and XBRL Company Facts JSON.
- `bronze_sec_documents`: filing HTML/text plus retrieval metadata.

Bronze records will retain source payloads, source URLs, ingestion timestamps, request identifiers, and file paths for lineage and replay.

### Silver layer

PySpark transformations will:

- enforce explicit schemas and normalize timestamps, ticker symbols, and numeric fields;
- remove duplicates using ticker, event time, article ID, accession number, or source record ID;
- quarantine malformed payloads using pipeline expectations;
- adjust and validate market fields without treating missing values as zero;
- create a many-to-many article-to-ticker relationship;
- parse SEC filing metadata and selected document sections;
- strip HTML, normalize text, and create overlapping document chunks;
- enrich market and document records with sector, industry, CIK, and source provenance.

Principal outputs will include `silver_market_bars`, `silver_companies`, `silver_news`, `silver_article_tickers`, `silver_financial_facts`, `silver_filings`, and `silver_research_chunks`.

### Gold layer

Materialized views will provide reusable analytics:

- `gold_stock_performance`: daily and rolling returns, volatility, volume changes, and price ranges;
- `gold_peer_comparison`: aligned company and sector performance;
- `gold_research_catalog`: searchable document metadata and freshness information;
- `gold_market_coverage`: row counts, date coverage, missingness, and pipeline-quality metrics.

Streaming tables will be used for append-only or incremental inputs. Materialized views will be used for joins and aggregations so updates remain consistent with current source data. The pipeline will publish managed Delta tables in Unity Catalog and apply expectations for ticker validity, timestamp presence, nonnegative volume, and document provenance.

## 3. Lakebase operational data model

Lakebase Postgres Autoscaling will store low-latency relational state. In the administrator-managed shared schema `bootcamp_students`, Signal Desk will own only tables suffixed `_srini`, including:

- `users`
- `watchlists`
- `watchlist_tickers`
- `research_notes`
- `analysis_reports`
- `agent_sessions`
- `agent_tool_events`
- `companies_cache`
- `price_snapshot_cache`
- `news_cache`
- `research_embeddings`

High-volume historical market records will remain in Delta rather than being duplicated in the operational database. Lakebase will contain only the user-facing transactional records and a bounded cache of recent research data required for responsive application and agent operations.

The application role will own only its `_srini` tables and will neither create nor drop the shared schemas. Database access will use the administrator-managed `database/lakebase-url` secret, SSL, bounded connection pooling, and parameterized queries with allowlisted fully qualified table identifiers. The authenticated identity supplied by Databricks will be enforced in the server; the agent will not be allowed to select an arbitrary `user_email` argument.

## 4. Action-taking AI agent

A Databricks Agent Bricks Supervisor Agent will use a purpose-built external FastMCP server as a tool provider. Retrieval tools will include:

- `get_stock_performance`
- `get_company_research`
- `compare_stocks`
- `semantic_research`
- `get_watchlist`
- `get_notable_updates`

Meaningful action tools will include:

- `update_watchlist` to add or remove a company;
- `save_research_note` to persist a user-confirmed thesis or observation;
- `save_analysis_report` to persist a multi-company report;
- optionally, `delete_research_note` to remove a user-owned note.

The agent will confirm consequential writes, use the authenticated user's identity, separate evidence from interpretation, expose sources and as-of dates, and never silently convert unavailable financial data into zero. Every tool call will create a sanitized audit event containing the tool name, duration, status, user, and bounded metadata.

For semantic research, filing and news chunks will be embedded and indexed in Lakebase using pgvector. The system will retain source URL, document type, filing date, ticker, and chunk identifiers so retrieved evidence is inspectable.

## 5. Analytics pipeline using Lakebase Change Data Feed

Lakebase Change Data Feed will capture inserts, updates, and deletes from selected operational tables and write row-level change history into Unity Catalog Delta tables. The feed is designed to flush changes approximately every 15 seconds, making it appropriate for near-real-time application analytics.

CDF will be enabled for:

- `watchlist_tickers`
- `research_notes`
- `analysis_reports`
- `agent_sessions`
- `agent_tool_events`

A second branch of the Lakeflow Spark Declarative Pipeline will process those Delta change tables:

1. `bronze_lakebase_changes` retains `_pg_change_type`, transaction, ordering, and event-time metadata.
2. `silver_agent_activity` standardizes identities, sessions, tool names, status, and duration while excluding sensitive note or report bodies.
3. Gold materialized views create:
   - `gold_daily_active_researchers`
   - `gold_tool_usage_and_latency`
   - `gold_agent_error_rate`
   - `gold_watchlist_change_activity`
   - `gold_research_saves`

These tables will support an administrative usage page in the frontend and demonstrate an end-to-end operational-to-analytical data flow.

Official documentation:

- [Lakebase Change Data Feed](https://docs.databricks.com/aws/en/oltp/projects/lakebase-cdf)
- [Lakeflow Spark Declarative Pipelines concepts](https://docs.databricks.com/aws/en/ldp/concepts/)

## 6. Frontend and core workflow

A new Flask frontend will provide a unified Databricks App for research, agent interaction, and saved work. The primary workflow will be:

1. Search for or select a company.
2. Ask the research agent a question or choose a comparison window.
3. Inspect price facts, news, filing evidence, source links, and freshness timestamps.
4. Add a company to a watchlist or save a confirmed note/report.
5. Revisit saved research and notable changes.

The interface will contain:

- a research question/chat panel;
- a watchlist with current cached prices and change indicators;
- company and peer-comparison views with periods, units, sources, and as-of times;
- expandable evidence cards for news and SEC filing passages;
- saved notes and reports;
- an agent activity and usage-analytics page.

Every data view will explicitly handle loading, empty, error, partial, and stale-data states. Agent responses will display their evidence and execution identity. The app will be served by Gunicorn and will bind to the Databricks Apps port.

## 7. Deployment

The frontend will be deployed as a Databricks App. The FastMCP service will be deployed as a second Databricks App so that the agent-facing service and user-facing application can scale and be permissioned independently.

A Databricks Declarative Automation Bundle will version and deploy:

- the market/filing ingestion Lakeflow Job;
- the Lakeflow Spark Declarative Pipeline;
- the frontend Databricks App;
- the FastMCP Databricks App;
- Unity Catalog schemas, volumes, and resource variables where supported.

Lakebase Autoscaling, the shared-schema `_srini` table contract, attached secret resources, Agent Bricks registration, and Lakebase CDF setup will be documented as environment bootstrap steps where they cannot be completely represented in the bundle. Separate development and production targets will parameterize catalog, schema, application names, and resource identifiers.

## 8. Big Data requirements

The project formally targets **Volume** and **Variety**, satisfying two of the three Vs.

### Volume: more than one million rows

The Massive Daily Market Summary provides one row per returned U.S. security per trading day using one API request per date. A conservative target of 5,000 securities across one trading year produces approximately:

`5,000 tickers × 252 trading days = 1,260,000 market rows`

The backfill will use 252 calls, throttled to four calls per minute, for an estimated API duration of approximately 63 minutes. If the measured count is below one million, the checkpointed job will continue into the second year available on the free plan. The final demonstration will include a validation query showing that the distinct Delta `(ticker, trading_date)` count exceeds one million.

### Variety: structured, semi-structured, and unstructured data

- **Structured:** OHLCV bars, ticker reference data, XBRL financial facts, and relational application events.
- **Semi-structured:** Massive and SEC JSON payloads, nested news insights, and filing indexes.
- **Unstructured:** filing HTML/text, company descriptions, news descriptions, and user-authored research notes.

PySpark will normalize the structured fields while preserving and chunking narrative text for semantic search.

### Optional third V: velocity

Lakebase CDF writes operational changes to Delta approximately every 15 seconds. The project will measure end-to-end freshness from a watchlist or note write to its appearance in a gold usage table. Achieving less than one minute will be reported as an additional velocity result, but the proposal does not depend on velocity to satisfy the two-V requirement.

## 9. Greenfield implementation scope

The capstone will deliver the following newly implemented modules:

| Module | Greenfield deliverable |
|---|---|
| External-data ingestion | A rate-limited Massive client, SEC EDGAR client, checkpointed backfill job, and raw landing contracts. |
| Spark transformations | A PySpark Lakeflow pipeline with bronze, silver, and gold Delta datasets and data-quality expectations. |
| Operational database | A Lakebase Autoscaling schema, migrations, ownership rules, connection pooling, and CDF-enabled event tables. |
| Agent service | A FastMCP server with retrieval and confirmed write tools, authenticated identity enforcement, and sanitized traces. |
| Semantic research | Filing/news chunking, embeddings, pgvector indexing, provenance fields, and retrieval evaluation. |
| Frontend | An authenticated Flask Databricks App for research, evidence inspection, watchlists, notes, reports, and usage analytics. |
| Deployment | A Declarative Automation Bundle plus documented Lakebase, CDF, secrets, and Agent Bricks bootstrap steps. |

## 10. Success criteria

The capstone will be considered complete when it demonstrates:

1. At least 1,000,000 market rows processed with PySpark into governed Delta tables.
2. At least two external data types integrated from Massive and SEC EDGAR.
3. A working Lakebase relational model for users, watchlists, research, and agent events.
4. An agent answer grounded in retrieved market/document evidence.
5. A confirmed agent write that updates a watchlist or saves research.
6. A Lakebase write appearing in a Delta CDF table and a gold usage metric.
7. A usable, authenticated Databricks App completing the research-and-save workflow.
8. Repeatable validation and deployment instructions, with automated unit and integration tests for critical paths.

## 11. Key risks and mitigations

- **Massive free-plan limits:** centralize all calls behind a four-per-minute limiter, use one grouped-market request per date, checkpoint completed dates, honor 429 `Retry-After`, and validate the row count before declaring the volume requirement complete.
- **SEC access policy:** use an identifying User-Agent, bounded concurrency, retry/backoff, and bulk archives for large downloads.
- **Sensitive or oversized traces:** store bounded event metadata rather than full tool results or user-authored report bodies.
- **Identity isolation:** derive user identity from trusted Databricks headers and apply ownership filters to every Lakebase read and write.
- **Pipeline cost and duration:** backfill incrementally, use serverless compute where available, and separate historical backfill from daily refresh.
- **Preview feature availability:** confirm Lakebase CDF support in the chosen workspace early; retain a Lakeflow pipeline from append-only agent events as a documented fallback.

## Architecture diagram

See [signal-desk-capstone-architecture.png](signal-desk-capstone-architecture.png).

## Implementation plan

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the dependency-ordered, unit-by-unit build and test plan.
