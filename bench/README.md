# Step 4.5 performance spike (#19)

Measures how many build evaluations per second the combat score can afford, decides plain
Python vs numpy, and sets the deterministic evaluation budget (E3) for `wfb build-all`.
Nothing here is imported by `app/`; step 8 writes the real `app/domain/combat.py` and
re-measures with the real search (C9).

```
uv run --with numpy python -m bench.run_spike            # full run, ~30 s
uv run --with numpy python -m bench.run_spike --quick    # smoke run, ~3 s
```

numpy is passed with `--with`, so it is not a project dependency yet.

## What one evaluation is

One candidate (8 mods), scored against 16 enemies, i.e. the Recommended case:

1. **Hit** (`workload.shot_model`): real `gamedata/` gun and mods through the real domain
   code (`modded_hit`, crit average, `expected_procs`, `dot_tick`, `effective_fire_rate`,
   modded magazine and reload).
2. **Timeline** (`timeline.py`): every shot until the 10 s cap with reloads; DoT ticks
   (Slash ignores armor; Toxin bypasses shields); Blast stacks with detonation at the cap
   and expiry; Corrosive and Heat armor strip, Viral and Magnetic amplification from the
   expected stacks in a sliding status-duration window.
3. **Fights** (C3 cost): shields first, spill into health, armor `0.9·√(AR/2700)`
   (capped at 90%), faction multipliers, kill time + one shot interval (the R5
   recommendation), else `10 / f` with `f` floored at 0.01; then the geometric mean.

Stand-ins with the right cost shape, not game facts: the 16 enemies (seeded random
health, shield, armor and faction multipliers, scaled to each gun so fights end between
~0.3 s and past the cap), the strip and amplification curves, the mod pool (category +
compat name, no compatibility tags) and conditional effects (all at max stacks).

Two evaluators run the same model: `evaluate_py.py` (event loop per enemy, stops at the
kill) and `evaluate_np.py` (events × enemies as matrices, cumulative sums find the shield
break and the kill). The run checks that they agree on every per-enemy cost of the first
50 candidates per gun.

## Results (2026-11-09, reference laptop)

Intel i7-9750H (6 cores, 12 threads), Python 3.12.16, numpy 2.5.4, one BLAS thread per
process. 200 candidates per gun, the same 200 for both evaluators; times are per evaluation
(best of 3).

| Weapon | shots/s | events | killed | hit µs | Python ms (16 / 2 enemies) | numpy ms (16 / 2 enemies) | max rel diff |
|---|---|---|---|---|---|---|---|
| Baza Prime | 31.7 | 931 | 11/16 | 48 | 5.88 / 1.00 | 0.980 / 0.652 | 3.2e-13 |
| Soma Prime | 28.5 | 997 | 12/16 | 53 | 5.80 / 1.23 | 1.103 / 0.695 | 3.1e-13 |
| Ignis Wraith | 15.2 | 349 | 12/16 | 41 | 1.58 / 0.44 | 0.618 / 0.433 | 1.4e-13 |
| Hek | 5.1 | 92 | 10/16 | 44 | 0.67 / 0.10 | 0.371 / 0.307 | 3.9e-14 |
| Rubico Prime | 8.6 | 114 | 9/16 | 43 | 0.88 / 0.13 | 0.383 / 0.327 | 5.1e-14 |
| Kuva Bramma | 1.3 | 73 | 12/16 | 45 | 0.35 / 0.10 | 0.385 / 0.349 | 1.2e-14 |
| Lex Prime | 4.0 | 104 | 11/16 | 49 | 0.72 / 0.11 | 0.409 / 0.331 | 4.9e-14 |

shots/s: the first candidate, fire-rate mods included. events and killed: mean over the
200 candidates. max rel diff: largest per-enemy cost difference between the two
evaluators over the first 50 candidates.

- One core, mean over the 7 guns, hit included: **Python 432/s, numpy 1,531/s**.
- numpy, process pool over all 7 guns: 1 process 1,329/s, 6 processes 4,901/s,
  **12 processes 5,981/s**.
- Without pinning BLAS to one thread, 12 processes ran slower than 6 (2,770 vs 3,911/s,
  quick run): each worker's BLAS threads oversubscribed the CPU. `bench/__init__.py`
  pins it; `build-all` must do the same.
- The numpy floor (~0.4 ms even for slow guns) is per-call overhead: ~50 small array
  operations and enemy arrays rebuilt per candidate. Caching the enemy matrices per
  enemy set and batching candidates that share a timeline are open speed-ups for step 8.

## Decisions

1. **numpy** for the combat evaluator (step 8). It is 5× faster on fast automatic guns,
   which dominate the run time, and equal on slow guns. The dependency is added
   when step 8 writes `app/domain/combat.py`, exact-pinned like every dependency (D).
   numpy is BSD-licensed, which is compatible with AGPL-3.0. Plain Python stays in the
   domain for the per-hit maths (~50 µs per candidate, not the bottleneck).
2. **Budget (E3): 20,000 evaluations per combat build** (target: `build-all` ≤ 8 h,
   one overnight run per game update).
   - 3,133 combat builds: 344 guns × (Recommended + 8 factions) + 37 Kuva/Tenet/Coda
     second-element Recommended builds.
   - Max builds use burst DPS only (~50 µs per candidate) and add little.
   - At spike speed: 3,133 × 20,000 / 5,981 ≈ 2.9 h. Conservative: every combat build
     is priced at the 16-enemy rate, but faction builds fight only their own 2 enemies.
   - With the real evaluator up to 2.5× slower (R2 branches, headshots, per-hit
     output): ≈ 7.3 h.

| Budget per build | at spike speed | at 2.5× slower |
|---|---|---|
| 10,000 | 1.5 h | 3.6 h |
| **20,000** | **2.9 h** | **7.3 h** |
| 50,000 | 7.3 h | 18 h |

3. **Search space:** the mod pool has 60–68 candidates per gun; C(65, 8) = 5.05e9
   sets before element order. Any useful budget needs branch-and-bound pruning (G34):
   20,000 evaluations cover 4e-6 of the sets.
4. **Open for step 8 (C9):** how often branch-and-bound finishes within 20,000
   evaluations (`optimal` vs `best_found`). That needs the real bound and search, so
   step 8 re-measures and revisits the budget if most builds end as `best_found`.
