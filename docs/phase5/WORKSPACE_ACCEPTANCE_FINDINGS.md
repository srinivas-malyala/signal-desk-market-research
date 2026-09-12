# Phase 5 Workspace Acceptance Findings

Updated: 2026-09-11 Pacific (2026-09-12 UTC)

## Purpose

This report records the Phase 5 workspace acceptance work for the Signal Desk
capstone. It preserves the verified results, the workspace-specific problems
encountered, the changes made in response, and the remaining acceptance gates.

The tests used Databricks profile `dataexpertio_srini`, Unity Catalog namespace
`bootcamp_students.student_sri`, SQL warehouse `b15d3d6f837ba428`, and the
administrator-managed Lakebase secret `database/lakebase-url`. Secret values are
not stored in this document or the repository.

## Executive summary

The canonical Spark research corpus, Lakebase migration, regular Delta serving
table, managed AI Search endpoint/index, triggered synchronization, and live
retrieval evaluation have passed their workspace checks. The live index contains
393 rows, and the 51-case retrieval suite passed every configured threshold with
complete provenance and no filter violations.

Phase 5 remains **workspace acceptance in progress** because the MCP application
still needs deployment-level health, action, idempotency, and trace tests. The
final authorization test also requires two real authenticated account principals;
only one principal was available during this acceptance session.

## Accepted components and evidence

| Area | Result | Evidence |
|---|---|---|
| Authentication and bundle validation | Passed | OAuth identity `malyalasrinivas@gmail.com`; strict development bundle validation passes |
| Canonical Spark corpus | Passed | 393 complete chunks from 98 sources: 86 articles and 12 SEC filings |
| Corpus integrity | Passed | Zero incomplete rows, duplicate chunk IDs, duplicate `(source_type, source_id, chunk_index)` keys, or untraceable chunks |
| Lakebase migration | Passed | Migration `0004` applied once; immediate second run applied nothing |
| Lakebase namespace | Passed | All 15 expected `_srini` tables exist in shared schema `bootcamp_students` and are owned by the connected role |
| CDC readiness | Passed | Five operational action/event tables use `REPLICA IDENTITY FULL` |
| Owner isolation | Passed | Correct-owner update affected one row; wrong-owner update affected zero; disposable records were fully removed |
| Search serving table | Passed | Publisher run `255439151353917` reconciled 393 canonical source rows to 393 regular Delta target rows with zero duplicate chunk IDs |
| Managed AI Search | Passed | Standard endpoint and triggered Delta Sync hybrid index are ready with 393 indexed rows |
| Index synchronization | Passed | Job `430452316532258`, run `52577799192254`, completed successfully |
| Live retrieval evaluation | Passed | 51 cases; Recall@5 1.0000, MRR 0.9902, nDCG@5 0.9928, zero provenance failures, zero filter violations |
| Focused local regression | Passed | 8 retrieval/evaluation tests and focused Ruff checks pass |

The corpus refresh completed through research-pipeline validation update
`ca094e65-f38e-4ebe-b121-0b1faeea946d` and refresh update
`56c5df46-e1a8-4d14-bd93-d467aadb554e`. The successful serving-table publisher
belongs to job `873159231343771`.

## Managed search resources

| Resource | Identifier |
|---|---|
| Vector Search endpoint | `signal-desk-research-dev` |
| Endpoint ID | `0f391010-a035-465f-a78e-0aeb39661485` |
| Delta Sync index | `bootcamp_students.student_sri.signal_desk_research_chunks_index` |
| Embedding model | `databricks-qwen3-embedding-0-6b` |
| Delta source table | `bootcamp_students.student_sri.research_search_documents` |
| Managed pipeline ID | `334dd82b-2b7f-48df-814e-f59a1e4614e4` |

The index uses a standard endpoint, triggered Delta Sync, hybrid retrieval, and
Databricks reranking. Retrieval applies metadata filters, reranks the faithful
retrieval-text column, deduplicates parents, and returns source provenance.

## Problems found and resolutions

### Unsupported endpoint permission

Strict bundle validation rejected `CAN_QUERY` for the Vector Search endpoint.
The endpoint permission was changed to the supported `CAN_USE` level.

### Materialized view could not be the index source

The workspace rejected direct AI Search creation from
`silver_research_chunks` because that object is a Lakeflow materialized view and
materialized-view sources are not enabled for AI Search in this workspace.

The implemented boundary is now:

