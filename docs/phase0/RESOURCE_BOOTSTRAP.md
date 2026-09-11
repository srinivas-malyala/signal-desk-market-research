# Phase 0 Resource Bootstrap

The bundle defines the two existing applications, two job entry points, a managed Volume, and a minimal serverless Lakeflow pipeline. It deliberately does not select a CLI profile. The development target uses the existing `bootcamp_students.student_sri` Unity Catalog schema; the bundle does not create or own that schema. Both apps attach the verified serverless warehouse `b15d3d6f837ba428` with `CAN_USE`.

## Application resource keys

The prototype remains deployable during the migration by attaching these secret resources:

| App | Key | Permission | Temporary purpose |
|---|---|---|---|
| `signal-desk-mcp-<target>` | `massive-api-key` | Can read | Massive free-plan API key |
| `signal-desk-mcp-<target>` | `lakebase-url` | Can read | Existing Lakebase URL compatibility |
| `signal-desk-mcp-<target>` | `sql-warehouse` | Can use | Governed agent analytics queries |
| `signal-desk-frontend-<target>` | `lakebase-url` | Can read | Existing dashboard Lakebase compatibility |
| `signal-desk-frontend-<target>` | `sql-warehouse` | Can use | Governed frontend analytics queries |

The administrator-provisioned `database/lakebase-url` secret remains the approved connection mechanism for Phase 4. Neither app creates a schema: they use shared Lakebase schema `bootcamp_students` with `_srini` table suffixes; replicated graph tables use `bootcamp_cdc`.

## Pre-deployment decisions

1. Select and authenticate one Databricks CLI profile.
2. Confirm access to the configured `bootcamp_students.student_sri` development schema.
3. Confirm the catalog is a regular Unity Catalog catalog, not a Lakebase catalog.
4. Verify key-only access to `database/lakebase-url`; never print or persist its value.
5. Refactor all Lakebase SQL to fully qualified `_srini` table names before deployment.
6. Add only the resource permissions listed above; do not grant `CAN_MANAGE` to ordinary app users.

## Validation

```bash
databricks bundle validate --strict --target dev \
  --profile '<selected-profile>'
```

The `prod` target intentionally has no default catalog or schema. Both values must be supplied explicitly so a production deployment cannot silently share the development namespace. No deployment or Lakebase mutation should be performed until the selected targets appear in the validation output.
