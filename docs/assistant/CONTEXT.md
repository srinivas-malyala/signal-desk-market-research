# Assistant feature context

Snapshot: local repository inspected 2026-10-12. This is a planning baseline,
not a live workspace health check. Existing working-tree changes belong to the
user and must be preserved.

## Existing architecture and extension points

| Existing file | Role / feature relevance |
|---|---|
| `dashboard/app.py` | OIDC/CSRF request boundary; direct research and confirmed write routes; fresh assertion helper |
| `dashboard/auth.py` | Google OIDC session and signed downstream identity |
| `dashboard/mcp_client.py` | User-bound tool calls; retain for proposal execution |
| `dashboard/lakebase.py` | Pooled SQL helper and strict table allowlist; extend for assistant storage |
| `shared/databricks_auth.py` | Explicit Render OAuth M2M config; reuse for endpoint invocation |
| `mcp_server/identity.py` | Existing machine and frontend identities; add distinct restricted embedded identity |
| `mcp_server/stock_research_mcp_server.py` | Nine-tool server, middleware, audit; implement restricted invocation surface |
| `mcp_server/action_service.py` | Transactional ownership, payload fingerprint, idempotent write replay |
| `mcp_server/lakebase.py` | Migration renderer, table registry, pooling |
| `mcp_server/migrations/0001..0005` | Existing checksum-protected operational migrations; confirm latest before adding |
| `agent/agent_bricks_config.yaml` | Existing standalone nine-tool Supervisor; preserve |
| `agent/system_prompt.md` | Existing standalone policy; add separate embedded policy |
| `tools/phase7_live_capture.py` | Observed input/streaming protocol; CLI-only harness, not production client |
| `render.yaml` | Service locks/startup/config; prepared Gunicorn default 240 seconds, not deployed |
| `databricks.yml` | Data-plane resources; does not deploy the Render frontend |
| `.github/workflows/ci.yml` | Current CI dependency install, limited lint scope, fast tests, secret/reproducibility checks |

The standalone Supervisor uses a fixed service identity. It cannot represent
the current browser owner. Four globally scoped research tools can be shared;
watchlist and notable-update reads must be fetched by Flask as the user.

Serving/index versions have evolved since earlier conversations. Resolve names
from current configuration and newest recorded evidence; never copy historical
index identifiers into the new client. The endpoint name in the standalone
configuration is not automatically the endpoint for the embedded feature.

## Assistant implementation map

M2 backend modules now exist: assistant_repository/service/history/context,
supervisor_client/protocol, assistant_runtime and gunicorn.conf.py. Migrations
0006/0007 add conversation/run/message storage and retention markers. Default-off
worker hooks provide generation recovery and optional 30-day transcript redaction.
Local backend acceptance is recorded in M2_STATUS.md. M3 routes, bounded public
streaming and responsive plain-text UI now exist, default-off. See M3_STATUS.md
for local/browser evidence and the still-open live streaming/citation gates.

M1 exception: `shared/contracts/assistant.py` now defines bounded candidate
contracts; both embedded agent files and evaluation fixtures exist. Production
MCP startup now mounts a default-off restricted `/embedded/mcp` surface. See
M1_FINDINGS.md for the local/live boundary. Below are implemented backend files
and proposed M3/M4/M5 files; the table is not proof of deployment.

| Proposed file | Responsibility |
|---|---|
| `dashboard/supervisor_client.py` | Authenticated endpoint adapter and event parsing |
| `dashboard/assistant_routes.py` | Blueprint, ownership checks, stream lifecycle |
| `dashboard/assistant_service.py` | Context assembly, generation orchestration, shared write helpers |
| `dashboard/assistant_repository.py` | Owned persistence, leases, proposals, recovery |
| `shared/contracts/assistant.py` | Typed requests, public events, proposals, receipts |
| `dashboard/static/assistant.js` / `assistant.css` | Chat rendering, stream reader, exact confirmations |
| `dashboard/templates/assistant.html` | Accessible chat component |
| `agent/embedded_system_prompt.md` / `embedded_agent_config.yaml` | Embedded agent policy and deployment specification |
| New migration and assistant tests | Storage and behavioral gates |

Names are proposed organization, not requirements to duplicate existing helpers.
Select the smallest modules that keep protocol, ownership, and execution clear.

## Context recovery

M4 adds assistant_proposals.py and assistant_proposals.js with migration 0008,
typed candidate capture, owner/hash-bound previews, revisions, expiry/dismissal
and non-executing confirmation. Default-off; see M4_STATUS.md for pending live
serialization validation and the M5 execution boundary.

Resume from root PLANS.md and the last milestone handoff, then read only the
required modules. Existing handoff records a historical Databricks profile;
obtain profile selection for live work under current instructions. Never include
credentials, raw user transcripts, or unsanitized API output in these documents.
