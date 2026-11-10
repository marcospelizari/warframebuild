"""Mods the search may pick for one gun (PLAN R6, G47, G56)."""

from collections.abc import Iterable
from dataclasses import dataclass

from app.domain import compatibility
from app.domain.effects import Support
from app.gamedata.models import Mod, Weapon


@dataclass(frozen=True)
class Pool:
    mods: list[Mod]  # sorted by uniqueName
    alternatives: dict[str, list[str]]  # kept uniqueName -> merged equivalents (G47)


def pool(weapon: Weapon, mods: Iterable[Mod]) -> Pool:
    """Fitting mods with fully modelled damage effects (R6). Mods with identical effects,
    tags and polarity and no family or set collapse into the lowest drain (G47)."""
    fit = sorted(
        (
            m
            for m in mods
            if m.category == weapon.category
            and m.effects.support == Support.FULL
            and m.effects.effects
            and compatibility.fits(
                weapon.mod_classes,
                weapon.compatibility_tags,
                m.compat_class,
                m.compatibility_tags,
                m.incompatibility_tags,
            )
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
