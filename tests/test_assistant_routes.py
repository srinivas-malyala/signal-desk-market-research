import json
import threading
from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

import pytest
from test_render_frontend_routes import BASE_URL, render_app  # noqa: F401 - shared real auth fixture

from dashboard.assistant_repository import AssistantConflict, AssistantNotFound


@pytest.fixture
def chat(render_app):  # noqa: F811 - imported pytest fixture
    app = render_app.app
    app.config.update(ASSISTANT_ENABLED=True, ASSISTANT_SCHEMA_READY=True)
    render_app._user_id.__globals__["lakebase"].query.return_value = [{"id": 7}]
    repo, client = Mock(), Mock()
    run, conversation, submission = str(uuid4()), str(uuid4()), str(uuid4())
    repo.create.return_value = {"id": conversation, "title": "Research", "created_at": datetime.now(UTC)}
    repo.list_conversations.return_value = []
    repo.turns.return_value = []
    repo.start.return_value = ({"id": run, "lease_token": str(uuid4())}, True)
    repo.finish.return_value = True
    repo.watchlist_snapshot.return_value = {"tickers": ["AAPL"], "captured_at": datetime.now(UTC)}

    def generate(history, state, **kwargs):
        state.text = state.final_text = "<script>untrusted</script> Answer"
        state.finalized = state.terminal = True
        yield state.text

    client.stream.side_effect = generate
    app.config.update(ASSISTANT_REPOSITORY_FACTORY=lambda: repo, ASSISTANT_CLIENT_FACTORY=lambda: client)
    browser = app.test_client()
    with browser.session_transaction(base_url=BASE_URL) as session:
        session["user_email"] = "student@example.com"
        session["user_subject"] = "browser-subject"
        session["csrf_token"] = "a" * 32
    return render_app, browser, repo, client, conversation, submission


def post(chat, payload=None, csrf=True, buffered=True):
    _, browser, _, _, conversation, submission = chat
    return browser.post(f"/api/assistant/conversations/{conversation}/messages", base_url=BASE_URL,
                        headers={"X-CSRF-Token": "a" * 32} if csrf else {},
                        json=payload if payload is not None else {"message": "Question", "client_message_id": submission},
                        buffered=buffered)


def test_chat_requires_auth_and_csrf(chat):
    module, browser, repo, *_ = chat
    assert post(chat, csrf=False).status_code == 403
    repo.start.assert_not_called()
    assert module.app.test_client().get("/api/assistant/conversations", base_url=BASE_URL).status_code == 401


def test_flags_disable_routes_and_ui(chat):
    module, browser, repo, *_ = chat
    module.app.config["ASSISTANT_ENABLED"] = False
    assert browser.get("/api/assistant/conversations", base_url=BASE_URL).status_code == 404
    assert b'id="assistant"' not in browser.get("/", base_url=BASE_URL).data
    repo.list_conversations.assert_not_called()
    module.app.config.update(ASSISTANT_ENABLED=True, ASSISTANT_SCHEMA_READY=False)
    assert post(chat).status_code == 503


@pytest.mark.parametrize("payload", [[], {}, {"message": "Question", "owner": 8},
    {"message": "x"*4001, "client_message_id": str(uuid4())},
    {"message": "Question", "client_message_id": "invalid"}])
def test_input_is_strict(chat, payload):
    assert post(chat, payload).status_code == 400
    chat[2].start.assert_not_called()


def test_owner_scoped_stream_has_safe_envelope_and_final_text(chat):
    response = post(chat)
    assert response.status_code == 200 and response.content_type.startswith("text/event-stream")
    assert response.headers["X-Accel-Buffering"] == "no"
    events = [json.loads(frame[6:]) for frame in response.text.split("\n\n") if frame.startswith("data: ")]
    assert [event["type"] for event in events] == ["status", "text_delta", "complete"]
    assert [event["sequence"] for event in events] == [1, 2, 3]
    assert events[-1]["text"].endswith("Answer")
    assert all(event["schema_version"] == 1 and event["request_id"] == response.headers["X-Request-ID"] for event in events)
    assert len({event["run_id"] for event in events}) == 1
    chat[2].start.assert_called_once_with(7, chat[4], chat[5], "Question")
    chat[2].watchlist_snapshot.assert_called_once_with(7)
    assert "browser-subject" not in response.text and "Bearer" not in response.text


def test_cross_owner_missing_and_capacity_fail_before_stream(chat):
    repo = chat[2]
    repo.start.side_effect = AssistantNotFound()
    assert post(chat).status_code == 404
    repo.start.side_effect = AssistantConflict("generation_capacity")
    assert post(chat).status_code == 429


def test_duplicate_does_not_start_upstream(chat):
    chat[2].start.return_value = ({"id": str(uuid4()), "state": "completed"}, False)
    response = post(chat)
    assert response.json["existing_run"]["state"] == "completed"
    chat[3].stream.assert_not_called()


def test_history_and_creation_use_authenticated_owner(chat):
    _, browser, repo, _, conversation, _ = chat
    assert browser.post("/api/assistant/conversations", base_url=BASE_URL, json={},
                        headers={"X-CSRF-Token":"a"*32}).status_code == 201
    repo.create.assert_called_once_with(7, "Research")
    assert browser.get(f"/api/assistant/conversations/{conversation}", base_url=BASE_URL).status_code == 200
    repo.turns.assert_called_once_with(7, conversation, limit=50)


def test_storage_exception_is_safe(chat):
    chat[2].list_conversations.side_effect = RuntimeError("private-database-details")
    response = chat[1].get("/api/assistant/conversations", base_url=BASE_URL)
    assert response.status_code == 503 and b"private-database" not in response.data


def test_browser_disconnect_cancels_local_wait_and_persists_interruption(chat):
    from dashboard.supervisor_client import SupervisorError

    repo, client = chat[2:4]
    saved = threading.Event()
    repo.finish.side_effect = lambda *args, **kwargs: saved.set() or True

    def blocked(history, state, *, cancel_event):
        assert cancel_event.wait(2)
        raise SupervisorError("generation_cancelled")
        yield  # Make this a streaming generator without yielding any text.

    client.stream.side_effect = blocked
    response = post(chat, buffered=False)
    response.close()
    assert saved.wait(2)
    assert repo.finish.call_args.kwargs["state"] == "interrupted"
    assert repo.finish.call_args.kwargs["error_code"] == "disconnected"


def test_uninitialized_account_never_creates_a_machine_owned_conversation(chat):
    chat[0]._user_id.__globals__["lakebase"].query.return_value = []
    assert post(chat).json["error_code"] == "account_not_ready"
    chat[2].start.assert_not_called()


def test_second_browser_identity_cannot_load_first_owners_conversation(chat):
    module, browser, repo, client, conversation, _ = chat
    module._user_id.__globals__["lakebase"].query.side_effect = lambda sql, args: [
        {"id": 7 if args[0] == "student@example.com" else 34}]

    def owned_turns(owner, conversation, **kwargs):
        if owner != 7:
            raise AssistantNotFound()
        return []

    repo.turns.side_effect = owned_turns
    assert browser.get(f"/api/assistant/conversations/{conversation}", base_url=BASE_URL).status_code == 200
    other = module.app.test_client()
    with other.session_transaction(base_url=BASE_URL) as session:
        session["user_email"] = "other@example.com"
        session["user_subject"] = "other-subject"
        session["csrf_token"] = "b"*32
    assert other.get(f"/api/assistant/conversations/{conversation}", base_url=BASE_URL).status_code == 404
    assert repo.turns.call_args.args[0] == 34
    client.stream.assert_not_called()
