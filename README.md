# warframeBuild

A free, non-commercial build optimizer for Warframe primary and secondary weapons.

Pick a gun and the tool computes:

- **Max damage**: the highest burst DPS against a neutral target.
- **Recommended**: the best all-rounder, averaged across all factions.
- **Per faction**: one build tuned for each faction's damage-type modifiers.

Builds include the mods (with slot order for elements), exilus, arcane, Incarnon perks,
the Kuva/Tenet bonus element, and the forma needed to fit them.
The damage math follows the WARFRAME Wiki pages
[Damage/Calculation](https://wiki.warframe.com/w/Damage/Calculation) and
[Calculating Bonuses](https://wiki.warframe.com/w/Calculating_Bonuses).

Status: early development (scaffold). How it works: [ARCHITECTURE.md](ARCHITECTURE.md).

## Development

Needs [uv](https://docs.astral.sh/uv/) (Python 3.12 is fetched by uv) and Node.js 24.

```sh
uv sync                      # Python environment in .venv
cd web && npm ci && npm run build && cd ..
uv run wfb serve             # http://127.0.0.1:8000
```

Game data: `gamedata/` is generated and committed. To rebuild it:

```sh
uv run wfb refresh            # downloads DE Public Export + WFCD into cache/raw/, rebuilds gamedata/
uv run wfb refresh --offline  # rebuild from files already in cache/raw/
uv run wfb check              # after a game update: changed sources, rows and wiki pages to re-check
```

WARFRAME Wiki pages are never downloaded by the tool; they are saved by hand into
`cache/raw/wiki/<Page>.wikitext` (`https://wiki.warframe.com/w/<Page>?action=raw`).
Refresh names any missing page; the list is `reference/wiki_pages.json`.

Checks (the same as CI):

```sh
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
cd web && npm run lint && npm run typecheck && npm test
```

After an API change, regenerate the frontend types:

```sh
uv run wfb openapi > web/openapi.json && (cd web && npm run gen:types)
```

## Repository

Developed on GitLab; GitHub is a read-only mirror.

## License

Code: [GNU AGPL-3.0](LICENSE).
Data: WFCD-derived data under MIT; WARFRAME Wiki-derived data under CC BY-NC-SA 3.0.
See [NOTICE](NOTICE) for details.

## Credits

- [Digital Extremes](https://www.digitalextremes.com/): Warframe is their trademark.
  This project is not affiliated with or endorsed by Digital Extremes.
- [Warframe Community Developers (WFCD)](https://github.com/WFCD): game data via
  [warframestat.us](https://api.warframestat.us) and `warframe-items`.
- [WARFRAME Wiki](https://wiki.warframe.com) contributors: damage formulas, Incarnon evolutions,
  faction modifiers, Archon Shards.
