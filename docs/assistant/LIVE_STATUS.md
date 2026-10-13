# Embedded assistant live status

Updated 2026-10-12 America/Los_Angeles (resource creation 2026-10-13 UTC).

## User-reported deployment evidence

- User deployed commit `6ee55ad` to the Render MCP service and redeployed after
  configuring the embedded credential.
- Screenshots show bearer authentication targeting `/embedded/mcp`, connection
  `bootcamp_students.student_sri.signal_desk_embedded_mcp_connection`, and service
  `bootcamp_students.student_sri.signal_desk_embedded_mcp` with exactly eight tools.
- User reports comparison and watchlist-candidate Playground tests passed using
  Llama 3.3 70B. This is user-reported evidence, not an independently captured
  Supervisor evaluation. The service screenshot showed status Unknown.

## Independently executed provisioning

Explicit profile: `dataexpertio_srini`; CLI v1.12.1.
Created a separate Supervisor with repository embedded instructions:

- Display name: Signal Desk Embedded Research
- Resource: `supervisor-agents/94a8ed23-5eca-420a-90a7-693eafa59752`
- Endpoint: `mas-94a8ed23-endpoint`
- Experiment: `3029127808983864`

Existing standalone Supervisor was not modified. No grant or business write was
performed. Endpoint readiness has not been checked; the new Supervisor is not
ready for application use and has no successfully attached research tool.

Attempting `create-tool` with `tool_type=uc_connection` and the full embedded
connection name failed: `Connection ... is not an MCP connection.` The connection
is auto-created for a governed MCP service, while this Supervisor attachment
path expects an MCP-marked connection. Do not recreate the Supervisor or alter
the existing working service/credential to bypass this error.

## Next step

Latest user evidence supersedes the attachment blocker below: screenshot shows
the governed UC MCP Service attached through the Supervisor UI. Comparison tool
arguments and output match; upstream Massive attribution remains missing. The
watchlist-add candidate returns executed=false and browser-review instructions.
SEC search correctly routed with arrays but returned research_error. Read-only
CLI lookup confirms the repository-default index_v4 is absent; shared zachy_vs
is online. Actual Render index override remains unverified.

User explicitly deferred index recovery and authorized M2 local implementation.
No index recreation will be attempted. Admin deletion is a user hypothesis, not
an independently verified cause. M1 citation gate remains open before full
rollout. Available research and proposal-only behavior can proceed meanwhile.

The documented governed service attachment uses `tool_type=uc_mcp` with
`uc_mcp: {name: <service full name>}`. CLI v1.12.1 advertises the tool type but
rejects its spec with `unknown field: uc_mcp` and `Tool spec must be provided`.
Thus the immediate blocker is the installed CLI payload model, not evidence of
a broken Render token or MCP service. Use the Supervisor UI to attach this
governed MCP service, or upgrade the CLI before retrying that documented payload.
Do not replace the working service with a legacy connection to bypass this.
Then add evaluation examples, check readiness, and run
live citation/proposal/adversarial evaluations. M1 remains partially complete.
M2 backend work and frontend query permission are still pending.

Reference: https://docs.databricks.com/api/supervisor-agents/v1/create-tool
