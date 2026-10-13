# M3 research chat status

Status: local routes/UI implemented and verified, 2026-10-12. Not deployed.
M3's deployed-streaming and verified-citation gates remain open.

## Current experience

When ASSISTANT_ENABLED=true, the existing Flask page gains a Research chat
navigation link and responsive chat section. Users create/select conversations,
ask questions and follow-ups, reload the latest 50 turns, load more conversation
list entries, stop local delivery and check/retry the last submission with its
original client_message_id. No transcript is stored in localStorage or cookies.
Model text is rendered with textContent, not HTML/Markdown or clickable URLs.
No proposal-confirmation controls or business-write paths are called by chat.
AI Search is explicitly labelled unavailable. No model-provided citation is
presented as verified; metadata-backed citation rendering is deferred.

New accounts must first load the existing watchlist to initialize their user
record. A missing record returns account_not_ready rather than creating a
machine-owned conversation. Identity comes exclusively from the existing auth
boundary and trusted users-table lookup, never from request/model owner fields.

## Implemented boundary

- assistant_routes.py registers a default-off blueprint. Existing OIDC/session
  and CSRF checks run first. Every repository call uses the authenticated owner.
- Strict JSON field allowlists, UUID validation, 4,000-character question bounds,
  bounded list pagination and history limits; cross-owner/missing records share 404.
- ASSISTANT_SCHEMA_READY gates reads/writes until migrations 0006/0007 are applied.
- Claims, ownership, duplicates and capacity are checked before SSE headers.
  Duplicate submissions return JSON existing_run without invoking the Supervisor.
- Per-event schema version, run ID, request ID and monotonic sequence. Five-second
  heartbeat comments and no-store/X-Accel-Buffering headers. No raw tool events,
  reasoning payloads or credentials are forwarded.
- Bounded delivery workers (four per process), one-event queue, 200-second local
  delivery budget and cancellation signal; no database connection is held while
  awaiting the model. Local client waits poll cancellation within 0.5 seconds
  after disconnect detection. Remote cancellation is not guaranteed.
- Completion carries authoritative final text, including text-only upstream
  responses. Saved success is emitted only after verified completion/persistence.
- Raw upstream bytes are bounded before newline buffering, with split UTF-8 and
  oversized unterminated-line tests. Public Unicode is not expanded into escaped
  surrogate pairs beyond frame limits. Browser framing is capped at 4 MB total,
  150 KB per frame and 100 KB accumulated text; invalid identity/order fails closed.

## Verification

22 route/delivery/UI-contract tests pass: real existing Flask auth/CSRF fixture,
two browser sessions, owner binding, flags, input rejection, duplicate/no-call,
safe storage errors, history/create, disconnect persistence, heartbeat, private
event filtering, capacity cleanup and Unicode bounds.
Three executable Node frame-parser tests pass.
Headless Chrome synthetic-fixture smoke passes for desktop/mobile, streamed text,
literal script text/non-execution, history reload and Stop/interrupted state.
Screenshots were visually inspected; no document-level horizontal overflow at
390 pixels. Fixture uses only localhost and synthetic records, not live OIDC,
Databricks or Lakebase. It is test-only and never imported into production.
11 existing disposable PostgreSQL regressions pass after service changes.
Full fast suite: 404 passed. Changed-file Ruff, credential scan, diff checks and
both exact Blueprint service startup/health probes pass. CI now runs Node framing
tests; hosted CI has not run on these unpushed changes.

## Reproduction

Python: pytest tests/test_assistant_routes.py tests/test_assistant_stream.py
tests/test_assistant_ui_contract.py. Node: node --test tests/assistant_frames.test.cjs.
Optional browser: PYTHONPATH=. python tests/assistant_ui_fixture.py, then run
tests/assistant_browser_smoke.cjs with Playwright and Chrome available. Test server
binds only 127.0.0.1:8769; stop it after verification. No new runtime dependency.

## Before pilot rollout

With separate deployment approval, apply migrations, configure frontend M2M
CAN_QUERY and SIGNAL_DESK_SUPERVISOR_ENDPOINT for the existing embedded endpoint,
then enable ASSISTANT_SCHEMA_READY and ASSISTANT_ENABLED for the read-only pilot.
Recovery/retention remain independently default-off. Verify real Render buffering,
request duration, first-response latency, concurrency, worker/pool limits and
two actual browser users. Missing AI Search does not require restoring/unpausing
the deferred jobs for local comparison chat, but sourced SEC/article acceptance
remains blocked until index recovery and observed citation metadata are verified.
M4/M5 action lifecycle and execution remain outside this implementation.
