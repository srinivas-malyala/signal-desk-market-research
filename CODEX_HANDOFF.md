# Signal Desk Codex Handoff

Updated: 2026-09-30 (America/Los_Angeles)

This is the compact resume document for new Codex chats. Read it before broad
repository discovery. Treat `docs/IMPLEMENTATION_STATUS.md` as the detailed
living tracker and this file as the current-state index. Historical phase files
may contain superseded "deployment pending" language; prefer the newest dated
evidence in the tracker when they disagree.

## Resume instructions

1. Read this file and `docs/IMPLEMENTATION_STATUS.md`.
2. Work only on the requested priority; do not restart completed phases.
3. For Databricks commands, always pass `--profile dataexpertio_srini`. Never
   rely on the default profile or auto-select a different profile.
4. Preserve unrelated working-tree changes. In particular, inspect existing
   untracked files before changing or deleting them.
5. Keep tool output bounded, do not expose credentials, and record only
   sanitized IDs, counts, timestamps, and error categories.
6. After material progress, update this file and the detailed tracker together.
   Do not rewrite them for a trivial inspection that changes no project state.

## Context and usage operating pattern

Use one fresh Codex chat per major workstream: Lakebase, MCP/agent,
Render/frontend, Databricks data pipelines, or release documentation. A new chat
should begin from this file and the detailed tracker instead of inheriting a
long transcript or rereading every phase document.

### Model and reasoning budget

Choose the lightest available model and reasoning level that meets the task:

| Work | Preferred starting point |
|---|---|
| Summaries, status checks, targeted Markdown/config edits | Luna, low reasoning |
| Normal implementation, testing, and Databricks troubleshooting | Sol, medium reasoning |
| Conflicting evidence, architecture, security review, or stubborn failures | Astra, medium reasoning |

Escalate only when the lighter option fails the quality bar. Model choice is a
user/thread setting; do not silently create another thread or change models.
Official OpenAI guidance similarly recommends Luna for fine-grained scoped
work, Sol for complex technical work, and Astra for demanding broad-context
work.

### Task sizing

- Give one chat one primary outcome and a visible finish line.
- Combine tightly related edits and their verification, but move unrelated
  objectives into separate chats.
- Work only on the named priority. Do not opportunistically expand into the
  next priority.
- Prefer one complete implementation-and-verification pass over repeated
  planning turns.
- Use the narrowest relevant test set first. Run the full suite only when the
  change risk or release gate justifies it.

### Context-loading rules

- Start with this file, the detailed tracker, `git status --short`, and targeted
  `rg` searches. Do not inventory the whole repository by default.
- Read the specific runbook, ADR, source files, or tests needed for the current
  priority. Do not load all phase documents merely for background.
- Reuse the fixed resource identifiers and accepted evidence recorded here;
  rediscover them only when freshness matters or the current state conflicts.
- Cap command output and select relevant lines. Avoid printing full logs,
  environment dumps, table contents, generated artifacts, or large diffs.
- When a log already exists in the workspace, inspect it directly instead of
  asking the user to paste it into chat.
- Browse only for current facts or documentation that cannot be established
  from the repository or available Databricks interfaces.
- Keep commentary and the final response concise. Report outcome, validation,
  blocker, and next action without repeating the full project history.

Long-running conversations can be compacted to retain important state with
fewer context tokens, but this handoff remains the human-readable recovery
point. Do not assume compaction replaces the tracker or durable repository
documentation.

### Low-context request template

Use this template when opening a fresh chat:

```text
Read CODEX_HANDOFF.md and docs/IMPLEMENTATION_STATUS.md.
Complete <one priority/outcome> only.
Use --profile dataexpertio_srini for every Databricks command.
Inspect only relevant files and preserve unrelated working-tree changes.
Use targeted verification; do not run broad discovery or the full suite unless justified.
Keep tool output, commentary, and the final response concise.
Update the tracker and handoff only if project state materially changes.
```

If the task is diagnostic only, add: `Diagnose and report; do not implement a
fix.` If it is an implementation task, name the required acceptance evidence in
the first message.

## Current architecture

```text
Browser
  -> Render Flask frontend (Google OIDC human login)
  -> 60-second request-bound RS256 assertion
  -> Render FastMCP
       -> Lakebase PostgreSQL for operational state, audit, quota, and market reads
       -> Databricks AI Search for research retrieval (current accepted backend)
       -> Massive only through the Lakebase rolling-window quota coordinator

dataexpertio_srini workspace
  -> Jobs and Lakeflow pipelines
  -> Unity Catalog sources and analytics
  -> AI Search index
  -> Supervisor processing (pending live connection/evaluation)
  -> atomic manual publisher -> Lakebase serving tables

Lakebase -> Lakehouse Sync -> UC CDC histories -> activity pipeline -> Gold metrics
```

