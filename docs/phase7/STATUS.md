# Phase 7 Status — Agent Bricks Integration

Updated: 2026-09-24

| Unit | Status | Evidence | Remaining gate |
|---|---|---|---|
| 7.1 Supervisor Agent and MCP connection | Local contract accepted; cross-workspace auth proof pending | Prompt and configuration reconciled to MCP contract 1.0; exact nine-tool inventory; ten executable routing, grounding, confirmation, invalid-input, and unavailable-data fixtures; deterministic captured-trace evaluator; Supervisor remains in `dataexpertio_srini` while MCP moves to `Srini Free Edition` | Prove a durable governed UC HTTP/MCP authentication flow to the Free app, deploy Supervisor, wait for readiness, and capture live traces; if Free cannot support that flow, expose equivalent paid-workspace UC function tools |
| 7.2 Identity propagation | Design revised for split workspaces | Prompt forbids model-supplied identity; Free frontend-to-MCP calls retain same-workspace user identity; paid data reads use app-specific M2M because Free user tokens are invalid in the paid workspace | Prove two real principals, tampered/missing identity rejection, shared-read identity disclosure, and the selected Supervisor authentication path |

Run local fixture validation:

```bash
python tools/phase7_agent_eval.py
```

After the Supervisor endpoint is online, capture one object per fixture with
`id`, ordered `tool_calls` (`tool` and `arguments`), and `final_answer`, then run:

```bash
python tools/phase7_agent_eval.py --results /path/to/captured-supervisor-results.json
```

The evaluator checks ordered tool selection, required argument alignment,
forbidden mutations, explicit confirmation, idempotency-key shape, required
answer disclosures, and hallucination-sensitive forbidden phrases. It does not
claim a live pass until captured deployed results are supplied.
