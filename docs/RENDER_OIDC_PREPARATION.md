# Render OIDC and application-credential preparation

Updated: 2026-10-07

## Accepted identity contract

- Provider: Google OpenID Connect.
- Issuer: `https://accounts.google.com`.
- Client type: OAuth 2.0 **Web application** using Authorization Code flow.
- Scopes: `openid email profile`.
- Final frontend origin: `https://signal-desk-frontend-s88i.onrender.com`.
- Final authorized redirect URI:
  `https://signal-desk-frontend-s88i.onrender.com/oidc/callback`.
- Bounded demo allowlist: enter permitted accounts in the frontend-only
  `ALLOWED_USER_EMAILS` Render secret.

The callback is fixed in `render.yaml` and must match the Google client exactly,
including scheme, host, path, case, and absence of a trailing slash. The
Blueprint service name is therefore part of the authentication contract. If
Render reports that the service name is unavailable, stop and update the
Blueprint, Google registration, this document, and the related contract tests
together.

## Google Cloud registration — completed

The OAuth 2.0 Web application client contains the assigned Render origin and
exact callback below. Client credentials belong only in the Render frontend
environment. Live browser login, verified-email allowlisting, logout/session
handling, CSRF, assertion rejection cases, and two-real-principal isolation have
all passed deployed acceptance.

The completed provider-side configuration is:

1. In the intended Google Cloud project, configure the OAuth consent screen.
   Use **External** for personal Gmail accounts, keep the app in Testing for the
   bounded capstone, and add each demo account as a test user.
2. Create an OAuth client ID with application type **Web application**.
3. Set the authorized JavaScript origin to
   `https://signal-desk-frontend-s88i.onrender.com`.
4. Set the authorized redirect URI to
   `https://signal-desk-frontend-s88i.onrender.com/oidc/callback`.
5. Copy the resulting client ID and client secret directly into the Render
   frontend secret fields. Do not save them in this repository or screenshots.
6. After deployment, execute one login and verify the ID token contains a
   verified email and stable subject. Then execute the configured allowlist's
   negative case with an unlisted account.

Google requires the runtime redirect URI to exactly equal an authorized value.
Render derives the public `onrender.com` hostname from the service name, which
is why registration follows reservation of the Blueprint service name.

## Generate application-only credentials

Run from the repository root:

```bash
uv run python tools/generate_render_credentials.py
```

The command creates `build/render-secrets/`, which is excluded by `.gitignore`,
with directory mode `0700` and file mode `0600`. The first run generates the
credential set. Later runs validate the existing files, key pairing,
permissions, and fingerprints without changing anything. A partial or tampered
set fails closed; use `--output` with a new ignored directory when intentionally
creating a separate set. Only SHA-256 fingerprints are printed.

| Local file | Render service and variable |
|---|---|
| `frontend-assertion-private.pem` | Frontend: `FRONTEND_ASSERTION_PRIVATE_KEY` |
| `mcp-assertion-public.pem` | MCP: `FRONTEND_ASSERTION_PUBLIC_KEY` |
| `flask-session-secret.txt` | Frontend: `FLASK_SESSION_SECRET` |
| `mcp-supervisor-token.txt` | MCP: `MCP_SUPERVISOR_TOKEN` |
| `manifest.json` | Local verification only; do not enter as a secret |

The private assertion key must never be entered on the MCP service. The public
key must never substitute for the frontend private key. The Supervisor token is
not an OIDC or Databricks credential and must be available only to the MCP
service and the governed Supervisor connection.

## Render secret-entry checklist

Enter values through Render's secret UI. Do not use shell command history,
committed `.env` files, build arguments, or screenshots.

### `signal-desk-mcp`

- [x] `LAKEBASE_URL` — administrator-provided SSL connection URL.
- [x] `MASSIVE_API_KEY` — existing free-plan key.
- [x] `DATA_WORKSPACE_CLIENT_ID` — owner-approved shared M2M client ID.
- [x] `DATA_WORKSPACE_CLIENT_SECRET` — owner-approved shared M2M secret.
- [x] `FRONTEND_ASSERTION_PUBLIC_KEY` — complete public PEM file.
- [x] `MCP_SUPERVISOR_TOKEN` — complete generated token.
- [x] `MCP_SUPERVISOR_SUBJECT` — non-secret fixed label, for example
  `signal-desk-supervisor`.

### `signal-desk-frontend`

- [x] `LAKEBASE_URL` — same database endpoint, ownership still enforced by user.
- [x] `DATA_WORKSPACE_CLIENT_ID` — same owner-approved shared M2M client ID.
- [x] `DATA_WORKSPACE_CLIENT_SECRET` — same owner-approved shared M2M secret.
- [x] `MCP_SERVER_URL` — final HTTPS URL for `signal-desk-mcp`.
- [x] `OIDC_CLIENT_ID` — Google Web application client ID.
- [x] `OIDC_CLIENT_SECRET` — Google client secret.
- [x] `FLASK_SESSION_SECRET` — complete generated session secret.
- [x] `FRONTEND_ASSERTION_PRIVATE_KEY` — complete private PEM file.
- [x] `ALLOWED_USER_EMAILS` — comma-separated bounded demo accounts.

Deployed acceptance confirms the checklist through observed behavior; secret
values were not read or copied into evidence. Public OIDC values are committed
in the Blueprint:
`OIDC_ISSUER_URL=https://accounts.google.com` and the exact callback above.

## Rotation and acceptance

For any rotation, compare the assertion public-key fingerprint against
`manifest.json`, deploy MCP first, then frontend, and reverify that missing,
expired, tampered, replayed, wrong-audience, and wrong-issuer assertions fail
closed. Rotate the assertion pair, session secret, and Supervisor token after
the final demo or immediately after suspected disclosure. Revoke the Google
client secret when the deployment is retired.
