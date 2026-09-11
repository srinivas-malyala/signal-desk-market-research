# Phase 4 Status — Lakebase Operational Store

Updated: 2026-09-11

Phase 4 configuration inputs are now available, but no live Lakebase write is claimed yet. The existing private-schema implementation must be revised before migration or application deployment.

| Unit | Current status | Confirmed contract | Next testable unit |
|---|---|---|---|
| 4.1 Connection secret | Implemented locally | Databricks secret `database/lakebase-url`; fetched with `WorkspaceClient`, Base64-decoded only in memory; key existence and deterministic decoding verified without disclosing the value | Perform a sanitized connectivity check |
| 4.2 Shared table namespace | Migration layer implemented | Strict table/index allowlists render three checksum-protected migrations into fully qualified `bootcamp_students.<base>_srini` objects without schema DDL | Refactor all application SQL, then apply migrations live |
| 4.3 Graph/CDF namespace | Contract confirmed | Synced graph tables are `bootcamp_cdc.<base>_srini` | Confirm source/target table names and inspect Lakehouse Sync before configuring replication |
| 4.4 CRUD and isolation | Pending | Writes are restricted to `_srini` tables and application user identity remains row-level data | Run disposable insert/update/delete, verify cleanup, and prove no unsuffixed or other-student table access |
| 4.5 Connection lifecycle | Partially implemented | Lazy bounded thread-safe pool, rollback on failure, and explicit pool shutdown are implemented | Add checkout health/reconnect tests and verify live behavior |

## Important namespace distinction

- Unity Catalog analytics remains `bootcamp_students.student_sri`.
- Lakebase operational data uses PostgreSQL schema `bootcamp_students` and table suffix `_srini`.
- Lakebase CDF/graph replicas use PostgreSQL schema `bootcamp_cdc` and table suffix `_srini`.

These are separate systems and must not share a single `schema` configuration variable.

## Safety gate

The helper and migration layer now enforce shared-schema `_srini` names and never create either shared schema. Application and embedding SQL still contains unsuffixed table names, so do not apply migrations or deploy either application until that next refactor is complete.

Local gate: 14 namespace, secret, migration-rendering, schema-validation, and pool-bound tests pass; focused lint is clean.

The attached administrator samples are reference implementations only. Their secret-fetching pattern and identifier-validation rationale are adopted; their GitHub-specific tables, username session flow, and application behavior are not part of Signal Desk.
