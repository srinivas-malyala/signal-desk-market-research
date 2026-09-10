# Phase 2 Status — Spark Market Pipeline and Volume Proof

Updated: 2026-09-10

Phase 2 is implemented and deterministically tested locally. Workspace execution and the measured one-million-row result remain explicit acceptance gates; this document does not claim those external proofs have passed.

| Unit | Implementation | Local evidence | Remaining workspace gate |
|---|---|---|---|
| 2.1 Bronze market streaming tables | Isolated and complete locally | Dedicated `market_pipeline` resource, modern Spark Declarative Pipelines API, Auto Loader, explicit response/manifest schemas, rescued data, immutable file/request lineage, and per-date reconciliation | Process the Volume pilot exactly once and prove every manifest row count matches Bronze |
| 2.2 Silver market bars | Complete locally | Ordered quality rules, deterministic `(ticker, trading_date)` ranking, accepted/quarantine conservation, and uniqueness assertion | Run expectations and reconciliation on Databricks serverless pipeline compute |
| 2.3 Gold market analytics | Complete locally | Daily returns, volume change, complete 20-session high/low/average-volume/annualized-volatility windows, broad-market percentile comparison, and coverage metrics; known-answer tests pass | Query bounded results through warehouse `b15d3d6f837ba428`; sector/industry peers wait for Phase 3 company enrichment |
| 2.4 One-million-row certification | Complete locally; measured result pending | Every limiter acquisition is appended to an audit ledger; job orchestrates landing → pipeline → certification; strict checks cover >1M distinct keys, rate limit, uniqueness, date range, and layer reconciliation | Deploy and run against `bootcamp_students.student_sri`, then retain the passing Delta certification record |

## Free Massive API budget

The controlled Phase 1 pilot measured 33,186 rows across two grouped-daily calls, or approximately 16,593 raw rows per successful response. Phase 2 therefore uses a default raw target of 1.1 million rows (about 67 similarly dense trading dates) while allowing up to 252 checkpointed dates if market density is lower. The client permits no more than four physical attempts in any rolling 60-second window, including retries.

The certification does not infer compliance from configured values. It reads the append-only limiter acquisition ledger and fails if the observed rolling maximum exceeds four. It also fails at exactly 1,000,000 Silver keys because the capstone requirement is strictly greater than one million.

## Dataset contract

```text
Volume response.json  ──Auto Loader──> bronze_market_daily ──classify──> silver_market_bars
Volume manifest.json  ──Auto Loader──> bronze_market_manifests               │
                                              │                               ├──> gold_stock_performance
                                              ├──> reconciliation             ├──> gold_market_peer_comparison
                                              │                               └──> gold_market_data_coverage
                                              └──────────> silver_market_quarantine
```

Gold peer comparisons deliberately use the covered broad market in Phase 2. Sector and industry are not fabricated; they will be added after the company/reference data becomes available in Phase 3.

## Deployment gate

The bundle validates against the selected `dataexpertio_srini` profile. Phase 2 now has a dedicated `market_pipeline` with explicit market-only source globs, and `market_volume_backfill` references it directly. It can therefore be deployed and tested without the Lakebase-dependent applications or embedding job. Run the 10-date market pipeline first, inspect reconciliation, and only then start the bounded full backfill.
