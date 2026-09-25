# ADR 0001: Application and service boundaries

- Status: Superseded by ADR 0006 for application hosting; logical service boundaries retained
- Date: 2026-09-10

## Context

The prototype contains a Python FastMCP service, a Python Flask dashboard, operational PostgreSQL tables, Massive integration, and an embedding job. The capstone also requires Spark processing, analytics, an action-taking agent, and a deployed frontend.

## Decision

Retain two independently deployed Python Databricks Apps:

1. The FastMCP app owns only Signal Desk tables suffixed `_srini` in the administrator-managed shared Lakebase schema and exposes bounded retrieval and action APIs.
2. The Flask app provides the user workflow and calls authenticated service APIs; it does not independently own or migrate the operational tables.

Use Lakebase Postgres Autoscaling for operational state, Unity Catalog Delta tables for analytical/history data, a serverless Lakeflow Spark Declarative Pipeline for Bronze/Silver/Gold transformations, and Lakeflow Jobs for external ingestion and embeddings. Deploy resources through one Declarative Automation Bundle.

Flask is retained because this is an extension of a working Python frontend. FastMCP is retained because its nine-tool surface already represents the desired agent boundary.

## Consequences

- Working UI and tool behavior can be migrated incrementally.
- Shared-schema table ownership remains unambiguous through strict `_srini` qualification.
- The frontend needs an authenticated MCP/backend client instead of direct operational SQL.
- Resource configuration must be portable and must use attached app resources.
