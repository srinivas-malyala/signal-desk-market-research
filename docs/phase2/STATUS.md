# Phase 2 Status — Spark Market Pipeline and Volume Proof

Updated: 2026-09-10

Phase 2 is implemented and deterministically tested locally. Workspace execution and the measured one-million-row result remain explicit acceptance gates; this document does not claim those external proofs have passed.

| Unit | Implementation | Local evidence | Remaining workspace gate |
|---|---|---|---|
| 2.1 Bronze market streaming tables | Isolated pipeline deployed | Dedicated `market_pipeline` resource, modern Spark Declarative Pipelines API, Auto Loader, explicit response/manifest schemas, rescued data, immutable file/request lineage, and per-date reconciliation | Process the Volume pilot exactly once and prove every manifest row count matches Bronze |
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

The first selective deployment attempt was rejected before resource creation because the workspace Pipeline API does not accept single-asterisk include patterns. Explicit per-file library entries are the tracked corrective action.

The explicit-file resource was then deployed successfully as pipeline `6d6d9a79-3b5d-4fca-af6d-61765d0aae60`; its first incremental update remains the next gate.

Update `dcb6b56c-1b58-49a1-be6c-fb5520187f9a` stopped during Bronze flow analysis before any table write: Massive's case-distinct `T` ticker and `t` timestamp fields were ambiguous under Spark's default case-insensitive resolver. The tracked correction is pipeline-scoped case-sensitive resolution, preserving both fields.

The market pipeline now enables `spark.sql.caseSensitive` without changing the research pipeline. Nineteen focused configuration, source-contract, and analytics tests plus lint pass before redeployment.

Update `a84ba60e-92cf-4d97-8d98-6b244432c706` completed all nine datasets. SQL warehouse evidence showed 10 `MATCH` dates and exactly 149,051 manifest/Bronze rows, but Silver contained zero accepted and 149,051 quarantined rows. Every quarantine reason was `schema_rescued`; the rescued payload contained only Massive's top-level `count`, now added to the explicit response schema. A controlled full refresh is required to replay the already-consumed Bronze files after deployment.

The corrected envelope schema passes 20 focused Phase 2 tests and lint.

The correction is deployed. A full refresh of this development-only market pipeline is pending explicit approval so Auto Loader can rebuild the nine managed Phase 2 tables from the same immutable 10-date source files.

Pipeline `6d6d9a79-3b5d-4fca-af6d-61765d0aae60` was redeployed with this correction; a new incremental update is the next gate.