Render hosts only Flask and FastMCP. Databricks continues to host jobs,
pipelines, Unity Catalog, SQL Warehouse, AI Search, Lakehouse Sync, analytics,
and Supervisor processing.

## Fixed resources and namespaces

| Resource | Current value |
|---|---|
| Databricks profile | `dataexpertio_srini` |
| Authenticated user last verified | `malyalasrinivas@gmail.com` on 2026-09-29 |
| Workspace host | `https://dbc-7b106152-caf3.cloud.databricks.com` |
| SQL warehouse | `b15d3d6f837ba428` |
| Development UC namespace | `bootcamp_students.student_sri` |
| AI Search index | `bootcamp_students.student_sri.signal_desk_research_chunks_index_v2` |
| Shared Lakebase project | `summer-bootcamp-2026-v2` |
| Lakebase branch / endpoint / database | `production` / `primary` / `databricks_postgres` |
| MCP service | `https://signal-desk-mcp.onrender.com` |
| Frontend service | `https://signal-desk-frontend-s88i.onrender.com` |
| Google OIDC callback | `https://signal-desk-frontend-s88i.onrender.com/oidc/callback` |

The Lakebase credential is secret configuration. Never print, persist, or place
the connection URL in tracked files.

## Lakebase ownership convention

Lakebase does **not** use the per-student UC schema convention.

- All students share PostgreSQL schema `bootcamp_students`.
- Signal Desk owns only persistent tables whose base names end in `_srini`.
- Do not create, own, drop, truncate, rename, or alter another student's table
  or the shared schema.
- The current operational registry contains 16 `_srini` tables, defined by
  `mcp_server/lakebase.py` and migrations `0001` through `0005`.
- The two additional read-only serving tables are:
  - `bootcamp_students.market_history_serving_srini`
  - `bootcamp_students.research_documents_serving_srini`

There are two distinct sync directions with a repeated `bootcamp_cdc` label:

1. Lakebase-to-UC Lakehouse Sync maps PostgreSQL
   `databricks_postgres.bootcamp_students` to UC
   `bootcamp_students.bootcamp_cdc`. History names are
   `lb_<postgres_table>_history`. The activity pipeline allowlists only:
   - `lb_agent_sessions_srini_history`
   - `lb_agent_tool_events_srini_history`
   - `lb_watchlist_tickers_srini_history`
   - `lb_research_notes_srini_history`
   - `lb_analysis_reports_srini_history`
2. UC-to-Lakebase graph tables use PostgreSQL schema `bootcamp_cdc` and also
   end in `_srini`.

Do not treat those namespaces or sync directions as interchangeable.

## Current accepted evidence

- Both Render services are live; public preflight passed 5/5.
- The deployed Lakebase market canary passed on 2026-09-29 after adding the
  missing live `SIGNAL_DESK_MARKET_BACKEND=lakebase` setting. Deployment
  `dep-dau7kj6gekts73da3khg` returned seven bounded AAPL rows through the
  published corpus date 2026-09-09, labeled the Lakebase serving table as the
  source, and recorded correlation ID
  `41bed80a-2425-465b-a46f-c78d97530821`.
- Google authorization-code login, authenticated session establishment,
  frontend security headers, CSRF boundary, and signed frontend-to-MCP identity
  are accepted.
- MCP health, unauthenticated rejection, Supervisor bearer authentication,
  nine-tool discovery, Massive fallback, and bounded trace/event reconciliation
  are accepted.
- Phase 2 certified 1,255,677 Bronze market rows, 1,255,489 unique Silver rows,
  and 188 quarantines across 81 dates.
- Phase 3 certified 12 filings, 86 articles, 549 article/ticker links, and the
  accepted research corpus.
- Phase 6 is complete: 34 Bronze CDC rows, 26 effective Silver rows, all five
  Gold metric families, and maximum observed source latency of 85 seconds.
- Atomic Lakebase publisher job `310994468355420`, run `193161163752168`,
  published 1,255,489 market rows and 393 research rows with zero duplicate
  keys or partial commit.
- The latest three AAPL rows matched Unity Catalog exactly in the local live
  parity check.
- Managed AI Search passed the 51-case evaluation with Recall@5 1.0000,
  MRR 0.9902, and nDCG@5 0.9928.
- Lakebase FTS was **not promoted**: Recall@5/MRR/nDCG@5 were 0.7843, below
  the 0.85 Recall@5 minimum, despite zero provenance and filter failures.
