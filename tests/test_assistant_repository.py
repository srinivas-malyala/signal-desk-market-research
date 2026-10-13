from contextlib import contextmanager
from unittest.mock import Mock
from uuid import uuid4

import pytest

from dashboard.assistant_repository import AssistantConflict, AssistantNotFound, AssistantRepository
from dashboard.assistant_service import AssistantService


def repository(rows):
    cursor = Mock()
    cursor.__enter__ = Mock(return_value=cursor)
    cursor.__exit__ = Mock(return_value=False)
    cursor.fetchone.side_effect = rows
    conn = Mock()
    conn.cursor.return_value = cursor

    @contextmanager
    def connection():
        yield conn

    return AssistantRepository(connection), cursor, conn


def test_cross_owner_claim_is_not_found():
    repo, cur, _ = repository([None])
    with pytest.raises(AssistantNotFound):
        repo.start(7, uuid4(), uuid4(), "Question")
    assert cur.execute.call_args.args[1][-1] == 7


def test_duplicate_returns_existing_without_inserting():
    import hashlib

    existing = {"id": str(uuid4()), "payload_hash": hashlib.sha256(b"Question").hexdigest()}
    repo, cur, conn = repository([{"id": "owned"}, existing])
    assert repo.start(7, uuid4(), uuid4(), "Question") == (existing, False)
    assert not any("INSERT" in call.args[0] for call in cur.execute.call_args_list)
    conn.commit.assert_called_once()


def test_changed_duplicate_rejected():
    repo, _, _ = repository([{"id": "owned"}, {"payload_hash": "different"}])
    with pytest.raises(AssistantConflict, match="submission_changed"):
        repo.start(7, uuid4(), uuid4(), "Question")


@pytest.mark.parametrize("count", [{"owned": 1, "total": 1}, {"owned": 0, "total": 4}])
def test_capacity_rejected(count):
    repo, _, _ = repository([{"id": "owned"}, None, count])
    with pytest.raises(AssistantConflict, match="generation_capacity"):
        repo.start(7, uuid4(), uuid4(), "Question")


def test_stale_worker_cannot_finalize():
    repo, cur, _ = repository([None])
    assert repo.finish(7, uuid4(), uuid4(), state="completed", text="Answer") is False
    sql, args = cur.execute.call_args.args
    assert "lease_until>clock_timestamp()" in sql and "user_id=%s" in sql
    assert args[3] == 7


@pytest.mark.parametrize("limit", [0, 1001, True, "100"])
def test_recovery_rejects_unbounded_batches(limit):
    repo, cur, _ = repository([])
    with pytest.raises(ValueError, match="invalid_limit"):
        repo.reconcile_expired(limit=limit)
    cur.execute.assert_not_called()


def test_duplicate_generation_does_not_invoke_model():
    repo, client = Mock(), Mock()
    repo.start.return_value = ({"id": "run", "state": "completed"}, False)
    assert list(AssistantService(repo, client).generate(7, "conversation", "submission", "Question"))[0]["type"] == "existing_run"
    client.stream.assert_not_called()


def test_generation_persists_verified_completion():
    repo, client = Mock(), Mock()
    repo.start.return_value = ({"id": "run", "lease_token": "lease"}, True)
    repo.turns.return_value = []
    repo.finish.return_value = True

    def stream(_history, state):
        state.final_text = "Answer"
        state.finalized = state.terminal = True
        yield "Answer"

    client.stream.side_effect = stream
    events = list(AssistantService(repo, client).generate(7, "conversation", "submission", "Question"))
    assert events[-1]["type"] == "complete"
    assert repo.finish.call_args.kwargs["state"] == "completed"


def test_disconnect_persists_interrupted_run():
    repo, client = Mock(), Mock()
    repo.start.return_value = ({"id": "run", "lease_token": "lease"}, True)
    repo.turns.return_value = []
    generator = AssistantService(repo, client).generate(7, "conversation", "submission", "Question")
    assert next(generator)["type"] == "status"
    generator.close()
    assert repo.finish.call_args.kwargs["state"] == "interrupted"
    assert repo.finish.call_args.kwargs["error_code"] == "disconnected"
    client.stream.assert_not_called()


def test_upstream_failure_persists_safe_category():
    from dashboard.supervisor_client import SupervisorError

    repo, client = Mock(), Mock()
    repo.start.return_value = ({"id": "run", "lease_token": "lease"}, True)
    repo.turns.return_value = []
    client.stream.side_effect = SupervisorError("dependency_permission")
    events = list(AssistantService(repo, client).generate(7, "conversation", "submission", "Question"))
    assert events[-1]["error_code"] == "dependency_error"
    assert repo.finish.call_args.kwargs["state"] == "failed"


def test_uncertain_terminal_commit_is_not_retried_or_reported_completed():
    repo, client = Mock(), Mock()
    repo.start.return_value = ({"id": "run", "lease_token": "lease"}, True)
    repo.turns.return_value = []
    repo.finish.side_effect = RuntimeError("private-database-connection")

    def stream(history, state):
        state.final_text = "Answer"
        state.finalized = state.terminal = True
        yield "Answer"

    client.stream.side_effect = stream
    events = list(AssistantService(repo, client).generate(7, "conversation", "submission", "Question"))
    assert events[-1]["type"] == "error"
    assert events[-1]["error_code"] == "storage_unavailable"
    assert "private-database" not in str(events)
    repo.finish.assert_called_once()


def test_context_database_failure_persists_before_public_error():
    repo, client = Mock(), Mock()
    repo.start.return_value = ({"id": "run", "lease_token": "lease"}, True)
    repo.turns.side_effect = RuntimeError("private-query-details")
    repo.finish.return_value = True
    generator = AssistantService(repo, client).generate(7, "conversation", "submission", "Question")
    assert next(generator)["error_code"] == "backend_unavailable"
    repo.finish.assert_called_once()
    generator.close()
    client.stream.assert_not_called()


def test_disconnect_explicitly_closes_upstream_generator():
    repo, client = Mock(), Mock()
    repo.start.return_value = ({"id": "run", "lease_token": "lease"}, True)
    repo.turns.return_value = []
    closed = []

    def stream(history, state):
        try:
            yield "partial"
        finally:
            closed.append(True)

    client.stream.side_effect = stream
    generator = AssistantService(repo, client).generate(7, "conversation", "submission", "Question")
    next(generator)
    next(generator)
    generator.close()
    assert closed == [True]
    repo.finish.assert_called_once()
    assert repo.finish.call_args.kwargs["state"] == "interrupted"