`canonical materialized view -> idempotent Spark MERGE -> regular Delta table -> triggered Delta Sync index`

The regular Delta table has Change Data Feed and row tracking enabled. This
matches the supported Delta Sync source pattern described in the
[Databricks AI Search creation guide](https://docs.databricks.com/aws/en/ai-search/create-ai-search).

### Successful serverless task reported as failed

The first publisher invocation completed its data work but raised
`SystemExit(0)`. The Databricks serverless Python task treated that exit as an
exception. The success path now calls `main()` without raising; the subsequent
run completed successfully.

### Invalid broad Unity Catalog grant

The workspace-local `users` group is not an account-level Unity Catalog
principal, so a broad index grant failed. The invalid grant was removed. The
resource owner retains access, and the MCP application declares the index as a
`uc_securable` resource so the Databricks App service principal can receive the
required access during deployment. This follows the
[Databricks Apps Vector Search resource pattern](https://docs.databricks.com/gcp/en/dev-tools/databricks-apps/vector-search).

Cross-user testing must use real account-level principals rather than a
workspace-local group or caller-supplied identity headers.

### Bundle proposed unnecessary index recreation

An explicit `columns_to_sync` list caused the bundle plan to propose destructive
index recreation even though the effective column list had not changed. Removing
the redundant list and relying on the documented all-columns default changed the
planned action to `skip`, preserving the healthy managed index.

### Reranker request contract changed

The live AI Search API rejected the older top-level `columns_to_rerank` request.
The retrieval client now nests the column selection under the reranker parameters
object. A regression test verifies the current SDK request shape.

## Retrieval evaluation findings

The committed workspace fixture contains 51 labeled cases:

- 40 article title, keyword, and semantic retrieval cases.
- 11 date-filtered SEC filing cases.
- All filing source identifiers were checked against the live corpus.

Final live results:

| Metric | Result |
|---|---:|
| Cases | 51 |
| Recall@5 | 1.0000 |
| Mean reciprocal rank | 0.9902 |
| nDCG@5 | 0.9928 |
| Provenance failures | 0 |
| Filter violations | 0 |
| Acceptance result | Passed |

The evaluator now calculates nDCG at the source level so multiple passages from
one source cannot inflate relevance. It also creates the report output directory
when needed.

The fixture is a strong workspace integration and filtering check, but it is not
yet a comprehensive semantic-quality benchmark because many labels use exact
titles or constrained dates. Later evaluation should add harder paraphrases,
multi-source questions, negative cases, and expert relevance judgments.

## Security and identity findings

- The MCP tools no longer accept a model-supplied `user_email` for user-scoped
  operations; identity must come from the trusted request context.
- Consequential write tools require explicit confirmation and an 8–128 character
  idempotency key.
- Idempotency reservation and the application write occur in one transaction;
  reuse with different parameters fails.
- Agent telemetry stores bounded pseudonymous subjects and excludes access
  tokens, secret values, idempotency values, note/report bodies, and large result
  arrays.
- No token, Massive API key, SEC identifying contact, or Lakebase connection URL
  is committed to the repository.

## Remaining acceptance gates

1. Deploy the `stock_research_mcp` Databricks App with its SQL warehouse,
   Lakebase, Massive secret, and managed-index resource bindings.
2. Verify the deployed health route and inspect startup/runtime logs.
3. Exercise a retrieval tool and at least one confirmed write action through the
   deployed MCP interface.
4. Repeat the same idempotency key and prove one logical write; retry it with a
   different payload and prove rejection.
5. Confirm successful and failed tool calls create bounded Lakebase session/event
   records without sensitive content.
6. Use two real authenticated account principals to prove owner isolation and
   identity propagation end to end.

The two-principal gate is externally blocked until a second account principal or
credential is available. It must not be simulated by forging request headers.

## Reproduction references

- Retrieval design: `docs/adr/0005-research-retrieval-and-embeddings.md`
- Phase status: `docs/phase5/STATUS.md`
- Workspace evaluation fixture: `fixtures/retrieval/phase5_workspace.json`
- Evaluation CLI: `tools/retrieval_eval.py`
- Managed retrieval client: `mcp_server/research_search.py`
- Delta publisher: `jobs/publish_research_search_documents.py`
- Search publisher job: `resources/research_search_publish.job.yml`

The sanitized generated evaluation report is intentionally ignored under
`build/phase5/re_eval/retrieval_eval.json`; the committed fixture and
evaluator provide the reproducible source of truth.
