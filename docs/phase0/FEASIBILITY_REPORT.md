# Phase 0 Feasibility Report

Status: Local harness implemented; live checks pending explicit credentials and workspace selection.

## Safety envelope

- Massive grouped daily requests: maximum five dates per feasibility run.
- Global feasibility limiter: four requests per rolling 60 seconds, below the five-per-minute free allowance.
- Credentials: environment only; never accepted as command-line arguments or written to evidence.
- Logged response headers: content type/length, date, retry-after, and request ID only.
- Massive volume claim: based on observed `results` counts and later certified from distinct Silver `(ticker, trading_date)` keys—not an estimate alone.

## Run commands

```bash
export MASSIVE_API_KEY='set-locally-do-not-commit'
export SEC_USER_AGENT='Signal Desk student-project contact@example.com'
uv run python tools/phase0_feasibility.py --profile '<user-selected-profile>'
```

The sanitized machine-readable result is written to `build/phase0/feasibility.json`.

Bundle validation is separate so configuration failures are obvious:

```bash
databricks bundle validate --strict --target dev --profile '<user-selected-profile>'
```

## Remaining workspace gates

1. Select one authenticated Databricks CLI profile.
2. Select an existing Lakebase project/branch/database or authorize a dedicated development project.
3. Deploy the minimal app before it initializes its schema so the app service principal becomes schema owner.
4. Insert, update, and delete a uniquely labeled disposable row.
5. Configure or inspect Lakebase Lakehouse Sync in the UI and verify ordered Delta changes and latency. If unavailable, implement the approved Lakeflow event-table fallback.
