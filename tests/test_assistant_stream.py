import json
import threading
from unittest.mock import Mock

import pytest

from dashboard.assistant_stream import PublicStream, StreamCapacity
from dashboard.supervisor_client import SupervisorClient, SupervisorError
from dashboard.supervisor_protocol import ResponseState


def test_heartbeats_and_disconnect_close_source_in_its_own_thread():
    stream = PublicStream(request_id="request", heartbeat=0.01)
    closed, released = threading.Event(), threading.Event()

    def source():
        try:
            assert released.wait(2)
            yield {"type":"complete", "run_id":"run"}
        finally:
            closed.set()

    stream.start(source(), {"type":"status", "run_id":"run"})
    output = iter(stream)
    assert json.loads(next(output)[6:])["sequence"] == 1
    assert next(output) == ": heartbeat\n\n"
    output.close()
    assert stream.cancelled.is_set()
    released.set()
    assert closed.wait(2)


def test_bounded_capacity_and_unstarted_reservation_cleanup(monkeypatch):
    import dashboard.assistant_stream as delivery

    monkeypatch.setattr(delivery, "_SLOTS", threading.BoundedSemaphore(1))
    stream = PublicStream(request_id="request")
    with pytest.raises(StreamCapacity):
        PublicStream(request_id="another")
    stream.close()
    stream.close()
    PublicStream(request_id="next").close()


def test_private_events_are_not_forwarded():
    def source():
        yield {"type":"function_call", "arguments":"private"}
        yield {"type":"complete", "run_id":"run", "state":"completed"}

    stream = PublicStream(request_id="request").start(source(), {"type":"status", "run_id":"run"})
    output = "".join(stream)
    assert "private" not in output
    assert '"sequence": 2' in output


def test_cancellation_before_invocation_does_not_authenticate_or_post():
    cancelled = threading.Event()
    cancelled.set()
    config, session = Mock(), Mock()
    with pytest.raises(SupervisorError, match="generation_cancelled"):
        list(SupervisorClient(config=config, session=session, endpoint="embedded")
             .stream([], ResponseState(), cancel_event=cancelled))
    config.authenticate.assert_not_called()
    session.post.assert_not_called()


def test_unicode_is_not_expanded_beyond_public_frame_bound():
    def source():
        yield {"type":"complete", "run_id":"run", "state":"completed", "text":"😀"*25000}

    stream = PublicStream(request_id="request").start(source(), {"type":"status", "run_id":"run"})
    frames = list(stream)
    assert len(frames[-1].encode()) < 150000
    assert json.loads(frames[-1][6:])["text"] == "😀"*25000
