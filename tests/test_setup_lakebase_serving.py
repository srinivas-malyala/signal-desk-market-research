from __future__ import annotations

import pytest

from tools.setup_lakebase_serving import identifier, table_names


def test_serving_table_names_follow_shared_suffix_convention() -> None:
    assert table_names("srini") == (
        "market_history_serving_srini",
        "research_documents_serving_srini",
    )


def test_serving_identifiers_reject_unsafe_values() -> None:
    with pytest.raises(ValueError, match="lowercase PostgreSQL identifier"):
        identifier("bootcamp-students", "schema")
    with pytest.raises(ValueError, match="lowercase PostgreSQL identifier"):
        table_names("srini;drop")
