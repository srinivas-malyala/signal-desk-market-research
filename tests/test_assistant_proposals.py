import pytest

from dashboard.assistant_proposals import normalize, public_proposal


def candidate(ticker="aapl"):
    return {"schema_version":"1", "type":"watchlist_add", "arguments":{"ticker":ticker}}


def test_canonical_hash_normalizes_and_rejects_identity():
    payload, digest = normalize(candidate())
    assert payload["arguments"] == {"ticker":"AAPL", "watchlist_name":"Primary"}
    assert normalize(candidate("AAPL"))[1] == digest
    assert normalize(candidate("MSFT"))[1] != digest
    with pytest.raises(ValueError):
        normalize({**candidate(), "owner":7})
    with pytest.raises(ValueError):
        normalize({**candidate(), "arguments":{"ticker":"AAPL", "confirmed":True}})


@pytest.mark.parametrize("value", [
    {"type":"unknown", "arguments":{}},
    {"type":"save_note", "arguments":{"ticker":"AAPL", "title":"x", "note_text":"x"*20001}},
    {"type":"save_report", "arguments":{"title":"x", "report_text":"x", "tickers":["AAPL","aapl"]}},
])
def test_invalid_proposals_fail_closed(value):
    with pytest.raises(ValueError):
        normalize(value)


def test_public_preview_omits_execution_authority():
    row = {key:"value" for key in ("id","payload","payload_hash","state","revision","expires_at")}
    assert "idempotency_key" not in public_proposal({**row, "idempotency_key":"private", "user_id":7})


def test_only_matched_typed_tool_outputs_become_candidates():
    import json

    from dashboard.supervisor_protocol import ResponseState

    state = ResponseState()
    output = json.dumps({"status":"proposal", "executed":False, "proposal":candidate()})
    state.accept({"type":"response.output_item.done", "item":{"type":"function_call_output", "call_id":"unknown", "output":output}})
    assert state.proposal_candidates == []
    state.accept({"type":"response.output_item.done", "item":{"type":"function_call", "call_id":"known", "name":"catalog__propose_watchlist_add"}})
    state.accept({"type":"response.output_item.done", "item":{"type":"function_call_output", "call_id":"known", "output":output}})
    assert state.proposal_candidates[0]["arguments"]["ticker"] == "AAPL"
    assert state.status == "interrupted"  # Candidate alone is not trusted completion.


def test_failed_or_incomplete_generation_never_stores_drafts():
    from unittest.mock import Mock

    from dashboard.assistant_service import AssistantService

    repo, client, proposals = Mock(), Mock(), Mock()
    repo.start.return_value = ({"id":"run", "lease_token":"lease"}, True)
    repo.turns.return_value = []

    def stream(history, state):
        state.proposal_candidates.append(candidate())
        yield "Partial"

    client.stream.side_effect = stream
    list(AssistantService(repo, client, proposal_repository=proposals).generate(7,"conversation","submission","Question"))
    proposals.create.assert_not_called()
