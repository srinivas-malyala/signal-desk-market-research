#!/usr/bin/env python3
"""Generate local-only Render application credentials without printing secrets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import stat
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "build" / "render-secrets"
CALLBACK_URL = "https://signal-desk-frontend.onrender.com/oidc/callback"
SECRET_FILES = (
    "frontend-assertion-private.pem",
    "mcp-assertion-public.pem",
    "flask-session-secret.txt",
    "mcp-supervisor-token.txt",
    "manifest.json",
)


def _paths(output: Path) -> tuple[Path, ...]:
    return tuple(output / name for name in SECRET_FILES)


def _write_secret(path: Path, value: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(value)


def generate(output: Path) -> dict[str, str]:
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(output, 0o700)
    expected = _paths(output)
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


def validate_existing(output: Path) -> dict[str, str]:
    expected = _paths(output)
    missing = [path.name for path in expected if not path.is_file()]
    if missing:
        raise RuntimeError(
            "credential directory is incomplete; missing "
            f"{', '.join(missing)}. Preserve it for investigation and use --output with a new directory."
        )
    if stat.S_IMODE(output.stat().st_mode) != 0o700:
        raise RuntimeError("credential directory permissions must be 0700")
    insecure = [path.name for path in expected if stat.S_IMODE(path.stat().st_mode) != 0o600]
    if insecure:
        raise RuntimeError(f"credential file permissions must be 0600: {', '.join(insecure)}")

    private_pem = expected[0].read_bytes()
    public_pem = expected[1].read_bytes()
    session_secret = expected[2].read_bytes().strip()
    supervisor_token = expected[3].read_bytes().strip()
    try:
        private_key = serialization.load_pem_private_key(private_pem, password=None)
        derived_public = private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        manifest = json.loads(expected[4].read_text(encoding="utf-8"))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError("existing credential set cannot be decoded or validated") from error
    if derived_public != public_pem:
        raise RuntimeError("assertion private and public keys do not match")

    fingerprints = {
        "assertion_public_key_sha256": hashlib.sha256(public_pem).hexdigest(),
        "session_secret_sha256": hashlib.sha256(session_secret).hexdigest(),
        "supervisor_token_sha256": hashlib.sha256(supervisor_token).hexdigest(),
    }
    mismatches = [name for name, value in fingerprints.items() if manifest.get(name) != value]
    if mismatches:
        raise RuntimeError(f"credential fingerprints do not match manifest: {', '.join(mismatches)}")
    if manifest.get("oidc_redirect_uri") != CALLBACK_URL:
        raise RuntimeError("credential manifest contains an unexpected OIDC redirect URI")
    return manifest


def prepare(output: Path) -> tuple[dict[str, str], bool]:
    if output.exists() and any(path.exists() for path in _paths(output)):
        return validate_existing(output), False
    return generate(output), True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    try:
        manifest, created = prepare(output)
    except (OSError, RuntimeError) as error:
        parser.exit(2, f"Credential validation failed: {error}\n")
    verb = "Generated new" if created else "Verified existing"
    print(f"{verb} local-only credentials in: {output}")
    print(f"Assertion public-key SHA-256: {manifest['assertion_public_key_sha256']}")
    print(f"Session secret SHA-256: {manifest['session_secret_sha256']}")
    print(f"Supervisor token SHA-256: {manifest['supervisor_token_sha256']}")
    if not created:
        print("No files were changed. Use --output with a new ignored directory to create a separate credential set.")
    print("Secret values were not printed. The default output directory is excluded by .gitignore.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
