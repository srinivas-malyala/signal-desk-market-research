"""Research-only chat boundary; existing application auth/CSRF runs first."""

from flask import Blueprint, Response, current_app, g, jsonify, request

from dashboard.assistant_repository import AssistantConflict, AssistantNotFound, AssistantRepository, identifier
from dashboard.assistant_runtime import enabled
from dashboard.assistant_service import AssistantService
from dashboard.assistant_stream import PublicStream, StreamCapacity
from dashboard.supervisor_client import SupervisorClient, SupervisorError


def register_assistant(app, owner_provider):
    app.config.setdefault("ASSISTANT_ENABLED", enabled("ASSISTANT_ENABLED"))
    app.config.setdefault("ASSISTANT_SCHEMA_READY", enabled("ASSISTANT_SCHEMA_READY"))
    blueprint = Blueprint("assistant", __name__, url_prefix="/api/assistant")

    def error(code, status, message="The chat request could not be completed."):
        return jsonify(status="error", error_code=code, message=message,
                       request_id=g.request_id), status

    @blueprint.before_request
    def feature_gate():
        if not current_app.config["ASSISTANT_ENABLED"]:
            return error("assistant_disabled", 404)
        if not current_app.config["ASSISTANT_SCHEMA_READY"]:
            return error("assistant_not_ready", 503)

    def dependencies():
        owner = owner_provider()
        if owner is None:
            raise AssistantConflict("account_not_ready")
        factory = current_app.config.get("ASSISTANT_REPOSITORY_FACTORY", AssistantRepository)
        return owner, factory()

    def body(fields):
        value = request.get_json(silent=True)
        if not isinstance(value, dict) or set(value) - set(fields):
            raise ValueError("invalid_input")
        return value

    def bound_limit(default):
        value = int(request.args.get("limit", default))
        if not 1 <= value <= 100:
            raise ValueError("invalid_limit")
        return value

    @blueprint.errorhandler(AssistantNotFound)
    def not_found(exc):
        return error("not_found", 404)

    @blueprint.errorhandler(AssistantConflict)
    def conflict(exc):
        if str(exc) == "account_not_ready":
            return error("account_not_ready", 409, "Load your watchlist to initialize your account, then retry chat.")
        return error("generation_capacity" if str(exc) == "generation_capacity" else "submission_conflict",
                     429 if str(exc) == "generation_capacity" else 409)

    @blueprint.errorhandler(ValueError)
    def bad_input(exc):
        return error("invalid_input", 400)

    @blueprint.errorhandler(Exception)
    def unavailable(exc):
        # Do not delegate database/transport exceptions to the generic raw logger.
        return error("assistant_unavailable", 503)

    @blueprint.route("/conversations", methods=["GET", "POST"])
    def conversations():
        owner, repo = dependencies()
        if request.method == "POST":
            payload = body({"title"})
            conversation = repo.create(owner, payload.get("title", "Research"))
            return jsonify(conversation=conversation), 201
        if set(request.args) - {"before", "limit"}:
            raise ValueError("invalid_input")
        limit = bound_limit(20)
        rows = repo.list_conversations(owner, limit=limit, before=request.args.get("before"))
        return jsonify(conversations=rows, next_cursor=str(rows[-1]["id"]) if len(rows) == limit else None)

    @blueprint.get("/conversations/<conversation>")
    def history(conversation):
        if set(request.args) - {"limit"}:
            raise ValueError("invalid_input")
        owner, repo = dependencies()
        return jsonify(turns=repo.turns(owner, identifier(conversation), limit=bound_limit(50)))

    @blueprint.post("/conversations/<conversation>/messages")
    def message(conversation):
        payload = body({"message", "client_message_id"})
        question = payload.get("message")
        if not isinstance(question, str) or not question.strip() or len(question) > 4000:
            raise ValueError("invalid_message")
        conversation, submission = identifier(conversation), identifier(payload.get("client_message_id"))
        owner, repo = dependencies()
        factory = current_app.config.get("ASSISTANT_CLIENT_FACTORY", SupervisorClient)
        try:
            client = factory()
            stream = PublicStream(request_id=g.request_id)
        except StreamCapacity:
            return error("generation_capacity", 429)
        except SupervisorError:
            return error("supervisor_not_configured", 503)
        source = AssistantService(repo, client, context_provider=repo.watchlist_snapshot).generate(
            owner, conversation, submission, question, cancel_event=stream.cancelled)
        try:
            # Claim/ownership/duplicate validation occurs before SSE headers.
            first = next(source)
            if first["type"] == "existing_run":
                source.close()
                stream.close()
                return jsonify(existing_run=first)
            if first["type"] == "error":
                source.close()
                stream.close()
                return error(first.get("error_code", "assistant_unavailable"), 503)
            stream.start(source, first)
        except BaseException:
            source.close()
            stream.close()
            raise
        response = Response(iter(stream), content_type="text/event-stream; charset=utf-8",
                            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
        response.call_on_close(stream.close)
        return response

    app.register_blueprint(blueprint)
