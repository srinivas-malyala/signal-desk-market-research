# Phase 3 Status — SEC and Unstructured Research Pipeline

Updated: 2026-09-10

Phase 3 workspace acceptance is complete for the bounded two-company workflow.

| Unit | Implementation | Local evidence | Remaining workspace gate |
|---|---|---|---|
| 3.1 SEC client and raw landing | Workspace verified | Two companies, 2 submissions, 2 Company Facts snapshots, and 12 filing documents landed with 16 SEC attempts, zero retries/failures; 100 article query results landed with 2 Massive attempts and zero retries; cached rerun made zero external calls | None for the bounded two-company pilot |
| 3.2 Structured companies, filings, facts, and articles | Workspace verified | 2 companies, 12 filings, 57,806 facts, zero orphan CIKs, duplicate accessions, or duplicate fact keys; 86 distinct articles and 549 links across 157 referenced tickers | None for the bounded two-company pilot |
| 3.3 Documents and research chunks | Workspace verified | 507 chunks across 98 filing/article sources; zero duplicate IDs, duplicate source indexes, or untraceable chunks; Gold catalog and bounded industry comparison queries succeeded | None for the bounded two-company pilot |

## Raw storage contract

```text
/Volumes/<catalog>/<schema>/<volume>/
├── sec/
│   ├── submissions/cik=<CIK>/checksum=<SHA256>/{response.json,manifest.json}
│   ├── companyfacts/cik=<CIK>/checksum=<SHA256>/{response.json,manifest.json}
│   └── filings/cik=<CIK>/accession=<ACCESSION>/{document.html,manifest.json}
└── research_articles/query_ticker=<TICKER>/checksum=<SHA256>/{response.json,manifest.json}
```

Submissions and Company Facts are snapshots and can legitimately change, so changed content creates a new checksum directory. A filing accession is treated as immutable; changed bytes for an already-landed accession fail closed. Cache pointers are mutable control metadata, not source evidence.

## Pipeline datasets

- Bronze: `bronze_sec_manifests`, `bronze_sec_submissions`, `bronze_sec_company_facts`, `bronze_sec_filing_documents`, and `bronze_research_articles`.
- Silver: `silver_sec_companies`, `silver_sec_filings`, `silver_sec_facts`, `silver_research_articles`, `silver_article_tickers`, and `silver_research_chunks`.
- Gold: `gold_industry_peer_comparison` and `gold_research_catalog`.
- Evidence: `sec_structured_reconciliation` and `research_chunk_reconciliation`.

## Identity and request safety

The approved SEC contact is accepted only from `SEC_USER_AGENT` or Databricks secret `sec/user-agent`. It is never a command-line parameter, manifest field, log field, or committed configuration value. The deployed job reads the provisioned secret at runtime.

Research-article requests reuse the Phase 1 process-safe Massive limiter and its append-only attempt ledger, so SEC work does not weaken the free-plan controls established for market data.

## Deployment gate

The `research_refresh` job runs SEC ingestion and article ingestion in parallel, then incrementally refreshes the dedicated research-only Spark pipeline after both succeed. These Phase 3 resources are deployed without either Lakebase-dependent application or `research_embeddings`; live execution uses the `sec/user-agent` secret and the Phase 2 `gold_stock_performance` table used for industry comparison.

The Databricks-backed `sec` scope and `user-agent` key are provisioned and key-only verified. The value was not read back or written to repository files.

The pre-deployment suite passes 34 focused SEC, article, document, pipeline-source, and configuration tests plus lint.

Selective deployment completed: SEC job `380855220996785`, article job `129689732201837`, research pipeline `82ec186f-f38e-4ebe-b121-0b1faeea946d`, and orchestrator `321391048242098`. The frontend, MCP application, and Lakebase-dependent embedding job remain undeployed.

Two-company refresh run `562225890540150` completed successfully.

Sanitized child evidence: SEC run `990810425081595` landed 2 submissions, 2 Company Facts snapshots, and 12 filing documents in 16 attempts with no retry or failure. Article run `485361230932702` landed 100 query results in 2 Massive attempts with no retry. Research update `e8dac8a4-a967-4aff-948e-f4fa5d7af170` completed.

Warehouse acceptance passed: 2 companies, 12 filings, and 57,806 facts have zero orphan or duplicate keys; 507 chunks across 98 sources have zero duplicate IDs, duplicate source indexes, or missing provenance; 86 distinct articles produce 549 article/ticker links across 157 referenced tickers; Gold catalog and bounded industry comparison queries succeeded.

Cache/idempotency acceptance also passed. Orchestrator run `892606879283451` completed successfully; article task run `1114483094003228` reused 2 cached queries with zero API calls or HTTP attempts, and SEC task run `57407285384248` reused 4 structured requests plus 12 filing documents with zero HTTP attempts. Incremental research update `fcff5d1b-fced-48c5-9d32-1e4be504bdbd` completed.
