# Contributing

- Python 3.12, managed with [uv](https://docs.astral.sh/uv/). Run everything through `uv run`.
- Before opening a pull request: `uv run ruff check .`, `uv run ruff format .`, `uv run mypy`,
  `uv run pytest`. CI runs the same commands.
- Install the hooks once with `uv run pre-commit install`.
- The `zapkite` library is read-only by construction. Pull requests that add order placement,
  modification or cancellation will not be merged.
- Never commit credentials. `.env` is ignored; document new settings in `.env.example`.
