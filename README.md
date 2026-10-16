# zap-kite-mcp

An MCP server that gives Claude read-only access to a Zerodha Kite Connect account and to
Indian market data through one `run_python` tool. Claude writes a Python script against the
`zapkite` library, the server runs it in an isolated subprocess and returns only what the
script printed, so large data never enters the model's context. The same server hosts
market watchers (Claude-authored conditions checked on a schedule without AI tokens, emailed
when they become true) and a small web app where users log in to Zerodha and manage watchers.

## How it fits together

| Piece | What it does |
|---|---|
| `zapkite` | Library Claude's scripts import: account reads, quotes, candles, instruments, a derived option chain with Black-76 greeks, indicators, market hours. Read-only by construction. |
| `zap_kite_mcp.server` | MCP server (Streamable HTTP, OAuth 2.1 authorization + resource server with dynamic client registration and PKCE), tools `run_python`, `auth_status`, `create_watcher`, `list_watchers`. |
| Gateway | Local `GET /kite/...` endpoint. Scripts hold only a per-run token; the gateway injects the user's Kite access token, allows read endpoints only and applies Kite's per-app rate limits. |
| Runner | Spawns `python -I` per script with a scrubbed environment, wall-clock timeout, output cap and a per-user workspace that persists between calls. |
| Watchers | Postgres-backed sweeper: baseline on first check, one alert per not-met→met transition, market-hours gate per exchange, pause when the Kite session ends and auto-resume after the next login. |
| Web app (`web/`) | Next.js app for Vercel: email + one-time-code sign-in, Zerodha login and callback, disconnect, watcher pause/resume/cancel. Shares the database and the crypto formats with the Python server. |

Kite facts that shape the design: Kite sessions end around 06:00 IST every day and cannot be
refreshed (users log in again from the web app); rate limits apply per API key, so one limiter
fronts all users; Kite has no option-chain or greeks API, so the chain is derived from the daily
instruments dump plus one batched quote call.

## Requirements

- Python 3.12 and [uv](https://docs.astral.sh/uv/).
- PostgreSQL 14 or newer.
- A Kite Connect app on the Connect plan (market data), with its redirect URL set to
  `<web app origin>/api/broker/kite/callback`.
- A [Resend](https://resend.com) API key for login codes and alert emails (optional in
  development: codes are logged instead).

## Run locally

```sh
cp .env.example .env            # fill KITE_API_KEY, KITE_API_SECRET, DATABASE_URL, secrets
uv sync
uv run zap-kite-mcp             # migrates the database, serves http://127.0.0.1:8019

cd web && cp .env.example .env  # same DATABASE_URL, SESSION_SECRET, CREDS_ENCRYPTION_KEY, Kite app
npm install && npm run dev      # http://127.0.0.1:3019
```

Set `DEV_LOGIN_EMAIL` and `DEV_LOGIN_CODE` in both `.env` files to sign in without email while
developing. Open the web app, sign in, click "Log in to Zerodha". Add the MCP to claude.ai as a
custom connector with URL `http://127.0.0.1:8019/mcp` (a public HTTPS URL in production); the
connector runs the OAuth flow with the same email sign-in.

`scripts/kite_login.py` obtains a Kite access token without the web app and
`scripts/live_smoke.py` exercises the library against the real API with it.

## Deploy

Python server: `deploy/` holds a hardened systemd unit, an nginx snippet (including the
root-level OAuth discovery routes a path-scoped issuer needs), a one-time `setup-uat.sh` and
`update.sh`. `package.json` wraps them: `npm run deploy:setup` once, then `npm run deploy` after
every push to `dev`; `npm run status` and `npm run logs` for operations.

Web app: import the repository into Vercel with root directory `web/`, add the variables from
`web/.env.example`, and point the Kite app's redirect URL at `https://<domain>/api/broker/kite/callback`.
Set `ZAP_KITE_MCP_APP_URL` on the Python server to the same domain.

## Development

```sh
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest       # needs Postgres; ZAP_KITE_MCP_TEST_DATABASE_URL overrides the default
```

The Python suite runs the real server against an in-process fake Kite: OAuth login, scripts
through the gateway, token expiry, watcher lifecycle and emails. `npm run web:check` typechecks,
lints and tests the web app; its tests pin the crypto formats to vectors produced by the Python
side.

## Licence

MIT. See [LICENSE](LICENSE).

## Staging

The `dev` branch is the staging source for both services. Vercel deploys it to
**Preview** (Development is Vercel's local environment), with project root `web/`.
`main` remains reserved for future production changes; do not promote staging previews.

- App and its `/api/*` routes: `https://staging-kite-app.slash.markets`.
  Add this project domain with Preview branch `dev`; use Vercel's returned DNS target.
- MCP connector: `https://staging-kite-mcp.slash.markets/mcp` on UAT `64.227.149.33`.
  `deploy/staging-nginx.conf` is a separate nginx site; obtain its TLS certificate with
  Certbot before enabling the HTTPS block. Preserve the existing UAT site.
- Vercel Preview `NEXT_PUBLIC_MCP_URL` must match the MCP connector URL. It is embedded
  at build time, so changes require a new deployment.
- UAT `.env`: `ZAP_KITE_MCP_PUBLIC_URL=https://staging-kite-mcp.slash.markets` and
  `ZAP_KITE_MCP_APP_URL=https://staging-kite-app.slash.markets` once the app domain works.
- Kite Connect redirect URL: `https://staging-kite-app.slash.markets/api/broker/kite/callback`.
  Set this in the Kite developer console only after the domain is ready.
- Keep the existing database, `SESSION_SECRET`, `CREDS_ENCRYPTION_KEY`, Kite credentials,
  and email configuration identical between UAT and Vercel Preview. Never regenerate them
  during this hostname migration. Staging currently shares the existing UAT data;
  a future production environment needs separately provisioned data and credentials.

`npm run deploy` invokes `/root/zap-kite-mcp-deploy/update.sh` on UAT. Keep that
operator copy synchronized with `deploy/update.sh`: it checks out `origin/dev`.
Git pushes trigger Vercel and CI; MCP deployment remains an explicit `npm run deploy`.
Changing the MCP OAuth issuer requires existing connector clients to reconnect using
its new URL. The former UAT route is retained for migration but is not a separate issuer.
An API-only hostname is deferred; the app continues using same-origin API requests.
