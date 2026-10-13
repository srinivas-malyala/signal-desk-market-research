# M6 acceptance and staged release

Status: local acceptance preparation in progress; not deployed or release-approved.
AI Search remains deferred by the user. All three scheduled jobs remain paused.
M5 commits 83b196d and 46d0ae7 are local; remote/deployed versions must be
recorded independently. This checklist is not evidence that live checks passed.

## Acceptance gates

| Gate | Local evidence | Remaining live evidence |
|---|---|---|
| Authentication and isolation | Signed-session/CSRF route tests, owner predicates and PostgreSQL composite constraints | Two real browser users cannot read, revise or confirm each other's IDs |
| Restricted research credential | Embedded invocation denial tests | Governed MCP credential rejects business writes and user-scoped reads, including manually supplied tool names |
| Research and streaming | Bounded protocol, deadlines, parser and synthetic browser tests | Real comparison/company research, follow-up and reload through Render; no raw tool/credential exposure |
| Stored proposals | Strict paired typed-output capture, immutable revisions and hashes | Capture sanitized actual Supervisor function-output shape; verify all four proposal types survive the deployed adapter |
| Confirmed actions | Fresh signed browser assertions, stored payload/key dispatch and receipt tests | Explicitly authorized reversible write under each real owner; exact readback and same-key retry |
| Recovery | Disposable PostgreSQL stale-lease and lost-write-reply tests | Controlled deployed interruption; renewed confirmation keeps original key; no autonomous business retry |
| Capacity | Shared claim limits and bounded transports tested locally | Measure 1, 2 and 4 concurrent users, fifth-user rejection, first public event, first text and total duration; verify disconnect releases capacity after bounded cleanup |
| Rollback | New route regression disables actions after a saved result, then chat; no new claim/write/model call or delete | Apply flags across all deployed workers; verify direct workflows and health; drain in-flight work |
| Retention | Prepared 30-day transcript policy, default-off tests | Approved proposal/receipt/legal-hold policy and backup treatment; explicit approval before transcript redaction activation |
| AI Search | Deferred; no successful citation/index acceptance claimed | Index recovery, filtered SEC/article retrieval and grounded citation acceptance remain pending |

Local checks use synthetic identities/MCP and disposable PostgreSQL, not real
workspace permissions. The rollback test proves rejection of subsequent requests,
not cancellation of an already dispatched write. Flag rollback never reverses
saved business state or deletes additive schemas/receipts.

## Staged procedure

1. Review and explicitly authorize pushing the selected commits. Record the exact
   commit and hosted CI result; do not deploy a dirty working-tree snapshot.
2. Obtain separate authorization for live deployment, migrations and grants.
   Apply checksum-protected migrations 0006–0009 only to configured suffix-owned
   objects using the existing migration runner. Verify intended role access;
   never change other students' objects. See [deployment runbook](DEPLOYMENT.md).
3. Deploy disabled. Keep chat, proposals, actions, recovery and retention false
   until their respective schema/configuration checks pass. Check health and
   existing auth, watchlist, notes, reports and analytics workflows first.
4. Pilot research-only after endpoint access and streaming gates pass. Keep
   actions false. Explain that semantic SEC/article evidence is unavailable;
   do not reinterpret an index error as no filings or claim full G1 acceptance.
5. Enable proposal review only after actual typed-output capture is validated.
   Review must remain non-executing. Verify edits require a new revision and
   renewed consent. Retrieved text and model prose never authorize a write.
6. Request action-pilot approval only after identity, restriction, retention-policy
   and recovery gates pass. Choose explicit reversible fixtures and cleanup
   authority. Never use existing user notes/reports as destructive test fixtures.
7. Exercise action-off, then chat-off rollback across workers; preserve schema,
   ownership, immutable keys and receipts. Reload results before retrying unknown
   outcomes. Do not invent new keys to bypass uncertainty.
8. Keep full release pending until all required G1–G8 evidence is recorded,
   including the deferred AI Search gate. No schedule is unpaused by this process.

## Evidence record for each live run

Record date, approved scope, commit, service deployment IDs, configuration flag
values, migration checksums, selected Databricks profile, pseudonymous principals,
test case, safe request/run/proposal correlation IDs, timings, outcome and cleanup.
Exclude JWTs, bearer tokens, connection URLs, user emails and transcript/body text.
Record a failed or unexecuted gate explicitly; screenshots of a tool call alone
do not prove frontend parsing, correct owner execution or persisted readback.

## Current local verification

The full fast suite passes (429 tests, 15 integration tests deselected), including
the added rollback regression and existing assistant routes (20 targeted tests).
Changed assistant modules and the route test pass Ruff; the credential scan and
three Node framing tests and Render reproducibility configuration checks pass.
Fresh installs and process startup were not rerun in this step.
M5's earlier 15 PostgreSQL and synthetic browser
checks remain historical evidence; they have not been rerun as live acceptance.
No live migrations, deployments, grants, writes, redaction or schedule changes
were performed during this acceptance-preparation step.
