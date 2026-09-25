# Phase 9 Status — Release and Capstone Proof

Updated: 2026-09-24

| Unit | Status | Completed | Remaining gate |
|---|---|---|---|
| 9.1 Deployment | Render artifacts locally accepted; external deployment pending | Two-service Blueprint, `$PORT`/health packaging, data-bundle separation, OIDC/JWT identity, explicit M2M clients, architecture, cost boundary, risk register, rollback, and acceptance harnesses are implemented; 231 tests and Ruff pass | Renew Databricks OAuth, provision OIDC/M2M/Render secrets, strictly validate the data bundle, and deploy both services |
| 9.2 End-to-end acceptance | Harnesses prepared | MCP post-deployment harness, Phase 7 trace evaluator, deterministic CDC fixtures, frontend smoke tests | Execute against deployed resources and two real principals |
| 9.3 Security/performance | Local controls accepted | Fail-closed identity, bounded inputs/responses, sanitized traces, cross-host quota coordination, privacy-safe analytics | Live cross-principal, concurrent quota, propagation latency, and deployed performance evidence |
| 9.4 Documentation/demo | Release artifacts updated for Render plan | Data dictionary, tool/API reference, traceability matrix, demo checklist, and Render deployment plan | Update/export the architecture diagram after connectivity design is accepted; upgrade both services to the smallest paid tier for final acceptance, then record readiness and final evidence |

Release documentation deliberately separates implemented/local acceptance from
workspace proof and external blockers. No deployed-agent, CDC latency, or
frontend completion is claimed before the checklist evidence is recorded.
