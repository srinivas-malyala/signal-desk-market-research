from __future__ import annotations

import sys
from pathlib import Path

import pytest

PIPELINES = Path(__file__).parents[1] / "pipelines"
sys.path.insert(0, str(PIPELINES))

from document_text import (  # noqa: E402
    build_research_chunks,
    extract_selected_sections,
    html_to_text,
    normalized_filing,
)

FIXTURE = Path(__file__).parents[1] / "fixtures" / "sec" / "filing.html"


def test_html_normalization_preserves_table_meaning_and_unicode() -> None:
    html = FIXTURE.read_text(encoding="utf-8").replace("Services", "Services™")
    text = html_to_text(html)
    assert "Metric" in text and "Net sales" in text and "$94,036" in text
    assert "Services™" in text
    assert "<table>" not in text


def test_malformed_html_and_repeated_boilerplate_are_deterministic() -> None:
    html = "<div>SECURITIES AND EXCHANGE COMMISSION<div>SECURITIES AND EXCHANGE COMMISSION<p>Body"
    assert html_to_text(html).splitlines() == ["SECURITIES AND EXCHANGE COMMISSION", "Body"]


def test_selected_sections_fall_back_to_full_nonempty_text() -> None:
    selected, headings = extract_selected_sections("Plain filing without item headings")
    assert selected == "Plain filing without item headings"
    assert headings == []
    assert normalized_filing("")["document_text"] == ""


def test_selected_item_extraction_records_headings() -> None:
    parsed = normalized_filing(FIXTURE.read_text(encoding="utf-8"))
    assert parsed["selected_sections"] == ["Item 2. Management's Discussion and Analysis"]
    assert "Net sales increased" in parsed["document_text"]


def test_chunk_boundaries_overlap_and_ids_are_stable() -> None:
    text = " ".join(f"word-{index}" for index in range(200))
    first = build_research_chunks(
        "filing", "accession-1", text, target_tokens=80, max_tokens=100, overlap_tokens=20
    )
    second = build_research_chunks(
        "filing", "accession-1", text, target_tokens=80, max_tokens=100, overlap_tokens=20
    )
    changed = build_research_chunks(
        "filing", "accession-1", text + " changed", target_tokens=80, max_tokens=100, overlap_tokens=20
    )
    assert len(first) > 1
    assert first == second
    assert first[0]["chunk_id"] != changed[0]["chunk_id"]
    assert first[0]["source_content_hash"] == first[-1]["source_content_hash"]
    assert set(first[0]["chunk_text"].split()) & set(first[1]["chunk_text"].split())


def test_chunks_preserve_sections_parents_and_contextual_embedding_text() -> None:
    text = "Item 1. Business\n" + " ".join(["business"] * 90) + "\nItem 7. Discussion\n" + " ".join(
        ["results"] * 90
    )
    chunks = build_research_chunks(
        "filing",
        "accession-2",
        text,
        title="Example Corp",
        ticker="EXM",
        source_date="2026-01-01",
        document_kind="10-K",
        target_tokens=60,
        max_tokens=80,
        overlap_tokens=10,
    )
    assert {chunk["section_name"] for chunk in chunks} == {"Item 1. Business", "Item 7. Discussion"}
    assert all(chunk["chunk_token_count"] <= 80 for chunk in chunks)
    assert all(chunk["parent_token_count"] <= 1600 for chunk in chunks)
    assert all(chunk["chunk_to_retrieve"] == chunk["chunk_text"] for chunk in chunks)
    assert "Company: Example Corp\nTicker: EXM\nDocument: 10-K" in chunks[0]["chunk_to_embed"]
    assert not any("business" in chunk["chunk_text"] and "results" in chunk["chunk_text"] for chunk in chunks)


def test_empty_document_has_no_chunks_and_invalid_boundaries_fail() -> None:
    assert build_research_chunks("filing", "id", "") == []
    with pytest.raises(ValueError):
        build_research_chunks("filing", "id", "text", target_tokens=40)
