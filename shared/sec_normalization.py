"""Pure reference normalization for dynamic SEC Company Facts payloads."""

from __future__ import annotations

import re
from typing import Any

CIK_PATTERN = re.compile(r"^\d{10}$")


def normalize_company_facts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_cik = payload.get("cik")
    cik_value = str(raw_cik) if raw_cik is not None else ""
    cik = cik_value.zfill(10)
    if not cik_value.isdigit() or len(cik_value) > 10 or not CIK_PATTERN.fullmatch(cik) or int(cik) == 0:
        raise ValueError("Company Facts payload has an invalid CIK")
    entity_name = payload.get("entityName")
    if not isinstance(entity_name, str) or not entity_name.strip():
        raise ValueError("Company Facts payload has no entity name")

    normalized: dict[tuple[Any, ...], dict[str, Any]] = {}
    taxonomies = payload.get("facts", {})
    if not isinstance(taxonomies, dict):
        raise ValueError("Company Facts payload facts must be an object")
    for taxonomy, concepts in taxonomies.items():
        if not isinstance(concepts, dict):
            continue
        for concept, definition in concepts.items():
            if not isinstance(definition, dict):
                continue
            units = definition.get("units", {})
            if not isinstance(units, dict):
                continue
            for unit, observations in units.items():
                if not isinstance(observations, list):
                    continue
                for observation in observations:
                    if not isinstance(observation, dict) or not observation.get("end") or not observation.get("filed"):
                        continue
                    row = {
                        "cik": cik,
                        "entity_name": entity_name.strip(),
                        "taxonomy": taxonomy,
                        "concept": concept,
                        "label": definition.get("label"),
                        "description": definition.get("description"),
                        "unit": unit,
                        "period_start": observation.get("start"),
                        "period_end": observation["end"],
                        "value": observation.get("val"),
                        "accession_number": observation.get("accn"),
                        "fiscal_year": observation.get("fy"),
                        "fiscal_period": observation.get("fp"),
                        "form": observation.get("form"),
                        "filed_date": observation["filed"],
                        "frame": observation.get("frame"),
                    }
                    key = (
                        cik,
                        taxonomy,
                        concept,
                        unit,
                        row["accession_number"],
                        row["period_start"],
                        row["period_end"],
                        row["frame"],
                    )
                    previous = normalized.get(key)
                    if previous is None or str(row["value"]) > str(previous["value"]):
                        normalized[key] = row
    return sorted(
        normalized.values(),
        key=lambda row: (
            row["taxonomy"],
            row["concept"],
            row["unit"],
            row["period_end"],
            row["accession_number"] or "",
        ),
    )
