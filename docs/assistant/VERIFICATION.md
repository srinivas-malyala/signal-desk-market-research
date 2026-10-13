# Assistant verification plan

Status: planned tests, not test results. Store sanitized results with commit and
date under ignored build/acceptance artifacts; link summaries from PLANS.md.

## Test layers

| Layer | Proposed coverage |
|---|---|
| Client/unit | Split SSE chunks, bounded buffers, EOF without completion, unknown events, deadlines, auth refresh, sanitized errors |
| Contracts | Strict request/proposal schemas, extra-field rejection, normalization/hash, citations backed by tool metadata |
| Routes | OIDC, CSRF, ownership, flags, pagination, duplicate submission, terminal stream errors |
| Database integration | Concurrent claims, lease loss, revision races, FK/unique constraints, rollback and crash recovery |
| Restricted MCP | Discovery plus manually invoked forbidden writes/user reads; existing credential regression |
| UI | Sanitized Markdown/URLs, keyboard use, stream interruption, exact preview, editing, confirmation, reload |
| Live acceptance | Two real users, deployed streaming, sourced answers, one authorized reversible write and exact retry |

Proposed new tests: test_supervisor_client.py, test_assistant_contracts.py,
test_assistant_routes.py, test_assistant_repository.py, test_assistant_actions.py,
test_embedded_mcp_policy.py, test_assistant_ui_contract.py. Use existing test
fixtures and injected client factories. Mark real network/database tests as
integration and deployed acceptance as e2e. Do not silently run writes through
the generic fast suite.

## Mandatory acceptance cases

- User A cannot load, revise, confirm, dismiss, or infer existence of B's records.
- Embedded credential is rejected for all three writes and both user-scoped reads.
- Model/retrieved instructions cannot authorize a write or supply ownership.
- Draft-only requests save nothing. Save proposals display exact content.
- Revision invalidates prior hash/confirmation; expired and incomplete proposals fail.
- Concurrent confirmations result in one mutation and consistent receipts.
- Crash after MCP commit recovers the original result with the same key.
- Changed payload with the same key is rejected by existing MCP enforcement.
- Duplicate message submission starts one run across different Gunicorn workers.
- Dead worker leases reconcile; stale worker cannot overwrite terminal outcome.
- Browser disconnect/timeout marks run interrupted and withholds action controls.
- Successful write plus failed readback shows verification pending, not write failed.
- Invalid source URL cannot execute JavaScript; model prose is not trusted citation proof.
- SEC/date/ticker filters remain arrays and align with the user's request.
- Missing evidence/fundamentals is labelled unavailable; dates/source are disclosed.
- Direct research, watchlist, notes/reports, auth, and analytics regressions pass.

## Local commands

Install both runtime extras because the dashboard imports FastMCP. M2 updates
CI to install both extras and adds a disposable PostgreSQL integration job;
hosted CI execution remains unverified until the commits are pushed.

```sh
uv sync --extra dashboard --extra mcp --dev
uv run pytest -m "not integration and not e2e"
uv run ruff check dashboard mcp_server shared tools tests
uv run python tools/check_no_secrets.py
uv run python tools/check_render_reproducibility.py --clean-install --process-smoke
```

Start with changed-feature tests, then the full fast suite at release. M2 CI lint
includes assistant, Supervisor and Gunicorn configuration modules; later runtime
modules still need proportional coverage. Clean-install checks may download
packages; process smoke and integration tests may require environment configuration.
Record failures rather than asserting success from static inspection.

## Live evidence checklist

Record selected profile/workspace, endpoint resource, commit, migration version,
flags, startup command, first-response/total timing, concurrent capacity, terminal
states, two-user isolation, restricted-call denials, confirmed write/readback,
retry behavior, and flag rollback. Do not store bearer tokens, database URLs,
user emails, or full transcripts. Live action tests must identify and clean up
their own test records only, within authorized scope.
