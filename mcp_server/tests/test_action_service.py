from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, Mock

import action_service
import pytest


def connection_with(cursor: Mock):
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor

    @contextmanager
    def get_connection():
        yield connection

    return connection, get_connection


def test_confirmed_action_commits_result_and_idempotency_together(monkeypatch: pytest.MonkeyPatch) -> None:
    cursor = Mock()
    cursor.fetchone.side_effect = [{"id": 7}, {"idempotency_key": "request-123"}]
    connection, get_connection = connection_with(cursor)
    monkeypatch.setattr(action_service.lakebase, "get_connection", get_connection)
    callback = Mock(return_value={"status": "success", "note_id": 42})

    result = action_service._execute(
        "person@example.com", "save_research_note", "request-123", True, callback
    )

    assert result == {"status": "success", "note_id": 42, "idempotent_replay": False}
    callback.assert_called_once_with(cursor, 7)
    connection.commit.assert_called_once()
    connection.rollback.assert_not_called()
    assert any("idempotency_records_srini" in call.args[0] for call in cursor.execute.call_args_list)


def test_repeated_key_returns_stored_result_without_repeating_action(monkeypatch: pytest.MonkeyPatch) -> None:
    cursor = Mock()
    cursor.fetchone.side_effect = [
        {"id": 7},
        None,
        {"result": {"status": "success", "note_id": 42, "idempotent_replay": False}},
    ]
    connection, get_connection = connection_with(cursor)
    monkeypatch.setattr(action_service.lakebase, "get_connection", get_connection)
    callback = Mock()

    result = action_service._execute(
        "person@example.com", "save_research_note", "request-123", True, callback
    )

    assert result == {"status": "success", "note_id": 42, "idempotent_replay": True}
    callback.assert_not_called()
    connection.commit.assert_called_once()


def test_reused_key_with_different_fingerprint_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    cursor = Mock()
    cursor.fetchone.side_effect = [
        {"id": 7},
        None,
        {"result": {"status": "success", "_request_fingerprint": "original"}},
    ]
    connection, get_connection = connection_with(cursor)
    monkeypatch.setattr(action_service.lakebase, "get_connection", get_connection)

    with pytest.raises(ValueError, match="different request"):
        action_service._execute(
            "person@example.com", "save_research_note", "request-123", True, Mock(), "different"
        )
    connection.rollback.assert_called_once()


@pytest.mark.parametrize(
    ("confirmed", "key", "message"),
    [(False, "request-123", "confirmation"), (True, "short", "idempotency_key")],
)
def test_unsafe_action_is_rejected_before_database_checkout(
    monkeypatch: pytest.MonkeyPatch, confirmed: bool, key: str, message: str
) -> None:
    get_connection = Mock()
    monkeypatch.setattr(action_service.lakebase, "get_connection", get_connection)
    with pytest.raises(ValueError, match=message):
        action_service._execute("person@example.com", "operation", key, confirmed, Mock())
    get_connection.assert_not_called()


def test_action_failure_rolls_back_both_write_and_idempotency_record(monkeypatch: pytest.MonkeyPatch) -> None:
    cursor = Mock()
    cursor.fetchone.side_effect = [{"id": 7}, {"idempotency_key": "request-123"}]
    connection, get_connection = connection_with(cursor)
    monkeypatch.setattr(action_service.lakebase, "get_connection", get_connection)

    def fail(_cursor, _user_id):
        raise RuntimeError("write failed")

    with pytest.raises(RuntimeError, match="write failed"):
        action_service._execute("person@example.com", "operation", "request-123", True, fail)
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()
