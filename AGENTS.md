# Signal Desk contributor guidance

## Start here

Read `GOALS.md`, the active milestone in `PLANS.md`, and
`docs/assistant/CONTEXT.md` before working on the embedded research assistant.
Read `CODEX_HANDOFF.md` and `docs/IMPLEMENTATION_STATUS.md` for the existing
deployment. Historical acceptance is not proof of current live health.

Inspect `git status --short` before editing. Preserve unrelated changes,
including deletions and untracked media. Use targeted discovery; do not reload
all phase documents. Follow the user's requested scope: planning does not
authorize implementation or deployment.

## Architecture constraints

- Render hosts Flask and FastMCP. Databricks hosts the Supervisor and data plane.
- Browser ownership comes from Google OIDC. Flask executes MCP writes using
  fresh, request-bound signed assertions for that browser user.
- The embedded Supervisor receives a separate restricted MCP credential. Permit
  only performance, company research, comparison, and semantic research tools.
  Enforce restrictions on invocation as well as tool discovery.
- Exclude watchlist reads, notable updates, and the three business write tools
  from the embedded connection. Fetch user context through Flask's user-bound path.
- Never use model-supplied identity, a user email argument, or a shared machine
  credential to authorize a browser user's state.
- Keep existing standalone Supervisor and direct frontend workflows functional.
- Research tool audit, cache, and quota writes are permitted; user-owned business
  mutations require explicit browser confirmation.

## Development rules

Use `docs/assistant/CONTRACTS.md` for API and state-machine contracts. Reject
unknown action types and fields. Treat model output and retrieved text as
untrusted. Store validated proposals before displaying executable controls.
Confirmation executes the stored immutable payload, with a stable idempotency
key; edits create a new revision. Recover uncertain writes through that key.

Use server-owned conversation history and ownership predicates on every query.
Use shared database coordination across Gunicorn workers. Do not hold a database
connection while waiting for a Supervisor stream. Keep transcripts out of
cookies and ordinary logs; sanitize rendered content and citation URLs.

Use the existing checksum-protected migration mechanism. Add a new migration;
never edit an applied one. Update table allowlists where needed. Persistent
Lakebase tables must use the configured suffix (currently `_srini`) in the shared
schema. Never alter other students' tables or the shared schema.

Use `apply_patch` for edits. Avoid opportunistic refactors and unrelated data
pipeline changes. Regenerate affected hashed service locks when dependencies
change. Do not import the CLI capture harness into the threaded web server.

## Verification and deployment

Follow `docs/assistant/VERIFICATION.md` for targeted tests and evidence, and
`docs/assistant/DEPLOYMENT.md` for rollout and rollback. Run proportional tests
after code changes; documentation-only changes require link and diff checks.
Report checks actually run, failures, and unverified assumptions accurately.

Load Databricks core plus the applicable product skill for platform work.
For live operations, obtain the user's chosen profile and always pass
`--profile <chosen-profile>`; never rely on defaults. The profile recorded in
historical handoffs is context, not fresh selection authority. Store credentials
only in approved secret configuration; never print tokens or connection URLs.

Deployment, grants, migrations against live databases, paid plan changes, and
live write evaluations require scope established by the user's request. Prepare
reviewable code and evidence first; do not infer deployment authority from a
planning request. Do not create threads or delegate unless requested.

## Keeping context current

Update milestone status and evidence in `PLANS.md` after meaningful progress.
Record accepted design changes in `docs/assistant/DECISIONS.md`. Update context
when verified architecture changes. Distinguish proposed, implemented, locally
verified, and deployed states. Update the existing handoff and implementation
tracker when runtime project state changes, not merely when planning files are added.
