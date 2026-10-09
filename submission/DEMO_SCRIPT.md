# Signal Desk Five Minute Demo Script

## Before recording

- Open https://signal-desk-mcp.onrender.com/ first and wait for the service to respond.
- Open https://signal-desk-frontend-s88i.onrender.com/ and sign in as `malyalasrinivas@gmail.com`.
- Confirm the header shows the signed-in researcher.
- Keep the repository architecture image and `EVIDENCE_MANIFEST.md` ready in separate tabs.

## 0:00 to 0:35 Introduction

Say: “Signal Desk is an evidence-grounded stock research application. Render hosts the Flask frontend and FastMCP service, while Databricks runs the Spark pipelines, governed Delta tables, SQL analytics, AI Search, and Agent Bricks Supervisor. Lakebase stores operational, user-owned state.”

Show the signed-in identity, primary navigation, and live application URL.

## 0:35 to 1:25 Research with evidence

Choose `Filing and news evidence`, enter `AAPL`, and ask: `What evidence supports a buy, hold, or sell view for AAPL?`

Point out:

- the authenticated MCP indicator;
- hybrid retrieval and Databricks reranking;
- the number of returned sources;
- filing and article labels, publication dates, scores, and source links;
- the investment-advice disclaimer.

Say: “The application separates attributable evidence from exact market metrics. Each narrative result links back to its source.”

## 1:25 to 2:10 Market and peer workflows

Switch to `Ticker performance` and run `AAPL`. Then switch to `Peer comparison` and compare two companies on a shared window.

Point out ticker normalization, the as-of date, the common comparison period, and safe handling when a snapshot or entitlement is unavailable.

## 2:10 to 3:00 Action-taking workflow

Scroll to the watchlist. Add a disposable ticker only after describing the confirmation boundary. Show the updated watchlist and explain that the underlying tool requires `confirmed=true` plus an idempotency key. Remove the disposable ticker before finishing.

Open the save-note or save-report control. Explain that notes and reports are user-owned Lakebase records and that analytics stores pseudonymous events rather than authored content. If recording a write, use a short disposable note and remove it after the demo.

Say: “The agent exposes six retrieval tools and three confirmed write tools. Exact retries return the original result instead of duplicating the write; changed payloads are rejected.”

## 3:00 to 3:40 Analytics

Open `Usage analytics`.

Point out:

- daily active researchers;
- agent error rate and invocation count;
- watchlist changes;
- saved research count;
- per-tool calls, errors, and P95 latency;
- sanitized recent activity.

Say: “Lakebase change histories flow through an incremental Databricks pipeline into Bronze, privacy-safe Silver, and five Gold metric families. A controlled acceptance sequence produced 18 history rows, 34 Bronze rows, 26 effective Silver rows, and measured a maximum source latency of 85 seconds.”

## 3:40 to 4:25 Big Data and architecture

Show the architecture diagram.

Say: “The project demonstrates Volume and Variety. The market pipeline processed 1,255,677 Bronze rows into 1,255,489 unique Silver records with 188 deterministic quarantines. Variety includes structured OHLCV and XBRL data, semi-structured JSON, and unstructured filing and news text that is chunked, embedded, indexed, and surfaced in research.”

Mention that the Spark pipelines are declared under `pipelines/` and deployed through bundle resources under `resources/`.

## 4:25 to 5:00 Deployment and quality

Show the Render deployment screenshot and the live application.

Say: “Render reports the MCP service as Live and Blueprint managed. Secrets stay in Render or Databricks secret storage. The current repository passes 281 automated tests and repository-wide Ruff checks. The deployed Supervisor passed all 10 evaluation cases.”

Close with the application URL and the evidence PDF.
