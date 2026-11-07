# warframeBuild — Plan

Status: approved 2026-11-06, revised by reviews through 2026-11-07 (R, V, S, T, F, E, G). `Headshot.md` (local, git-ignored) is only the checklist for filling `reference/headshot.json`.

## Context

Warframe gun modding is complex math. Goal: a tool opened in the browser where selecting a gun returns optimized builds:

1. **Max damage** — highest burst DPS vs a neutral target.
2. **Recommended** — the build kept equipped for general play: best mean normalized time-to-kill over representative enemies of all main factions (V5/E2).
3. **Per faction** — one build per faction, using that faction's damage-type modifiers.

v1 runs locally; designed so it can later be hosted publicly (free, no monetization).
Math source: wiki `Damage/Calculation`, `Calculating_Bonuses`. Data: DE Public Export (base), WFCD (Incarnon Form attacks, enemy base stats), saved wiki pages (perks, faction modifiers, shards, rivens) — see T1/T2.

## Decisions (grilling session, 2026-11-06)

Review 2026-11-06 (R1–R8) review 2026-11-07 (V1–V17) and security review 2026-11-07 (S1–S10), terms check (T1–T4) and frontend review 2026-11-07 (F1–F9) and engine review 2026-11-07 (E1–E12) and deep review 2026-11-07 (G1–G30) revised several rows; rows marked `R#` / `V#` / `S#` / `T#` / `F#` / `E#` / `G#`. Where rows conflict, the later letter wins (G over E).

### R1 — combat score (Recommended + faction builds)
- Representative enemies (G1): ~2 per main faction, Steel Path, level 120, non-Eximus (no Overguard), in hand-made `reference/enemies.json` (health, shield, armor, base level, faction, source page) built from saved wiki pages (T2 list: Enemy Level Scaling, The Steel Path, enemy pages). WFCD `Enemy.json` not used (no Murmur/Scaldra/Techrot, no base level, pre-Update-36 resistances). Sentients use base stats; adaptation **not** modelled (V12). Assumptions stated on the page.
- Includes: armor (`DM = 1 − 0.9·√(AR/2700)`, AR after strips; verified in `Damage/Calculation` 2026-11-07; armor does not reduce shield damage), armor strip from Corrosive, Heat and strip mods/arcanes with cap and decay rules from the wiki (V9), shields (Toxin bypass), Viral health amp, faction modifiers, reload, magazine.
- Finite targets: each enemy has health, shields and armor at level 120; damage past the kill is overkill and wasted (V5). Delayed damage (DoT ticks, Blast detonation) counts at the time it lands. A 10 s cap ends the simulation; an enemy not dead by then gets TTK = cap (flagged).
- Simulation (G7, replaces E1): the official metric is a **deterministic expected-damage TTK**, identical in the optimizer, `/calc` and the display: expected damage per shot (crit tiers, procs, DoT, strips as expected values) accumulated over time until the enemy's health is gone. No randomness in ranking. Monte Carlo (fixed seed) only in tests (R7) and to precompute a spread for the final builds ("90% of fights 1.4–2.3 s").
- TTK definition (G5): time of the killing shot + one shot interval (no zero TTK). If the 10 s cap is reached, TTK is extrapolated as `cap × enemy EHP / damage dealt` and the page says "10 s cap reached".
- Scoring (E2 + G4): **faction build** minimizes the geometric mean of TTK over its own enemies. Denominator per enemy = TTK of its faction's best build on that enemy (stored with the builds for `/calc`). Ratio per enemy = `denominator / build TTK`. Per faction: geometric mean of its enemies' ratios. **Recommended** = geometric mean over the 8 factions (each faction weighs equally). An edited or Recommended build may exceed 1.0 on some factions; shown with plain words ("kills Corpus 1.3× faster than the Corpus build"). Displayed: TTK per enemy, direct vs delayed damage (V3).
- Factions with builds (E2): main 8 — Grineer, Corpus, Infested, Corrupted (Orokin), Sentient, The Murmur, Scaldra, Techrot. Sub-factions (Kuva Grineer, Corpus Amalgam, Infested Deimos, Narmer, Zariman, Anarchs) have no own build; a parent faction's enemy set may include one sub-faction enemy. Tenno excluded.
- Engagement distance: target always inside falloff start (full damage). Falloff start / end / minimum shown in build info (V10).

