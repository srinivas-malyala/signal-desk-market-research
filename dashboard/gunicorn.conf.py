"""Worker lifecycle for the Render frontend; loaded before any fork."""

from dashboard.assistant_runtime import start_recovery, worker_timeout

timeout = worker_timeout()


def post_worker_init(worker):
    worker.assistant_recovery = start_recovery()


def worker_exit(server, worker):
    recovery = getattr(worker, "assistant_recovery", None)
    if recovery is not None:
        recovery.stop()
