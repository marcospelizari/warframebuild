# warframeBuild — Plan

Status: approved 2026-11-06. Headshot Score spec: `Headshot.md`.

## Context

Warframe gun modding is complex math. Goal: a tool opened in the browser where selecting a gun returns optimized builds:

1. **Max damage** — highest burst DPS vs a neutral target.
2. **Recommended** — best all-rounder: highest burst DPS averaged across all factions.
3. **Per faction** — one build per faction, using that faction's damage-type modifiers.

v1 runs locally; designed so it can later be hosted publicly (free, no monetization).
Math source: wiki `Damage/Calculation`, `Calculating_Bonuses`. Data: `api.warframestat.us` + wiki (Incarnon perks).

## Decisions (grilling session, 2026-11-06)

Review 2026-11-06 (R1–R8) revised several rows; rows marked `R#`.

### R1 — combat score (Recommended + faction builds)
- Representative enemies: ~2 per faction (e.g. armored Grineer heavy, shielded Corpus unit, Infested…), Steel Path, fixed level 120, documented in `reference/enemies.json` with source (wiki enemy pages, CC BY-NC-SA).
- Includes: armor (damage-reduction formula verified on the wiki before coding: `Damage/Calculation` and `Calculating_Bonuses` give different forms), armor strip (Corrosive stacks), shields (Toxin bypass), Viral health amp, faction modifiers, reload, magazine.
- Fixed combat window (default 10 s): damage dealt in the window; delayed damage (DoT ticks, Blast detonation) counted only inside it. Direct vs delayed shown separately.
- Score = damage in window (time-to-kill as secondary display).

