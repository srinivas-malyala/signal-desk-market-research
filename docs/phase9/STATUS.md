# Phase 9 Status — Release and Capstone Proof

Updated: 2026-09-24

| Unit | Status | Completed | Remaining gate |
|---|---|---|---|
| 9.1 Deployment | Split-workspace redesign planned | Paid data bundle/resources remain verified; impact matrix, risk register, rollback, and independently testable Free-app deployment sequence are documented | Renew Free OAuth, pass egress/M2M gates, refactor clients, split deployment surfaces, validate both profiles, then deploy MCP/frontend and remaining paid resources |
| 9.2 End-to-end acceptance | Harnesses prepared | MCP post-deployment harness, Phase 7 trace evaluator, deterministic CDC fixtures, frontend smoke tests | Execute against deployed resources and two real principals |
| 9.3 Security/performance | Local controls accepted | Fail-closed identity, bounded inputs/responses, sanitized traces, cross-host quota coordination, privacy-safe analytics | Live cross-principal, concurrent quota, propagation latency, and deployed performance evidence |
| 9.4 Documentation/demo | Release artifacts updated for new host plan | Data dictionary, tool/API reference, traceability matrix, demo checklist, and split-workspace plan | Update/export the architecture diagram after connectivity design is accepted; include the Free Edition restart/readiness step and final evidence |

Release documentation deliberately separates implemented/local acceptance from
workspace proof and external blockers. No deployed-agent, CDC latency, or
frontend completion is claimed before the checklist evidence is recorded.
