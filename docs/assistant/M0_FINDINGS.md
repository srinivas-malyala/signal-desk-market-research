# M0 protocol and design spike evidence

Date: 2026-10-12, America/Los_Angeles.
Status: local spike and existing-endpoint baseline verified; embedded-endpoint
proposal/citation proof remains pending M1 provisioning. No deployment, grants,
configuration updates, database migrations, or business writes were performed.

## Reproducible artifacts

- `tools/assistant_m0_probe.py`: fixed live research/formatting cases and offline
  SSE structural inspector. Explicit profile/host/endpoint required. Output
  contains counts, argument types, and statuses; no transcripts or credentials.
- `tests/test_assistant_m0.py`: synthetic SSE failure cases and real installed
  FastMCP HTTP transport over an in-process ASGI mount. No external dependencies.
- Targeted verification: 18 tests pass across assistant M0 and existing phase-7
  evaluator tests; changed-file Ruff passes; tracked-file secret scan passes.
  Local Python is 3.13; service deployment Python 3.11 startup proof remains M6.

## Live platform baseline

User selected `dataexpertio_srini`, targeting
`https://dbc-7b106152-caf3.cloud.databricks.com`. CLI is 1.12.1.
Existing standalone Supervisor resource:
`supervisor-agents/cb6be7ba-3357-48b4-9cf6-2849157d82f0`.
Endpoint `mas-cb6be7ba-endpoint` reports READY / NOT_UPDATING.

`serving-endpoints get-open-api` failed with “No entity is being served by the
endpoint.” Do not interpret this as endpoint unavailability; invocations worked.
The embedded endpoint does not yet exist. Do not substitute this unrestricted
standalone endpoint for the embedded feature in production configuration.

## Observed request and response

Request path: POST `/serving-endpoints/<name>/invocations`; bearer OAuth;
body contains `input` role/content items, `stream=true`, and
`databricks_options.long_task=true`. Full role/content history is accepted;
previous_response_id and structured-output API parameters were not tested.

Observed events: `response.output_text.delta`, `response.output_item.done`,
followed by the SSE `[DONE]` marker. Items include message, function_call, and
function_call_output. Item status fields were absent. No response.completed
event was observed. Accept explicit DONE after a finalized assistant text item
as stream completion; accept response.completed when present; bare EOF remains
interrupted. Any failure/incomplete event overrides completion.

Function calls and outputs can share an item ID. Deduplicate by type and ID,
not ID alone. Otherwise tool-call inspection loses evidence.

| Probe | Observed result | Limits |
|---|---|---|
| AAPL filing research | Text deltas, finalized messages and tool output; ~70.21 s | Initial collector did not track DONE or distinguish shared IDs; not a terminal/citation proof |
| AAPL/MSFT comparison | Text deltas, finalized messages and tool output; ~64.47 s | Same initial-collector limitation |
| Multi-turn comparison | compare_stocks, tickers=list, lookback_days=int; final assistant + DONE; ~20.35 s | Protocol baseline, not assessment of research correctness |
| Invalid ticker | get_stock_performance with ticker=str and lookback_days=int; final assistant + DONE; ~14.45 s | Safe error wording was not evaluated by metadata-only collector |
| Exact JSON formatting | No tool calls; text deltas, final assistant + DONE; ~3.28 s | Strict envelope shape failed; no reliable JSON fallback established |

The first collectors returned interrupted for otherwise finalized streams
because they required response.completed. These are diagnostic findings, not
successful action acceptance. The final parser recognizes observed DONE semantics.

Final live re-run using the corrected parser completed in 20.77 seconds with
compare_stocks (tickers=list, lookback_days=int), four output-item events,
135 text-delta events, and one DONE marker. No text annotations were present.
The CLI returned exit 0 and terminal_state=completed. This closes the existing
endpoint's stream-termination baseline without asserting embedded proposal proof.

No annotation objects were observed on assistant output_text content. This does
not prove source URLs are unavailable inside tool output. Explicit extraction
and verification of tool-result provenance remains necessary in M1/M2.

## Restricted MCP mounting result

Installed FastMCP 2.14.7 matches both service lock files. Two separate
`http_app(path='/mcp', stateless_http=True, json_response=True)` applications
mounted under different Starlette prefixes work with StreamableHttpTransport.
Their child lifespan contexts must be entered explicitly through AsyncExitStack.
Do not mount the restricted server into the legacy FastMCP tool namespace;
use separate HTTP apps so tool discovery and invocation remain isolated.

The prototype exposes four research stubs and a non-mutating proposal formatter.
Manual calls to all five forbidden business tools fail; the embedded test
credential receives 401 on the legacy mount. The legacy credential can still
invoke its own tool. Proposal structured content is returned correctly through
the local HTTP transport. This proves library capability, not real broker,
production identity, stateful legacy sessions, or Unity Gateway deployment.

M1 must retain legacy session behavior and authentication, extend identity with
a separate embedded credential, and test the production middleware and startup.

## Selected implementation decisions

1. Use separate restricted HTTP mount and credential, not prompt-only restrictions.
2. Prefer a typed non-mutating proposal formatter over model-emitted final JSON.
   Its output is only a candidate; Flask validates/stores it after verified stream
   completion. It must never write a watchlist, note, or report. Live Supervisor
   invocation of this formatter is a required M1 acceptance gate.
3. Use full server-owned completed history initially; no continuation-ID assumption.
4. Configure 256,000-byte event and 2,000,000-byte capture caps in the CLI spike.
   These are conservative initial bounds, not measured production sizing.
5. Keep the MCP checksum migration runner as schema owner. Apply an additive
   migration before enabling Flask chat; do not create a second frontend runner.
6. Reconcile expired owned run leases when loading/submitting conversations and
   before claiming proposals. Recover uncertain business writes only on a fresh
   authenticated user request with the original payload/key. No background service
   may impersonate a browser user. A future maintenance sweeper may mark abandoned
   generations interrupted; it must not execute pending proposals.

## Remaining exit gates

- Live typed proposal tool and citation metadata must be verified on the embedded
  restricted connection after M1 provisioning. This is not possible on the current
  unmodified standalone nine-tool endpoint.
- Full embedded schema, frontend service-principal query permission, legacy
  stateful session startup, and Render stream capacity remain future gates.
- Do not declare the entire original M0 exit gate complete or enable actions
  based solely on this local prototype and standalone baseline.

## Re-run examples

```sh
.venv/bin/python -m pytest tests/test_assistant_m0.py tests/test_phase7_agent_eval.py -q
.venv/bin/ruff check tools/assistant_m0_probe.py tests/test_assistant_m0.py
.venv/bin/python -m tools.assistant_m0_probe --live --profile dataexpertio_srini --host https://dbc-7b106152-caf3.cloud.databricks.com --endpoint mas-cb6be7ba-endpoint --case multi_turn --timeout 180
```

Probe nonzero exit indicates HTTP/protocol failure or interrupted stream. Printed
metadata does not validate grounding, exact returned action arguments, or source
authenticity. Keep those evaluation gates separate.