### Game model
| # | Gap | Decision |
|---|-----|----------|
| Q1 | Mod pool | All mods in the game (no inventory). |
| Q2/R1 | Metric | **Max** = burst DPS (avg shot damage × effective fire rate, reload ignored). **Recommended** and **faction builds** = combat score vs representative enemies (see R1 below). |
| Q3/Q13/R1 | Status | Direct + avg DoT (Slash, Heat, Toxin, Electricity, Gas) + Blast average detonation, weighted by status chance. Viral (health amp) and Corrosive (armor strip) stacks modelled in the combat score (R1); not in Max. |
| Q4/R1 | Faction | Max: none. Faction builds: combat score limited to that faction's representative enemies (`reference/enemies.json`), including faction damage-type modifiers (`gamedata/factions.json`, parsed from the saved wiki `Damage/Overview Table`), armor and shields. |
| Q5/R1/V5 | Recommended | The build Marcos keeps equipped for general play (no mod/element swaps per faction): best mean **normalized TTK score** over all representative enemies (see R1 above). |
| Q6/Q43 | Capacity + forma | Optimizer picks mods by each build's own metric (burst DPS for Max, combat score for the rest), then a forma solver fits capacity 60 (catalyst assumed) with the fewest forma, using built-in `polarities` + `exilusPolarity`, avoiding mismatches. Drain: match halves (round up), mismatch +25%, universal/Omni matches all (verify on wiki). Overframe-style slot colors: white = no forma used and no mismatch (built-in polarity matched, or no polarity), green = forma'd, red = mismatch; header 'Forma: N  Capacity x/60'. Built-in polarity slot positions not in API → solver places them; flagged. If no forma layout fits, build is flagged. |
| Q7/V11 | Weapons | Normal primary + secondary only. Excluded at refresh with a reason (count in refresh report): Kitguns, Exalted guns, Archguns, Zaws, Amps, sentinel weapons (M2 handles those separately). Melee, Warframes later. |
| V6/G3/G12 | Scored attack | `reference/main_attack.json` lists the scored attack(s) for **every Incarnon weapon** and every weapon with more than one attack (never chosen by attack name: e.g. Laetum's main damage is `Auto Radial Attack`; Dread/Paris use `Incarnon Form Charged Shot`). Launchers/AoE combine all parts of one shot (Kuva Bramma: impact + blast + cluster bombs). Alt fire ignored in v1. |
| Q8/R2 | Conditionals | Each effect tagged with its condition: `on_crit`, `on_noncrit`, `on_status`, `on_kill` stacks, `on_headshot`, timed uptime. Damage computed per branch (crit / non-crit, status / no status) and combined by probability; uptime-based buffs weighted by uptime. Only jointly achievable conditions combined (e.g. a non-crit perk never stacks with crit-only bonuses on the same hit). Kill-stack effects (Galvanized, Merciless) at max stacks, badge + required action shown ("needs kills"). Bane only in its faction build. Regression case: Laetum Devastating Attrition (+2000% on non-crit, 50%) and Overwhelming Attrition (non-crit, non-status hits). Forced procs (V8): `forced_proc` effects on the crit branch (Hunter Munitions: Slash on crit) or per hit (Internal Bleeding: Slash chance scaled by fire rate). |
| Q8b | Arcanes | One arcane slot optimized, max rank, max stacks, badge. |
| Q11/Q28a | Incarnon | Incarnon weapons: builds always use Incarnon Form stats + best perk per EVO tier, shown on page. No Normal/Incarnon toggle. |
| Q12/R5 | Headshots | Reviewed table `reference/headshot.json`, per weapon **and per form** (normal / Incarnon): `body` or `headshot`, with reason + source. `Headshot.md` (local, git-ignored) is only the checklist to fill it (its points section is ignored; G29); Claude drafts, Marcos reviews. Unlisted → body. Headshot rows apply `× (WP mult + WP bonus)` (not AoE). Assumption stated on page. No numeric score. |
| Q14 | External buffs | Out of v1 (abilities, passives, Vex Armor, Roar, Ballistic Battery, Energy Channel). |
| Q29 | Kuva/Tenet/Coda bonus element | Assume 60%; builds precomputed for **each of the 7 possible bonus elements** (G17); default view = best element; element selector switches precomputed builds and is stored in the URL. |
| Q30 | Exilus | 9th slot searched with exilus mods (`isUtility: true` + overrides list; flag incomplete, e.g. Vigilante Armaments). Utility-only result shown as "free choice". |
| Q31 | Mod sets | Damage-relevant set bonuses from `modSet`/`modSetValues` (e.g. Vigilante crit upgrade) applied by piece count. |
| Q33 | Ranks | Mods and arcanes always max rank. |
| Q35/R4/R8 | Companions | Each build recommends one companion setup (beast or sentinel/robotic). (a) Gun buffs from companion mods (Cat's Eye, Reinforced Bond, Tenacious Bond, + full review), with activation requirements shown (e.g. companion crit > 50%, shields > 1200) and uptime per R2 (Cat's Eye 50%). (b) Sentinels: robotic weapon with its own mods = separate DPS source; **Fired Up buffs the sentinel weapon only** (Heat on sentinel weapon), not the gun. Gun is re-optimized under each candidate companion setup (R4); M2 builds maximize **total** score (gun + sentinel), same scoring model for both. Page shows Gun, Sentinel, Total. Companion melee/abilities out of scope. |
| Q36 | Other sources | In v1: Archon Shards, Riven advice. Out (later): Focus school passives, Warframe abilities/passives (Q14). |
| Q37 | Archon Shards | Optimizer suggests best 5 shards per build (gun bonuses only; shards sit on the Warframe and affect all its weapons). Normal values default, Tauforged toggle (×1.5): **both variants precomputed** by `wfb build-all`; the toggle switches precomputed results. Conditional ones (Topaz per-kill crit) at max, badge. |
| Q38/R8 | Rivens | Not part of builds (random). Riven advice for the Max build: a riven **replaces an occupied slot**, then the build is re-optimized; search over combinations of up to 3 positives + 1 negative (average roll; disposition fixed 1.20×), including element combinations and negative interactions; show best combo ("god roll") with score vs no-riven, plus the top single stats as a reading aid. **Disposition retired** (wiki 2026-11-07): all weapons fixed at 1.20×, so roll ranges are the same for every weapon. Search scope (G15): rank single stats by re-evaluating the Max build with the riven in its weakest slot; then try combos of only the top ~6 positives × top ~4 harmless negatives, re-optimizing only the best 3. |

→ Per weapon: Max + Recommended + 8 faction builds = **10 builds**, each with companion setup + 5 shards (normal and Tauforged); plus riven advice for Max.

### Engineering
| # | Gap | Decision |
|---|-----|----------|
| Q9/Q18 | Architecture | Single app, layered, one process: FastAPI serves API + built frontend. |
| Q19 | Python | uv + Python 3.12, `.venv`, `uv.lock`. VS Code F5 → `.venv`. |
| Q20/F | Frontend | Vite + React + TypeScript + Tailwind + shadcn/ui (+ Recharts) + Lucide + TanStack Query + **TanStack Router** + **dnd-kit** (keyboard-accessible drag). **No Zustand**: editor state = `useReducer`; anything persistent lives in the URL. Built to static, served by FastAPI. No Next.js, no TanStack Table. Damage engine stays server-side (`/calc`) in v1; a client engine (TS twin or Rust/WASM) is a later option. |
| Q21/S3 | Repo | GitLab primary; GitLab push mirror → GitHub (read-only copy), **protected branches only** (`master` public, work branches private). Tokens stay outside the repo (`~/.config/gitlab/`). CI = GitLab CI only. |
| Q22 | License | Code AGPL-3.0 (data licenses: Q42). Credits in NOTICE + UI footer: Digital Extremes (trademark, no affiliation), WFCD, wiki.warframe.com. Check DE fan-content terms before public hosting. |
| Q23/V14/S1 | Hosting | Local v1, host-ready: no public admin endpoints; `/builds` is a static read; `/calc` (one build, editor) has a per-request time limit, global concurrency cap (queue, then 503) and per-IP rate limit. Dockerfile. Host chosen later. Hardening checklist S4–S10 is part of step 11. |
| Q24 | Tests | pytest (unit + API via TestClient), Vitest + React Testing Library. No E2E, no live-data tests in v1. |
| Q25/S3/D | CI gates | ruff (lint + format check), mypy on all of `app/` (E12), pytest; eslint (incl. no `dangerouslySetInnerHTML`), `tsc --noEmit`, vitest, `vite build`; **gitleaks** (secrets); **pip-audit** + **`npm audit --omit=dev`**; installs with `uv sync --locked` and `npm ci`. Any failure blocks merge. No coverage gate. |
| Q26 | Fixtures | Parser tests: trimmed raw JSON/wikitext for ~10 weapons in `tests/fixtures/`. Domain/optimizer/API tests: read committed `gamedata/` subset. Tests never hit network. |
| Q27 | Workflow | Branch per build step, MR into `master`. Claude writes code + commit message (subject + body + `Refs:`); Marcos runs git add/commit/push. CI green before merge. |
| Q28b/R3/S1 | Speed + precompute | Builds are **precomputed offline**, never on a request: `wfb refresh` ends with `wfb build-all` (all weapons, parallel) writing static JSON to `cache/builds/` (keyed by dataset + reference + calculator/search versions). `/builds` only reads those files. Search budget is **deterministic** (E3): a fixed number of evaluations/search nodes, ties broken by entity ID, so the same data gives the same builds on any machine; ≤ 5 s per weapon on Marcos's PC is a measured target, not the limit. Budget exhausted → `status: best_found` (vs `exhaustive`). Search (E4): cheap burst-DPS upper bound prunes candidates; the combat simulation runs only on a top-K shortlist. Riven advice (M2) precomputed the same way. Same path locally and hosted. |
| Q32/R6 | Refresh | CLI `uv run wfb refresh`: download → `cache/raw/`, parse → staging, **validate** (schema, counts, support-status diff), then swap into `gamedata/` atomically; on failure the last good dataset stays. Report coverage diff. Marcos commits the `gamedata/` diff. |
| Q34 | UI language | English only. |
| Q39/V17 | Milestones + releases | M1 core (usable), M2 add-ons (Archon Shards, companions + sentinel weapon, riven advice). **M1 done** = all M1 issues closed, CI green, R7 cases within tolerance, Marcos's browser check passed → tag `v0.1.0` on `master`, GitLab release + `CHANGELOG.md`. M2 → `v0.2.0`. Public hosting → `v1.0.0`. Version in `pyproject.toml` + `web/package.json`, shown in UI footer. |
| Q41/T1 | Data store + sources | Raw downloads in git-ignored `cache/raw/` (`de/`, `wfcd/`, `wiki/`, `SOURCES.json` with dates + hashes). **Base: DE Public Export** (official, published by DE for tools): `index_en.txt.lzma` (decode with `xz --format=lzma`, strip `\r`) → `Manifest/<name>!00_<hash>`: ExportWeapons, ExportUpgrades (mods + sets), ExportRelicArcane, ExportSentinels, ExportManifest (images). **WFCD** for what DE lacks (G2): polarities, `exilusPolarity`, weapon class/type (rifle, shotgun, sniper, bow, pistol…), `attacks[]` (incl. Incarnon), falloff, charge time, `imageName`; joined on `uniqueName` (346/346 guns, 0 stat differences). Enemies come from the wiki (G1), not WFCD. **Wiki** only for Incarnon perks, faction modifiers, Archon Shard values, riven roll ranges. Not used: warframe-public-export-plus / browse.wf (built from extracted game files; EULA "datamine" clause). Refresh parses into committed `gamedata/` (validated, atomic swap). App never fetches at runtime. |
| Q42 | Data licenses | GitHub mirror is public → first push is public. Verified 2026-11-06: WFCD `warframe-items` + `warframe-status` = MIT; wiki.warframe.com = CC BY-NC-SA 3.0. Code AGPL-3.0; wiki-derived files (`incarnon.json`, `archon_shards.json`, `factions.json`, riven factors) CC BY-NC-SA 3.0, store names + numbers only (no wiki prose); WFCD-derived data keeps MIT notice; images never committed. Project stays non-commercial (no ads/paid tier). DE Public Export data is DE content, used under the Content Policy (non-commercial). |
| T2 | Wiki access | Weird Gloop (wiki host) terms forbid automated use without prior consent; `robots.txt` disallows `api.php`. **For now Marcos saves pages by browser** (`<page>?action=raw`) into `cache/raw/wiki/`: Incarnon_Evolutions, Sandbox2 (User:Kazani/Sandbox2), Archon_Shard, Riven_Mods, Damage, Overview_Table (Damage/Overview Table), Calculation (Damage/Calculation); added by G1/G8: Enemy Level Scaling, The Steel Path, Status Effect, the faction pages The Murmur, Scaldra and Techrot, and the representative enemy pages (list in the step-8 issue). Native Incarnon perks come from a personal wiki sandbox page (Sandbox2) that may disappear; fallback = the weapons' own wiki pages. `wfb refresh` never fetches the wiki. Asking Weird Gloop for consent to automate: open. |
| T3 | DE terms | Content Policy (2020-07-16): non-commercial only; **no Warframe/DE logo** (decided: never use it; own name + neutral icon, text "for Warframe"); no charging users; text links only. EULA: we never datamine, read accounts/inventory, or touch the game client. Images served from DE's own Public Export (`ExportManifest` `textureLocation`), cached locally, never committed. Other creators' builds/art not copied. |
| T4 | Our terms | Before public hosting: site **Terms** (not affiliated with DE, calculations may be wrong, provided as-is, AGPL source link) and **Privacy notice** (IP logs + retention, no analytics, GDPR/LGPD contact). Both pages in the UI footer. |
| R6 | Unknown mechanics | Every mod/arcane/perk/buff has `support: full / partial / unsupported` (+ note). If an unsupported or partial entry could change a ranking (it has a damage-related effect and is eligible for the weapon), builds are computed **without** it and show "may be beaten by X (unsupported)"; a build is **blocked** only when an optimistic bound for X beats the result (G13). Cache keys include dataset hash, reference hash, calculator + search versions, scoring settings. |
| R7 | Combat verification | ~6 Simulacrum cases in M1, one mechanic each: DoT ticks (Slash/Heat), status chance > 100%, Bane double-dip on DoT, weak point, Incarnon AoE + falloff, one Recommended build vs armored Steel Path enemy. Each case records game version, enemy + level, distance, hit location, mods, perks, buffs; observed vs predicted within stated tolerance; stored as tests. Each case also records the `gamedata/` dataset hash (V16). |
| V4 | Mod families | `reference/mod_families.json`: mutually exclusive mods (Serration / Amalgam Serration, Primed X / X, Split Chamber / Galvanized Chamber, …). One rule (`domain/families.py`) used by the optimizer and `/calc`. |
| D | Dependencies | Exact pins: `uv.lock` and `web/package-lock.json` committed; Docker and CI images pinned by digest (`python:3.12.x-slim@sha256:…`), never `:latest`. **Renovate** in a weekly GitLab scheduled pipeline (bot token with MR rights) opens update MRs with `minimumReleaseAge` 14 days; security fixes skip the wait. Marcos merges. |
| S2–S10 | Security baseline | `/img/{name}`: name must be in the known `imageName` set, never joined into a path (S2). `/calc` + `q`: Pydantic models with `extra="forbid"`, max body size, `q` ≤ 64 chars, plain substring search, no regex from input (S4). Scraped text is untrusted: React escaping only, download size caps in refresh, bounded parser regexes (S5). Headers: CSP `default-src 'self'`, `X-Content-Type-Options: nosniff`, `frame-ancestors 'none'`, HSTS behind TLS; no CORS (same origin); `/docs` off in production (S6). Generic 500, no stack traces, debug off (S7). Docker: multi-stage, non-root, read-only FS except cache, digest-pinned, no secrets in layers (S8). Minimal access logs, IP retention limit set at hosting, no analytics (S9). Footer link to the source (AGPL requirement) (S10). |
| V15 | Refresh politeness | Applies to DE Public Export and WFCD downloads: generic User-Agent `warframeBuild/<version> (+<GitLab repo URL>)` (no personal email), ≤ 1 request/s, retry with exponential backoff on 429/5xx, `Retry-After` honored. The wiki is never fetched (T2). |
| V16 | Data version | `gamedata/meta.json`: fetch date, dataset hash, game update name (from WFCD data where available). Shown in UI footer with app version. |
| F1 | Routes + sharing | `/` (landing + search), `/w/<weapon>` (Max), `/w/<weapon>/recommended`, `/w/<weapon>/<faction>`. FastAPI serves `index.html` for unknown GET paths outside `/api` and `/img`. Edited builds encoded in `?b=` (compact, versioned, size-capped), validated by `/calc` on open; invalid → message + optimized build. No server-side storage. |
| F2 | Shared types | `openapi-typescript` generates `web/src/api/types.ts` from FastAPI's OpenAPI schema at build time (no `/docs` exposure needed); CI fails if the committed file is out of date. |
| F3/F4 | Own graphics + design step | Own SVG polarity icons, damage-type icons and mod-card frame (no DE UI/art, T3). Step 9.5: Claude makes 2–3 visual directions as viewable mockups; Marcos picks one; its tokens and icons feed step 10. |
| F5 | Page states | Landing/empty search; weapon not found; excluded weapon shown in search with its reason (V11); no precomputed builds; build `blocked` with reasons; `/calc` 429/503/validation errors; loading skeletons; top-level error boundary. |
| F6–F8 | Editor (M1) | F6: after any edit show the difference vs the optimized build (score/DPS delta). F7: picker greys out incompatible mods and family clashes (V4) with the reason, live capacity overflow, search in picker, edits debounced (~300 ms) with stale `/calc` requests cancelled. F8: "Why this mod?" = score/DPS lost when that mod is removed and the rest **re-evaluated** (no re-optimization), precomputed by `wfb build-all`. |
| F9 | Compare builds (M2) | Highlight slots that differ between Max, Recommended and faction builds. |
| E5 | Stable IDs | DE `uniqueName` is the canonical ID everywhere (API, `?b=`, caches); URLs and API paths use a slug derived from it (G19: `uniqueName` contains slashes). `gamedata/joins.json` maps DE ↔ WFCD ↔ wiki names; refresh fails on unmatched or duplicate joins. `?b=` stores short stable hashes of IDs plus `dataset_hash` (G26/G21); a removed/renamed mod opens as an empty slot with a notice. |
| E6/E7 | Runtime | `/calc` runs in a bounded `ProcessPoolExecutor` (pool size = concurrency cap; CPU work never on the event loop); **one** uvicorn worker so cap + rate limit are global. Behind a proxy: `--proxy-headers --forwarded-allow-ips=<trusted proxy>` only. |
| E8 | Calc invariant | Test: `/calc` on each optimized build returns exactly the precomputed score; `/calc` uses the stored denominators (E2). |
| E9 | Hosted builds | A CI job runs `wfb build-all` from committed `gamedata/` + `reference/` (deterministic per E3) and the image build copies its output; images are fetched into a volume at container start from DE's Public Export (never baked from the repo). |
| E10 | Cache keys | Calculator version = hash of `app/domain/` + `app/optimize/` sources, computed automatically; plus dataset hash, reference hash, scoring settings. |
| E11 | Golden builds | Committed golden builds for ~10 weapons (`tests/golden/`); any change appears as a reviewed diff. |
| E12 | One schema | Pydantic models for `gamedata/` defined once (`app/data/models.py`), used by refresh validation and by the app loader. |
| G2/G11 | Data mapping | DE `productCategory` only splits LongGuns/Pistols; class from WFCD. 134 duplicate mod names in DE (Serration ×3: beginner, intermediate, normal): beginner/intermediate variants filtered; markup like `<DT_SLASH_COLOR>` stripped; set bonuses from `ExportModSet`. Arcanes have no type/compat field: hand-made `reference/arcane_compat.json` (incl. class-only arcanes such as Shotgun Vendetta, Longbow Sharpshot). |
| G6 | Pruning bound | The pruning bound must be optimistic: burst DPS × max Viral × max faction modifier with armor fully stripped. Only then may a result be labelled `exhaustive`. |
| G8 | Status details | From the saved wiki `Status Effect` page: Puncture (+crit chance), Cold (+crit damage), Magnetic (shield damage), Slash DoT ignores armor, Slash/Toxin stacks tick separately while Heat/Electricity/Gas pool, DoT uses the crit of the applying hit, Blast stacks 1.5 s (4 on bosses), Corrosive per-stack value. |
| G9 | Crit tiers | Above 100% crit chance, "non-crit" means the lowest tier; R2 branches use tier probabilities; Vigilante set bonus upgrades the tier. |
| G10 | Fire rate | Triggers in DE: AUTO, SEMI, CHARGE, HELD, BURST, ACTIVE, DUPLEX, Auto Burst. ACTIVE, Auto Burst, burst count and odd values (Lanka `fireRate` 0) come from `reference/fire_overrides.json`; refresh fails on a gun with no usable fire rate. |
| G14 | Shards | Archon Shards (M2) are searched jointly with the gun core (they change the crit-vs-status choice), not added greedily. |
| G16 | Determinism | `PYTHONHASHSEED=0`, sorted iteration, `math.fsum`, scores rounded before comparison, seeds derived from a hash, pinned Python + numpy patch versions; byte-identical claim tested on Marcos's PC and CI. |
| G18–G21 | API contract | One `Build` schema returned by `/builds` and `/calc`: modded arsenal stats, per-slot polarity + forma, enemy list, denominators, F8 values, chart data, badges, `assumptions[]`. Paths use `{slug}`. `/api/weapons` returns slug, class, incarnon, `excluded_reason`. `/api/mods` returns all class mods with `compatible`, `reason`, family, support, and the options per EVO tier. Errors: `{code, message, field}`, `Retry-After` on 429/503. Caching: `/builds` ETag = cache key; `/img` and assets immutable; `index.html` no-cache. Responses carry `dataset_hash`; a stale tab reloads. |
| G22 | Mobile (M1) | 2-column grid, full-screen picker sheet, tap-to-swap reorder (drag on desktop only), stacked lazily loaded charts. Browser check includes a phone. |
| G23/G25 | Assumptions + clarity | One assumptions panel fed by `assumptions[]` (headshots, Steel Path 120, falloff, Kuva 60%, max stacks, catalyst, no Sentient adaptation, 10 s cap). Arsenal stats shown separately from simulated results so players can check them in-game. Recommended score explained in plain words. |
| G24 | Own builds | M1: non-Primed fallback (one click swaps Primed/rare mods to their base family variant, V4, re-scored via `/calc`). M2: "start empty" to enter your own build and compare. |
| G27 | Frontend extras | Recharts loaded lazily; fixed image sizes; table fallback for every chart; `?b=` codec round-trip tests; API mocks generated from OpenAPI. |
| G30 | Maintenance + legal | Per game update, a report lists hand-made `reference/` rows to re-check (headshot ~345 rows, companions, families, arcane compat, enemies, fire overrides). Served builds derive from wiki data, so CC BY-NC-SA applies to them too: stated in site Terms (T4) and NOTICE. |
| Q40 | Code layout | Layers kept; one module per entity inside each layer; subfolder when a module passes ~300 lines. Hand-made JSON in `reference/`. |

## Data facts (verified 2026-11-06; sources superseded by T1/G2 on 2026-11-07. Counts for refresh validation: DE ExportWeapons 841 entries, ExportUpgrades 1603; WFCD Primary+Secondary guns joined on `uniqueName`. Field names below are WFCD's.)

- `GET /mods` — (WFCD 1809; DE 1603). `name`, `polarity`, `baseDrain`, `fusionLimit`, `compatName`, `type`, `isUtility` (weapon exilus), `modSet`, `modSetValues`, `levelStats[].stats[]` = **free text** → parser.
- `GET /weapons` — (WFCD 644; DE 841 incl. melee and others). `damagePerShot` (20 types), `criticalChance`, `criticalMultiplier`, `procChance`, `fireRate`, `multishot`, `magazineSize`, `reloadTime`, `trigger`, `productCategory`, `description`, `imageName`, `attacks[]`.
- Incarnon attacks (G3): 69 weapons have Incarnon attacks in WFCD `attacks[]`, with varying names (`Incarnon Form`, `Incarnon Form Charged Shot`, `Auto Radial Attack`, …): chosen through `reference/main_attack.json`, never by name.
- Arcanes: `/arcanes` is stale. Use `GET /items` → `category == "Arcanes"`, `type in {"Primary Arcane","Secondary Arcane"}`.
- Incarnon perks: wiki MediaWiki API `action=parse&prop=wikitext`: `Incarnon_Evolutions` (45 Genesis) + `User:Kazani/Sandbox2` (8 native). `{{CustomCollapsible|<Weapon>|…}}` per weapon, rows EVO1–EVO5, values `'''+X%'''`. Melee filtered.
- Companion mods: `type == "Companion Mod"` (158), `compatName` = `COMPANION`/`ROBOTIC`/`BEAST`/`Sentinel`/specific companion (e.g. `Adarza Kavat`). Gun buffs are free text → hand-reviewed list `reference/companion_buffs.json` (source per entry).
- Robotic weapons: not in `/weapons`; `GET /items`, `type == "Companion Weapon"`, `productCategory == "SentinelWeapons"` (Deth Machine Rifle, Laser Rifle, Vulklok…), with damage/fire rate. Which mods they accept (normal class mods + sentinel-only?) → verify on wiki before coding.
- Archon Shards: API (`/items/search/archon shard`) has names/colors only, no stats. Values from wiki `Archon_Shard` (MediaWiki wikitext) → `reference/archon_shards.json` with source. Gun-relevant: Crimson +25% (+37.5%) Primary Status Chance / Secondary Crit Chance (additive with mods); Violet +30% (+45%) Primary Electricity +10% (+15%) per Crimson/Azure/Violet shard, combines with mod elements; Emerald Toxin status +30% (+45%) (additive with Elementalist); Topaz Secondary Crit +1% (+1.5%) per Heat-affected kill, max 50% (75%).
- Rivens: disposition retired, fixed 1.20× (wiki `Riven_Mods`, 2026-11-07); DE and WFCD (GitHub data) both show 1.2 (the 0.5 seen earlier came from the warframestat API cache). Riven stat base values from wiki.
- Faction modifiers: wiki `Damage/Overview Table` (Update 36+): 15 factions × damage types, `+` = ×1.5, `−` = ×0.5, per faction only (no health types). Builds only for the main 8 (E2).
- Images: DE `ExportManifest.json` → `textureLocation` (e.g. `/Lotus/Interface/Icons/…png!00_<hash>`) served from `https://content.warframe.com/PublicExport<textureLocation>`; cached in `cache/img/`.

## Damage rules (from wiki, must implement)

- Pipeline: base damage bonuses (keep weapon distribution) → elemental/physical on modded base → quantize (scale = modded base / 32, round half up, combined elements quantized as one sum) → ×multishot (expected value) → faction → crit avg `1 + C·(M−1)` → weak point if headshot weapon (not AoE).
- Bonus operations per effect: `stacking_multiply` (additive % in group, e.g. Serration + Merciless — verify arcane group on wiki), `multiply`, `add` (flat after %, e.g. Laetum/Arcane Avenger crit), `set` (Acuity multishot → base; Semi-Cannonade fire rate → base).
- Effective fire rate by `trigger`: Auto/Auto-Spool (full)/Semi/Duplex/Held = modded; Charge `1/(charge + 1/fireRate)`; Burst `count/(1/fireRate + (count−1)·delay)`.
- Status (V7, verify each on the wiki before coding): proc type chosen by damage share of the hit; status chance per pellet/projectile (multishot and shotguns); status chance > 100% = guaranteed procs + chance of one more.
- Class mechanics (V10, verify on the wiki): Held/beam ramp-up, sniper combo multiplier, falloff per attack (scoring assumes inside falloff start).
- Elements: slots left→right (top row then bottom), first mod per element combines, duplicates add to combined, innate + Kuva bonus element last.
- Physical mods only scale existing physical types.
- DoT: tick `(Σseeds+1)·C·M`, C 0.5 Heat/Elec/Toxin/Gas, 0.35 Slash; not quantized; Bane enters `(1+F)²`.
- Blast: 10 stacks, detonation `3 × ΣH`, expiry `max(1, 0.3H)`.
- AoE / Incarnon AoE: impact + radial combined (V6); target inside falloff start.

## Layout

```
warframeBuild/
  PLAN.md  CHANGELOG.md  LICENSE (AGPL-3.0)  NOTICE  README.md (credits)   (Headshot.md: local, git-ignored)
  pyproject.toml  uv.lock  Dockerfile  .gitlab-ci.yml
  app/                       (Q40: layers; one module per entity; split a module into a subfolder past ~300 lines)
    data/       sources/de_export.py (Public Export index + manifests)  sources/wfcd.py  sources/wiki_local.py (reads saved pages in cache/raw/wiki/)
                models.py (E12)  joins.py (E5)  images.py  cli.py (`wfb refresh`, `wfb build-all`, `wfb serve`)
    parse/      common.py (stat-text regex, shared)  mods.py  arcanes.py  sets.py  exilus.py  incarnon.py
                M2: shards.py  companions.py  rivens.py
    domain/     effects.py (stat/effect model + operations)  damage.py  elements.py  status.py
                fire_rate.py  conditions.py (R2 branches/uptime)  enemy.py (armor, shields, strip, Viral; R1)  combat.py (window score; R1)
                headshot.py (table lookup)  polarity.py (drain + forma solver)  support.py (R6)   (pure, no I/O)
    optimize/   core.py (gun build search)  scoring.py (neutral/faction/mean)  cache.py
                addons/ M2: shards.py  companions.py  rivens.py
    api/        routes/weapons.py  routes/calc.py  routes/mods.py  schemas.py  app.py (serves web/dist)
  gamedata/     generated by `wfb refresh`, committed: meta.json weapons.json mods.json arcanes.json incarnon.json factions.json; M2 companions.json rivens.json
  cache/        gitignored: raw/ (API + wikitext downloads), img/, builds/ (optimizer cache)
  reference/    hand-made JSON: enemies.json (G1), headshot.json (R5), arcane_compat.json (G11), fire_overrides.json (G10), damage_types.json, mod_families.json (V4), main_attack.json (V6), overrides.json; M2: archon_shards.json, companion_buffs.json, riven_factors.json
                (named `reference/` to avoid clashing with the `app/data/` layer)
  web/src/      Vite + React + TS
    components/ui/ (shadcn)  components/build/ (grid, mod card, pickers)  components/charts/
    api/ (TanStack Query hooks + generated types.ts, F2)  routes/ (TanStack Router, F1)  state/ (editor useReducer + `?b=` codec)
    assets/icons/ (own polarity + damage-type SVGs, F3)
  tests/        mirrors app/: tests/parse/test_mods.py, tests/domain/test_damage.py, … + fixtures/ + golden/ (E11)
  gamedata/joins.json (E5) · app/domain/families.py (V4)
  web/src/**/*.test.tsx   Vitest, next to components
```

## API

- `GET /api/weapons?class=primary|secondary&q=` → slug, name, class, incarnon, `excluded_reason` (G19).
- `GET /api/weapons/{slug}/builds` (G18–G21: one `Build` schema, see row) → `{headshot: {mode: body|headshot, reason, source}, incarnon: bool, attack, falloff{start,end,min}, max, recommended, factions{}}` (V1). Each build: `status: exhaustive|best_found|blocked`, `blocked_reasons[]` (unsupported entries that could change the ranking) (V2), slots[8], exilus, arcane, perks, bonus element, burst DPS (Max) or score + TTK per enemy + direct/delayed damage (Recommended, factions) (V3), drain, forma.
- `POST /api/calc` — editor recompute of one build (validated: known weapon, compatible mods, ≤8+1 slots, no duplicate families per `mod_families.json`; Pydantic `extra="forbid"`, max body size). Time limit, concurrency cap, per-IP rate limit (S1/S4).
- `GET /api/mods?weapon=<slug>` — all class mods with `compatible` + `reason`, family, support; arcanes; options per Incarnon EVO tier (G20).
- `GET /img/{name}` — locally cached images; `name` looked up in the known `imageName` set (S2).
- Any other GET outside `/api` and `/img` → `index.html` (SPA routes, F1).
- No refresh endpoint (CLI only).

## UI

```
[search weapon...........]
+------------------------------------------+
| BRATON PRIME  [img]  assumes: headshots  |
| Max | Recommended | Faction: [Grineer v] |
+------------------------------------------+
| Arcane [..*]  Exilus [..]  Bonus: Heat 60% |
| [mod1][mod2][mod3][mod4]   DPS 48,210    |
| [mod5][mod6][mod7][mod8]   Crit 38%  ... |
| Incarnon: EVO2 x | EVO3 y | EVO4 z | EVO5 |
| Drain 58/60  Forma: 2 (V,-)  "assumes headshots" |
+------------------------------------------+
| Companion: Sentinel X  [Fired Up*][Tenacious Bond*] |
| Robotic: Deth Machine Rifle [mods...]    |
| Gun 48,210 + Sentinel 3,100 = Total 51,310 |
+------------------------------------------+
| Archon Shards: [Violet][Violet][Crimson][Emerald][..]  [Tauforged o] |
+------------------------------------------+
| Riven advice (Max build): + Multishot, + Crit Dmg, + Toxin ... |
|   least harmful negative: Zoom   God roll: +62% DPS |
+------------------------------------------+
| Damage by type | Direct/DoT/Blast | Faction comparison |
+------------------------------------------+
```
- Companion, Archon Shards and Riven advice panels arrive in M2.
- Mod card: image, name, drain (after polarity), slot polarity icon + color **and** marker so color is never the only signal (V13): white = no forma / no mismatch, green + ✓ "forma" = forma'd, red + ✕ "mismatch" = mismatch; badge (conditional / set piece).
- Build header shows search status ("optimal" / "best found" / "blocked: <reason>") (V2); Recommended and faction tabs show score, TTK per enemy, direct vs delayed (V3); build info shows falloff start/end/min (V10).
- Charts (shadcn charts): damage by type, Direct/DoT/Blast stacked, faction comparison (Recommended vs faction's own build). Read `dataviz` skill first.
- Editor: click slot → picker (F7); drag reorder with dnd-kit (mouse + keyboard); change arcane/exilus/perks → `POST /api/calc` via TanStack Query (debounced, cancellable); `useReducer` state mirrored to `?b=`; delta vs optimized (F6); "Why this mod?" per slot (F8); "Reset to optimized".
- Routes, sharing and page states: F1, F5.
- Footer: credits/disclaimer (DE, WFCD, wiki), app version, dataset date + game update (V16), source code link (AGPL, S10).

## Build order (Q39; one branch + MR each)

### M1 — core (first usable version)
0. First commit (public on GitHub via mirror): `PLAN.md` (this plan; plain Markdown in the repo, not the GitLab wiki — push mirror copies only the main repo), `LICENSE` (AGPL-3.0), `NOTICE` (WFCD MIT notices; wiki CC BY-NC-SA 3.0 for wiki-derived files; Digital Extremes trademark/no-affiliation disclaimer), `README.md` (purpose, credits), `.gitignore` (`cache/`, `.venv/`, `web/node_modules/`, `web/dist/`). Marcos commits + pushes. (`Headshot.md` is git-ignored: local only.)
1. Scaffold: uv project, Vite app, FastAPI serving `web/dist`, CI with all gates green on empty tests, GitLab push mirror (set up by Marcos).
2. Data layer + `wfb refresh` + fixtures script.
3. Parser (mods, arcanes, sets, exilus) + overrides + tests.
4. Damage domain + tests (wiki examples).
4.5. **Performance spike** (E4): measure evaluations/s of the expected-value simulation on Marcos's PC; decide plain Python vs numpy (or other) before adding any dependency; set the evaluation budget (E3).
5. **Checkpoint:** Marcos supplies 3–5 arsenal builds (weapon, mods, displayed numbers); match within rounding. Plus the ~6 Simulacrum combat cases (R7) as they become testable (some after step 8).
6. Incarnon perk scrape/parse + tests.
7. Headshot table `reference/headshot.json` (per weapon + form; Claude drafts with `Headshot.md` checklist, Marcos reviews) + lookup + tests.
8. Enemies + combat score (R1), conditions (R2), support status (R6); factions + optimizer (mods, exilus, arcane, perks, Kuva element; deterministic evaluation budget (E3), optimistic pruning bound (G6), `best_found` status, versioned cache) + forma solver + tests (e.g. Laetum built-in madurai reused; unpolarized weapon needs ≥ N forma; Laetum non-crit perks regression).
9. API + validation + tests.
9.5. Visual direction (F3/F4): 2–3 mockup directions (artifact pages), Marcos picks one; own polarity, damage-type icons and mod-card frame.
10. UI on the chosen direction: routes (F1), generated types (F2), grid + tabs → charts → editor (F6–F8), page states (F5); Vitest.
11. Dockerfile + hardening (S4–S9): multi-stage, non-root, read-only FS except cache, digest-pinned base, image includes precomputed `cache/builds/`; security headers, error handling, limits, logging policy. Full security code review after this step.

### M2 — add-ons (each plugs into optimizer as an extra layer after the gun core)
12. Archon Shards (`archon_shards.json` + shard search, Tauforged toggle) + tests + UI panel.
13. Companions: review all Companion Mods → `companion_buffs.json` (gun buffs vs sentinel-weapon buffs like Fired Up); robotic weapons + mod rules (wiki); gun re-optimized per candidate setup (R4); total score; tests; arsenal checkpoint with a sentinel weapon.
14. Riven advice (wiki riven factors; riven replaces a slot + re-optimize; combo search 3+1) + tests + UI panel.
15. Compare builds (F9): highlight slots that differ between Max, Recommended and faction builds.

## Verification

- Release gate (V17): M1 done criteria in Q39/V17.

- CI gates (Q25) green on every MR.
- Domain matches wiki examples and Marcos's arsenal cases.
- Optimizer quality (R3): on small pools (≤ ~15 mods) production search equals exhaustive search, incl. cases needing element reordering and crit-vs-status competition; result status `exhaustive` or `best_found`.
- Determinism (E3): `wfb build-all` twice (and on CI) gives byte-identical output. Golden builds (E11) unchanged unless reviewed. `/calc` = precomputed score (E8).
- Speed (R3/S1): `wfb build-all` benchmark on Marcos's PC, every weapon ≤ 5 s; total run time reported.
- Security (S2–S8): tests for `/img` traversal attempts, unknown fields / oversized body / long `q` rejected, headers present, generic 500.
- Combat cases (R7) within tolerance; R2 regression (Laetum non-crit perks).
- Manual (Marcos, browser): `uv run wfb serve` → `http://127.0.0.1:8000`, open Braton Prime (Incarnon) and a Kuva weapon: perks + bonus element shown, charts render, swap/reorder changes DPS = `POST /api/calc` output.
- Frontend (F): a shared `?b=` link reopens the same edited build; `/w/<weapon>/<faction>` survives reload; keyboard-only reorder works; types check fails CI when `types.ts` is stale.

## Open risks

- Free-text parsing coverage; overrides absorb gaps; refresh reports diff.
- Hand-entered faction table, arcane stacking group, wiki sandbox page for native Incarnons — stale after game updates.
- `isUtility` exilus flag incomplete.
- Built-in polarities lack slot positions; some weapons (e.g. Braton Prime) show none in API → confirm in arsenal checkpoint.
- Archon shard values and riven factors hand-entered from wiki; stale after balance changes.
- Search space grows (mods × arcane × perks × bonus element × companion × shards): optimize gun core first, then add-ons searched jointly with gun candidates (R4/G14); keep inside the evaluation budget (E3).
- Companion buff list hand-reviewed; robotic weapon mod rules unverified until wiki check. Companion search multiplies optimizer work → must stay inside the evaluation budget (search companion setups after gun prune, few candidates).
- Quantization drift vs arsenal; checkpoint 5 catches it.
- Legal: DE Content Policy can change (check before hosting and at each release); Weird Gloop consent for automated wiki access still open (T2).
