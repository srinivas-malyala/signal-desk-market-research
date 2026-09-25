# Phase 6 — Lakebase CDC and usage analytics

Updated: 2026-09-24

| Unit | Status | Evidence | Remaining gate |
|---|---|---|---|
| 6.1 Lakebase CDC replication | Schema and five required tables enabled; data acceptance pending | The active schema mapping is **Enabled** from PostgreSQL `databricks_postgres.bootcamp_students` to Unity Catalog `bootcamp_students.bootcamp_cdc`; table evidence shows **Enabled** for `agent_tool_events_srini`, `agent_sessions_srini`, `watchlist_tickers_srini`, `research_notes_srini`, and `analysis_reports_srini`, each with an `lb_*_srini_history` destination and replication position | Query and describe the five destination histories, then execute controlled insert/update/delete propagation and measure latency |
| 6.2 Silver activity and Gold usage metrics | Local acceptance complete | Source and output namespaces are independently parameterized: CDC reads `bootcamp_students.bootcamp_cdc.lb_*_srini_history`, while Silver/Gold remain in `bootcamp_students.student_sri`; normalized streaming table with five append flows; deduplicated safe Silver activity; five Gold metric families; deterministic synthetic CDC acceptance passes | Deploy and run after the five history sources are confirmed queryable; reconcile controlled live events and record end-to-end latency |

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

This is local implementation acceptance, not evidence that Lakehouse Sync is
running. Unit 6.1 and the deployed pipeline remain explicit workspace gates.
