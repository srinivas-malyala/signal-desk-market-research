from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = (ROOT / "dashboard/static/assistant.js").read_text()
TEMPLATE = (ROOT / "dashboard/templates/assistant.html").read_text()


def test_chat_never_executes_model_html_or_actions():
    assert "textContent" in SCRIPT
    for unsafe in ("innerHTML", "insertAdjacentHTML", "eval(", "/proposals/", "/api/watchlist", "/api/notes", "/api/reports"):
        assert unsafe not in SCRIPT
    assert "RESEARCH ONLY" in TEMPLATE


def test_accessible_controls_and_safe_delivery_states():
    for control in ("question", "send", "stop", "reload", "retry", "conversation", "new"):
        assert f'id="assistant-{control}"' in TEMPLATE
    assert 'aria-live="polite"' in TEMPLATE
    assert 'for="assistant-question"' in TEMPLATE
    assert "credentials:'same-origin'" in SCRIPT
    assert "X-CSRF-Token" in SCRIPT
    assert "client_message_id:pending.id" in SCRIPT
    assert "without verified completion" in SCRIPT
    assert "reader.cancel()" in SCRIPT
