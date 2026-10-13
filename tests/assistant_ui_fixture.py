"""Localhost-only synthetic browser fixture. Never import into production."""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from flask import Flask, g, jsonify, render_template, request

from dashboard.assistant_proposals import normalize
from dashboard.assistant_routes import register_assistant
from dashboard.supervisor_client import SupervisorError
from dashboard.user_writes import UserWrites

ROOT = Path(__file__).parents[1] / "dashboard"
app = Flask(__name__, template_folder=str(ROOT / "templates"), static_folder=str(ROOT / "static"))
conversations, runs = {}, {}
drafts = {}
watchlist = set()


class Proposals:
    def create(self, owner, run, candidate):
        payload, digest = normalize(candidate)
        row = {"id":str(uuid4()), "payload":payload, "payload_hash":digest, "state":"pending", "revision":1,
               "expires_at":datetime.now(UTC)+timedelta(minutes=30), "conversation":runs[run]["conversation_id"]}
        drafts[row["id"]] = row
        return row

    def list(self, owner, conversation):
        return [row for row in drafts.values() if row["conversation"] == conversation]

    def revise(self, owner, proposal, digest, arguments):
        previous = drafts[proposal]
        previous["state"] = "superseded"
        payload, new_digest = normalize({**previous["payload"], "arguments":arguments})
        row = {**previous, "id":str(uuid4()), "payload":payload, "payload_hash":new_digest,
               "state":"pending", "revision":previous["revision"]+1}
        drafts[row["id"]] = row
        return row

    def dismiss(self, owner, proposal, digest):
        drafts[proposal]["state"] = "dismissed"
        return drafts[proposal]

    def begin_execution(self, owner, proposal, digest):
        row = drafts[proposal]
        if row["payload_hash"] != digest:
            raise ValueError("changed fixture draft")
        if row["state"] == "succeeded":
            return row, False
        row.update(state="executing", lease_token=str(uuid4()), idempotency_key=row.get("idempotency_key",str(uuid4())))
        return row, True

    def finish_execution(self, owner, proposal, lease, *, state, receipt=None, error=None):
        drafts[proposal].update(state=state,receipt=receipt)
        return True

    def receipt_context(self, owner, conversation):
        return []


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
    def update_watchlist(self, *, ticker, action, **kwargs):
        if action == "add":
            watchlist.add(ticker)
        else:
            watchlist.discard(ticker)
        return {"status":"success","ticker":ticker,"action":action}

    def get_watchlist(self, **kwargs):
        return {"status":"success","tickers":list(watchlist)}

    def stream(self, history, state, *, cancel_event):
        count = 40 if "slow" in history[-1]["content"].lower() else 3
        for _ in range(count):
            if cancel_event.wait(0.1):
                raise SupervisorError("generation_cancelled")
            state.text += "Synthetic answer. "
            yield "Synthetic answer. "
        state.final_text = state.text + "<script>window.injected=true</script>"
        state.finalized = state.terminal = True
        state.proposal_candidates.append({"schema_version":"1", "type":"watchlist_add", "arguments":{"ticker":"AAPL"}})


app.config.update(ASSISTANT_ENABLED=True, ASSISTANT_SCHEMA_READY=True,
                  ASSISTANT_REPOSITORY_FACTORY=Repository, ASSISTANT_CLIENT_FACTORY=Client,
                  ASSISTANT_PROPOSALS_ENABLED=True, ASSISTANT_PROPOSALS_SCHEMA_READY=True,
                  ASSISTANT_PROPOSAL_REPOSITORY_FACTORY=Proposals)
fixture_actions = os.getenv("ASSISTANT_FIXTURE_ACTIONS") == "true"
app.config.update(ASSISTANT_ACTIONS_ENABLED=fixture_actions,ASSISTANT_EXECUTION_SCHEMA_READY=fixture_actions)


@app.before_request
def fixture_identity():
    g.request_id = str(uuid4())
    if request.method == "POST" and request.headers.get("X-CSRF-Token") != "fixture-csrf":
        return jsonify(message="Fixture CSRF required"), 403


register_assistant(app, lambda: 7, lambda: UserWrites(Client(),lambda: "synthetic-user",g.request_id))


@app.get("/")
def index():
    return render_template("index.html", assistant_enabled=True, csrf_token="fixture-csrf",
                           user_email="Synthetic browser fixture", show_logout=False, assistant_proposals_enabled=True,
                           assistant_actions_enabled=fixture_actions)


@app.get("/api/overview")
def overview():
    return jsonify(watchlist=[], news=[], notes=[], reports=[], activity=[])


@app.get("/api/analytics")
def analytics():
    return jsonify(state="empty", datasets={}, source="Synthetic fixture", execution_identity="Fixture")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8769, threaded=True, debug=False)
