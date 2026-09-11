# Phase 4 Status — Lakebase Operational Store

Updated: 2026-09-11

Phase 4 configuration inputs are now available, but no live Lakebase write is claimed yet. The existing private-schema implementation must be revised before migration or application deployment.

| Unit | Current status | Confirmed contract | Next testable unit |
|---|---|---|---|
| 4.1 Connection secret | Ready for implementation | Databricks secret `database/lakebase-url`; fetched with `WorkspaceClient`, Base64-decoded only in memory; key existence verified without reading the value | Add deterministic secret/override tests, then perform a sanitized connectivity check |
| 4.2 Shared table namespace | Refactor required | Operational schema `bootcamp_students`; every application table is `<base>_srini`; applications must not create or drop the shared schema | Add validated table-name registry and render versioned migrations with fully qualified names |
| 4.3 Graph/CDF namespace | Contract confirmed | Synced graph tables are `bootcamp_cdc.<base>_srini` | Confirm source/target table names and inspect Lakehouse Sync before configuring replication |
| 4.4 CRUD and isolation | Pending | Writes are restricted to `_srini` tables and application user identity remains row-level data | Run disposable insert/update/delete, verify cleanup, and prove no unsuffixed or other-student table access |
| 4.5 Connection lifecycle | Pending | SSL is encoded in the secret URL; credentials must never be logged | Add pooling, connection health checks, rollback handling, and retry on stale connections |

## Important namespace distinction

- Unity Catalog analytics remains `bootcamp_students.student_sri`.
- Lakebase operational data uses PostgreSQL schema `bootcamp_students` and table suffix `_srini`.
- Lakebase CDF/graph replicas use PostgreSQL schema `bootcamp_cdc` and table suffix `_srini`.

These are separate systems and must not share a single `schema` configuration variable.

## Safety gate

The current helpers correctly default to secret scope `database` and key `lakebase-url`, but they set the Lakebase search path to private schema `student_sri`; `schema.sql` and application queries also use unsuffixed table names. Do not run the current migration or deploy either application until the table-name registry and migration rendering enforce the shared-schema suffix contract.

The attached administrator samples are reference implementations only. Their secret-fetching pattern and identifier-validation rationale are adopted; their GitHub-specific tables, username session flow, and application behavior are not part of Signal Desk.
