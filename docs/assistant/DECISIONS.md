# Assistant design decisions

Status: proposed implementation design, 2026-10-12. No platform deployment claimed.

| ID | Decision | Reason / validation |
|---|---|---|
| D1 | Flask invokes Supervisor server-side using OAuth M2M | Browser never receives Databricks credentials; reuse explicit shared auth |
| D2 | Separate embedded Supervisor and restricted credential | Preserve standalone behavior; enforce research-only business permissions |
| D3 | Four research tools; user context loaded by Flask | Existing machine identity cannot read browser-owned state correctly |
| D4 | Browser confirmation executes immutable stored proposals | Exact consent, ownership, revision and retry binding |
| D5 | Server-owned Lakebase conversation records | Isolation, restart recovery, bounded context; no transcripts in cookies |
| D6 | Streamed POST with sanitized public events | Existing CSRF flow; endpoint adapter isolates schema changes |
| D7 | Database coordination across workers | In-memory locks do not coordinate current Gunicorn processes |
| D8 | Feature flags and additive migrations | Stage research/actions independently; rollback without dropping user data |
| D9 | Fixed 180-second model deadline, 210-second lease, worker timeout at least 240 seconds | Local blocking/slow-drip and startup tests verified; deployed streaming is M3 |
| D10 | Opt-in post-fork recovery per Gunicorn worker | No pre-fork threads/connections; bounded SKIP LOCKED batches coordinate through PostgreSQL |
| D11 | Prepare 30-day transcript redaction, disabled by default | User selected 30 days; preserve IDs/hashes rather than cascading retry metadata away |
| D12 | Do not retry uncertain terminal database commits | Safe persistence error; duplicate/reload reads durable state or lease recovers interruption |

## Questions to resolve before dependent implementation

| ID | Question | Required evidence / milestone |
|---|---|---|
| Q1 | Which current request and event schema does embedded endpoint support? | Sanitized captures and endpoint schema; M0 |
| Q2 | Can typed proposal-tool arguments be extracted reliably? | Valid/malformed examples; choose typed tool or strict envelope; M0 |
| Q3 | How does installed FastMCP mount a restricted surface and enforce calls? | Local startup/discovery/manual forbidden-call tests; M0/M1 |
| Q4 | Which citations/tool outcomes are exposed without leaking private trace data? | Captured evidence and adapter allowlist; M0 |
| Q5 | What transcript retention, deletion, and role grants fit production? | Document policy before production; M2/M6 |
| Q6 | Can Render/Gunicorn support measured stream concurrency and duration? | Actual deployed buffering/timeout/load results; M3/M6 |
| Q7 | Is remote cancellation supported and which options are accepted? | Endpoint evidence; otherwise promise response stop only; M0/M3 |
| Q8 | Who runs migrations and reconciles abandoned leases? | Explicit deployment and recovery procedure; M2/M6 |
| Q9 | Which profile/workspace and embedded endpoint are approved? | User selection for live operations; M0/M1 |

## M0 evidence, 2026-10-12

See M0_FINDINGS.md. Q9 profile selection is resolved: dataexpertio_srini.
Q1 is verified for the existing endpoint via live requests; OpenAPI retrieval
fails despite READY. Q3 is proven locally for isolated stateless mounts, with
production/stateful legacy acceptance remaining M1. Q2 selects a typed proposal
formatter: local transport works; live embedding is pending and strict JSON
formatting failed. Q4 citations remain unproven. Q7 supports response stopping
only; no remote cancellation claim. Q8 uses existing MCP migration ownership and
owned request-driven lease reconciliation; business write recovery requires a
fresh authenticated user request. These decisions do not grant new live permissions.

M0 remains partially verified until the embedded-only live gates close.

## Change record template

```text
Date / decision ID:
Previous assumption:
Verified evidence:
Selected behavior and reason:
Contract / tests / deployment documents affected:
Remaining limits:
```
