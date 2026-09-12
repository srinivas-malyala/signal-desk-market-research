from __future__ import annotations

import pytest
from audit import pseudonymous_subject, result_summary, safe_parameters, trusted_email


def test_forwarded_identity_is_required_for_user_owned_tools() -> None:
    with pytest.raises(ValueError, match="trusted Databricks"):
        trusted_email(None)
    assert trusted_email({"email": " Person@Example.com "}) == "person@example.com"
    assert pseudonymous_subject("Person@Example.com") == pseudonymous_subject(" person@example.com ")
    assert "person@example.com" not in str(pseudonymous_subject("person@example.com"))


def test_trace_metadata_excludes_bodies_tokens_and_oversized_results() -> None:
    parameters = safe_parameters(
        {
            "ticker": "AAPL",
            "note_text": "secret thesis" * 100,
            "report_text": "private report" * 100,
            "source_context": {"raw": "private evidence"},
            "idempotency_key": "request-sensitive-123",
        }
    )
    serialized = repr(parameters)
    assert "secret thesis" not in serialized
    assert "private report" not in serialized
    assert "private evidence" not in serialized
    assert "request-sensitive-123" not in serialized
    assert parameters["note_text"]["characters"] == 1300

    result = result_summary(
        {"status": "success", "ticker": "AAPL", "daily_bars": [{"close": number} for number in range(500)]}
    )
    assert result == {
        "status": "success",
        "ticker": "AAPL",
        "collection_counts": {"daily_bars": 500},
    }
