# Phase 3 Status — SEC and Unstructured Research Pipeline

Updated: 2026-09-10

Phase 3 is implemented and deterministically tested locally. No workspace deployment or live two-company ingestion is claimed here.

| Unit | Implementation | Local evidence | Remaining workspace gate |
|---|---|---|---|
| 3.1 SEC client and raw landing | Complete locally | Identifying User-Agent enforcement, official-host allowlist, conservative five-request/second rolling limiter, two-worker default with a four-worker hard cap, retry/backoff including `Retry-After`, 24-hour cache, content-addressed snapshots, accession-keyed immutable filings, and SHA-256 manifests | Store the approved contact in `sec/user-agent`; run AAPL/MSFT ingestion and retain sanitized metrics |
| 3.2 Structured companies, filings, facts, and articles | Complete locally | Dynamic taxonomy/concept/unit XBRL model, fiscal-period fields, amendments, deterministic fact/accession deduplication, company/CIK/ticker mapping, SEC SIC industry enrichment, Massive article deduplication, and many-to-many article/ticker bridge | Run serverless pipeline expectations and inspect `sec_structured_reconciliation` |
| 3.3 Documents and research chunks | Complete locally | Binary Auto Loader for filing HTML, table-aware HTML normalization, selected Item extraction, boilerplate handling, deterministic overlap, stable SHA-256 chunk IDs, filing/article union, Gold research catalog, and provenance/uniqueness reconciliation | Inspect parsed filings and `research_chunk_reconciliation`; query bounded catalog results through the SQL warehouse |

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

The approved SEC contact is accepted only from `SEC_USER_AGENT` or Databricks secret `sec/user-agent`. It is never a command-line parameter, manifest field, log field, or committed configuration value. The deployed job therefore needs the secret before its first run.

Research-article requests reuse the Phase 1 process-safe Massive limiter and its append-only attempt ledger, so SEC work does not weaken the free-plan controls established for market data.

## Deployment gate

The `research_refresh` job runs SEC ingestion and article ingestion in parallel, then incrementally refreshes the shared Spark pipeline only after both succeed. Bundle deployment remains deferred because the same bundle contains Lakebase-dependent applications and the usable student Lakebase password is still pending.
