from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from shared.sec_normalization import normalize_company_facts

FIXTURE = Path(__file__).parents[1] / "fixtures" / "sec" / "companyfacts.json"


def payload() -> dict:
    return json.loads(FIXTURE.read_text())


def test_company_facts_preserve_fiscal_period_taxonomy_and_accession() -> None:
    rows = normalize_company_facts(payload())
    assert rows == [
        {
            "cik": "0000320193",
            "entity_name": "Apple Inc.",
            "taxonomy": "us-gaap",
            "concept": "Assets",
            "label": "Assets",
            "description": "Total assets",
            "unit": "USD",
            "period_start": "2024-09-29",
            "period_end": "2025-06-28",
            "value": 331495000000,
            "accession_number": "0000320193-25-000079",
            "fiscal_year": 2025,
            "fiscal_period": "Q3",
            "form": "10-Q",
            "filed_date": "2025-08-01",
            "frame": "CY2025Q2I",
        }
    ]


def test_company_facts_support_multiple_units_and_deduplicate_snapshots() -> None:
    value = payload()
    assets = value["facts"]["us-gaap"]["Assets"]
    assets["units"]["USD"].append(copy.deepcopy(assets["units"]["USD"][0]))
    assets["units"]["shares"] = [
        assets["units"]["USD"][0] | {"val": 15000000000, "frame": "CY2025Q2I-shares"}
    ]
    rows = normalize_company_facts(value)
    assert len(rows) == 2
    assert {row["unit"] for row in rows} == {"USD", "shares"}


def test_company_facts_reject_missing_or_invalid_cik() -> None:
    value = payload()
    value.pop("cik")
    with pytest.raises(ValueError, match="invalid CIK"):
        normalize_company_facts(value)
