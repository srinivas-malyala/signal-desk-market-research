# Embedded AI Research Assistant goals

Updated: 2026-10-12, America/Los_Angeles.
Status: M1 restricted MCP surface implemented and locally verified; live embedded
Supervisor provisioning and application chat remain pending. See
`docs/assistant/M1_FINDINGS.md` for evidence and external gates.
The separate Supervisor now exists; tool attachment and live verification remain
pending. See `docs/assistant/LIVE_STATUS.md` for actual IDs and the blocker.

## Outcome

A signed-in Signal Desk user can conduct multi-turn research through the
Databricks Supervisor, review a proposed watchlist change or saved draft,
confirm the exact content, and see the result in their own existing application
state. Retries and interrupted connections must not duplicate a mutation.

## Release goals

| ID | Goal | Required evidence |
|---|---|---|
| G1 | Grounded conversational research | Performance, comparison, and filtered SEC/article answers with verified sources and dates |
| G2 | Correct ownership | Two real users have isolated conversations, proposals, and saved state |
| G3 | Restricted Supervisor | Embedded credential cannot invoke business writes or ownership-scoped reads |
| G4 | Deliberate actions | Exact preview, explicit confirmation, immutable revision, stable retry key, successful readback |
| G5 | Recoverable conversations | Reloaded history; failed/interrupted runs labelled; duplicate submissions deduplicated |
| G6 | Reliable streaming | Bounded duration, disconnect handling, sanitized events, measured concurrent capacity |
| G7 | Safe delivery | Feature flags, additive migration, deployment evidence, tested flag rollback |
| G8 | Existing workflows preserved | Direct research, watchlist, saved research, authentication, and analytics regressions pass |

## Initial scope

Multi-turn research, server-owned history, citations, progress, user-context
snapshots, draft editing, and four proposal types: watchlist add/remove,
save note, save report. Support the existing Primary watchlist initially.

## Deferred scope

Trading, automatic writes, autonomous ingestion refresh, unrestricted SQL,
cross-user shared conversations, end-user credential delegation through the
Supervisor, guaranteed remote cancellation, and a new task queue unless measured
web-tier capacity requires one. Changes to the existing standalone Supervisor
are outside this feature's default scope.

## Definition of done

All G1–G8 evidence is linked from `PLANS.md`; all required tests pass; security
and failure cases in `docs/assistant/VERIFICATION.md` pass; infrastructure limits
are measured; configuration and user guidance are updated; read-only pilot
precedes action rollout. No milestone is complete solely because code exists.
