"""Mods the search may pick for one gun (PLAN R6, G47, G56)."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from app.domain import compatibility
from app.domain.effects import Stat, Support
from app.gamedata.models import Arcane, Effects, Mod, ModSet, Weapon
from app.gamedata.store import GameData


@dataclass(frozen=True)
class Pool:
    mods: list[Mod]  # sorted by uniqueName
    alternatives: dict[str, list[str]]  # kept uniqueName -> merged equivalents (G47)


PRIMER_ONLY = frozenset({Stat.BLAST_RADIUS})


def _primer_only(m: Mod) -> bool:
    return bool(m.effects.effects) and all(e.stat in PRIMER_ONLY for e in m.effects.effects)


def fits(weapon: Weapon, m: Mod) -> bool:
    """The mod can be equipped on the gun: same category, class and tags (G56, G82)."""
    return m.category == weapon.category and compatibility.fits(
        weapon.mod_classes,
        weapon.compatibility_tags,
        m.compat_class,
        m.compatibility_tags,
        m.incompatibility_tags,
    )


@dataclass(frozen=True)
class Unmodelled:
    kind: Literal["perk", "mod", "arcane"]
    name: str
    effects: Effects


def unmodelled(data: GameData, weapon: Weapon) -> list[Unmodelled]:
    """Entries the gun can use but the search leaves out: partial or unsupported (R6, G90 U5).
    Incarnon perks first, then mods, then arcanes, each by name."""
    incarnon = data.incarnon_by_id.get(weapon.unique_name)
    perks = [Unmodelled("perk", p.name, p.effects) for p in incarnon.perks] if incarnon else []
    mods = [Unmodelled("mod", m.name, m.effects) for m in data.mods.mods if fits(weapon, m)]
    arcanes = [
        Unmodelled("arcane", a.name, a.effects) for a in data.arcanes if arcane_fits(weapon, a)
    ]
    return [
        u
        for group in (perks, mods, arcanes)
        for u in sorted(group, key=lambda u: u.name)
        if u.effects.support != Support.FULL
    ]


def arcane_fits(weapon: Weapon, a: Arcane) -> bool:
    return a.category == weapon.category and a.weapon_type in (None, weapon.weapon_type)


def pool(weapon: Weapon, mods: Iterable[Mod], sets: Iterable[ModSet], primer: bool = False) -> Pool:
    """Fitting mods with fully modelled damage effects, their own or their set's bonus (R6;
    e.g. Vigilante Supplies). Mods with identical effects, tags and polarity and no family
    or set collapse into the lowest drain (G47). Mods that only change what the primer
    score counts (blast radius) join the primer's pool only."""
    set_damage = {
        s.unique_name
        for s in sets
        if all(b.support == Support.FULL for b in s.bonuses) and any(b.effects for b in s.bonuses)
    }
    fit = sorted(
        (
            m
            for m in mods
            if m.effects.support == Support.FULL
            and (m.effects.effects or m.mod_set in set_damage)
            and (primer or not _primer_only(m))
            and fits(weapon, m)
        ),
        key=lambda m: (m.base_drain, m.unique_name),
    )
    kept: list[Mod] = []
    alternatives: dict[str, list[str]] = {}
    first: dict[str, Mod] = {}
    for m in fit:
        if m.family is not None or m.mod_set is not None:
            kept.append(m)
            continue
        key = "|".join(
            (
                m.effects.model_dump_json(),
                ",".join(m.compatibility_tags or []),
                ",".join(m.incompatibility_tags or []),
                m.polarity,
                str(m.exilus),
            )
        )
        if key in first:
            alternatives.setdefault(first[key].unique_name, []).append(m.unique_name)
            continue
        first[key] = m
        kept.append(m)
    return Pool(sorted(kept, key=lambda m: m.unique_name), alternatives)
