# ADR 0002: Trusted identity and sensitive-data handling

- Status: Accepted
- Date: 2026-09-10

## Context

The prototype accepts `user_email` as a model-controlled tool argument, uses a demo identity fallback in the dashboard, and stores complete tool parameters/results in traces. Those behaviors cannot safely establish record ownership.

## Decision

- User ownership is derived from Databricks forwarded identity or a short-lived signed internal assertion; a plain tool argument is never authoritative.
- Deployed endpoints fail closed when required identity is absent.
- Application service-principal authentication uses SDK `Config()` and attached resources.
- Secrets, access tokens, database credentials, note/report bodies, raw documents, and oversized API results are prohibited trace fields.
- Traces contain correlation ID, pseudonymous user subject, tool name, action type, status, timing, bounded record identifiers, and safe error code.
- Consequential writes require explicit confirmation and an idempotency key.

## Data classification

| Class | Examples | Storage/log rule |
|---|---|---|
| Public source data | prices, company profiles, SEC filings, published news | May be stored with provenance; bounded in logs |
| User-owned content | watchlists, notes, reports | Lakebase only; owner-scoped; body excluded from traces/analytics |
| Identity metadata | forwarded email/subject, service-principal ID | Use for authorization; pseudonymize in analytics |
| Secret | API key, OAuth token, database credential | Attached resource or secret; never committed or logged |

## Consequences

Existing user-scoped MCP signatures need a compatibility migration. Existing dashboard demo behavior is allowed only under an explicit local mock flag and never in a deployed environment.
