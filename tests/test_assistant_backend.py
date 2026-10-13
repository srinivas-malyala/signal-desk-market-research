import json
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from dashboard.assistant_context import watchlist_context
from dashboard.assistant_history import build_history
from dashboard.supervisor_client import SupervisorClient, SupervisorError
from dashboard.supervisor_protocol import ProtocolError, ResponseState, decode_events


def final_event(text="Answer"):
    return {"type": "response.output_item.done", "item": {
        "id": "same", "type": "message", "role": "assistant",
        "content": [{"type": "output_text", "text": text}],
    }}


def test_history_excludes_failed_and_trims_complete_pairs():
    turns = [{"state": "completed", "user_text": str(i), "assistant_text": "Answer"} for i in range(20)]
    turns.append({"state": "failed", "user_text": "private", "assistant_text": "failed"})
    history, omitted = build_history(turns, "Current")
    assert omitted
    assert len(history) == 19
    assert history[0]["content"] == "11"
    assert history[-1] == {"role": "user", "content": "Current"}


def test_unicode_history_byte_limit():
    history, omitted = build_history([{"state": "completed", "user_text": "x", "assistant_text": "😀" * 6000}], "Now")
    assert omitted and len(history) == 1


@pytest.mark.parametrize("question", ["", " ", "x" * 4001, None])
def test_invalid_questions(question):
    with pytest.raises(ValueError):
        build_history([], question)


def test_done_requires_finalized_assistant_and_failure_overrides():
    state = ResponseState()
    state.accept({"type": "transport.done"})
    assert state.status == "interrupted"
    state.accept(final_event())
    assert state.status == "interrupted"
    state.accept({"type": "transport.done"})
    assert state.status == "completed"
    state.accept({"type": "response.incomplete"})
    assert state.status == "failed"


def test_same_id_tool_does_not_hide_message():
    state = ResponseState()
    state.accept({"type": "response.output_item.done", "item": {"id": "same", "type": "function_call"}})
    state.accept(final_event())
    state.accept({"type": "transport.done"})
    assert state.status == "completed" and state.final_text == "Answer"


def test_sse_and_truncated_frames():
    events = list(decode_events([": heartbeat", "data: " + json.dumps(final_event()), "", "data: [DONE]", ""]))
    assert len(events) == 2
    with pytest.raises(ProtocolError, match="truncated_frame"):
        list(decode_events(["data: [DONE]"]))


@pytest.mark.parametrize("payload", ["[]", "not json", "x" * 256001])
def test_invalid_or_oversized_sse(payload):
    with pytest.raises(ProtocolError):
        list(decode_events(["data: " + payload, ""]))


def test_transport_auth_payload_and_cleanup():
    config = Mock(host="https://workspace.example.com")
    config.authenticate.return_value = {"Authorization": "Bearer test"}
    response = Mock(status_code=200, headers={"Content-Type": "text/event-stream"})
    response.iter_lines.return_value = ["data: " + json.dumps(final_event()), "", "data: [DONE]", ""]
    session = Mock()
    session.post.return_value = response
    state = ResponseState()
    client = SupervisorClient(config=config, session=session, endpoint="embedded-endpoint")
    assert list(client.stream([{"role": "user", "content": "Question"}], state)) == []
    assert state.status == "completed"
    assert session.post.call_args.kwargs["allow_redirects"] is False
    assert session.post.call_args.kwargs["json"]["stream"] is True
    config.authenticate.assert_called_once()
    response.close.assert_called_once()


@pytest.mark.parametrize("status,category", [(401, "dependency_auth"), (403, "dependency_permission"), (429, "dependency_capacity"), (500, "dependency_unavailable")])
def test_transport_safe_errors(status, category):
    config = Mock(host="https://workspace.example.com")
    config.authenticate.return_value = {}
    session = Mock()
    session.post.return_value = Mock(status_code=status)
    with pytest.raises(SupervisorError, match=category):
        list(SupervisorClient(config=config, session=session, endpoint="embedded").stream([], ResponseState()))
    session.post.return_value.close.assert_called_once()


@pytest.mark.parametrize("event", [
    [], {"type": "response.output_item.done", "item": "bad"},
    {"type": "response.output_item.done", "item": {"type": []}},
    {"type": "response.completed", "response": "bad"},
    {"type": "response.completed", "response": {"status": "completed", "output": {}}},
    {"type": "response.output_item.done", "item": {"type": "message", "role": "assistant", "content": ["bad"]}},
    {"type": "response.output_item.done", "item": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": 4}]}},
])
def test_malformed_shapes_raise_safe_protocol_errors(event):
    with pytest.raises(ProtocolError):
        ResponseState().accept(event)


def test_context_is_allowlisted_bounded_data_not_authority():
    context = watchlist_context({"captured_at": datetime(2026, 10, 12, tzinfo=UTC),
                                "tickers": ["aapl", "AAPL", "MSFT"], "token": "secret", "owner": 42})
    assert "secret" not in context and '"owner"' not in context
    assert '"tickers": ["AAPL", "MSFT"]' in context
    history, _ = build_history([], "Question", context=context)
    assert "not action authorization" in history[0]["content"]


def test_context_rejects_unbounded_and_undated_snapshots():
    with pytest.raises(ValueError):
        watchlist_context({"captured_at": datetime.now(), "tickers": []})
    with pytest.raises(ValueError):
        watchlist_context({"captured_at": datetime.now(UTC), "tickers": ["AAPL"] * 51})
    with pytest.raises(ValueError):
        build_history([], "Question", context="😀" * 1001)