### Game model
| # | Gap | Decision |
|---|-----|----------|
| Q1 | Mod pool | All mods in the game (no inventory). |
| Q2/R1 | Metric | **Max** = burst DPS (avg shot damage × effective fire rate, reload ignored). **Recommended** and **faction builds** = combat score vs representative enemies (see R1 below). |
| Q3/Q13/R1 | Status | Direct + avg DoT (Slash, Heat, Toxin, Electricity, Gas) + Blast average detonation, weighted by status chance. Viral (health amp) and Corrosive (armor strip) stacks modelled in the combat score (R1); not in Max. |
| Q4/R1 | Faction | Max: none. Faction builds: combat score limited to that faction's representative enemies (`reference/enemies.json`), including faction damage-type modifiers (`reference/factions.json`), armor and shields. |
| Q5/R1 | Recommended | The build Marcos keeps equipped for general play (no mod/element swaps per faction): best mean combat score over all representative enemies. |
| Q6/Q43 | Capacity + forma | Optimizer picks mods for DPS, then a forma solver fits capacity 60 (catalyst assumed) with the fewest forma, using built-in `polarities` + `exilusPolarity`, avoiding mismatches. Drain: match halves (round up), mismatch +25%, universal/Omni matches all (verify on wiki). Overframe-style slot colors: white = no forma used and no mismatch (built-in polarity matched, or no polarity), green = forma'd, red = mismatch; header 'Forma: N  Capacity x/60'. Built-in polarity slot positions not in API → solver places them; flagged. If no forma layout fits, build is flagged. |
| Q7 | Weapons | Primary + secondary. Melee, Warframes later. |
| Q8/R2 | Conditionals | Each effect tagged with its condition: `on_crit`, `on_noncrit`, `on_status`, `on_kill` stacks, `on_headshot`, timed uptime. Damage computed per branch (crit / non-crit, status / no status) and combined by probability; uptime-based buffs weighted by uptime. Only jointly achievable conditions combined (e.g. a non-crit perk never stacks with crit-only bonuses on the same hit). Kill-stack effects (Galvanized, Merciless) at max stacks, badge + required action shown ("needs kills"). Bane only in its faction build. Regression case: Laetum Devastating Attrition (+2000% on non-crit, 50%) and Overwhelming Attrition (non-crit, non-status hits). |
| Q8b | Arcanes | One arcane slot optimized, max rank, max stacks, badge. |
| Q11/Q28a | Incarnon | Incarnon weapons: builds always use Incarnon Form stats + best perk per EVO tier, shown on page. No Normal/Incarnon toggle. |
| Q12/R5 | Headshots | Reviewed table `reference/headshot.json`, per weapon **and per form** (normal / Incarnon): `body` or `headshot`, with reason + source. `Headshot.md` criteria are the checklist to fill it; Claude drafts, Marcos reviews. Unlisted → body. Headshot rows apply `× (WP mult + WP bonus)` (not AoE). Assumption stated on page. No numeric score. |
| Q14 | External buffs | Out of v1 (abilities, passives, Vex Armor, Roar, Ballistic Battery, Energy Channel). |
| Q29 | Kuva/Tenet/Coda bonus element | Assume 60%, optimizer picks the element, page shows it. |
| Q30 | Exilus | 9th slot searched with exilus mods (`isUtility: true` + overrides list; flag incomplete, e.g. Vigilante Armaments). Utility-only result shown as "free choice". |
| Q31 | Mod sets | Damage-relevant set bonuses from `modSet`/`modSetValues` (e.g. Vigilante crit upgrade) applied by piece count. |
| Q33 | Ranks | Mods and arcanes always max rank. |
| Q35/R4/R8 | Companions | Each build recommends one companion setup (beast or sentinel/robotic). (a) Gun buffs from companion mods (Cat's Eye, Reinforced Bond, Tenacious Bond, + full review), with activation requirements shown (e.g. companion crit > 50%, shields > 1200) and uptime per R2 (Cat's Eye 50%). (b) Sentinels: robotic weapon with its own mods = separate DPS source; **Fired Up buffs the sentinel weapon only** (Heat on sentinel weapon), not the gun. Gun is re-optimized under each candidate companion setup (R4); M2 builds maximize **total** score (gun + sentinel), same scoring model for both. Page shows Gun, Sentinel, Total. Companion melee/abilities out of scope. |
| Q36 | Other sources | In v1: Archon Shards, Riven advice. Out (later): Focus school passives, Warframe abilities/passives (Q14). |
| Q37 | Archon Shards | Optimizer suggests best 5 shards per build (gun bonuses only; shards sit on the Warframe and affect all its weapons). Normal values default, Tauforged toggle (×1.5). Conditional ones (Topaz per-kill crit) at max, badge. |
| Q38/R8 | Rivens | Not part of builds (random). Riven advice for the Max build: a riven **replaces an occupied slot**, then the build is re-optimized; search over combinations of up to 3 positives + 1 negative (average roll, weapon disposition), including element combinations and negative interactions; show best combo ("god roll") with score vs no-riven, plus the top single stats as a reading aid. |

→ Per weapon: Max + Recommended + ~8 factions ≈ **10 builds**, each with companion setup + 5 shards; plus riven advice for Max.

