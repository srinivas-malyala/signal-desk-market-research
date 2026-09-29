# Phase 9 Status — Release and Capstone Proof

Updated: 2026-09-29

| Unit | Status | Completed | Remaining gate |
|---|---|---|---|
| 9.1 Deployment | Both Render services live; Lakebase serving cutover pending | Blueprint, reproducible builds, MCP and frontend health, Google OIDC callback/session flow, signed frontend-to-MCP identity, Lakebase connectivity, Massive fallback, and strict data-only bundle validation are accepted | Reauthenticate `dataexpertio_srini`, execute ADR 0007's serving gates, then complete the separately tracked frontend analytics and Supervisor connections |
| 9.2 End-to-end acceptance | Partial live acceptance | Public preflight passed 5/5; MCP Supervisor auth, nine-tool discovery, and bounded 2/2 trace/event reconciliation passed; Phase 6 CDC-to-Gold acceptance is complete | Pass governed/semantic reads, then reversible write/idempotency, frontend core workflow, Supervisor evaluation, and two-real-principal isolation |
| 9.3 Security/performance | Deployed perimeter accepted; data-plane gates remain | Fail-closed frontend/API behavior, security headers, OIDC session flow, MCP unauthenticated rejection, bounded inputs/responses, sanitized traces, cross-host quota coordination, privacy-safe analytics, and measured 85-second CDC source latency | Live cross-principal, concurrent Massive quota, least-privilege Lakebase runtime-role positive/negative permissions, research-quality parity, and deployed performance evidence |
| 9.4 Documentation/demo | Render architecture accepted; final live evidence pending | Data dictionary, tool/API reference, traceability matrix, demo checklist, Render deployment plan, and visually verified 1800×1120 PNG/SVG architecture diagram | Upgrade both services to the smallest paid tier for final acceptance, then record readiness and final evidence |

Release documentation deliberately separates deployed perimeter proof from
data-plane and workflow acceptance. The services and Phase 6 CDC path are live;
the agent/write workflow is not complete until the Lakebase-only MCP serving,
frontend analytics, and remaining checklist gates pass.
