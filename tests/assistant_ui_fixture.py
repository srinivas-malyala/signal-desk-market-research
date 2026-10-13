"""Localhost-only synthetic browser fixture. Never import into production."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from flask import Flask, g, jsonify, render_template, request

from dashboard.assistant_routes import register_assistant
from dashboard.supervisor_client import SupervisorError

ROOT = Path(__file__).parents[1] / "dashboard"
app = Flask(__name__, template_folder=str(ROOT / "templates"), static_folder=str(ROOT / "static"))
conversations, runs = {}, {}


class Repository:
    def create(self, owner, title="Research"):
        row = {"id": str(uuid4()), "title": title, "created_at": datetime.now(UTC)}
        conversations[row["id"]] = row
        return row

    def list_conversations(self, owner, **kwargs):
        return list(conversations.values())[::-1]

    def watchlist_snapshot(self, owner):
        return {"tickers": ["AAPL"], "captured_at": datetime.now(UTC)}

    def turns(self, owner, conversation, **kwargs):
        return [row for row in runs.values() if row["conversation_id"] == conversation]

    def start(self, owner, conversation, submission, question):
        for row in runs.values():
            if row["submission"] == submission:
                return row, False
        row = {"id": str(uuid4()), "lease_token": str(uuid4()), "state": "running",
               "conversation_id": conversation, "submission": submission, "user_text": question,
               "assistant_text": "", "created_at": datetime.now(UTC)}
        runs[row["id"]] = row
        return row, True

    def finish(self, owner, run, lease, *, state, text, error_code=None):
        runs[run].update(state=state, assistant_text=text)
        return True


class Client:
    def stream(self, history, state, *, cancel_event):
        count = 40 if "slow" in history[-1]["content"].lower() else 3
        for _ in range(count):
            if cancel_event.wait(0.1):
                raise SupervisorError("generation_cancelled")
            state.text += "Synthetic answer. "
            yield "Synthetic answer. "
        state.final_text = state.text + "<script>window.injected=true</script>"
        state.finalized = state.terminal = True


app.config.update(ASSISTANT_ENABLED=True, ASSISTANT_SCHEMA_READY=True,
                  ASSISTANT_REPOSITORY_FACTORY=Repository, ASSISTANT_CLIENT_FACTORY=Client)


@app.before_request
def fixture_identity():
    g.request_id = str(uuid4())
    if request.method == "POST" and request.headers.get("X-CSRF-Token") != "fixture-csrf":
        return jsonify(message="Fixture CSRF required"), 403


register_assistant(app, lambda: 7)


@app.get("/")
def index():
    return render_template("index.html", assistant_enabled=True, csrf_token="fixture-csrf",
                           user_email="Synthetic browser fixture", show_logout=False)


@app.get("/api/overview")
def overview():
    return jsonify(watchlist=[], news=[], notes=[], reports=[], activity=[])


@app.get("/api/analytics")
def analytics():
    return jsonify(state="empty", datasets={}, source="Synthetic fixture", execution_identity="Fixture")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8769, threaded=True, debug=False)
