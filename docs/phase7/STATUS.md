# Phase 7 Status — Agent Bricks Integration

Updated: 2026-09-21

| Unit | Status | Evidence | Remaining gate |
|---|---|---|---|
| 7.1 Supervisor Agent and MCP connection | Local contract acceptance complete | Prompt and configuration reconciled to MCP contract 1.0; exact nine-tool inventory; ten executable routing, grounding, confirmation, invalid-input, and unavailable-data fixtures; deterministic captured-trace evaluator | Admin-enabled MCP deployment, UC HTTP connection, Supervisor deployment, endpoint readiness, and live trace capture |
| 7.2 Identity propagation | Implementation dependency prepared | Prompt forbids model-supplied identity; MCP trusts only Databricks-forwarded request identity and fails user-scoped calls closed | Deploy the full frontend → Supervisor → MCP path and prove two real principals plus tampered/missing identity rejection |

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
