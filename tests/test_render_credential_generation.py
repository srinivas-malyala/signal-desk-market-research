from __future__ import annotations

import json
import stat

import jwt
import pytest

from tools.generate_render_credentials import CALLBACK_URL, generate, prepare, validate_existing


def test_generated_render_credentials_are_private_and_cryptographically_matched(tmp_path) -> None:
    output = tmp_path / "render-secrets"
    manifest = generate(output)

    private_key = (output / "frontend-assertion-private.pem").read_text()
    public_key = (output / "mcp-assertion-public.pem").read_text()
    token = jwt.encode({"sub": "test", "aud": "signal-desk-mcp"}, private_key, algorithm="RS256")
    claims = jwt.decode(token, public_key, algorithms=["RS256"], audience="signal-desk-mcp")
    assert claims["sub"] == "test"
    assert manifest["oidc_redirect_uri"] == CALLBACK_URL
    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    for path in output.iterdir():
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_manifest_contains_only_fingerprints_not_secret_values(tmp_path) -> None:
    output = tmp_path / "render-secrets"
    generate(output)
    manifest_text = (output / "manifest.json").read_text()
    manifest = json.loads(manifest_text)
    assert set(manifest) == {
        "assertion_algorithm",
        "assertion_key_bits",
        "assertion_public_key_sha256",
        "oidc_issuer",
        "oidc_provider",
        "oidc_redirect_uri",
        "session_secret_sha256",
        "supervisor_token_sha256",
    }
    assert (output / "flask-session-secret.txt").read_text().strip() not in manifest_text
    assert (output / "mcp-supervisor-token.txt").read_text().strip() not in manifest_text


def test_generator_refuses_to_overwrite_credentials(tmp_path) -> None:
    output = tmp_path / "render-secrets"
    generate(output)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        generate(output)


def test_prepare_is_idempotent_and_validates_existing_set(tmp_path) -> None:
    output = tmp_path / "render-secrets"
    created_manifest, created = prepare(output)
    existing_manifest, created_again = prepare(output)

    assert created is True
    assert created_again is False
    assert existing_manifest == created_manifest
    assert validate_existing(output) == created_manifest


def test_validation_rejects_tampered_secret_without_overwriting(tmp_path) -> None:
    output = tmp_path / "render-secrets"
    generate(output)
    token_path = output / "mcp-supervisor-token.txt"
    original = token_path.read_bytes()
    token_path.write_bytes(b"tampered\n")
    token_path.chmod(0o600)

    with pytest.raises(RuntimeError, match="fingerprints do not match"):
        prepare(output)
    assert token_path.read_bytes() != original
