# Phase 5 Status — MCP agent tools and semantic research

Updated: 2026-09-11

| Unit | Status | Evidence | Remaining gate |
|---|---|---|---|
| 5.0 Retrieval design | Complete | ADR 0005 records section-aware parent/child chunking, Qwen3 embeddings, Delta Sync AI Search, hybrid retrieval, provenance, and evaluation targets | None |
| 5.1 Service and observability | In progress | Existing nine-tool server and Lakebase traces are characterized | Trusted identity, bounded trace/event metadata, dependency/error contracts |
| 5.2 Retrieval tools | In progress | Existing Massive, research, watchlist, and notable-update tools are characterized | Correct windows/mappings, evidence metadata, bounds, tests |
| 5.3 Action tools | In progress | Watchlist, note, and report writes exist | Confirmation, transactional idempotency, trusted ownership, isolation tests |
| 5.4 Semantic retrieval | In progress | Phase 3 produced 507 traceable chunks | Canonical chunk contract, managed index, filtered search client, evaluation gate |

## Accepted implementation sequence

1. Replace duplicate character chunking with the canonical Spark-owned contract.
2. Provision the standard Vector Search endpoint and Delta Sync index through the
   bundle, using `databricks-qwen3-embedding-0-6b`.
3. Refactor semantic search to the managed index with filters and provenance.
4. Harden trusted identity, confirmations, idempotency, and bounded audit events.
5. Run local contracts and retrieval metrics, then deploy and run workspace gates.

## External gate

The selected profile is `dataexpertio_srini`. Its cached OAuth credentials were
not valid when Phase 5 began, so workspace deployment and live Vector Search
evaluation require profile reauthentication. No committed code contains a token,
Massive key, SEC contact, or Lakebase URL.

