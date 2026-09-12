# Phase 4 Status — Lakebase Operational Store

Updated: 2026-09-11

Phase 4 workspace acceptance is complete. The shared-schema migrations, pooled access layer, CDC prerequisites, and self-cleaning CRUD/isolation proof all passed against Lakebase.

| Unit | Current status | Confirmed contract | Next testable unit |
|---|---|---|---|
| 4.1 Connection secret | Workspace verified | Databricks secret `database/lakebase-url` connected successfully without disclosure; PostgreSQL 17+, both shared schemas, operational `USAGE`/`CREATE`, and graph `USAGE` were verified | None |
| 4.2 Shared table namespace | Workspace verified | Four checksum-protected migrations created 15 fully qualified `_srini` tables without schema DDL; all 15 are owned by the connected role and a second migration pass applied nothing | None |
| 4.3 Graph/CDF namespace | CDC prerequisites verified | Six operational tables use `REPLICA IDENTITY FULL`, including the five selected action/event sources; `bootcamp_cdc` is reserved for UC-to-Lakebase synced tables, while the Lakebase-to-UC history destination is selected during Phase 6 UI setup | Configure and test Lakehouse Sync in Phase 6 |
| 4.4 CRUD and isolation | Workspace verified | Two disposable users and one note exercised insert/read/update/delete and cascade cleanup; a wrong-owner update affected zero rows; table names are allowlisted | Cross-principal deployed-app identity proof continues in Phase 5/8 |
| 4.5 Connection lifecycle | Workspace verified | Lazy bounded thread-safe pools, stale-checkout replacement, rollback on failure, and explicit MCP pool shutdown are implemented and exercised by live operations | None for Phase 4 |

## Important namespace distinction

- Unity Catalog analytics remains `bootcamp_students.student_sri`.
- Lakebase operational data uses PostgreSQL schema `bootcamp_students` and table suffix `_srini`.
- Lakebase CDF/graph replicas use PostgreSQL schema `bootcamp_cdc` and table suffix `_srini`.

These are separate systems and must not share a single `schema` configuration variable.

## Acceptance evidence

The helper and versioned migration layer enforce shared-schema `_srini` names and never create either shared schema. Application, trace, dashboard, and embedding SQL now resolve through the same allowlisted table registry; the obsolete unversioned `schema.sql` entry point has been removed.

Local gate: 41 configuration, namespace, migration, pooled-connection, dashboard, broker, and compatibility tests pass; focused lint is clean. Strict bundle validation also confirms both apps receive `database/lakebase-url` as the `lakebase-url` resource and retain their SQL warehouse resources.

Live preflight and migrations passed on 2026-09-11. The role can connect, use both shared schemas, and create `_srini` objects in `bootcamp_students`; the database is PostgreSQL 17 or newer and the `vector` extension is installed. Migration versions `0001` through `0004` applied once; the immediate and later reruns applied nothing.

All 15 expected tables exist and are owned by the connected role. Six tables report full replica identity: the five selected action/event sources plus the article/ticker bridge added by migration `0004`. The repeatable two-user CRUD smoke test created two users and one note, updated the owner-scoped row, proved a wrong-owner update count of zero, deleted both users, and verified cascade cleanup left zero disposable notes.

Repository acceptance passes 122 tests and whole-repository lint. The sanitized smoke harness is `tools/phase4_lakebase_smoke.py`; it prints no role, host, URL, password, or user-authored content.

The attached administrator samples are reference implementations only. Their secret-fetching pattern and identifier-validation rationale are adopted; their GitHub-specific tables, username session flow, and application behavior are not part of Signal Desk.
