import threading
from unittest.mock import Mock

import pytest

from dashboard.assistant_runtime import RecoveryWorker, start_recovery, worker_timeout


def test_recovery_default_off_does_not_create_database_client(monkeypatch):
    monkeypatch.delenv("ASSISTANT_RECOVERY_ENABLED", raising=False)
    factory = Mock()
    assert start_recovery(factory) is None
    factory.assert_not_called()


def test_recovery_requires_migrated_schema(monkeypatch):
    monkeypatch.setenv("ASSISTANT_RECOVERY_ENABLED", "true")
    monkeypatch.setenv("ASSISTANT_SCHEMA_READY", "false")
    with pytest.raises(ValueError, match="assistant_schema_not_ready"):
        start_recovery(Mock())


def test_startup_periodic_recovery_and_shutdown(monkeypatch):
    monkeypatch.setenv("ASSISTANT_RECOVERY_ENABLED", "true")
    monkeypatch.setenv("ASSISTANT_SCHEMA_READY", "true")
    repo = Mock()
    ran = threading.Event()
    repo.reconcile_expired.side_effect = lambda **kwargs: ran.set() or 0
    worker = start_recovery(lambda: repo)
    try:
        assert ran.wait(1)
        repo.reconcile_expired.assert_called_once_with(limit=100)
    finally:
        worker.stop()
    assert not worker.thread.is_alive()


def test_recovery_errors_are_redacted_and_next_tick_can_succeed(caplog):
    repo = Mock()
    repo.reconcile_expired.side_effect = [RuntimeError("private-connection-details"), 2]
    worker = RecoveryWorker(repo)
    worker.tick()
    worker.tick()
    assert repo.reconcile_expired.call_count == 2
    assert "private-connection-details" not in caplog.text
    assert "storage_unavailable" in caplog.text


@pytest.mark.parametrize("setting,value", [
    ("ASSISTANT_RECOVERY_ENABLED", "yes"),
    ("ASSISTANT_RECOVERY_INTERVAL_SECONDS", "0"),
    ("ASSISTANT_RECOVERY_BATCH_SIZE", "1001"),
])
def test_invalid_recovery_configuration_fails_closed(monkeypatch, setting, value):
    monkeypatch.setenv("ASSISTANT_RECOVERY_ENABLED", "true")
    monkeypatch.setenv("ASSISTANT_SCHEMA_READY", "true")
    monkeypatch.setenv(setting, value)
    with pytest.raises(ValueError):
        start_recovery(Mock())


def test_worker_timeout_has_persistence_headroom(monkeypatch):
    monkeypatch.delenv("FRONTEND_WORKER_TIMEOUT_SECONDS", raising=False)
    assert worker_timeout() == 240
    monkeypatch.setenv("FRONTEND_WORKER_TIMEOUT_SECONDS", "60")
    with pytest.raises(ValueError):
        worker_timeout()


def test_retention_is_disabled_unless_explicitly_configured():
    repo = Mock()
    repo.reconcile_expired.return_value = 0
    RecoveryWorker(repo).tick()
    repo.redact_expired_transcripts.assert_not_called()
    repo.redact_expired_transcripts.return_value = 2
    RecoveryWorker(repo, retention_days=30).tick()
    repo.redact_expired_transcripts.assert_called_once_with(days=30, limit=100, apply=True)


def test_retention_requires_recovery_worker(monkeypatch):
    monkeypatch.setenv("ASSISTANT_RETENTION_ENABLED", "true")
    monkeypatch.setenv("ASSISTANT_RECOVERY_ENABLED", "false")
    with pytest.raises(ValueError, match="retention_requires_recovery"):
        start_recovery(Mock())
