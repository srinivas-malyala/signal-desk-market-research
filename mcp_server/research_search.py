"""Managed Databricks AI Search adapter for attributable research passages."""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import Any

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.vectorsearch import RerankerConfig, RerankerConfigRerankerParameters

from shared.databricks_auth import hosting_mode, workspace_client

DEFAULT_INDEX = "bootcamp_students.student_sri.signal_desk_research_chunks_index"
EMBEDDING_MODEL = "databricks-qwen3-embedding-0-6b"
QUERY_INSTRUCTION = (
    "Instruct: Retrieve an attributable SEC filing or market-news passage that answers the research question.\n"
    "Query: "
)
RESULT_COLUMNS = [
    "chunk_id",
    "parent_id",
    "source_type",
    "source_id",
    "tickers",
    "ticker",
    "title",
    "source_date",
    "source_url",
    "fetched_at",
    "section_name",
    "chunk_index",
    "chunk_to_retrieve",
    "chunk_token_count",
    "parent_text",
    "parent_token_count",
    "source_content_hash",
]
SOURCE_TYPES = frozenset({"filing", "article"})


def _iso_date(value: str | date | datetime | None, field_name: str) -> str | None:
    if value is None or value == "":
        return None
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError as error:
        raise ValueError(f"{field_name} must be an ISO date (YYYY-MM-DD).") from error


def build_filters(
    tickers: list[str] | None = None,
    source_types: list[str] | None = None,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    if tickers:
        symbols = sorted({str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()})
        if not symbols:
            raise ValueError("tickers must contain at least one ticker when supplied.")
        filters["tickers"] = symbols
    if source_types:
        normalized = sorted({str(value).strip().casefold() for value in source_types if str(value).strip()})
        unknown = set(normalized) - SOURCE_TYPES
        if unknown:
            raise ValueError(f"Unsupported source type: {sorted(unknown)[0]}.")
        filters["source_type"] = normalized
    start = _iso_date(start_date, "start_date")
    end = _iso_date(end_date, "end_date")
    if start and end and start > end:
        raise ValueError("start_date must be on or before end_date.")
    if start:
        filters["source_date >="] = start
    if end:
        filters["source_date <="] = end
    return filters


def _rows(response: Any) -> list[dict[str, Any]]:
    manifest = getattr(response, "manifest", None)
    result = getattr(response, "result", None)
    columns = [column.name for column in (getattr(manifest, "columns", None) or [])]
    data = getattr(result, "data_array", None) or []
    parsed: list[dict[str, Any]] = []
    for values in data:
        names = list(columns)
        if len(values) == len(names) + 1:
            names.append("score")
        row = dict(zip(names, values, strict=False))
        raw_score = row.pop("score", row.pop("_score", None))
        if raw_score is not None:
            try:
                row["score"] = float(raw_score)
            except (TypeError, ValueError):
                row["score"] = raw_score
        parsed.append(row)
    return parsed


class ResearchSearch:
    def __init__(
        self,
        workspace: WorkspaceClient | None = None,
        *,
        index_name: str | None = None,
        access_token: str | None = None,
    ) -> None:
        if workspace is None:
            if hosting_mode() == "render":
                workspace = workspace_client()
            elif access_token:
                host = os.environ.get("DATABRICKS_HOST")
                if not host:
                    raise ValueError("DATABRICKS_HOST is required for on-behalf-of-user search.")
                workspace = WorkspaceClient(host=host, token=access_token)
            else:
                workspace = workspace_client()
        self.workspace = workspace
        self.index_name = index_name or os.environ.get("SIGNAL_DESK_VECTOR_SEARCH_INDEX", DEFAULT_INDEX)

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        tickers: list[str] | None = None,
        source_types: list[str] | None = None,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
    ) -> dict[str, Any]:
        text = (query or "").strip()
        if not text:
            raise ValueError("A non-empty semantic research query is required.")
        limit = min(max(int(top_k), 1), 5)
        filters = build_filters(tickers, source_types, start_date, end_date)
        candidate_limit = min(max(limit * 4, 20), 50)
        response = self.workspace.vector_search_indexes.query_index(
            index_name=self.index_name,
            columns=RESULT_COLUMNS,
            query_text=f"{QUERY_INSTRUCTION}{text}",
            query_type="HYBRID",
            num_results=candidate_limit,
            filters_json=json.dumps(filters, sort_keys=True) if filters else None,
            reranker=RerankerConfig(
                model="databricks_reranker",
                parameters=RerankerConfigRerankerParameters(
                    columns_to_rerank=["chunk_to_retrieve"]
                ),
            ),
        )
        matches: list[dict[str, Any]] = []
        seen_parents: set[str] = set()
        for row in _rows(response):
            parent_key = str(row.get("parent_id") or row.get("chunk_id"))
            if parent_key in seen_parents:
                continue
            seen_parents.add(parent_key)
            row["passage"] = row.pop("chunk_to_retrieve", None)
            row["context"] = row.pop("parent_text", None)
            matches.append(row)
            if len(matches) == limit:
                break
        return {
            "status": "success",
            "contract_version": "1.0",
            "query": text,
            "matches": matches,
            "count": len(matches),
            "retrieval": {
                "index": self.index_name,
                "embedding_model": EMBEDDING_MODEL,
                "query_type": "HYBRID",
                "reranker": "databricks_reranker",
                "candidate_limit": candidate_limit,
                "result_limit": limit,
                "filters": filters,
            },
            "limitations": [
                "Narrative search is not authoritative for exact financial values; use structured SEC facts.",
                "Results reflect the most recently completed triggered index synchronization.",
            ],
        }