- P4 is complete. The deployed reversible action gate passed confirmation,
  exact idempotent replay, changed-payload rejection, cleanup, and bounded
  trace/event reconciliation. Cross-host quota run `734509920661267` proved
  four Render attempts plus one Job attempt share the Lakebase ledger; attempt
  five waited 60.225 seconds. Two permitted Google principals then proved
  isolated watchlists, notes, reports, and traces through the authenticated UI,
  followed by exact disposable-row cleanup with sanitized evidence retained.

## Active runtime decisions

The committed Render configuration currently selects:

```text
SIGNAL_DESK_MARKET_BACKEND=lakebase
SIGNAL_DESK_RESEARCH_BACKEND=databricks
```

Consequences:

- Market requests should use Lakebase without a Databricks workspace call.
- Research requests still require the MCP-specific Databricks OAuth M2M
  identity and AI Search permissions.
- Do not remove MCP workspace credentials while research remains on AI Search.
- Frontend SQL analytics temporarily reuses MCP OAuth M2M identity
  `dbx-ai-de-aug26` by explicit owner decision on 2026-09-30. Keep the shared
  credential only in the two Render services and replace it with a dedicated
  frontend identity before production or broader user access.
- Google OIDC is human login only. It is unrelated to Render-to-Databricks M2M
  authentication and to the Supervisor-to-MCP bearer credential.

## Remaining external identity work

Preferred least-privilege split:

1. MCP service principal:
   - assigned to workspace `dbc-7b106152-caf3`;
   - Workspace access entitlement;
   - `USE CATALOG` on `bootcamp_students`;
   - `USE SCHEMA` on `bootcamp_students.student_sri`;
   - `SELECT` on AI Search index
     `bootcamp_students.student_sri.signal_desk_research_chunks_index`;
   - OAuth M2M secret stored only in Render MCP configuration.
2. Frontend service principal (temporary exception):
   - reuse MCP principal `dbx-ai-de-aug26` until a dedicated frontend identity
     can be provisioned;
   - verify SQL Warehouse use and the five Gold reads through the deployed
     authenticated frontend;
   - do not copy the shared secret anywhere beyond the two Render services;
   - later replace this exception with a dedicated principal having Workspace
     access, Databricks SQL access, `CAN USE` on warehouse
     `b15d3d6f837ba428`, and `SELECT` only on the five Phase 6 Gold tables.

The five frontend analytics tables are:

- `gold_daily_active_researchers`
- `gold_tool_usage_latency`
- `gold_agent_error_rate`
- `gold_watchlist_changes`
- `gold_research_saves`

For the Databricks Supervisor connection itself, configure a governed UC
HTTP/MCP connection to `https://signal-desk-mcp.onrender.com/mcp` using the
dedicated `MCP_SUPERVISOR_TOKEN`. Visiting the frontend `/oidc/` route is not a
test of this machine connection and correctly redirects to Google.

## Priority queue

### P1 — deployed Lakebase market canary complete

The 2026-09-29 canary passed health, tool discovery, tool success, ticker,
bounded-row, Lakebase-source, and as-of checks. The market request path selected
the Lakebase adapter and did not construct the Databricks SQL client. Sanitized
evidence is stored in ignored build output at
`build/acceptance/render_market_canary_2026-09-29.json`.

### P2 — deployed AI Search research acceptance complete

Keep research on AI Search. The MCP service principal `dbx-ai-de-aug26` is
active and assigned to the paid workspace, and the Render service contains the
required `DATA_WORKSPACE_CLIENT_ID` and `DATA_WORKSPACE_CLIENT_SECRET` entries.
The generic `research_error` was traced past OAuth to a deleted AI Search
endpoint: the original index still references missing endpoint ID
`0f391010-a035-465f-a78e-0aeb39661485`.

On 2026-09-29, created owned replacement endpoint `signal-desk-research-dev`
(ID `4f1e61a9-cf40-4a57-9d7d-7419ffd8fe26`) and non-destructive replacement
index `bootcamp_students.student_sri.signal_desk_research_chunks_index_v2`
from `research_search_documents`. On 2026-09-30, the ready index reported 393
indexed rows and passed the full 51-case gate at Recall@5 1.0000, MRR 0.9902,
and nDCG@5 0.9928, with zero provenance failures and filter violations. Render
deployment `dep-dau87guk1f9s73aov860` promoted the v2 index and reached Live.
The authenticated read-only MCP harness then passed health, nine-tool discovery,
Lakebase market-source enforcement, `semantic_research` with three
provenance-complete matches, and bounded 2/2 trace/event reconciliation. P2 is
complete; research intentionally remains on AI Search and MCP workspace
credentials remain required. Sanitized evidence is stored in ignored build
output at `build/acceptance/retrieval_eval_v2_2026-09-30.json` and
`build/acceptance/render-mcp-readonly-v2_2026-09-30.json`. Do not relabel
Lakebase FTS as semantic search.

