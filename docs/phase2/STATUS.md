# Phase 2 Status — Spark Market Pipeline and Volume Proof

Updated: 2026-09-10

Phase 2 workspace acceptance is complete, including the measured one-million-row and Massive free-rate-limit certification.

| Unit | Implementation | Local evidence | Remaining workspace gate |
|---|---|---|---|
| 2.1 Bronze market streaming tables | Workspace verified | Dedicated deployed market pipeline; 81 manifest dates and 1,255,677 rows exactly match Bronze | None |
| 2.2 Silver market bars | Workspace verified | 1,255,489 accepted rows plus 188 deterministic quarantines equal Bronze; zero duplicate Silver keys | None |
| 2.3 Gold market analytics | Workspace verified | Coverage spans 2025-09-23 through 2026-09-09; bounded performance and peer queries pass | None for Phase 2 |
| 2.4 One-million-row certification | Workspace verified | Persisted PASSED report proves 1,255,489 distinct Silver keys and a measured maximum of 4 Massive attempts per rolling minute | None |

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

Full-refresh update `ca1bbd17-bab5-40d8-a05b-6bf248d03f15` was explicitly approved and completed successfully, rebuilding only the development market tables from the immutable 10-date Volume source.

Warehouse acceptance passed: all 10 dates report `MATCH`; 149,051 manifest rows equal 149,051 Bronze rows; Silver contains 149,031 accepted rows and 20 `duplicate_ticker_date` quarantines with zero duplicate accepted keys; all 10 coverage dates are `COMPLETE`; and the bounded Gold performance query succeeded.

After Phase 3 acceptance, strict bundle validation passed and the Lakebase-independent volume orchestration was selectively deployed as job `356134100996112`. Its bounded run retains the existing four-attempts-per-rolling-minute limiter, scans at most 252 dates, and stops landing when the available raw estimate reaches 1.1 million rows before refreshing and certifying the Spark tables.

Bounded certification run 748482763142265 completed successfully with the default limits.

Its landing stage completed successfully: 71 API dates produced 1,106,626 newly available raw rows and 116,806,780 landed bytes, including 69 data dates and 2 no-data dates, with zero retries or failures. Together with the earlier pilot, the Volume contains 81 market-date partitions.

Incremental market update a854185a-a1c8-4edc-b887-115998831964 completed. The persisted certification is PASSED: 1,255,677 manifest and Bronze rows reconcile exactly to 1,255,489 distinct Silver keys plus 188 quarantined rows, with zero duplicate Silver keys. The evidence covers 81 dates from 2025-09-23 through 2026-09-09 and records 83 audited API attempts with an observed maximum of 4 in any rolling minute. Independent SQL warehouse statement 01f1ad75-a4ec-18b6-b06a-f495785e1152 confirmed the layer counts.
