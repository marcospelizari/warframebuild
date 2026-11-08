# warframeBuild

- Code placement follows ARCHITECTURE.md → "Code structure": layers, allowed imports, where
  game facts live. Read it before adding a module; `tests/test_layers.py` enforces it.
- No new modules under `app/data/`; it is being moved to `gamedata/` and `pipeline/`.
- Gates before handing work back: `uv run pytest`, `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run mypy`.
