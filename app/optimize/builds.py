"""Every precomputed build of one gun (PLAN G15, G85, G35, C6, G84).

Guns without a progenitor bonus get one variant: Max, Recommended and one build per faction.
Kuva/Tenet/Coda guns: element 1 gets all of them, element 2 Max + Recommended, and its
faction builds are element 1's with the element swapped (`what_if`, not optimized).
"""

from collections.abc import Generator, Sequence
from dataclasses import dataclass
from typing import Literal

from app.domain.effects import DamageType
from app.gamedata.builds import Build, ElementRow, Variant, WeaponBuilds
from app.gamedata.models import Arcane, Enemy, Mod, Perk, Weapon
from app.gamedata.store import GameData
from app.optimize.combat import combat
from app.optimize.forma import forma_layout, stored_forma
from app.optimize.scoring import (
    Objective,
    best_combat,
    best_max,
    build_loadout,
    combat_objective,
    enemies_objective,
    max_objective,
)
from app.optimize.search import MAX_EVALUATIONS, Option, Result, rounded
from app.optimize.variants import OPTIMIZED, Ranked, elements, ranked, what_if

Status = Literal["optimal", "best_found", "what_if"]


@dataclass(frozen=True)
class Search:
    """One search and its stored build. faction None: Recommended (every enemy)."""

    kind: Literal["combat", "max"]
    bonus: DamageType | None
    faction: str | None = None


@dataclass(frozen=True)
class Swap:
    """`base` (element 1's faction build) with element 2 swapped in, re-scored (G15)."""

    base: Result
    top: DamageType
    second: DamageType
    faction: str


@dataclass(frozen=True)
class WhatIf:
    """`base` (element 1's Recommended) scored with `element` as the bonus (G85 rows)."""

    base: Result
    element: DamageType


Task = Search | Swap | WhatIf


@dataclass(frozen=True)
class Found:
    result: Result | None  # Search only
    build: Build | None  # Search, Swap
    value: float | None = None  # WhatIf


Plan = Generator[list[Task], list[Found], WeaponBuilds]


def weapon_builds(data: GameData, weapon: Weapon, budget: int = MAX_EVALUATIONS) -> WeaponBuilds:
    """The plan run in this process; build-all runs the same tasks in parallel."""
    steps = plan(data, weapon)
    batch = next(steps)
    while True:
        try:
            batch = steps.send([run(data, weapon, t, budget) for t in batch])
        except StopIteration as stop:
            done: WeaponBuilds = stop.value
            return done


def plan(data: GameData, weapon: Weapon) -> Plan:
    """The gun's builds as batches of independent tasks; each batch is answered in order.
    Evaluations happen only in `run`, so where the tasks run does not change the builds."""
    factions = _factions(data)
    rolls = elements(weapon)
    if not rolls:
        rec, plain_max, *per_faction = yield [
            Search("combat", None),
            Search("max", None),
            *(Search("combat", None, f) for f in factions),
        ]
        return _stored(
            weapon, [_variant(None, plain_max, rec, dict(zip(factions, per_faction, strict=True)))]
        )

    found = yield [Search("combat", e) for e in rolls]
    recs = {e: f for e, f in zip(rolls, found, strict=True)}
    order = ranked(weapon, [Ranked(e, _result(recs[e])) for e in rolls])
    top = order[0].element
    second = order[1].element if len(order) > 1 else None
    done = yield [
        Search("max", top),
        *(Search("combat", top, f) for f in factions),
        *([Search("max", second)] if second else []),
    ]
    top_max, by = done[0], dict(zip(factions, done[1 : 1 + len(factions)], strict=True))
    base = _result(recs[top])
    swaps = [Swap(_result(by[f]), top, second, f) for f in factions] if second else []
    last = yield [*(WhatIf(base, r.element) for r in order), *swaps]
    variants = [_variant(top, top_max, recs[top], by)]
    if second:
        swapped = {f: _build_of(x) for f, x in zip(factions, last[len(order) :], strict=True)}
        variants.append(
            Variant(
                element=second,
                max=_build_of(done[-1]),
                recommended=_build_of(recs[second]),
                factions=swapped,
                denominators=_denominators(swapped),
            )
        )
    rows = [
        ElementRow(
            element=r.element,
            rank=i + 1,
            searched=rounded(r.recommended.score),
            what_if=_value(x),
            optimized=i < OPTIMIZED,
        )
        for i, (r, x) in enumerate(zip(order, last[: len(order)], strict=True))
    ]
    return _stored(weapon, variants, rows)


