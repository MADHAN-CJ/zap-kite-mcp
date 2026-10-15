# zap-kite-mcp

An MCP server that gives Claude read-only access to a Zerodha Kite Connect account and to
Indian market data through a single `run_python` tool. Claude writes a Python script against
the `zapkite` library, the server runs it in an isolated subprocess and returns only what the
script printed. The same server hosts market watchers (Claude-authored conditions checked
without AI tokens) and a small web app for connecting Zerodha and managing watchers.

Status: under construction. Install and operations documentation lands with the first release.

## Development

```sh
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest
```

## Licence

MIT. See [LICENSE](LICENSE).
