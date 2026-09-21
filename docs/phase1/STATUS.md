# Phase 1 Status — Massive Market Ingestion

Updated: 2026-09-21

| Unit | Implementation | Evidence | Remaining gate |
|---|---|---|---|
| 1.1 Shared Massive client and limiter | Cross-host implementation complete locally | Every physical attempt is limited; file-backed single-host mode retained; deployed MCP and ingestion paths select a Lakebase transaction-lock coordinator with database time, four-attempt/60-second ceiling, and fail-closed behavior | Apply migration `0005` and exercise simultaneous Job/MCP callers after app deployment |
| 1.2 Trading dates and checkpoints | Workspace verified | Two-year bounds, weekday planning, six explicit states, atomic persistence, stale recovery, corrupt-state failure, 20-date interruption/resume test, and successful UC Volume resume | None |
| 1.3 Immutable raw landing | Workspace verified | Atomic response/manifest pairs, SHA-256 validation, replay, holiday no-data state, row stop, structured metrics, strict bundle validation, 10-date workspace run, and zero-call rerun | None for the single-job workspace workflow |

## Controlled two-date pilot

The pilot used the existing `massive/api-key` Databricks secret through the explicitly selected `dataexpertio_srini` profile. Public market payloads and sanitized control evidence were written only beneath ignored `build/phase1-pilot`.

| Metric | Result |
|---|---:|
| Dates | 2026-09-08 through 2026-09-09 |
| HTTP attempts | 2 |
| Landed rows | 33,186 |
| Landed response bytes | 3,633,854 |
| Retries | 0 |
| Failures | 0 |

An identical rerun produced `api_dates=0`, `http_attempts=0`, and `skipped_dates=2`, proving checkpoint idempotency without consuming additional Massive quota.

## Deferred deployment checks

- Run the same code as the serverless `market_ingestion` Lakeflow Job.
- Confirm `os.replace` and advisory lock behavior on `/Volumes/bootcamp_students/student_sri/signal_desk_raw`.
- Complete a 10-date pilot and reconcile all manifest row counts.
- Apply Lakebase migration `0005`, then prove the fifth acquisition across one Job and one MCP host waits for the first rolling-window slot. Interactive Massive traffic remains disabled until that gate passes.

## Workspace deployment evidence

- 2026-09-10 — Selectively deployed `bootcamp_students.student_sri.signal_desk_raw` and development job `market_ingestion` (job ID `591105044211834`).
- 2026-09-10 — Run `998731877059605` failed before the Massive client was constructed: serverless `spark_python_task` execution did not define `__file__`. No API quota was consumed and no raw response was landed.
- 2026-09-10 — The entry point now falls back to Databricks' injected `filename`; the same guard covers the later article, SEC, certification, and embedding jobs. The regression suite passes 40 targeted tests plus lint.
- 2026-09-10 — The shared Massive limiter now locks a dedicated lock file, atomically replaces its JSON state, and writes one immutable JSON audit record per acquisition. This avoids unsupported repeated append/truncate operations on UC Volumes while retaining the four-attempt rolling limit.
- 2026-09-10 — Selectively redeployed `market_ingestion` with that limiter; the existing completed date and retryable checkpoint remain available for safe resume.
- 2026-09-10 — Retry run `281427550011155` landed 16,710 rows for 2026-09-08 with one API call. Its second date failed with `OSError` before another request; two automatic job retries also made zero calls. The persisted state and audit each contain exactly the one successful acquisition, isolating the remaining incompatibility to repeated in-place mutation/append on the UC Volume.
- 2026-09-10 — Redeployed the corrected development job; workspace pilot retry is the next gate.
- 2026-09-10 — Run `335002703842351` completed the 10-date workspace pilot with 149,051 available rows, nine trading dates with data, one no-data date, zero retries, and zero failures. It skipped two checkpointed dates and used eight additional Massive calls for the remaining dates.
- 2026-09-10 — Successful Spark Python entry points now return normally instead of raising `SystemExit(0)`; nonzero workload outcomes still fail the task. The regression suite remains green at 44 tests plus lint.
- 2026-09-10 — Explicitly redeployed the finalized job for the zero-call workspace rerun.
- 2026-09-10 — Run `809484306892540` proved workspace idempotency: all 10 dates were skipped, 149,051 available rows were reconciled, and no API call, retry, byte transfer, or failure occurred.
- No Lakebase-dependent application or embedding resource was deployed.

## Cross-host coordination implementation

Migration `0005` defines the namespaced attempt ledger
`bootcamp_students.massive_api_attempts_srini`. Each acquisition takes the same
PostgreSQL transaction advisory lock, counts attempts using Lakebase's clock,
and records its allowance before committing. This prevents host clock skew and
races between the MCP app, market ingestion, and article ingestion. Database
failure raises a safe limiter error before any Massive request is sent.

The legacy Volume-backed limiter remains available only for explicit
`process` mode and local/single-host testing. Bundle job parameters and MCP app
configuration explicitly select `lakebase`; there is no automatic fallback.
