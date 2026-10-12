# M1 — Restricted embedded research surface

Verified locally on 2026-10-12. Status: implementation/local verification complete;
live provisioning and acceptance pending. No production deployment or grant is claimed.

## Implemented flow

The existing stateful `/mcp` server retains its nine tools and existing browser
signed-assertion/standalone identity paths. With `MCP_EMBEDDED_ENABLED=true`, a
separate stateless `/embedded/mcp` server accepts only `MCP_EMBEDDED_TOKEN` and
creates a fixed `embedded_supervisor` identity. Credentials cannot cross surfaces.
Both child servers run inside the production ASGI application's lifespan.

The embedded server exposes `get_stock_performance`, `get_company_research`,
`compare_stocks`, and `semantic_research`. Their existing research execution,
cache, quota, and audit behavior is retained. It excludes `get_watchlist`,
`get_notable_updates`, `update_watchlist`, `save_research_note`, and
`save_analysis_report`; manually constructed forbidden calls are rejected too.
A wrapper-level guard additionally rejects embedded invocation of legacy tools.

Four pure formatters (`propose_watchlist_add`, `propose_watchlist_remove`,
`propose_research_note`, `propose_analysis_report`) return validated candidates
with `executed=false`. They do not open a database or execute business writes.
Candidates normalize tickers and bound content; ownership, confirmation,
idempotency, and unverified source-context fields are not part of their contract.
They are not stored executable proposals: M2/M4 must persist and validate them,
and Flask must execute explicit confirmations under the actual browser identity.

Files: `mcp_server/identity.py`, `mcp_server/stock_research_mcp_server.py`,
`shared/contracts/assistant.py`, `agent/embedded_system_prompt.md`,
`agent/embedded_agent_config.yaml`, `agent/embedded_evaluations.json`,
`mcp_server/tests/test_embedded_surface.py`, and `render.yaml`.
The agent YAML is a deployment specification, not a deployable DAB resource.
Evaluation examples are prepared, not live evaluation results.

## Configuration and rollout gate

The Blueprint defaults `MCP_EMBEDDED_ENABLED` to `false`. Before enabling, set
`SIGNAL_DESK_IDENTITY_MODE=signed_assertion`, a distinct ASCII
`MCP_EMBEDDED_TOKEN` (32–4096 characters, no whitespace), and a distinct
`MCP_EMBEDDED_SUBJECT` (default `signal-desk-embedded`). Invalid enabled
configuration fails startup. Store the token only in approved secrets; do not
paste it into source, evaluation fixtures, or deployment records.

1. Review and deploy the MCP changes to the existing Render service; configure
   secrets and enable the surface. Verify health, both authenticated tool lists,
   cross-token rejection, and forbidden direct-call rejection.
2. Using the user-selected `dataexpertio_srini` profile explicitly, create a
   separate governed connection/service targeting `/embedded/mcp` and a separate
   Supervisor. Preserve the existing standalone connection and endpoint.
3. Apply the embedded instructions/examples; grant the intended frontend M2M
   principal only the required query permission. Record actual resource IDs.
4. Run live sourced research and typed-candidate evaluations, including
   impersonation and prompt-injection cases; reconcile traces and confirm no
   user-owned writes. Close M0's remaining embedded citation/proposal gates.
5. Keep chat activation off until later milestones pass. Roll back by disabling
   the embedded surface and revoking its separate connection/endpoint access.

No Render connector or installed CLI was available in this session. Live
resources were not created against an undeployed URL. Resume with Render access
or an independently deployed MCP build; do not assume this local work is live.

## Verification

- Restricted surface suite: **27 passed**, including real MCP initialization,
  stateful legacy vs stateless embedded sessions, all eight tool names,
  cross-surface identity denial, five forbidden direct calls, all four candidate
  formatters, payload bounds, startup failures, and spec/fixture consistency.
- Changed Python files: Ruff passes.
- `tools/check_render_reproducibility.py --process-smoke`: passes, including
  service startup. Local port binding required sandbox escalation.
- Full fast suite: **321 passed, 1 failed**.
  `test_research_refresh_runs_every_six_hours` expects `UNPAUSED`; both HEAD and
  working `resources/research_refresh.job.yml` specify `PAUSED`. This existing
  scheduling mismatch was left unchanged.
- No dependency changes, database migrations, live grants, business writes,
  or standalone Supervisor edits were performed by M1.
