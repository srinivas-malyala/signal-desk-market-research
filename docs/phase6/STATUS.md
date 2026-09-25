# Phase 6 — Lakebase CDC and usage analytics

Updated: 2026-09-25 UTC

| Unit | Status | Evidence | Remaining gate |
|---|---|---|---|
| 6.1 Lakebase CDC replication | Workspace acceptance complete | The active schema mapping is **Enabled** from PostgreSQL `databricks_postgres.bootcamp_students` to Unity Catalog `bootcamp_students.bootcamp_cdc`; all five allowlisted history tables are queryable; one isolated transaction produced the expected 18 history rows across inserts, update images, and deletes; first arrival was observed after approximately 82.5 seconds and the last after approximately 84.2 seconds | None |
| 6.2 Silver activity and Gold usage metrics | Workspace acceptance complete | Pipeline `8e68c3b1-25b5-4c5a-b715-b5509f40ff46` completed baseline update `0eaf88b2-41c0-4822-9599-7d3d6726cd8f` and controlled incremental update `3a7fdcc2-2818-4aa3-a2d5-68a909b29995`; Bronze/Silver counts and all five Gold metric families reconcile to the controlled source changes | None |

## Phase 6.2 implementation

`bronze_lakebase_changes` incrementally reads the five Lakehouse Sync history
tables and retains the required `_pg_change_type`, `_pg_lsn`, `_pg_xid`,
`_sort_by`, and `_timestamp` metadata under normalized names. A deterministic
change ID makes exact replay safe. The target uses one append flow per source,
which avoids a streaming union and keeps source-specific selection explicit.
The source namespace is `bootcamp_students.bootcamp_cdc`; the pipeline
publishes its own Bronze, Silver, and Gold datasets separately under
`bootcamp_students.student_sri`. Lakehouse Sync maps a PostgreSQL table such as
`agent_sessions_srini` to `lb_agent_sessions_srini_history` in the destination
schema. Although the schema-level sync includes other students' eligible
tables, this pipeline allowlists only the five `_srini` history sources.

`silver_agent_activity` removes update preimages, deduplicates repeated change
identities, preserves inserts, postimages, and deletes, and derives activity
date and source latency. User identity is represented only by a stable SHA-256
pseudonym of the Lakebase numeric user identifier. Email, note/report content,
titles, thesis text, source context, trace parameters, and idempotency values are
not selected into the analytics graph.

The Gold materialized views expose:

- daily active pseudonymous researchers and invocation counts;
- per-tool volume, success/error counts, null-duration counts, average latency,
  and p50/p95 latency;
- daily agent error rate;
- daily watchlist create/update/delete counts; and
- daily research-note/report create/update/delete counts.

Every Gold dataset publishes `source_max_synced_at`, `metric_refreshed_at`, and
`metric_source`; applicable datasets also retain maximum source latency.

## Synthetic acceptance evidence

The fixture `fixtures/cdc/phase6_activity_events.json` models five Lakebase
tables with a late event, exact duplicates, an update preimage/postimage pair,
deletes, a null duration, an agent error, masked identity input, private authored
content, and one malformed envelope. Pure reference transformations in
`shared/activity_analytics.py` mirror the Spark contracts for fast known-answer
tests without requiring live CDC.

The controlled sequence proves:

- 14 valid envelopes normalize and one malformed envelope is quarantined;
- duplicate operations and update preimages reduce to 11 effective Silver rows;
- a pre-midnight event remains attributed to 2026-09-10 despite arriving after
  midnight;
- 2026-09-11 has two active researchers, three invocations, one error, and an
  error rate of 0.3333;
- the null semantic-retrieval duration is counted without corrupting latency
  aggregates;
- one watchlist create and delete plus note create/update/delete and report
  create reconcile exactly; and
- neither direct email nor private authored-content sentinels appear in any
  normalized or metric output.

## Live workspace acceptance evidence

The bounded harness `tools/phase6_cdf_acceptance.py` created one isolated test
user and related rows, updated each mutable source, deleted the explicit tool
event, and deleted the user so that foreign-key cascades removed the remaining
operational rows. It committed at `2026-09-25T04:14:35.431387Z` and verified
that no test row remained in any of the seven affected Lakebase tables.

Lakehouse Sync produced the exact expected history cardinalities:

| Source | History operations | First observed source timestamp | Approximate commit-to-arrival |
|---|---:|---|---:|
| `watchlist_tickers_srini` | 4 | `2026-09-25T04:15:57.935Z` | 82.5 seconds |
| `research_notes_srini` | 4 | `2026-09-25T04:15:58.240Z` | 82.8 seconds |
| `analysis_reports_srini` | 2 | `2026-09-25T04:15:58.737Z` | 83.3 seconds |
| `agent_sessions_srini` | 4 | `2026-09-25T04:15:59.599Z` | 84.2 seconds |
| `agent_tool_events_srini` | 4 | `2026-09-25T04:15:59.599Z` | 84.2 seconds |

Lakehouse Sync exposes PostgreSQL UUID values in these history tables as a
Base64 string rather than their original hyphenated representation. The
analytics pipeline intentionally casts the source value to string and does not
attempt to decode it, so session correlation remains stable without relying on
a presentation-specific UUID format.

The first deployed update established a 16-row Bronze / 12-row Silver baseline.
After the controlled transaction, the incremental update completed with 34
Bronze and 26 Silver rows. Bronze retained all 18 new history images; Silver
retained the 14 effective inserts, postimages, and deletes and excluded all four
update preimages. Gold reconciliation for `2026-09-25` returned:

- one watchlist create, update, and delete;
- one note create, update, and delete plus one report create and delete;
- one successful `phase6_cdf_acceptance` invocation with 123 ms duration;
- one daily active pseudonymous researcher and one invocation; and
- zero errors and a zero error rate.

Gold reported a maximum source latency of 85 seconds. Every Gold row included
source freshness and metric refresh timestamps, and the controlled transaction
left no operational test data behind. This completes the Phase 6 workspace
acceptance gate.
