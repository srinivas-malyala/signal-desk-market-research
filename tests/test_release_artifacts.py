from __future__ import annotations

import re
from pathlib import Path

from mcp_server import lakebase

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "docs" / "release"


def test_release_artifacts_exist_and_have_no_template_placeholders() -> None:
    expected = {
        "DATA_DICTIONARY.md",
        "TOOL_API_REFERENCE.md",
        "REQUIREMENTS_TRACEABILITY.md",
        "DEMO_CHECKLIST.md",
    }
    assert {path.name for path in RELEASE.glob("*.md")} == expected
    for path in RELEASE.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert "<your-" not in text
        assert "demo@example.com" not in text


def test_data_dictionary_covers_every_allowlisted_lakebase_table() -> None:
    dictionary = (RELEASE / "DATA_DICTIONARY.md").read_text(encoding="utf-8")
    for table in lakebase.TABLE_BASES:
        assert f"`{table}`" in dictionary
    assert "massive_api_attempts_srini" in dictionary
    assert "user-authored content; cdc analytics excludes text" in dictionary.lower()


def test_tool_reference_matches_all_nine_mcp_tools() -> None:
    reference = (RELEASE / "TOOL_API_REFERENCE.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"^### `([a-z_]+)`$", reference, flags=re.MULTILINE))
    assert documented == {
        "get_stock_performance",
        "get_company_research",
        "compare_stocks",
        "get_watchlist",
        "update_watchlist",
        "save_research_note",
        "save_analysis_report",
        "semantic_research",
        "get_notable_updates",
    }
    assert "malyala.de@gmail.com" in reference
    assert "four attempts per 60 seconds" in reference


def test_traceability_names_every_required_capstone_component() -> None:
    matrix = (RELEASE / "REQUIREMENTS_TRACEABILITY.md").read_text(encoding="utf-8")
    for component in (
        "Spark data pipeline",
        "Third-party API",
        "Lakebase data model",
        "Action-taking AI agent",
        "Analytics pipeline",
        "Frontend",
        "Deployed application",
        "Two Big Data Vs",
    ):
        assert f"| {component} |" in matrix
    assert "1,255,489" in matrix
    assert "blocked externally" in matrix.lower()


def test_demo_checklist_includes_external_gates_and_negative_cases() -> None:
    checklist = (RELEASE / "DEMO_CHECKLIST.md").read_text(encoding="utf-8")
    for required in (
        "dataexpertio_srini",
        "migration `0005`",
        "simultaneous Job/MCP quota acceptance",
        "two real principals",
        "Invalid ticker",
        "Missing identity fails closed",
        "1,255,489",
    ):
        assert required in checklist
