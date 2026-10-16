# Contributing

- The Python server lives in `mcp/` (Python 3.12, [uv](https://docs.astral.sh/uv/)); the Next.js
  web app lives at the repository root (Node 22).
- Before opening a pull request: `npm run mcp:check` and `npm run typecheck && npm run lint && npm test`.
  CI runs the same commands.
- Install the hooks once with `uv run pre-commit install`.
- The `zapkite` library is read-only by construction. Pull requests that add order placement,
  modification or cancellation will not be merged.
- Never commit credentials. `.env` is ignored; document new settings in `.env.example`.