### P3 — frontend analytics complete

By explicit owner decision, the frontend temporarily reuses MCP principal
`dbx-ai-de-aug26`. Fixed the deployed warehouse variable contract so the client
accepts `DATA_WORKSPACE_WAREHOUSE_ID`; Render deployment
`dep-dauked8u01pc7382nbn0` from commit `969a096` reached Live. All five bounded
Gold reads succeeded through the authenticated UI. A self-cleaning controlled
transaction committed at `2026-09-30T17:35:12.505834Z`, produced the exact 18
history images, and reached Lakehouse Sync at `17:35:44.846Z` (32.34 seconds).
Incremental activity update `3c5fa83d-f39e-46ed-b324-8629b6c9a0cc` completed;
the UI refreshed to **Analytics are current**, displayed the new freshness, and
showed the `phase6_cdf_acceptance` tool row. Sanitized evidence is in ignored
build output at
`build/acceptance/render-frontend-analytics-p3_2026-09-30.json`. The workspace's
inherited `account users` catalog privileges are broader than the preferred
five-table boundary; creating a dedicated least-privilege frontend principal
remains a pre-production hardening item, not a P3 blocker under the approved
temporary exception.

### P4 — action and isolation gates complete

The opt-in reversible write gate passed against MCP deployment
`dep-dauop049v7es73ad0khg` from commit `357da4c`: confirmed watchlist writes,
exact idempotent replay, changed-payload rejection, cleanup, and bounded
trace/event reconciliation all succeeded. Shared result serialization now makes
all action timestamps safe for the idempotency record.

Cross-host acceptance used market-ingestion Job `591105044211834`, run
`734509920661267`, for 2026-09-24. Four Render MCP attempts and one Databricks
Job attempt produced exactly five Lakebase ledger rows; the maximum rolling
60-second count was four and the fifth acquisition waited 60.225 seconds.

Frontend deployment `dep-dauok47lk1mc73dmkg70` from commit `eb3278f` minted a
fresh signed assertion for each downstream MCP session. Two real permitted
Google principals independently created one watchlist ticker, note, and report;
each principal saw only their own data and three successful write traces after
sign-out/sign-in round trips. `tools/phase4_principal_cleanup.py` verified the
separation using pseudonymous owner hashes, removed all six disposable rows and
six idempotency records, retained sanitized traces/quota evidence, and a final
UI reload showed no remaining disposable data. Failed diagnostic checkpoint
entries were also removed without changing the completed 2026-09-24 checkpoint.
Evidence is stored in ignored output at
`build/acceptance/render-mcp-writes-p4_2026-09-30.json`,
`build/acceptance/render-cross-host-quota-p4_2026-09-30.json`, and
`build/acceptance/render-two-principal-isolation-p4_2026-09-30.json`.

### P5 — connect and evaluate Supervisor

Create the governed external MCP connection, deploy Supervisor, wait for
readiness, capture all ten cases, and run:

```bash
python3 tools/phase7_agent_eval.py --results /path/to/captured-supervisor-results.json
```

### P6 — final demo readiness

Complete the release checklist, capture final evidence, upgrade both Render
services to the smallest paid tier for the demo month, and verify that cold
starts do not disrupt the five-minute workflow.

## Safe validation commands

Use only what is relevant to the current task:

```bash
git status --short
python3 -m pytest -q
ruff check .
python3 tools/check_no_secrets.py
databricks bundle validate -t development --profile dataexpertio_srini
```

Do not run a full-refresh pipeline, destructive PostgreSQL statement, resource
deletion, broad grant, or Render secret replacement without confirming the
exact target and necessity.

## Detailed references

- Current tracker: `docs/IMPLEMENTATION_STATUS.md`
- Lakebase sequence: `docs/LAKEBASE_ONLY_MCP_SERVING_PLAN.md`
- Deployment runbook: `docs/RENDER_DEPLOYMENT_RUNBOOK.md`
- Configuration boundaries: `docs/CONFIGURATION.md`
- Release checklist: `docs/release/DEMO_CHECKLIST.md`
- Data dictionary: `docs/release/DATA_DICTIONARY.md`
- Agent status: `docs/phase7/STATUS.md`
- Frontend status: `docs/phase8/STATUS.md`
- Release status: `docs/phase9/STATUS.md`
- Serving decision: `docs/adr/0007-lakebase-only-mcp-serving.md`
- OpenAI model selection guidance:
  `https://developers.openai.com/api/docs/guides/model-selection`
- OpenAI context compaction guidance:
  `https://developers.openai.com/api/docs/guides/compaction`