### Engineering
| # | Gap | Decision |
|---|-----|----------|
| Q9/Q18 | Architecture | Single app, layered, one process: FastAPI serves API + built frontend. |
| Q19 | Python | uv + Python 3.12, `.venv`, `uv.lock`. VS Code F5 → `.venv`. |
| Q20 | Frontend | Vite + React + TypeScript + Tailwind + shadcn/ui (+ shadcn charts / Recharts) + Lucide + TanStack Query + Zustand. Built to static, served by FastAPI. No Next.js, no TanStack Table (no table view). |
| Q21 | Repo | GitLab primary; GitLab push mirror → GitHub (read-only copy). CI = GitLab CI only. |
| Q22 | License | Code AGPL-3.0 (data licenses: Q42). Credits in NOTICE + UI footer: Digital Extremes (trademark, no affiliation), WFCD, wiki.warframe.com. Check DE fan-content terms before public hosting. |
| Q23 | Hosting | Local v1, host-ready: input validation, no public admin endpoints, bounded optimizer CPU, Dockerfile. Host chosen later. |
| Q24 | Tests | pytest (unit + API via TestClient), Vitest + React Testing Library. No E2E, no live-data tests in v1. |
| Q25 | CI gates | ruff (lint + format check), mypy (domain/parse), pytest; eslint, `tsc --noEmit`, vitest, `vite build`. Any failure blocks merge. No coverage gate. |
| Q26 | Fixtures | Parser tests: trimmed raw JSON/wikitext for ~10 weapons in `tests/fixtures/`. Domain/optimizer/API tests: read committed `gamedata/` subset. Tests never hit network. |
| Q27 | Workflow | Branch per build step, MR into `master`. Claude writes code + commit message (subject + body + `Refs:`); Marcos runs git add/commit/push. CI green before merge. |
| Q28b/R3 | Speed | Cold cache, Marcos's PC: all builds of one weapon ≤ 5 s. Timeout returns best found with a visible `status: best_found` (vs `exhaustive` when proven optimal). Disk cache after. |
| Q32/R6 | Refresh | CLI `uv run wfb refresh`: download → `cache/raw/`, parse → staging, **validate** (schema, counts, support-status diff), then swap into `gamedata/` atomically; on failure the last good dataset stays. Report coverage diff. Marcos commits the `gamedata/` diff. |
| Q34 | UI language | English only. |
| Q39 | Milestones | M1 core (usable), M2 add-ons (Archon Shards, companions + sentinel weapon, riven advice). |
| Q41 | Data store | `wfb refresh` fetches raw API + wiki into gitignored `cache/raw/`, parses, writes normalized JSON committed in `gamedata/` (weapons, mods, arcanes, incarnon; M2 companions, rivens; `meta.json` with sources + fetch date). App reads only `gamedata/` + `reference/`; never fetches at runtime. Refresh diff = what the game update changed. Images cached in gitignored `cache/img/` (DE art, not committed). |
| Q42 | Data licenses | GitHub mirror is public → first push is public. Verified 2026-11-06: WFCD `warframe-items` + `warframe-status` = MIT; wiki.warframe.com = CC BY-NC-SA 3.0. Code AGPL-3.0; wiki-derived files (`incarnon.json`, `archon_shards.json`, `factions.json`, riven factors) CC BY-NC-SA 3.0, store names + numbers only (no wiki prose); WFCD-derived data keeps MIT notice; images never committed. Project stays non-commercial (no ads/paid tier). |
| R6 | Unknown mechanics | Every mod/arcane/perk/buff has `support: full / partial / unsupported` (+ note). If an unsupported or partial entry could change a ranking (it has a damage-related effect and is eligible for the weapon), that optimization is **blocked** for affected builds with an explanation, not silently ranked. Cache keys include dataset hash, reference hash, calculator + search versions, scoring settings. |
| R7 | Combat verification | ~6 Simulacrum cases in M1, one mechanic each: DoT ticks (Slash/Heat), status chance > 100%, Bane double-dip on DoT, weak point, Incarnon AoE + falloff, one Recommended build vs armored Steel Path enemy. Each case records game version, enemy + level, distance, hit location, mods, perks, buffs; observed vs predicted within stated tolerance; stored as tests. |
| Q40 | Code layout | Layers kept; one module per entity inside each layer; subfolder when a module passes ~300 lines. Hand-made JSON in `reference/`. |

## Data facts (verified 2026-11-06)

