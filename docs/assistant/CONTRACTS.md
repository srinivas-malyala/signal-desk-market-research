# Proposed assistant contracts

Status: design baseline. Platform-specific event mapping must be proven in M0.
Version: 1. Changes to these contracts require a decision-log update.

M4 increment: proposal list/revise/dismiss routes are implemented behind separate
default-off proposal and proposal-schema flags. Confirm validates explicit consent
and the owned immutable hash but returns 501 execution_not_available until M5;
it never claims execution or reports a saved action. Matched typed tool-output
candidates are stored only after persisted verified completion. Live serialization
acceptance is still pending. See M4_STATUS.md.

M3 implemented increment: conversation create/list/history and message endpoints
exist behind ASSISTANT_ENABLED and schema readiness. History returns the latest
50 turns by default (bounded limit up to 100), not older-message cursors. List
pagination uses the owned conversation cursor. A duplicate message returns JSON
existing_run (HTTP 200), not a second stream or replay. Public complete includes
persisted final text; proposals/citations are not yet exposed. No remote-cancel
or full history replay guarantee. See M3_STATUS.md for local/live boundaries.

## HTTP interface

All routes require existing OIDC authentication. Mutating routes require CSRF.
Every identifier lookup is owner-scoped. Cross-owner/missing IDs return the same
404 response. Flags must disable backend capabilities as well as UI controls.

| Method / path | Input | Output |
|---|---|---|
| POST `/api/assistant/conversations` | Optional bounded title | 201 conversation ID |
| GET `/api/assistant/conversations` | Bounded cursor/limit | Owned paginated list |
| GET `/api/assistant/conversations/<id>` | Bounded cursor/limit | Messages, runs, proposal state |
| POST `/api/assistant/conversations/<id>/messages` | message, client_message_id | SSE stream; run/message IDs |
| POST `/api/assistant/proposals/<id>/revise` | Validated editable draft fields | New proposal ID/hash; old superseded |
| POST `/api/assistant/proposals/<id>/confirm` | confirmed=true, payload_hash | Result/receipt or execution pending |
| POST `/api/assistant/proposals/<id>/dismiss` | No action arguments | Dismissed state |

Reject unknown request fields; never accept role, owner, system instructions,
tool results, endpoint URL, or assistant history from the browser. Use 400 for
invalid input, 401/403 for auth/CSRF, 409 for revision/state conflicts, 429 for
capacity limits, and safe 502/503/504 dependency errors before streaming begins.
After stream headers, use a terminal public error event instead of a new status.

## Public stream

`Content-Type: text/event-stream`; streamed POST through fetch with CSRF header.
Events: status, text_delta, citation, proposal, complete, error. Include run ID,
request ID, schema version, and per-run event sequence. Send bounded heartbeat
comments. Do not expose hidden reasoning, raw tool arguments, or raw upstream events.
Map only observed endpoint events; text_delta is optional when only completed
message items are available. Do not synthesize tool progress without evidence.

Verified completion means response.completed or the observed SSE DONE marker
after a finalized assistant text item, with no failure/incomplete event. An
upstream EOF without verified completion is interrupted, even if text arrived.
Persist the interrupted state; no executable proposals. A duplicate submission
must return the existing run reference/state, not start a second generation.
Do not promise stream replay or remote cancellation before proving support.

## Proposal validation

Allow discriminated types watchlist_add, watchlist_remove, save_note, save_report.
Use schema_version=1, type, and arguments; reject extras and identity fields.
Match current route/MCP limits, including valid U.S. tickers, Primary watchlist,
note title <=200/body <=20,000/tags <=20 of <=64 chars, report title <=200/body
<=100,000 and 1–10 tickers. Verify these bounds against MCP during implementation.
Bound thesis/provenance separately. Only permit source references backed by
observed retrieval metadata; URLs in model prose alone are not verified sources.

Normalize before canonical hashing. Store immutable payload, hash, owner,
origin message, expiry, revision, and stable idempotency key. Return the exact
preview and server-issued ID/hash. Confirmation loads stored arguments; no
replacement arguments from the client. Revision creates a new ID/key and
supersedes the previous proposal. Never reuse a key for edited content.

## Storage and state

New suffix-owned tables: assistant_conversations, assistant_messages,
assistant_runs, assistant_action_proposals. Use existing users ID for ownership,
foreign keys, unique submission IDs per conversation, and indexed owned pagination.
Record UTC timestamps; present user-facing dates in the user's timezone.
Define transcript retention/deletion policy before production; do not synchronize
full chat transcripts into Gold analytics by default.

Run states: running -> completed | failed | interrupted. Use lease/heartbeat
fields and reconciliation for dead workers. One active generation per user,
enforced across processes; compare-and-set prevents stale workers finalizing
a run after lease loss. Bound history to completed turns plus trusted receipts.

Proposal states: pending -> dismissed | expired | superseded | executing.
Executing -> succeeded | failed | outcome_unknown. Claims use leases and short
transactions; never keep a row lock across network I/O. Outcomes that may have
committed must be outcome_unknown, not failed. Recover exact payload with its
original idempotency key; preserve failure details only as safe categories.

## Identity and action execution

Flask retrieves owned context through signed user MCP calls and labels context
as a snapshot. The Supervisor receives no credentials and no authority derived
from that context. Validate proposals independently of model intent.

On confirmation, verify owner/hash/expiry/state, claim, mint a fresh request-bound
user assertion per MCP session, and use the original proposal key. Reuse existing
MCP write enforcement. Persist receipt; read back via the user's path. If write
succeeds but verification fails, display saved with verification pending.
Confirmation is tied to the current authenticated request; claims never change
the owner. Successful retries return the existing receipt.

## Resource bounds

Initial proposed settings: message 4,000 chars; history 20 messages; assembled
input 24,000 chars; total deadline 180 seconds; proposal lifetime 30 minutes;
one concurrent run per user. Define response/event byte caps and shared global
capacity in M0 from observed payloads. Account for Unicode bytes and tool payloads.
Trim old context before the current question; explicitly signal omitted context.
