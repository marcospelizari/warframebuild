# Architecture

warframeBuild computes optimized builds for Warframe primary and secondary weapons
and shows them in the browser. This page summarizes how it works.

## What it computes

For each weapon:

- **Max damage**: highest burst DPS (average shot damage × effective fire rate) against a neutral target,
  with sustained DPS (including reloads) shown next to it.
- **Recommended**: one build to keep equipped for general play, without swapping mods per faction.
- **Faction builds**: one build for each main faction (Grineer, Corpus, Infested, Corrupted,
  Sentient, The Murmur, Scaldra, Techrot).

Each build covers the 8 mod slots in slot order (element combinations depend on it), exilus,
arcane, Incarnon evolutions, the Kuva/Tenet/Coda bonus element and the forma needed to fit
the mods. Later versions add Archon Shards, aura mods, companions, riven advice, Warframe ability buffs
and an enemy picker that re-scores a build against one chosen enemy (for information; builds stay
optimized per faction).

## Scoring

- Recommended and faction builds are scored by **expected-damage time-to-kill** against a fixed
  set of representative Steel Path enemies (level 120), including armor, shields, armor strip,
  status effects, damage over time, reload and faction damage modifiers.
- A faction build minimizes the geometric mean time-to-kill over that faction's enemies.
  Recommended maximizes the geometric mean, over the factions, of how close it gets to each
  faction's own build. Because those reference times are fixed, the search simply minimizes a
  weighted geometric mean of time-to-kill; the ratios are only shown on the page.
- Time-to-kill is the time of the event that kills: delayed damage (damage over time, Blast)
  counts when it lands. Fights are capped at 10 seconds; an enemy still alive scores by the share
  of its health removed, always worse than any kill, and is shown as "not killed in 10 s".
- The calculation is deterministic. Monte Carlo simulation is used only for testing and to show
  the spread of real fights.
- Every build lists its assumptions (headshots or body shots, enemy level, falloff, maximum stacks
  for conditional effects, and similar), each with a link to its public source. The list is open
  by default, next to the results.
- A per-hit list shows each shot, damage-over-time tick and reload, so results can be compared
  with in-game damage numbers.

Damage formulas follow the WARFRAME Wiki pages "Damage/Calculation", "Calculating Bonuses" and
"Status Effect".

## Search

Builds are computed offline, not when a page is opened, with a fixed, deterministic evaluation
budget. When every legal build of a gun fits the budget, all of them are scored and the best is
labelled "optimal" within the stated search scope (for example: the two best bonus elements).
Otherwise a local search starts from the empty build and takes the best-improving move (add,
remove or swap a mod, change one choice) until none helps or the budget ends; that result is
"best found". The same data produces the same builds on any machine.

The budget is 20,000 evaluations per combat build, sized so a full `build-all` stays within
one overnight run on a 6-core laptop; the combat evaluator uses numpy. Measurements and the
workload are in `bench/README.md` (step 4.5 spike; step 8 re-measures with the real search).

## Data

| Source | Used for |
|--------|----------|
| [Warframe Public Export](https://content.warframe.com/PublicExport) (Digital Extremes) | Weapons, mods, arcanes, sentinels, item images |
| [WFCD warframe-items](https://github.com/WFCD/warframe-items) | Weapon polarities, weapon class, attack modes, falloff, arcane slots |
| [warframe-public-export-plus](https://github.com/calamity-inc/warframe-public-export-plus) | Mod and weapon compatibility tags, starter-mod flag (fields the Public Export lacks) |
| [WARFRAME Wiki](https://wiki.warframe.com) | Incarnon evolutions, faction damage modifiers, enemy stats, status rules, forced procs and burst data (weapon data modules), Archon Shards, riven ranges |

- Downloads are cached locally and never committed. Game images are never stored in the repository.
- Wiki pages and export-plus files are not fetched automatically. They are saved by hand and
  parsed locally.
- `wfb refresh` turns the downloads into validated, versioned data in `gamedata/`. `wfb check`
  reports which sources changed after a game update.
- The site never contacts these sources at runtime.
- Data, reference tables and computed builds are published together as one release; a failed
  or interrupted build keeps the previous release in service.

## Stack

- Backend: Python 3.12, FastAPI, uv. One process serves the API and the built frontend.
- Frontend: Vite, React, TypeScript, Tailwind, shadcn/ui, TanStack Query and Router, dnd-kit.
- The editor re-scores an edited build on the server (`POST /api/calc`). Builds can be shared
  by link.

## Code structure

The backend is split into layers. Every module belongs to exactly one layer, and a layer
imports only the layers listed for it. `tests/test_layers.py` checks the import rule and
rules 4 (size and names) on every CI run, so they hold while a task grows.

| Layer | Owns | May import | Files and network |
|-------|------|------------|-------------------|
| `app/domain/` | Game rules and their types: effects, damage, elements, status, fire rate, enemies, combat score, families, polarity | nothing in `app` | none (pure) |
| `app/parse/` | Turning stat text into domain effects: mods, arcanes, set bonuses, Incarnon perks | `domain` | none (pure) |
| `app/gamedata/` | The published data contract: `gamedata/` schema and the loader that reads a dataset or release | `domain` | reads only |
| `app/optimize/` | Build search and scoring over loaded data | `domain`, `gamedata` | none |
| `app/pipeline/` | Everything offline: downloads, source adapters, building and validating `gamedata/`, publishing, `check`, images, fixtures, `build-all` and releases | `domain`, `parse`, `gamedata`, `optimize` | the only layer that downloads or writes files |
| `app/api/` | HTTP routes, request and response schemas, serving the frontend | `domain`, `gamedata`, `optimize` | reads through `gamedata` |
| `app/cli.py` | The `wfb` command: argument parsing only, calls the layers above | everything | via the layers |

Rules for placing code:

1. **New code goes into the layer that owns its job.** A game formula goes in `domain`,
   never in `api` or `pipeline`. A new top-level package means changing this table and
   `tests/test_layers.py` together.
2. **Game facts that change with updates live in data, not in code.** Damage types,
   factions, enemies, weapon categories and mod rules come from `gamedata/` or `reference/`.
   Code holds only one table per source that maps that source's encoding (DE damage slots,
   DE tags, WFCD type names) to our types, and an unknown value fails the refresh.
   A domain type such as `DamageType` is the single list of its values.
3. **Source encodings stay in their adapter** (`pipeline/sources/`). `domain` and `parse`
   never know about DE or WFCD field names.
4. **One module per entity or job.** A module over 300 lines fails CI and becomes a
   subpackage of modules per entity. Names say the job: `common`, `utils`, `helpers` and
   `misc` fail CI. Shared code stays inside its layer (e.g. `pipeline/errors.py`).
5. **Tests mirror `app/`**: `tests/domain/test_damage.py` tests `app/domain/damage.py`.

`bench/` holds performance measurements outside `app/`: nothing in `app/` imports it, and its
stand-in mechanics are not game rules.

The old `app/data/` package was split into these layers in step 3d (models and loader →
`gamedata`, everything offline → `pipeline`, the command → `app/cli.py`); CI fails if it
comes back.

## Licences

Code: GNU AGPL-3.0. Data: Digital Extremes content under the Warframe Content Policy (non-commercial);
WFCD- and export-plus-derived data under MIT; WARFRAME Wiki-derived data, and the builds computed from it, under
CC BY-NC-SA 3.0. See [NOTICE](NOTICE).

This is a free, non-commercial fan project, not affiliated with Digital Extremes.
