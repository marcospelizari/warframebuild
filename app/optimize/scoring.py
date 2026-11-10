"""Build objectives (PLAN G4) and their searches: Max = damage per second on a neutral target
(G80); Recommended = combat score over every faction's representative enemies, faction
builds over one faction's (R1). Faction damage mods only in their own faction's build."""

from collections.abc import Callable, Sequence

from app.domain.combat import neutral_dps
from app.domain.effects import Faction, Stat, Support
from app.domain.headshot import Head
from app.gamedata.models import Arcane, Mod, Perk, Weapon
from app.gamedata.store import GameData
from app.optimize.candidates import pool
from app.optimize.combat import combat
from app.optimize.conditions import resolve
from app.optimize.loadout import Loadout, loadout
from app.optimize.search import MAX_EVALUATIONS, Option, Result, search
from app.optimize.timeline import Timeline


def max_score(lo: Loadout, head: Head) -> float:
    """Conditions held as mid-mission (G78); forms aimed at heads hit `head` (the reference
    head), body forms the body."""
    on_head = head if lo.mark is not None else None
    return neutral_dps(Timeline(lo, resolve(lo, on_head is not None), on_head, None).events())


def best_max(data: GameData, weapon: Weapon, budget: int = MAX_EVALUATIONS) -> Result:
    ref = data.reference_head
    head = Head(ref.multiplier, critical=ref.critical)
    mods = [m for m in pool(weapon, data.mods.mods).mods if not _bane(m)]  # no faction: no use
    return _search(data, weapon, mods, lambda lo: max_score(lo, head), budget)


def best_combat(
    data: GameData, weapon: Weapon, faction: str | None = None, budget: int = MAX_EVALUATIONS
) -> Result:
    """`faction`: that faction's build; None: Recommended (every faction, no faction mods).
    The score is 1 / combat cost (higher is better)."""
    enemies = [e for e in data.enemies if faction is None or e.faction == faction]
    if not enemies:
        raise ValueError(f"no representative enemies for {faction!r}")
    mods = combat_mods(data, weapon, faction)

    def score(lo: Loadout) -> float:
        return 1 / combat(lo, enemies, data.factions).score

    return _search(data, weapon, mods, score, budget)


def combat_mods(data: GameData, weapon: Weapon, faction: str | None) -> list[Mod]:
    """The pool without faction damage mods, except those of `faction`'s enemies."""
    banes = {e.bane for e in data.enemies if e.faction == faction} if faction else set()
    return [m for m in pool(weapon, data.mods.mods).mods if _allowed(m, banes)]


def choices(data: GameData, weapon: Weapon) -> list[list[Option]]:
    """Choice slots: the arcane, then one per Incarnon EVO tier; only fully modelled entries
    with effects (R6); None = empty or a perk without damage effects."""
    arcanes: list[Option] = [None]
    arcanes += [
        a
        for a in sorted(data.arcanes, key=lambda a: a.unique_name)
        if a.category == weapon.category
        and a.weapon_type in (None, weapon.weapon_type)
        and _modelled(a.effects.support, a.effects.effects)
    ]
    out = [arcanes]
    incarnon = data.incarnon_by_id.get(weapon.unique_name)
    all_perks = incarnon.perks if incarnon else []
    for tier in sorted({p.tier for p in all_perks}):
        perks = [
            p
            for p in all_perks
            if p.tier == tier and _modelled(p.effects.support, p.effects.effects)
        ]
        out.append([None, *perks])
    return out


def _search(
    data: GameData,
    weapon: Weapon,
    mods: Sequence[Mod],
    objective: Callable[[Loadout], float],
    budget: int,
) -> Result:
    incarnon = data.incarnon_by_id.get(weapon.unique_name)

    def score(regular: list[Mod], exilus: Mod | None, picks: tuple[Option, ...]) -> float:
        arcane = picks[0]
        perks = [p.name for p in picks[1:] if isinstance(p, Perk)]
        lo = loadout(
            weapon,
            regular,
            incarnon=incarnon,
            perks=perks,
            arcane=arcane if isinstance(arcane, Arcane) else None,
            sets=data.set_by_id,
            exilus=exilus,
        )
        return objective(lo)

    return search(mods, score, budget, choices(data, weapon))


def _bane(m: Mod) -> bool:
    return any(e.stat == Stat.FACTION_DAMAGE for e in m.effects.effects)


def _allowed(m: Mod, banes: set[Faction | None]) -> bool:
    return not _bane(m) or all(
        e.faction in banes for e in m.effects.effects if e.stat == Stat.FACTION_DAMAGE
    )


def _modelled(support: Support, effects: Sequence[object]) -> bool:
    return support == Support.FULL and bool(effects)
