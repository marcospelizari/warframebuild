"""Every precomputed build of one gun (PLAN G15, G85, G35, C6, G84).

Guns without a progenitor bonus get one variant: Max, Recommended and one build per faction.
Kuva/Tenet/Coda guns: element 1 gets all of them, element 2 Max + Recommended, and its
faction builds are element 1's with the element swapped (`what_if`, not optimized).
"""

from collections.abc import Sequence
from typing import Literal

from app.domain.effects import DamageType
from app.domain.polarity import Layout, Slot
from app.gamedata.builds import Build, ElementRow, Forma, FormaSlot, Variant, WeaponBuilds
from app.gamedata.models import Arcane, Enemy, Perk, Weapon
from app.gamedata.store import GameData
from app.optimize.combat import combat
from app.optimize.forma import forma_layout
from app.optimize.scoring import best_combat, best_max, build_loadout, combat_objective
from app.optimize.search import MAX_EVALUATIONS, Result, rounded
from app.optimize.variants import OPTIMIZED, elements, rank, what_if

Status = Literal["optimal", "best_found", "what_if"]


def weapon_builds(data: GameData, weapon: Weapon, budget: int = MAX_EVALUATIONS) -> WeaponBuilds:
    def stored(variants: list[Variant], rows: list[ElementRow]) -> WeaponBuilds:
        return WeaponBuilds(
            weapon=weapon.unique_name, slug=weapon.slug, variants=variants, elements=rows
        )

    if not elements(weapon):
        recommended = best_combat(data, weapon, budget=budget)
        return stored([_optimized(data, weapon, None, recommended, budget, [])[0]], [])

    ranked = rank(data, weapon, budget)
    scope = [f"elements: top {min(OPTIMIZED, len(ranked))} of {len(ranked)}"]
    top = ranked[0]
    first, faction_results = _optimized(data, weapon, top.element, top.recommended, budget, scope)
    variants = [first]
    if len(ranked) > 1:
        second = ranked[1].element
        swap = [f"what-if: {top.element.value} build, not optimized for {second.value}"]
        by_faction = {
            f: _swapped(data, weapon, r, second, f, swap) for f, r in faction_results.items()
        }
        variants.append(
            Variant(
                element=second,
                max=_build(
                    data, weapon, best_max(data, weapon, second, budget), second, None, scope
                ),
                recommended=_build(
                    data, weapon, ranked[1].recommended, second, data.enemies, scope
                ),
                factions=by_faction,
                denominators=_denominators(by_faction),
            )
        )
    objective = combat_objective(data)
    rows = [
        ElementRow(
            element=r.element,
            rank=i + 1,
            searched=rounded(r.recommended.score),
            what_if=rounded(what_if(data, weapon, top.recommended, r.element, objective)),
            optimized=i < OPTIMIZED,
        )
        for i, r in enumerate(ranked)
    ]
    return stored(variants, rows)


def _optimized(
    data: GameData,
    weapon: Weapon,
    bonus: DamageType | None,
    recommended: Result,
    budget: int,
    scope: list[str],
) -> tuple[Variant, dict[str, Result]]:
    """All builds of one element; also the faction search results (element 2 reuses them)."""
    results = {f: best_combat(data, weapon, f, bonus, budget) for f in _factions(data)}
    by_faction = {
        f: _build(data, weapon, r, bonus, _enemies_of(data, f), scope) for f, r in results.items()
    }
    variant = Variant(
        element=bonus,
        max=_build(data, weapon, best_max(data, weapon, bonus, budget), bonus, None, scope),
        recommended=_build(data, weapon, recommended, bonus, data.enemies, scope),
        factions=by_faction,
        denominators=_denominators(by_faction),
    )
    return variant, results


def _swapped(
    data: GameData,
    weapon: Weapon,
    r: Result,
    bonus: DamageType,
    faction: str,
    scope: list[str],
) -> Build:
    """`r` with `bonus` as the progenitor element, re-scored for `faction` (G15)."""
    score = what_if(data, weapon, r, bonus, combat_objective(data, faction))
    swapped = Result(r.mods, r.exilus, r.picks, score, r.status, 0)
    return _build(data, weapon, swapped, bonus, _enemies_of(data, faction), scope, "what_if")


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
    if enemies is not None:
        lo = build_loadout(data, weapon, r.mods, r.exilus, r.picks, bonus)
        fought = combat(lo, list(enemies), data.factions).enemies
        costs = {x.enemy.unique_name: rounded(x.outcome.cost) for x in fought}
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
        forma=_forma(forma_layout(weapon, r.mods, r.exilus)),
        costs=costs,
    )


def _forma(layout: Layout | None) -> Forma | None:
    if layout is None:
        return None

    def slot(s: Slot) -> FormaSlot:
        return FormaSlot(polarity=s.polarity, forma=s.forma, drain=s.drain)

    return Forma(
        regular=[slot(s) for s in layout.regular],
        exilus=slot(layout.exilus) if layout.exilus else None,
        forma=layout.forma,
        used=layout.used,
        capacity=layout.capacity,
    )