- `GET /mods` — 1809. `name`, `polarity`, `baseDrain`, `fusionLimit`, `compatName`, `type`, `isUtility` (weapon exilus), `modSet`, `modSetValues`, `levelStats[].stats[]` = **free text** → parser.
- `GET /weapons` — 644. `damagePerShot` (20 types), `criticalChance`, `criticalMultiplier`, `procChance`, `fireRate`, `multishot`, `magazineSize`, `reloadTime`, `trigger`, `productCategory`, `description`, `imageName`, `attacks[]`.
- Incarnon Form: `attacks[]` entries `"Incarnon Form"` / `"Incarnon Form AoE"` (`speed`, `crit_chance` %, `crit_mult`, `status_chance` %, `damage{}`, `falloff`). 69 weapons incl. variants.
- Arcanes: `/arcanes` is stale. Use `GET /items` → `category == "Arcanes"`, `type in {"Primary Arcane","Secondary Arcane"}`.
- Incarnon perks: wiki MediaWiki API `action=parse&prop=wikitext`: `Incarnon_Evolutions` (45 Genesis) + `User:Kazani/Sandbox2` (8 native). `{{CustomCollapsible|<Weapon>|…}}` per weapon, rows EVO1–EVO5, values `'''+X%'''`. Melee filtered.
- Companion mods: `type == "Companion Mod"` (158), `compatName` = `COMPANION`/`ROBOTIC`/`BEAST`/`Sentinel`/specific companion (e.g. `Adarza Kavat`). Gun buffs are free text → hand-reviewed list `reference/companion_buffs.json` (source per entry).
- Robotic weapons: not in `/weapons`; `GET /items`, `type == "Companion Weapon"`, `productCategory == "SentinelWeapons"` (Deth Machine Rifle, Laser Rifle, Vulklok…), with damage/fire rate. Which mods they accept (normal class mods + sentinel-only?) → verify on wiki before coding.
- Archon Shards: API (`/items/search/archon shard`) has names/colors only, no stats. Values from wiki `Archon_Shard` (MediaWiki wikitext) → `reference/archon_shards.json` with source. Gun-relevant: Crimson +25% (+37.5%) Primary Status Chance / Secondary Crit Chance (additive with mods); Violet +30% (+45%) Primary Electricity +10% (+15%) per Crimson/Azure/Violet shard, combines with mod elements; Emerald Toxin status +30% (+45%) (additive with Elementalist); Topaz Secondary Crit +1% (+1.5%) per Heat-affected kill, max 50% (75%).
- Rivens: `weapons[].omegaAttenuation` = disposition multiplier (Braton Prime 1.25, Laetum 0.5). Riven mods (`type` contains `Riven`) have `upgradeEntries[].upgradeValues[].value` = base per stat. Rank/combination factors (2 vs 3 positives, negative) from wiki `Riven_Mods` → verify before coding.
- Images: `https://cdn.warframestat.us/img/<imageName>` (301 → `raw.githubusercontent.com/wfcd/warframe-items/...`). Cached locally on refresh.

## Damage rules (from wiki, must implement)

- Pipeline: base damage bonuses (keep weapon distribution) → elemental/physical on modded base → quantize (scale = modded base / 32, round half up, combined elements quantized as one sum) → ×multishot (expected value) → faction → crit avg `1 + C·(M−1)` → weak point if headshot weapon (not AoE).
- Bonus operations per effect: `stacking_multiply` (additive % in group, e.g. Serration + Merciless — verify arcane group on wiki), `multiply`, `add` (flat after %, e.g. Laetum/Arcane Avenger crit), `set` (Acuity multishot → base; Semi-Cannonade fire rate → base).
- Effective fire rate by `trigger`: Auto/Auto-Spool (full)/Semi/Duplex/Held = modded; Charge `1/(charge + 1/fireRate)`; Burst `count/(1/fireRate + (count−1)·delay)`.
- Elements: slots left→right (top row then bottom), first mod per element combines, duplicates add to combined, innate + Kuva bonus element last.
- Physical mods only scale existing physical types.
- DoT: tick `(Σseeds+1)·C·M`, C 0.5 Heat/Elec/Toxin/Gas, 0.35 Slash; not quantized; Bane enters `(1+F)²`.
- Blast: 10 stacks, detonation `3 × ΣH`, expiry `max(1, 0.3H)`.
- Incarnon AoE: apply `falloff`.

