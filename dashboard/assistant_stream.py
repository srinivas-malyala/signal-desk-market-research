"""Bounded public SSE delivery with heartbeat and local disconnect cancellation."""

import json
import queue
import threading
import time

_SLOTS = threading.BoundedSemaphore(4)


class StreamCapacity(RuntimeError):
    pass


class PublicStream:
    def __init__(self, *, request_id, heartbeat=5, deadline=200):
        self.slots = _SLOTS
        if not self.slots.acquire(blocking=False):
            raise StreamCapacity()
        self.request_id = request_id
        self.heartbeat = heartbeat
        self.deadline = deadline
        self.cancelled = threading.Event()
        self.pending = queue.Queue(maxsize=1)
        self.started = time.monotonic()
        self.sequence = 0
        self.worker = None

    def close(self):
        self.cancelled.set()
        if self.worker is None:
            self.slots.release()
            self.worker = False  # Unstarted reservation is released exactly once.

    def start(self, source, first):
        self.run_id = first["run_id"]
        def put(value):
            while not self.cancelled.is_set():
                try:
                    self.pending.put(value, timeout=0.1)
                    return True
                except queue.Full:
                    if time.monotonic() - self.started >= self.deadline:
                        self.cancelled.set()
            return False

        def produce():
            try:
                if put(first):
                    for event in source:
                        if not put(event):
                            break
                put(None)
            except Exception:
                put({"type": "error", "run_id": first.get("run_id"), "state": "interrupted",
                     "error_code": "backend_unavailable"})
                put(None)
            finally:
                try:
                    source.close()
                finally:
                    self.slots.release()

        self.worker = threading.Thread(target=produce, name="assistant-stream", daemon=True)
        try:
            self.worker.start()
        except Exception:
            self.slots.release()
            self.worker = False
            self.cancelled.set()
            source.close()
            raise
        return self

    def __iter__(self):
        try:
            while not self.cancelled.is_set():
                remaining = self.deadline - (time.monotonic() - self.started)
                if remaining <= 0:
                    return
                try:
                    event = self.pending.get(timeout=min(self.heartbeat, remaining))
                except queue.Empty:
                    yield ": heartbeat\n\n"
                    continue
                if event is None:
                    return
                if event.get("type") not in {"status", "text_delta", "complete", "error"}:
                    continue
                self.sequence += 1
                payload = {**event, "run_id": self.run_id, "schema_version": 1, "request_id": self.request_id,
                           "sequence": self.sequence}
                yield "data: " + json.dumps(payload, ensure_ascii=False, default=str) + "\n\n"
        finally:
            self.close()
