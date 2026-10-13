"""Default-off, post-fork generation recovery; no transcript logging or purge."""

from __future__ import annotations

import logging
import os
import threading

from dashboard.assistant_repository import AssistantRepository

logger = logging.getLogger("signal_desk.assistant")
GENERATION_TIMEOUT_SECONDS = 180
GENERATION_LEASE_SECONDS = 210


def integer_setting(name, default, minimum, maximum):
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        raise ValueError(f"invalid_{name}") from None
    if not minimum <= value <= maximum:
        raise ValueError(f"invalid_{name}")
    return value


def enabled(name):
    value = os.getenv(name, "false").lower()
    if value not in {"true", "false"}:
        raise ValueError(f"invalid_{name}")
    return value == "true"


def worker_timeout():
    # Fixed lease must exceed the model deadline; leave persistence headroom.
    return integer_setting("FRONTEND_WORKER_TIMEOUT_SECONDS", 240, 240, 600)


class RecoveryWorker:
    def __init__(self, repository, *, interval=60, batch=100, retention_days=None):
        self.repository = repository
        self.interval = interval
        self.batch = batch
        self.retention_days = retention_days
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self.run, name="assistant-recovery", daemon=True)

    def tick(self):
        try:
            count = self.repository.reconcile_expired(limit=self.batch)
            logger.info("assistant_recovery_completed count=%d", count)
            if self.retention_days is not None:
                count = self.repository.redact_expired_transcripts(days=self.retention_days, limit=self.batch, apply=True)
                logger.info("assistant_retention_completed count=%d", count)
        except Exception:
            # Driver exceptions may contain connection details; never log them.
            logger.warning("assistant_recovery_failed category=storage_unavailable")

    def run(self):
        while not self.stopped.is_set():
            self.tick()
            if self.stopped.wait(self.interval):
                return

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self.stopped.set()
        self.thread.join(timeout=1)


def start_recovery(repository_factory=AssistantRepository):
    retention = enabled("ASSISTANT_RETENTION_ENABLED")
    if not enabled("ASSISTANT_RECOVERY_ENABLED"):
        if retention:
            raise ValueError("retention_requires_recovery")
        return None
    if not enabled("ASSISTANT_SCHEMA_READY"):
        raise ValueError("assistant_schema_not_ready")
    interval = integer_setting("ASSISTANT_RECOVERY_INTERVAL_SECONDS", 60, 10, 3600)
    batch = integer_setting("ASSISTANT_RECOVERY_BATCH_SIZE", 100, 1, 1000)
    days = integer_setting("ASSISTANT_RETENTION_DAYS", 30, 1, 3650) if retention else None
    return RecoveryWorker(repository_factory(), interval=interval, batch=batch, retention_days=days).start()
