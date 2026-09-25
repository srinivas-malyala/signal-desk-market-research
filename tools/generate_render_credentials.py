#!/usr/bin/env python3
"""Generate local-only Render application credentials without printing secrets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "build" / "render-secrets"
CALLBACK_URL = "https://signal-desk-frontend.onrender.com/oidc/callback"


def _write_secret(path: Path, value: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(value)


def generate(output: Path) -> dict[str, str]:
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(output, 0o700)
    expected = (
        output / "frontend-assertion-private.pem",
        output / "mcp-assertion-public.pem",
        output / "flask-session-secret.txt",
        output / "mcp-supervisor-token.txt",
        output / "manifest.json",
    )
    existing = [path.name for path in expected if path.exists()]
    if existing:
        raise FileExistsError(f"refusing to overwrite existing credential files: {', '.join(existing)}")

    private_key = rsa.generate_private_key(public_exponent=65_537, key_size=3_072)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    session_secret = secrets.token_urlsafe(64).encode("ascii")
    supervisor_token = secrets.token_urlsafe(64).encode("ascii")

    _write_secret(expected[0], private_pem)
    _write_secret(expected[1], public_pem)
    _write_secret(expected[2], session_secret + b"\n")
    _write_secret(expected[3], supervisor_token + b"\n")
    manifest = {
        "oidc_provider": "Google OpenID Connect",
        "oidc_issuer": "https://accounts.google.com",
        "oidc_redirect_uri": CALLBACK_URL,
        "assertion_algorithm": "RS256",
        "assertion_key_bits": "3072",
        "assertion_public_key_sha256": hashlib.sha256(public_pem).hexdigest(),
        "session_secret_sha256": hashlib.sha256(session_secret).hexdigest(),
        "supervisor_token_sha256": hashlib.sha256(supervisor_token).hexdigest(),
    }
    _write_secret(expected[4], (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = generate(args.output.resolve())
    print(f"Generated local-only credentials in: {args.output.resolve()}")
    print(f"Assertion public-key SHA-256: {manifest['assertion_public_key_sha256']}")
    print(f"Session secret SHA-256: {manifest['session_secret_sha256']}")
    print(f"Supervisor token SHA-256: {manifest['supervisor_token_sha256']}")
    print("Secret values were not printed. The output directory is excluded by .gitignore.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
