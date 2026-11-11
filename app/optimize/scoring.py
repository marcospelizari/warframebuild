"""Build objectives (PLAN G4) and their searches: Max = damage per second on a neutral target
(G80); Recommended = combat score over every faction's representative enemies, faction
builds over one faction's (R1). Faction damage mods only in their own faction's build."""

from collections.abc import Callable, Sequence

from app.domain.combat import neutral_dps
from app.domain.effects import DamageType, Faction, Stat, Support
from app.domain.headshot import Head
from app.gamedata.models import Arcane, Mod, Perk, Weapon
from app.gamedata.store import GameData
from app.optimize import forma
from app.optimize.candidates import arcane_fits, pool
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


Objective = Callable[[Loadout], float]


def max_objective(data: GameData) -> Objective:
    ref = data.reference_head
    head = Head(ref.multiplier, critical=ref.critical)
    return lambda lo: max_score(lo, head)


def combat_objective(data: GameData, faction: str | None = None) -> Objective:
    """1 / combat cost (higher is better) over every representative enemy, or `faction`'s."""
    enemies = [e for e in data.enemies if faction is None or e.faction == faction]
    if not enemies:
        raise ValueError(f"no representative enemies for {faction!r}")
    return lambda lo: 1 / combat(lo, enemies, data.factions).score


def best_max(
    data: GameData,
    weapon: Weapon,
    bonus: DamageType | None = None,
    budget: int = MAX_EVALUATIONS,
) -> Result:
    """`bonus`: the progenitor bonus element (Kuva/Tenet/Coda, G15)."""
    mods = [
        m for m in pool(weapon, data.mods.mods, data.mods.sets).mods if not _bane(m)
    ]  # no faction: no use
    return _search(data, weapon, mods, max_objective(data), bonus, budget)


def best_combat(
    data: GameData,
    weapon: Weapon,
    faction: str | None = None,
    bonus: DamageType | None = None,
    budget: int = MAX_EVALUATIONS,
) -> Result:
    """`faction`: that faction's build; None: Recommended (every faction, no faction mods)."""
    objective = combat_objective(data, faction)
    return _search(data, weapon, combat_mods(data, weapon, faction), objective, bonus, budget)


def combat_mods(data: GameData, weapon: Weapon, faction: str | None) -> list[Mod]:
    """The pool without faction damage mods, except those of `faction`'s enemies."""
    banes = {e.bane for e in data.enemies if e.faction == faction} if faction else set()
    return [m for m in pool(weapon, data.mods.mods, data.mods.sets).mods if _allowed(m, banes)]


def choices(data: GameData, weapon: Weapon) -> list[list[Option]]:
    """Choice slots: the arcane, then one per Incarnon EVO tier; only fully modelled entries
    with effects (R6); None = empty or a perk without damage effects."""
    arcanes: list[Option] = [None]
    arcanes += [
        a
        for a in sorted(data.arcanes, key=lambda a: a.unique_name)
        if arcane_fits(weapon, a) and _modelled(a.effects.support, a.effects.effects)
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


def build_loadout(
    data: GameData,
    weapon: Weapon,
    mods: list[Mod],
    exilus: Mod | None,
    picks: Sequence[Option],
    bonus: DamageType | None = None,
) -> Loadout:
    """The loadout of a searched build: choice slots = arcane, then one perk per EVO tier."""
    arcane = picks[0] if picks else None
    return loadout(
        weapon,
        mods,
        bonus,
        data.incarnon_by_id.get(weapon.unique_name),
        [p.name for p in picks[1:] if isinstance(p, Perk)],
        arcane=arcane if isinstance(arcane, Arcane) else None,
        sets=data.set_by_id,
        exilus=exilus,
    )


def _search(
    data: GameData,
    weapon: Weapon,
    mods: Sequence[Mod],
    objective: Objective,
    bonus: DamageType | None,
    budget: int,
) -> Result:
    def score(regular: list[Mod], exilus: Mod | None, picks: tuple[Option, ...]) -> float:
        if not forma.fits(weapon, regular, exilus):
            return 0.0  # over capacity with any forma (Q6): never chosen
        return objective(build_loadout(data, weapon, regular, exilus, picks, bonus))

    return search(mods, score, budget, choices(data, weapon))


def _bane(m: Mod) -> bool:
    return any(e.stat == Stat.FACTION_DAMAGE for e in m.effects.effects)


def _allowed(m: Mod, banes: set[Faction | None]) -> bool:
    return not _bane(m) or all(
        e.faction in banes for e in m.effects.effects if e.stat == Stat.FACTION_DAMAGE
    )


def _modelled(support: Support, effects: Sequence[object]) -> bool:
    return support == Support.FULL and bool(effects)