## Layout

```
warframeBuild/
  PLAN.md  Headshot.md  LICENSE (AGPL-3.0)  README.md (credits)
  pyproject.toml  uv.lock  Dockerfile  .gitlab-ci.yml
  app/                       (Q40: layers; one module per entity; split a module into a subfolder past ~300 lines)
    data/       sources/warframestat.py, sources/wiki.py, cache.py, images.py, cli.py (`wfb refresh`, `wfb serve`)
    parse/      common.py (stat-text regex, shared)  mods.py  arcanes.py  sets.py  exilus.py  incarnon.py
                M2: shards.py  companions.py  rivens.py
    domain/     effects.py (stat/effect model + operations)  damage.py  elements.py  status.py
                fire_rate.py  conditions.py (R2 branches/uptime)  enemy.py (armor, shields, strip, Viral; R1)  combat.py (window score; R1)
                headshot.py (table lookup)  polarity.py (drain + forma solver)  support.py (R6)   (pure, no I/O)
    optimize/   core.py (gun build search)  scoring.py (neutral/faction/mean)  cache.py
                addons/ M2: shards.py  companions.py  rivens.py
    api/        routes/weapons.py  routes/calc.py  routes/mods.py  schemas.py  app.py (serves web/dist)
  gamedata/     generated by `wfb refresh`, committed: meta.json weapons.json mods.json arcanes.json incarnon.json; M2 companions.json rivens.json
  cache/        gitignored: raw/ (API + wikitext downloads), img/, builds/ (optimizer cache)
  reference/    hand-made JSON: factions.json, enemies.json (R1), headshot.json (R5), damage_types.json, overrides.json; M2: archon_shards.json, companion_buffs.json, riven_factors.json
                (named `reference/` to avoid clashing with the `app/data/` layer)
  web/src/      Vite + React + TS
    components/ui/ (shadcn)  components/build/ (grid, mod card, pickers)  components/charts/
    api/ (TanStack Query hooks)  store/ (Zustand)  pages/
  tests/        mirrors app/: tests/parse/test_mods.py, tests/domain/test_damage.py, … + fixtures/
  web/src/**/*.test.tsx   Vitest, next to components
```

## API

