# Assistant rollout and recovery runbook

Status: proposed; no deployment performed. Read the existing Render deployment
runbook and current configuration before executing. Live operations require an
authorized scope and user-selected Databricks profile.

## Configuration contract

| Proposed setting | Initial value / behavior |
|---|---|
| ASSISTANT_ENABLED | false; disables chat APIs and UI |
| ASSISTANT_ACTIONS_ENABLED | false; prevents proposal execution server-side |
| SIGNAL_DESK_SUPERVISOR_ENDPOINT | Embedded endpoint name; required when enabled |
| SUPERVISOR_TOTAL_TIMEOUT_SECONDS | 180; proposed total deadline |
| SUPERVISOR_MAX_HISTORY_MESSAGES | 20 |
| SUPERVISOR_MAX_INPUT_CHARS | 24000 |
| ASSISTANT_PROPOSAL_TTL_SECONDS | 1800 |

Reuse DATA_WORKSPACE_HOST/CLIENT_ID/CLIENT_SECRET through shared auth. Grant
frontend principal CAN_QUERY on the embedded endpoint. Add a dedicated embedded
MCP credential stored in protected Render configuration and Databricks secret
storage, with no reuse of the unrestricted Supervisor token. Confirm exact
setting names in M1. Do not put secret values into YAML, logs, CLI JSON, or prompts.

## Deployment sequence

1. Record baseline commit/deployment and preserve existing local changes.
2. Pass local verification and service locked-install/startup checks. Update
   affected hashed locks with repository tooling; no hand-edited hashes.
3. Apply the additive assistant migration through the checksum-protected runner
   with the deployment/migration identity. Verify only suffix-owned objects changed.
   Confirm role grants, indexes, and rollback behavior before application rollout.
4. Deploy MCP restriction support with existing standalone behavior preserved.
   Verify tool discovery and forbidden direct calls using the embedded credential.
5. Provision embedded UC connection/Supervisor, grant access, verify readiness and
   protocol. Store non-secret IDs in deployment evidence. Use explicit selected
   profile for every CLI call; discover current CLI syntax before mutations.
6. Deploy Flask with flags false. Verify existing health/auth/direct workflows.
7. Enable chat only for the permitted pilot; test real streaming through Render,
   timeout behavior, OIDC/CSRF, conversation persistence, and two-user isolation.
8. Measure worker/thread/pool capacity. Configure total and Gunicorn timeouts
   from results; current frontend command uses 60 seconds. Do not assume SSE
   heartbeats eliminate worker timeouts or platform buffering.
9. Enable actions for pilot after proposal, identity, retry, and recovery gates pass.
10. Expand access after acceptance evidence; update training/configuration/handoff.

If streaming capacity is insufficient, implement durable run execution before
general rollout. Do not silently switch paid plans or add infrastructure.

## Recovery and observability

### Implemented M2 recovery and retention policy

Owned conversation reload now reconciles expired generation leases for that
conversation before reading turns. New submissions also reconcile expired runs.
`AssistantRepository.reconcile_expired(limit=100)` is an internal, bounded,
SKIP LOCKED maintenance primitive returning only a count. It changes expired
generation metadata to interrupted; it never resumes model work or confirms
business writes. No scheduled worker or public maintenance route is installed.
M3 may invoke a bounded batch at application initialization after migrations;
periodic scheduling must be explicitly configured before operational rollout.

Transcript retention currently has no automatic deletion. Tables remain until
an approved retention interval and deletion/recovery process are selected. Do
not attach an automatic purge to startup or migrations. Future pruning must
preserve active runs and all proposal/idempotency/receipt records needed for
recovery; proposal retention cannot be chosen before M4/M5 storage exists.
Restrict database access and keep transcripts out of ordinary logs. The lack
of a scheduled sweep and an approved retention interval are rollout gates,
not claims of completed operations.

The client defaults to 180 seconds; generation leases are 210 seconds. Current
Gunicorn timeout is 60 seconds and is intentionally unchanged while chat is
unregistered. Before enabling M3 streaming, set and verify a worker timeout
above the generation deadline plus terminal-persistence margin (initial proposed
240 seconds), and measure Render/proxy buffering and disconnect behavior.
Four transport slots are per process, not deployment-wide; repository run capacity
is shared through PostgreSQL. Abandoned readers retain their process slots until
real exit. Sustained capacity errors require investigation, not automatic retries
or raising limits. Guaranteed remote cancellation remains out of scope.

Record request/run/conversation IDs, pseudonymous owner, endpoint version,
duration, safe error category, proposal ID/status, and replay/readback outcome.
Keep full transcript logging off. Existing tool-event metrics do not automatically
capture the chat experience or correct browser attribution for machine research;
add explicit chat metrics without mislabelling service calls as human activity.

On startup and periodically through the selected recovery mechanism, reconcile
expired generation/execution leases. Generation interruptions remain visible.
For outcome_unknown writes, recover using the original owner/payload/key and a
fresh browser-authorized execution request; do not substitute the service identity.
Design unattended recovery authority explicitly before adding it. Browser logout
or disconnect is not authorization to execute a pending proposal.

## Rollback

1. Disable ASSISTANT_ACTIONS_ENABLED; reject new confirmation requests.
2. Disable ASSISTANT_ENABLED; stop accepting new generations.
3. Record/drain active runs and reconcile claimed writes without new payloads.
4. Restore the prior Flask/MCP build only if schema and credential policy remain
   compatible. Preserve the standalone endpoint and existing direct workflows.
5. Retain additive tables, receipts, keys, and conversations for recovery. No
   destructive down migration or resource deletion as automatic rollback.
6. Verify health, auth, direct reads/writes, and flag rejection behavior.

Rollout evidence must include whether in-flight writes were committed, pending,
or uncertain. Disabling a flag cannot reverse an already committed action.
