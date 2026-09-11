# Phase 0 Feasibility Report

Status: Workspace, Massive, and SEC checks passed on 2026-09-10. The admin-managed Lakebase URL secret and shared-table namespace were confirmed on 2026-09-11; connectivity, CRUD, and CDF execution remain Phase 4 gates.

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

1. Refactor operational SQL from the obsolete private `student_sri` schema assumption to fully qualified `bootcamp_students.<table>_srini` names.
2. Fetch the connection URL from admin-managed secret `database/lakebase-url` and verify connectivity without exposing it.
3. Verify create/read/write permissions for `_srini` tables without creating or modifying the shared schemas.
4. Insert, update, and delete a uniquely labeled disposable row.
5. Configure or inspect Lakebase Lakehouse Sync and verify ordered changes in the shared `bootcamp_cdc` namespace. If unavailable, implement the approved Lakeflow event-table fallback.
