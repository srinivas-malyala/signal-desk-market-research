# ADR 0005: Research chunking, embeddings, and retrieval

- Status: Accepted
- Date: 2026-09-11
- Scope: Phase 5 semantic research

## Context

Signal Desk must retrieve attributable evidence from SEC filings and market-news
articles. The Phase 3 prototype produces character-window chunks and the original
embedding job uses `all-MiniLM-L6-v2` with Lakebase pgvector. That path is useful
as a baseline, but it loses filing-section boundaries, has a short input limit,
duplicates chunking logic, and makes the application responsible for embedding
index lifecycle.

Exact financial values should not depend on similarity search. The existing SEC
Company Facts pipeline remains the authoritative route for structured XBRL facts;
semantic retrieval is for narrative evidence, explanations, risks, and news.

## Decision

### Canonical chunks

Use one deterministic, section-aware chunker in the Spark research pipeline.

- Preserve SEC Item boundaries and never join text across Items.
- Create child chunks targeting 500 lexical tokens, capped at 650, with 75-token
  overlap. Article text targets 375 tokens with a 50-token overlap when it is long
  enough to split.
- Group children into parent passages capped at 1,600 lexical tokens. Search
  matches a child and returns its parent for small-to-big context expansion.
- Persist separate `chunk_to_embed` and `chunk_to_retrieve` fields. The embedding
  input adds bounded company, ticker, form/article type, date, and section context;
  the returned passage remains faithful source text.
- Derive stable child and parent identifiers from source identity, content hash,
  section, and ordinal. Persist model-independent token counts and provenance.
- Keep tables as identifiable passages where possible, but route requests for
  exact values to structured Company Facts instead of treating narrative search
  as an accounting database.

“Token” in the Spark contract means a deterministic whitespace-delimited lexical
token. This avoids installing a model tokenizer on pipeline compute. The selected
model's context window is much larger than the resulting passages, so the lexical
cap is deliberately conservative.

### Embedding model and index

Use the Databricks Foundation Model API endpoint
`databricks-qwen3-embedding-0-6b` at 1,024 dimensions through a managed Delta Sync
Vector Search index.

- Qwen3 is instruction-aware and supports substantially longer inputs than the
  MiniLM prototype. Use a short retrieval instruction for queries and no task
  instruction for documents.
- Use a standard Vector Search endpoint, a triggered Delta Sync index, hybrid
  keyword/vector retrieval, metadata filters, and Databricks reranking when
  available.
- Request 20 candidates, rerank, and expose at most five passages to the agent.
- Enable Change Data Feed and row tracking on the canonical Delta chunk table so
  the index can update incrementally.
- Keep GTE (`databricks-gte-large-en`) as the production fallback if Qwen3 preview
  availability or quality is unacceptable. Retain MiniLM only as an evaluation
  baseline, not as the production serving path.

The managed index replaces the Phase 3 pgvector embedding job. Lakebase remains
the operational store for users, watchlists, notes, reports, sessions,
idempotency, and tool events; it is not the primary corpus vector store.

### Retrieval contract

The `semantic_research` tool accepts a required query and optional ticker,
source-type, and date filters. Every result includes score, child passage, parent
context, source type and identifier, ticker, title, source date, section, and URL.
The tool reports the index and model used, query mode, candidate/result limits,
as-of time, and limitations. Missing evidence is returned as missing evidence; it
is never substituted or inferred.

### Evaluation

Maintain a labeled retrieval fixture and calculate Recall@k, mean reciprocal rank,
and nDCG. Also inspect citation completeness, groundedness, p95 latency, filter
correctness, and empty-result behavior. The Phase 5 local gate validates the
harness and contracts; workspace acceptance requires at least 50 labeled questions
representing filings, articles, exact-keyword cases, and filter combinations.

Initial acceptance targets are Recall@5 >= 0.85, MRR >= 0.70, 100% provenance
completeness, and zero filter violations. Targets may be revised only with recorded
evaluation evidence.

## Consequences

- Chunking exists in one Spark-owned implementation instead of both the pipeline
  and embedding job.
- Corpus changes flow Delta table -> Change Data Feed -> managed Vector Search;
  application requests do not synchronously create embeddings.
- Search serving no longer consumes Lakebase connection-pool capacity.
- A Qwen3-to-GTE change requires rebuilding or versioning the index and rerunning
  the same labeled evaluation set.
- Databricks workspace authentication and index provisioning remain external gates
  for live acceptance; local implementation and deterministic tests do not depend
  on them.

## References

- [Databricks supported Foundation Model API models](https://docs.databricks.com/aws/en/machine-learning/foundation-model-apis/supported-models)
- [Create a Vector Search index](https://docs.databricks.com/aws/en/ai-search/create-ai-search)
- [Vector Search retrieval quality evaluation](https://docs.databricks.com/aws/en/ai-search/retrieval-quality-eval)
- [Vector Search overview and hybrid search](https://docs.databricks.com/aws/en/ai-search/ai-search)
- [`ai_prep_search` function](https://docs.databricks.com/gcp/en/sql/language-manual/functions/ai_prep_search)
- [Foundation Model API reference](https://docs.databricks.com/gcp/en/machine-learning/foundation-model-apis/api-reference)
- [Qwen3 Embedding 0.6B model card](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
- [MiniLM baseline model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
- [Chunking evaluation study](https://arxiv.org/abs/2608.12335)
- [Contextual retrieval study](https://arxiv.org/abs/2511.18177)

