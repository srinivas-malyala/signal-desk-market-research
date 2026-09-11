# ADR 0004: Deployment and environments

- Status: Accepted
- Date: 2026-09-10

## Decision

Use a single Declarative Automation Bundle with `dev` and `prod` targets. Catalog, schema, volume, warehouse, app names, and Lakebase attachment identifiers are parameters. No target embeds or silently chooses a Databricks CLI profile; every operator command supplies `--profile` explicitly.

Development defaults to serverless jobs and pipelines. Destructive operations, production deployment, Lakebase project creation, branch deletion, and schema removal require explicit user authorization. The administrator owns the shared Lakebase schemas; migrations create or alter only allowlisted `_srini` tables.

## Consequences

Phase 0 bundle validation requires the user to choose an authenticated workspace profile. Platform-specific Lakebase and Lakehouse Sync steps remain in a bootstrap runbook when the bundle cannot manage them.
