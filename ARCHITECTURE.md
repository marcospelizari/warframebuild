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

Builds are computed offline, not when a page is opened. A branch-and-bound search with a fixed,
deterministic evaluation budget finds them. A build is labelled "optimal" only when the search
proves it within the stated search scope (for example: the two best bonus elements); otherwise it
is "best found". The same data produces the same builds on any machine.

## Data

| Source | Used for |
|--------|----------|
| [Warframe Public Export](https://content.warframe.com/PublicExport) (Digital Extremes) | Weapons, mods, arcanes, sentinels, item images |
| [WFCD warframe-items](https://github.com/WFCD/warframe-items) | Weapon polarities, weapon class, attack modes, falloff, arcane slots |
| [WARFRAME Wiki](https://wiki.warframe.com) | Incarnon evolutions, faction damage modifiers, enemy stats, status rules, Archon Shards, riven ranges |

- Downloads are cached locally and never committed. Game images are never stored in the repository.
- Wiki pages are not fetched automatically. They are saved by hand and parsed locally.
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

## Licences

Code: GNU AGPL-3.0. Data: Digital Extremes content under the Warframe Content Policy (non-commercial);
WFCD-derived data under MIT; WARFRAME Wiki-derived data, and the builds computed from it, under
CC BY-NC-SA 3.0. See [NOTICE](NOTICE).

This is a free, non-commercial fan project, not affiliated with Digital Extremes.
