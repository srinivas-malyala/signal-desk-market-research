# Render OIDC and application-credential preparation

Updated: 2026-09-24

## Accepted identity contract

- Provider: Google OpenID Connect.
- Issuer: `https://accounts.google.com`.
- Client type: OAuth 2.0 **Web application** using Authorization Code flow.
- Scopes: `openid email profile`.
- Final frontend origin: `https://signal-desk-frontend.onrender.com`.
- Final authorized redirect URI:
  `https://signal-desk-frontend.onrender.com/oidc/callback`.
- Bounded demo allowlist: enter permitted accounts in the frontend-only
  `ALLOWED_USER_EMAILS` Render secret.

The callback is fixed in `render.yaml` and must match the Google client exactly,
including scheme, host, path, case, and absence of a trailing slash. The
Blueprint service name is therefore part of the authentication contract. If
Render reports that the service name is unavailable, stop and update the
Blueprint, Google registration, this document, and the related contract tests
together.

## Google Cloud registration — user action required

Registration is not claimed complete until these provider-side steps are done:

1. In the intended Google Cloud project, configure the OAuth consent screen.
   Use **External** for personal Gmail accounts, keep the app in Testing for the
   bounded capstone, and add each demo account as a test user.
2. Create an OAuth client ID with application type **Web application**.
3. Set the authorized JavaScript origin to
   `https://signal-desk-frontend.onrender.com`.
4. Set the authorized redirect URI to
   `https://signal-desk-frontend.onrender.com/oidc/callback`.
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

- [ ] `LAKEBASE_URL` — administrator-provided SSL connection URL.
- [ ] `MASSIVE_API_KEY` — existing free-plan key.
- [ ] `DATA_WORKSPACE_CLIENT_ID` — MCP-specific M2M client ID.
- [ ] `DATA_WORKSPACE_CLIENT_SECRET` — MCP-specific M2M secret.
- [ ] `FRONTEND_ASSERTION_PUBLIC_KEY` — complete public PEM file.
- [ ] `MCP_SUPERVISOR_TOKEN` — complete generated token.
- [ ] `MCP_SUPERVISOR_SUBJECT` — non-secret fixed label, for example
  `signal-desk-supervisor`.

### `signal-desk-frontend`

- [ ] `LAKEBASE_URL` — same database endpoint, ownership still enforced by user.
- [ ] `DATA_WORKSPACE_CLIENT_ID` — frontend-specific M2M client ID.
- [ ] `DATA_WORKSPACE_CLIENT_SECRET` — frontend-specific M2M secret.
- [ ] `MCP_SERVER_URL` — final HTTPS URL for `signal-desk-mcp`.
- [ ] `OIDC_CLIENT_ID` — Google Web application client ID.
- [ ] `OIDC_CLIENT_SECRET` — Google client secret.
- [ ] `FLASK_SESSION_SECRET` — complete generated session secret.
- [ ] `FRONTEND_ASSERTION_PRIVATE_KEY` — complete private PEM file.
- [ ] `ALLOWED_USER_EMAILS` — comma-separated bounded demo accounts.

Public OIDC values are committed in the Blueprint:
`OIDC_ISSUER_URL=https://accounts.google.com` and the exact callback above.

## Rotation and acceptance

After entering secrets, compare the assertion public-key fingerprint against
`manifest.json`, deploy MCP first, then frontend, and verify missing, expired,
tampered, replayed, wrong-audience, and wrong-issuer assertions fail closed.
Rotate the assertion pair, session secret, and Supervisor token after the final
demo or immediately after suspected disclosure. Revoke the Google client secret
when the deployment is retired.
