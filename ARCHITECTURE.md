# Architecture

warframeBuild computes optimized builds for Warframe primary and secondary weapons
and shows them in the browser. This page summarizes how it works.

## What it computes

For each weapon:

- **Max damage**: highest burst DPS (average shot damage × effective fire rate) against a neutral target.
- **Recommended**: one build to keep equipped for general play, without swapping mods per faction.
- **Faction builds**: one build for each main faction (Grineer, Corpus, Infested, Corrupted,
  Sentient, The Murmur, Scaldra, Techrot).

Each build covers the 8 mod slots in slot order (element combinations depend on it), exilus,
arcane, Incarnon evolutions, the Kuva/Tenet/Coda bonus element and the forma needed to fit
the mods. Later versions add Archon Shards, companions and riven advice.

## Scoring

- Recommended and faction builds are scored by **expected-damage time-to-kill** against a fixed
  set of representative Steel Path enemies (level 120), including armor, shields, armor strip,
  status effects, damage over time, reload and faction damage modifiers.
- A faction build minimizes the geometric mean time-to-kill over that faction's enemies.
  Recommended maximizes the geometric mean, over the factions, of how close it gets to each
  faction's own build.
- The calculation is deterministic. Monte Carlo simulation is used only for testing and to show
  the spread of real fights.
- Every build lists its assumptions (headshots or body shots, enemy level, falloff, maximum stacks
  for conditional effects, and similar).

Damage formulas follow the WARFRAME Wiki pages "Damage/Calculation", "Calculating Bonuses" and
"Status Effect".

## Search

Builds are computed offline, not when a page is opened. A branch-and-bound search with a fixed,
deterministic evaluation budget finds them. A build is labelled "optimal" only when the search
proves it; otherwise it is "best found". The same data produces the same builds on any machine.

## Data

| Source | Used for |
|--------|----------|
| [Warframe Public Export](https://content.warframe.com/PublicExport) (Digital Extremes) | Weapons, mods, arcanes, sentinels, item images |
| [WFCD warframe-items](https://github.com/WFCD/warframe-items) | Weapon polarities, weapon class, attack modes, falloff |
| [WARFRAME Wiki](https://wiki.warframe.com) | Incarnon evolutions, faction damage modifiers, enemy stats, status rules, Archon Shards, riven ranges |

- Downloads are cached locally and never committed. Game images are never stored in the repository.
- Wiki pages are not fetched automatically. They are saved by hand and parsed locally.
- `wfb refresh` turns the downloads into validated, versioned data in `gamedata/`. `wfb check`
  reports which sources changed after a game update.
- The site never contacts these sources at runtime.

## Stack

- Backend: Python 3.12, FastAPI, uv. One process serves the API and the built frontend.
- Frontend: Vite, React, TypeScript, Tailwind, shadcn/ui, TanStack Query and Router, dnd-kit.
- The editor re-scores an edited build on the server (`POST /api/calc`). Builds can be shared
  by link.

## Licences

Code: GNU AGPL-3.0. Data: Digital Extremes content under the Warframe Content Policy (non-commercial);
WFCD-derived data under MIT; WARFRAME Wiki-derived data, and the builds computed from it, under
CC BY-NC-SA 3.0. See [NOTICE](NOTICE).

This is a free, non-commercial fan project, not affiliated with Digital Extremes.
