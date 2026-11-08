# warframeBuild

- Code placement follows ARCHITECTURE.md → "Code structure": layers, allowed imports, where
  game facts live. Read it before adding a module; `tests/test_layers.py` enforces it.
- `tests/test_layers.py` also fails on modules over 300 lines, on `common`/`utils`/
  `helpers` names and on `app/data/`. Plan the split before a module gets there.
- Reviews (the `review` skill, run on every branch before hand-off) check ARCHITECTURE.md
  "Code structure" rules 1–5 and verify game mechanics against the saved wiki pages in
  `cache/raw/wiki/`, citing page and line; a rule without a saved source is a finding.
- Gates before handing work back: `uv run pytest`, `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run mypy`.
