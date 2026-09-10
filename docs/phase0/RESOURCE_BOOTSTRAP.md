# Phase 0 Resource Bootstrap

The bundle defines the two existing applications, two job entry points, a managed Volume, and a minimal serverless Lakeflow pipeline. It deliberately does not select a CLI profile.

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
2. Override `catalog`, `schema`, and `warehouse_id` for that workspace.
3. Confirm the catalog is a regular Unity Catalog catalog, not a Lakebase catalog.
4. Confirm whether an existing Lakebase development branch/database will be reused.
5. Add only the resource permissions listed above; do not grant `CAN_MANAGE` to ordinary app users.

## Validation

```bash
databricks bundle validate --strict --target dev \
  --profile '<selected-profile>' \
  --var 'catalog=<catalog>' \
  --var 'schema=<schema>' \
  --var 'warehouse_id=<warehouse-id>'
```

No deployment or Lakebase mutation should be performed until the selected targets appear in the validation output.
