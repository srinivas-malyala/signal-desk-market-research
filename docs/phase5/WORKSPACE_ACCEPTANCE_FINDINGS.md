# Phase 5 Workspace Acceptance Findings

Updated: 2026-10-07 Pacific

## Purpose

This report records the Phase 5 workspace acceptance work for the Signal Desk
capstone. It preserves the verified results, the workspace-specific problems
encountered, and the changes made in response. Historical workspace findings
are retained below, followed by reconciliation to the final Render deployment.

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

Phase 5 is complete for the capstone deployment. The originally outstanding MCP
health, action, idempotency, trace, and authorization gates later passed on
Render, including isolation and cleanup with two real authenticated principals.
Market reads are Lakebase-primary; research remains on the accepted Databricks
AI Search v2 index because Lakebase FTS did not meet its Recall@5 threshold.

## Accepted components and evidence

| Area | Result | Evidence |
|---|---|---|
| Authentication and bundle validation | Passed | OAuth identity `malyalasrinivas@gmail.com`; strict development bundle validation passes |
| Canonical Spark corpus | Passed | 393 complete chunks from 98 sources: 86 articles and 12 SEC filings |
| Corpus integrity | Passed | Zero incomplete rows, duplicate chunk IDs, duplicate `(source_type, source_id, chunk_index)` keys, or untraceable chunks |
| Lakebase migration | Passed | Checksum-protected migrations `0001` through `0005` are applied; repeat runs apply nothing |
| Lakebase namespace | Passed | All 16 expected `_srini` tables exist in shared schema `bootcamp_students` and are owned by the connected role |
| CDC readiness | Passed | Six selected action/event or bridge tables use `REPLICA IDENTITY FULL` |
| Owner isolation | Passed | Correct-owner update affected one row; wrong-owner update affected zero; disposable records were fully removed |
| Search serving table | Passed | Publisher run `255439151353917` reconciled 393 canonical source rows to 393 regular Delta target rows with zero duplicate chunk IDs |
| Managed AI Search | Passed | Standard endpoint and triggered Delta Sync hybrid index are ready with 393 indexed rows |
| Index synchronization | Passed | Job `430452316532258`, run `52577799192254`, completed successfully |
| Live retrieval evaluation | Passed | 51 cases; Recall@5 1.0000, MRR 0.9902, nDCG@5 0.9928, zero provenance failures, zero filter violations |
| Governed market retrieval | Passed | 9 AAPL rows reconciled independently; 0.24% known-answer return; 2-day freshness; safe snapshot entitlement fallback; 1 Massive attempt |
| Deployment acceptance harness | Deployed accepted | Nine-tool discovery, governed and semantic retrieval, opt-in writes, replay/conflict/cleanup, and bounded traces/events passed |
| Final identity and agent acceptance | Passed | Two real principals proved isolation and cleanup; governed Supervisor evaluation passed 10/10 |
| Full local regression | Passed | 285 tests pass on 2026-10-07; release evidence also records Ruff and credential-scan acceptance |

The corpus refresh completed through research-pipeline validation update
`ca094e65-f38e-4ebe-b121-0b1faeea946d` and refresh update
`56c5df46-e1a8-4d14-bd93-d467aadb554e`. The successful serving-table publisher
belongs to job `873159231343771`.

## Managed search resources

| Resource | Identifier |
|---|---|
| Vector Search endpoint | `signal-desk-research-dev` |
| Endpoint ID | `4f1e61a9-cf40-4a57-9d7d-7419ffd8fe26` |
| Delta Sync index | `bootcamp_students.student_sri.signal_desk_research_chunks_index_v2` |
| Embedding model | `databricks-qwen3-embedding-0-6b` |
| Delta source table | `bootcamp_students.student_sri.research_search_documents` |

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
original Databricks Apps design proposed a `uc_securable` resource, but that
deployment path was superseded by Render. The deployed MCP reaches AI Search
with the owner-approved shared `dbx-ai-de-aug26` OAuth M2M identity.

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

## Governed market retrieval acceptance

The Phase 5.2 runner performs two independent bounded reads of the selected
Silver/Gold warehouse path and reconciles the tool response to the independently
read rows. It then permits one rate-limited Massive snapshot request to prove
that the free-plan entitlement either returns a usable snapshot or degrades to a
safe daily-aggregate fallback.

The 2026-09-11 AAPL run passed all eight checks:

| Check | Result |
|---|---:|
| Warehouse/tool rows | 9 / 9 |
| As-of date | 2026-09-09 |
| Staleness | 2 days |
| Independently calculated return | 0.24% |
| Tool return | 0.24% |
| Snapshot | Unavailable with safe entitlement fallback |
| Massive physical attempts | 1 |
| Maximum rolling-minute budget | 4 |

The sanitized generated result is ignored at
`build/phase5/retrieval_acceptance.json`; the runner and its deterministic tests
are committed.

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

## Final deployment reconciliation

The original Databricks App gates were superseded by the two-service Render
deployment and are not remaining work. The final accepted outcome is:

1. Both Render services are live and their public health probes return 200.
2. Lakebase is primary for market and operational state; Databricks AI Search v2
   remains the accepted research backend.
3. Retrieval and confirmed write actions passed exact replay,
   changed-payload rejection, cleanup, and bounded trace/event reconciliation.
4. Two real authenticated principals proved end-to-end ownership isolation.
5. The shared cross-host Massive quota coordinator passed simultaneous Job/MCP
   acceptance and failed closed at the configured rolling limit.
6. The governed Supervisor endpoint is READY and its deployed evaluation passed
   10/10.
7. Lakebase FTS remains unpromoted: its 51-case Recall@5 was 0.7843 versus the
   committed 0.85 minimum, with zero provenance and filter violations.

## Reproduction references

- Retrieval design: `docs/adr/0005-research-retrieval-and-embeddings.md`
- Phase status: `docs/phase5/STATUS.md`
- Workspace evaluation fixture: `fixtures/retrieval/phase5_workspace.json`
- Evaluation CLI: `tools/retrieval_eval.py`
- Governed retrieval acceptance: `tools/phase5_retrieval_acceptance.py`
- Post-deployment MCP smoke: `tools/phase5_mcp_smoke.py`
- Managed retrieval client: `mcp_server/research_search.py`
- Delta publisher: `jobs/publish_research_search_documents.py`
- Search publisher job: `resources/research_search_publish.job.yml`

The sanitized generated evaluation report is intentionally ignored under
`build/phase5/re_eval/retrieval_eval.json`; the committed fixture and
evaluator provide the reproducible source of truth.
