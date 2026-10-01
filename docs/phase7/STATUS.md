# Phase 7 Status — Agent Bricks Integration

Updated: 2026-10-01

| Unit | Status | Evidence | Remaining gate |
|---|---|---|---|
| 7.1 Supervisor Agent and MCP connection | Deployed; live evaluation 8/10 | Active governed HTTP connection, exact nine-tool UC MCP Service, READY Supervisor endpoint, four focused examples, streamed capture harness, and eight passing deployed cases | Correct Agent Bricks array serialization for filtered semantic research and the draft-only no-completion timeout; recapture 10/10 |
| 7.2 Identity propagation | Deployed browser isolation and Supervisor machine identity accepted | Prompt forbids model-supplied identity; browser users authenticate with OIDC; frontend uses request-bound assertions; two real principals proved isolated state; Supervisor uses a fixed secret-backed server-side subject through Unity Gateway | Replace temporary shared data-plane principals before production |

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
answer disclosures, and hallucination-sensitive forbidden phrases. Current
ignored deployed evidence scores 8/10; see `CODEX_HANDOFF.md` for the two open
cases and exact live resource identifiers.