def run(data: GameData, weapon: Weapon, task: Task, budget: int) -> Found:
    """One task: a search plus its stored build, a swapped faction build, or a what-if."""
    scope = _scope(weapon)
    if isinstance(task, WhatIf):
        value = what_if(data, weapon, task.base, task.element, combat_objective(data))
        return Found(None, None, rounded(value))
    if isinstance(task, Swap):
        swap = [f"what-if: {task.top.value} build, not optimized for {task.second.value}"]
        score = what_if(data, weapon, task.base, task.second, combat_objective(data, task.faction))
        r = task.base
        swapped = Result(r.mods, r.exilus, r.picks, score, r.status, 0)
        enemies = _enemies_of(data, task.faction)
        return Found(None, _build(data, weapon, swapped, task.second, enemies, swap, "what_if"))
    if task.kind == "max":
        found = best_max(data, weapon, task.bonus, budget)
        return Found(found, _build(data, weapon, found, task.bonus, None, scope))
    found = best_combat(data, weapon, task.faction, task.bonus, budget)
    enemies = data.enemies if task.faction is None else _enemies_of(data, task.faction)
    return Found(found, _build(data, weapon, found, task.bonus, enemies, scope))


def _scope(weapon: Weapon) -> list[str]:
    rolls = elements(weapon)
    return [f"elements: top {min(OPTIMIZED, len(rolls))} of {len(rolls)}"] if rolls else []


def _result(f: Found) -> Result:
    assert f.result is not None
    return f.result


def _value(f: Found) -> float:
    assert f.value is not None
    return f.value


def _build_of(f: Found) -> Build:
    assert f.build is not None
    return f.build


def _variant(bonus: DamageType | None, top_max: Found, rec: Found, by: dict[str, Found]) -> Variant:
    by_faction = {f: _build_of(x) for f, x in by.items()}
    return Variant(
        element=bonus,
        max=_build_of(top_max),
        recommended=_build_of(rec),
        factions=by_faction,
        denominators=_denominators(by_faction),
    )


def _stored(
    weapon: Weapon, variants: list[Variant], rows: list[ElementRow] | None = None
) -> WeaponBuilds:
    return WeaponBuilds(
        weapon=weapon.unique_name, slug=weapon.slug, variants=variants, elements=rows or []
    )


def _factions(data: GameData) -> list[str]:
    return sorted({e.faction for e in data.enemies})


def _enemies_of(data: GameData, faction: str) -> list[Enemy]:
    return [e for e in data.enemies if e.faction == faction]


def _denominators(by_faction: dict[str, Build]) -> dict[str, float]:
    return {enemy: cost for b in by_faction.values() for enemy, cost in b.costs.items()}


def _build(
    data: GameData,
    weapon: Weapon,
    r: Result,
    bonus: DamageType | None,
    enemies: Sequence[Enemy] | None,
    scope: list[str],
    status: Status | None = None,
) -> Build:
    """`enemies`: the combat build's scored enemies; None for Max."""
    costs: dict[str, float] = {}
    objective = max_objective(data)
    if enemies is not None:
        lo = build_loadout(data, weapon, r.mods, r.exilus, r.picks, bonus)
        fought = combat(lo, list(enemies), data.factions, data.status_rules).enemies
        costs = {x.enemy.unique_name: rounded(x.outcome.cost) for x in fought}
        objective = enemies_objective(data, enemies)
    arcane = r.picks[0] if r.picks else None
    return Build(
        mods=[m.unique_name for m in r.mods],
        exilus=r.exilus.unique_name if r.exilus else None,
        arcane=arcane.unique_name if isinstance(arcane, Arcane) else None,
        perks=[p.name for p in r.picks[1:] if isinstance(p, Perk)],
        score=rounded(r.score),
        status=status or r.status,
        search_scope=scope,
        evaluations=r.evaluations,
        forma=stored_forma(forma_layout(weapon, r.mods, r.exilus)),
        costs=costs,
        without=_without(data, weapon, r, bonus, objective),
    )


def _without(
    data: GameData, weapon: Weapon, r: Result, bonus: DamageType | None, objective: Objective
) -> dict[str, float]:
    """F8: the score with each mod, the exilus and the arcane removed, the rest kept."""

    def score(mods: Sequence[Mod], exilus: Mod | None, picks: tuple[Option, ...]) -> float:
        return rounded(objective(build_loadout(data, weapon, list(mods), exilus, picks, bonus)))

    out = {
        m.unique_name: score([x for x in r.mods if x is not m], r.exilus, r.picks) for m in r.mods
    }
    if r.exilus:
        out[r.exilus.unique_name] = score(r.mods, None, r.picks)
    if r.picks and isinstance(r.picks[0], Arcane):
        out[r.picks[0].unique_name] = score(r.mods, r.exilus, (None, *r.picks[1:]))
    return out
