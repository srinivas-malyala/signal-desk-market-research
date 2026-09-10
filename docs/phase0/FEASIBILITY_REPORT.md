# Phase 0 Feasibility Report

Status: Workspace, Massive, and SEC checks passed on 2026-09-10; the Lakebase CDF check remains gated as described below.

## Verified results

- Databricks profile: `dataexpertio_srini` (passed current-user, Apps, Lakeflow Pipelines, and Lakebase project-list checks).
- Bundle: strict development-target validation passed.
- Massive: five grouped-daily calls returned 82,714 rows with no failures.
- Observed average: 16,542.8 rows per trading date.
- One-million-row projection: 61 trading dates/calls, with a theoretical minimum of 15.25 API minutes at the configured four-calls-per-minute limit.
- Secret handling: the existing `massive/api-key` Databricks secret was decoded in memory and was not logged or written to evidence.
- SEC: submissions and Company Facts requests for Apple (CIK `0000320193`) both returned HTTP 200 using the user-approved identifying contact. The contact value is not stored in the report.

## Safety envelope

- Massive grouped daily requests: maximum five dates per feasibility run.
- Global feasibility limiter: four requests per rolling 60 seconds, below the five-per-minute free allowance.
- Credentials and identifying contacts: environment or an explicitly selected Databricks secret; never accepted as command-line arguments or written to evidence.
- Logged response headers: content type/length, date, retry-after, and request ID only.
- Massive volume claim: based on observed `results` counts and later certified from distinct Silver `(ticker, trading_date)` keys—not an estimate alone.

## Run commands

```bash
export MASSIVE_API_KEY='set-locally-do-not-commit'
export SEC_USER_AGENT='Signal Desk student-project contact@example.com'
uv run python tools/phase0_feasibility.py --profile '<user-selected-profile>'
```

When the key already exists in a Databricks secret scope, keep it out of the
local environment and read it in memory:

```bash
uv run python tools/phase0_feasibility.py \
  --profile '<user-selected-profile>' \
  --massive-secret-scope massive \
  --massive-secret-key api-key
```

The sanitized machine-readable result is written to `build/phase0/feasibility.json`.

Bundle validation is separate so configuration failures are obvious:

```bash
databricks bundle validate --strict --target dev --profile '<user-selected-profile>'
```

## Remaining workspace gates

1. Replace the approved student-role placeholder with the usable Lakebase connection secret when it becomes available.
2. Verify that the `student` role can connect and create/read/write tables in the pre-created `student_sri` schema.
3. Insert, update, and delete a uniquely labeled disposable row.
4. Configure or inspect Lakebase Lakehouse Sync in the UI and verify ordered Delta changes and latency. If unavailable, implement the approved Lakeflow event-table fallback.
