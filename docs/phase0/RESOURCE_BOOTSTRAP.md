# Phase 0 Resource Bootstrap

The bundle defines the two existing applications, two job entry points, a managed Volume, and a minimal serverless Lakeflow pipeline. It deliberately does not select a CLI profile. The development target uses the existing `bootcamp_students.student_sri` Unity Catalog schema; the bundle does not create or own that schema.

## Application resource keys

The prototype remains deployable during the migration by attaching these secret resources:

| App | Key | Permission | Temporary purpose |
|---|---|---|---|
| `signal-desk-mcp-<target>` | `massive-api-key` | Can read | Massive free-plan API key |
| `signal-desk-mcp-<target>` | `lakebase-url` | Can read | Existing Lakebase URL compatibility |
| `signal-desk-frontend-<target>` | `lakebase-url` | Can read | Existing dashboard Lakebase compatibility |

Phase 4 replaces `lakebase-url` with a `postgres` resource pointing to an explicitly selected Autoscaling Lakebase branch and database. The MCP app must be deployed before it initializes the application schema.

## Pre-deployment decisions

1. Select and authenticate one Databricks CLI profile.
2. Confirm access to the configured `bootcamp_students.student_sri` development schema.
3. Supply `warehouse_id` before deployment.
4. Confirm the catalog is a regular Unity Catalog catalog, not a Lakebase catalog.
5. Replace the provisional Lakebase connection string when usable credentials become available.
6. Add only the resource permissions listed above; do not grant `CAN_MANAGE` to ordinary app users.

## Validation

```bash
databricks bundle validate --strict --target dev \
  --profile '<selected-profile>' \
  --var 'warehouse_id=<warehouse-id>'
```

The `prod` target intentionally has no default catalog or schema. Both values must be supplied explicitly so a production deployment cannot silently share the development namespace. No deployment or Lakebase mutation should be performed until the selected targets appear in the validation output.
