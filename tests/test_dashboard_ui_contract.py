from pathlib import Path

ROOT = Path(__file__).parents[1]
TEMPLATE = (ROOT / "dashboard" / "templates" / "index.html").read_text(encoding="utf-8")
SCRIPT = (ROOT / "dashboard" / "static" / "app.js").read_text(encoding="utf-8")
STYLES = (ROOT / "dashboard" / "static" / "styles.css").read_text(encoding="utf-8")


def test_frontend_exposes_core_navigation_and_trust_context() -> None:
    for anchor in ("#research", "#watchlist-section", "#saved", "#analytics"):
        assert f'href="{anchor}"' in TEMPLATE
    assert "{{ user_email }}" in TEMPLATE
    assert "Tool access runs as this authenticated user" in TEMPLATE
    assert "not personalized investment advice" in TEMPLATE


def test_frontend_has_accessible_status_and_keyboard_contracts() -> None:
    assert TEMPLATE.count('aria-live="polite"') >= 4
    assert 'class="skip-link"' in TEMPLATE
    assert "focus-visible" in STYLES
    assert "prefers-reduced-motion" in STYLES
    assert "aria-label=\"Remove" in SCRIPT


def test_frontend_handles_required_data_states_and_provenance() -> None:
    for state in ("Loading", "No evidence matched", "partially refreshed", "stale", "rate limit"):
        assert state.casefold() in (TEMPLATE + SCRIPT).casefold()
    for context in ("source_url", "source_date", "as_of", "execution_identity", "source_max_synced_at"):
        assert context in SCRIPT
    assert "window.confirm" in SCRIPT
    assert "Idempotency-Key" in SCRIPT
