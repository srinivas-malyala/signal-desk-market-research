from unittest.mock import Mock

import pytest

from dashboard.assistant_execution import ExecutionService
from dashboard.user_writes import UserWrites


def fixture(kind="watchlist_add"):
    repo, client, tokens = Mock(), Mock(), Mock(side_effect=["write-user", "read-user"])
    args = {"ticker":"AAPL", "watchlist_name":"Primary"} if kind.startswith("watchlist") else {
        "ticker":"AAPL", "title":"Draft", "note_text":"Body", "thesis_tags":[]}
    row = {"id":"proposal", "lease_token":"lease", "idempotency_key":"original-key",
           "payload":{"type":kind, "arguments":args}}
    repo.begin_execution.return_value = (row, True)
    repo.finish_execution.return_value = True
    client.update_watchlist.return_value = {"status":"success", "ticker":"AAPL", "action":"add"}
    client.get_watchlist.return_value = {"status":"success", "tickers":[{"ticker":"AAPL"}]}
    client.save_research_note.return_value = {"status":"success", "note_id":42}
    return repo, client, tokens, ExecutionService(repo, UserWrites(client, tokens, "request"))


def test_fresh_user_identity_for_write_and_readback():
    repo, client, tokens, service = fixture()
    result = service.execute(7,"proposal","hash")
    assert result["receipt"]["verification"] == "verified"
    assert client.update_watchlist.call_args.kwargs["access_token"] == "write-user"
    assert client.get_watchlist.call_args.kwargs["access_token"] == "read-user"
    assert client.update_watchlist.call_args.kwargs["idempotency_key"] == "original-key"
    assert repo.finish_execution.call_args.args[:3] == (7,"proposal","lease")


def test_unknown_write_and_readback_failures_have_different_outcomes():
    repo, client, tokens, service = fixture()
    client.update_watchlist.side_effect = RuntimeError("private-upstream-details")
    result = service.execute(7,"proposal","hash")
    assert result["state"] == "outcome_unknown"
    assert "private-upstream" not in str(result)
    repo, client, tokens, service = fixture()
    client.get_watchlist.side_effect = RuntimeError("read failure")
    result = service.execute(7,"proposal","hash")
    assert result["state"] == "succeeded" and result["receipt"]["verification"] == "pending"


def test_uncertain_terminal_persistence_never_retries_write():
    repo, client, tokens, service = fixture()
    repo.finish_execution.side_effect = RuntimeError("commit acknowledgement lost")
    assert service.execute(7,"proposal","hash")["state"] == "outcome_unknown"
    client.update_watchlist.assert_called_once()


def test_replayed_success_does_not_write_again():
    repo, client, tokens, service = fixture()
    repo.begin_execution.return_value = ({"state":"succeeded", "receipt":{"verification":"verified"}}, False)
    assert service.execute(7,"proposal","hash")["replayed"]
    client.update_watchlist.assert_not_called()
    tokens.assert_not_called()


def test_identity_preparation_failure_is_known_not_executed():
    repo, client, tokens, service = fixture()
    tokens.side_effect = RuntimeError("private identity data")
    assert service.execute(7,"proposal","hash")["state"] == "failed"
    client.update_watchlist.assert_not_called()


def test_notes_verify_only_through_owner_scoped_repository():
    repo, client, tokens, service = fixture("save_note")
    repo.readback_saved.return_value = True
    assert service.execute(7,"proposal","hash")["receipt"]["note_id"] == 42
    assert repo.readback_saved.call_args.args[0] == 7


@pytest.mark.parametrize("result", [{"status":"success", "note_id":True}, {"status":"error"}, {}])
def test_invalid_receipts_are_unknown_not_success(result):
    repo, client, tokens, service = fixture("save_note")
    client.save_research_note.return_value = result
    assert service.execute(7,"proposal","hash")["state"] == "outcome_unknown"


def test_pending_verification_retry_reads_but_never_writes():
    repo, client, tokens, service = fixture()
    repo.begin_execution.return_value = ({"state":"succeeded", "payload":{"type":"watchlist_add",
        "arguments":{"ticker":"AAPL"}}, "receipt":{"verification":"pending"}}, False)
    result = service.execute(7,"proposal","hash")
    assert result["receipt"]["verification"] == "verified"
    client.update_watchlist.assert_not_called()
    repo.update_verification.assert_called_once()


def test_report_provenance_is_stable_across_request_ids():
    repo, client, tokens, service = fixture()
    row = {"id":"proposal", "lease_token":"lease", "idempotency_key":"original-key", "payload":{
        "type":"save_report", "arguments":{"title":"Report","thesis":"","tickers":["AAPL"],"report_text":"Body"}}}
    repo.begin_execution.return_value = (row, True)
    repo.readback_saved.return_value = True
    client.save_analysis_report.return_value = {"status":"success", "report_id":9}
    service.execute(7,"proposal","hash")
    source = client.save_analysis_report.call_args.kwargs["source_context"]
    assert source == {"origin":"assistant","proposal_id":"proposal","payload_hash":"hash"}
    assert "request_id" not in source  # Retry fingerprint must stay identical.


def test_trusted_receipt_context_excludes_private_metadata():
    from dashboard.assistant_context import execution_context

    context = execution_context([{"action":"save_note","user_id":7,"receipt":{
        "note_id":42,"verification":"verified","token":"private", "idempotency_key":"secret"}}])
    assert "private" not in context and "secret" not in context and "user_id" not in context
    assert "not action authorization" in context


def test_remove_verifies_absent_membership():
    repo, client, tokens, service = fixture("watchlist_remove")
    client.update_watchlist.return_value = {"status":"success","ticker":"AAPL","action":"remove"}
    client.get_watchlist.return_value = {"status":"success","tickers":[]}
    result = service.execute(7,"proposal","hash")
    assert result["state"] == "succeeded" and result["receipt"]["verification"] == "verified"
    assert client.update_watchlist.call_args.kwargs["action"] == "remove"
