# Phase 7 Status — Agent Bricks Integration

Updated: 2026-09-24

| Unit | Status | Evidence | Remaining gate |
|---|---|---|---|
| 7.1 Supervisor Agent and MCP connection | Local contract accepted; Render machine-auth proof pending | Prompt and configuration reconciled to MCP contract 1.0; exact nine-tool inventory; ten executable routing, grounding, confirmation, invalid-input, and unavailable-data fixtures; deterministic captured-trace evaluator; Supervisor remains in `dataexpertio_srini` while MCP moves to Render | Create a governed UC HTTP/MCP connection to the Render endpoint using a separate machine credential or supported OAuth M2M flow, deploy Supervisor, wait for readiness, and capture live traces |
| 7.2 Identity propagation | Render trust boundary locally accepted | Prompt forbids model-supplied identity; browser users authenticate with OIDC; frontend issues a 60-second RS256 request-bound assertion; MCP rejects expired, tampered, missing, wrong-request and forwarded-header identity; paid reads use separate M2M identities; Supervisor maps to a fixed server-side subject | Prove two real deployed principals, shared-read identity disclosure, and the live Supervisor machine-authentication path |

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