- `GET /api/weapons?class=primary|secondary&q=`
- `GET /api/weapons/{name}/builds` → `{headshot: {score, tier}, incarnon: bool, max, recommended, factions{}}`; each build: slots[8], exilus, arcane, perks, bonus element, DPS breakdown, drain, forma.
- `POST /api/calc` — editor recompute (validated: known weapon, compatible mods, ≤8+1 slots, no duplicate families).
- `GET /api/mods?weapon=` — compatible mods/arcanes/perks for pickers.
- `GET /img/{name}` — locally cached images.
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
- Mod card: image, name, drain (after polarity), slot polarity icon + color (white = no forma, no mismatch / green = forma'd / red = mismatch), badge (conditional / set piece).
- Charts (shadcn charts): damage by type, Direct/DoT/Blast stacked, faction comparison (Recommended vs faction's own build). Read `dataviz` skill first.
- Editor: click slot → picker; drag reorder; change arcane/exilus/perks → `POST /api/calc` via TanStack Query; Zustand store; "Reset to optimized". Not saved.
- Footer: credits/disclaimer (DE, WFCD, wiki).

## Build order (Q39; one branch + MR each)

### M1 — core (first usable version)
0. First commit (public on GitHub via mirror): `PLAN.md` (this plan; plain Markdown in the repo, not the GitLab wiki — push mirror copies only the main repo), `LICENSE` (AGPL-3.0), `NOTICE` (WFCD MIT notices; wiki CC BY-NC-SA 3.0 for wiki-derived files; Digital Extremes trademark/no-affiliation disclaimer), `README.md` (purpose, credits), `.gitignore` (`cache/`, `.venv/`, `web/node_modules/`, `web/dist/`). Marcos commits + pushes. (`Headshot.md` is git-ignored: local only.)
1. Scaffold: uv project, Vite app, FastAPI serving `web/dist`, CI with all gates green on empty tests, GitLab push mirror (set up by Marcos).
2. Data layer + `wfb refresh` + fixtures script.
3. Parser (mods, arcanes, sets, exilus) + overrides + tests.
4. Damage domain + tests (wiki examples).
5. **Checkpoint:** Marcos supplies 3–5 arsenal builds (weapon, mods, displayed numbers); match within rounding. Plus the ~6 Simulacrum combat cases (R7) as they become testable (some after step 8).
6. Incarnon perk scrape/parse + tests.
7. Headshot table `reference/headshot.json` (per weapon + form; Claude drafts with `Headshot.md` checklist, Marcos reviews) + lookup + tests.
8. Enemies + combat score (R1), conditions (R2), support status (R6); factions + optimizer (mods, exilus, arcane, perks, Kuva element; time budget, `best_found` status, versioned cache) + forma solver + tests (e.g. Laetum built-in madurai reused; unpolarized weapon needs ≥ N forma; Laetum non-crit perks regression).
9. API + validation + tests.
10. UI: grid + tabs → charts → editor; Vitest.
11. Dockerfile (host-ready; not deployed).

### M2 — add-ons (each plugs into optimizer as an extra layer after the gun core)
12. Archon Shards (`archon_shards.json` + shard search, Tauforged toggle) + tests + UI panel.
13. Companions: review all Companion Mods → `companion_buffs.json` (gun buffs vs sentinel-weapon buffs like Fired Up); robotic weapons + mod rules (wiki); gun re-optimized per candidate setup (R4); total score; tests; arsenal checkpoint with a sentinel weapon.
14. Riven advice (wiki riven factors; riven replaces a slot + re-optimize; combo search 3+1) + tests + UI panel.

## Verification

- CI gates (Q25) green on every MR.
- Domain matches wiki examples and Marcos's arsenal cases.
- Optimizer quality (R3): on small pools (≤ ~15 mods) production search equals exhaustive search, incl. cases needing element reordering and crit-vs-status competition; result status `exhaustive` or `best_found`.
- Speed (R3): cold-cache benchmark on Marcos's PC, all builds of a weapon ≤ 5 s; reported in CI log (non-blocking) and checked locally.
- Combat cases (R7) within tolerance; R2 regression (Laetum non-crit perks).
- Manual (Marcos, browser): `uv run wfb serve` → `http://127.0.0.1:8000`, open Braton Prime (Incarnon) and a Kuva weapon: perks + bonus element shown, charts render, swap/reorder changes DPS = `POST /api/calc` output.

## Open risks

- Free-text parsing coverage; overrides absorb gaps; refresh reports diff.
- Hand-entered faction table, arcane stacking group, wiki sandbox page for native Incarnons — stale after game updates.
- `isUtility` exilus flag incomplete.
- Built-in polarities lack slot positions; some weapons (e.g. Braton Prime) show none in API → confirm in arsenal checkpoint.
- Archon shard values and riven factors hand-entered from wiki; stale after balance changes.
- Search space grows (mods × arcane × perks × bonus element × companion × shards): optimize gun core first, then add-ons greedily per build; keep inside time budget.
- Companion buff list hand-reviewed; robotic weapon mod rules unverified until wiki check. Companion search multiplies optimizer work → must stay inside time budget (search companion setups after gun prune, few candidates).
- Quantization drift vs arsenal; checkpoint 5 catches it.
- Legal check before public hosting: Digital Extremes fan-content terms (WFCD + wiki licenses verified, see Q42).
