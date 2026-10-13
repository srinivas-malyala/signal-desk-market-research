"""Backend generation lifecycle; no Flask route or confirmed-write execution."""

from dashboard.assistant_context import watchlist_context
from dashboard.assistant_history import build_history
from dashboard.supervisor_client import SupervisorError
from dashboard.supervisor_protocol import ResponseState


class AssistantService:
    def __init__(self, repository, client, *, context_provider=None):
        self.repository = repository
        self.client = client
        self.context_provider = context_provider

    def generate(self, owner, conversation, submission, question):
        run, created = self.repository.start(owner, conversation, submission, question)
        if not created:
            yield {"type": "existing_run", "run_id": str(run["id"]), "state": run["state"]}
            return
        state = ResponseState()
        terminal = "interrupted"
        error = "disconnected"
        finalized = False
        try:
            turns = self.repository.turns(owner, conversation)
            context = watchlist_context(self.context_provider(owner)) if self.context_provider else ""
            history, omitted = build_history(turns, question, context=context)
            yield {"type": "status", "run_id": str(run["id"]), "history_omitted": omitted}
            # Repository methods have released their pooled connections here.
            for delta in self.client.stream(history, state):
                yield {"type": "text_delta", "text": delta}
            terminal = state.status
            error = None if terminal == "completed" else "invalid_stream"
            finalized = self.repository.finish(owner, run["id"], run["lease_token"], state=terminal,
                                               text=state.final_text or state.text, error_code=error)
            yield {"type": "complete" if terminal == "completed" and finalized else "error",
                   "run_id": str(run["id"]), "state": terminal if finalized else "interrupted"}
        except SupervisorError:
            terminal, error = "failed", "dependency_error"
            yield {"type": "error", "run_id": str(run["id"]), "state": "failed", "error_code": error}
        finally:
            if not finalized:
                self.repository.finish(owner, run["id"], run["lease_token"], state=terminal,
                                       text=state.final_text or state.text, error_code=error)
