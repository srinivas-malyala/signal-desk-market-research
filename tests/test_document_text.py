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
    first = build_research_chunks("filing", "accession-1", text, chunk_size=220, overlap=30)
    second = build_research_chunks("filing", "accession-1", text, chunk_size=220, overlap=30)
    changed = build_research_chunks("filing", "accession-1", text + " changed", chunk_size=220, overlap=30)
    assert len(first) > 1
    assert first == second
    assert first[0]["chunk_id"] != changed[0]["chunk_id"]
    assert first[0]["source_content_hash"] == first[-1]["source_content_hash"]


def test_empty_document_has_no_chunks_and_invalid_boundaries_fail() -> None:
    assert build_research_chunks("filing", "id", "") == []
    with pytest.raises(ValueError):
        build_research_chunks("filing", "id", "text", chunk_size=100)
