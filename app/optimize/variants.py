"""Kuva/Tenet/Coda bonus element variants (PLAN Q29/G15, G85).

Every elemental bonus the gun can roll gets a full Recommended search; they rank by that
score (ties in the gun's listed order). The top 2 are optimized; the others are what-if rows:
the best build's mods with the element swapped, re-evaluated, not optimized. Impact is not
offered yet (checklist: progenitor Impact bonus).
"""

from dataclasses import dataclass

from app.domain.effects import DamageType
from app.domain.elements import ELEMENTS
from app.gamedata.models import Weapon
from app.gamedata.store import GameData
from app.optimize.scoring import Objective, build_loadout
from app.optimize.search import Result, rounded

OPTIMIZED = 2


@dataclass(frozen=True)
class Ranked:
    element: DamageType
    recommended: Result  # full Recommended search with this element


def elements(weapon: Weapon) -> list[DamageType]:
    """Elemental bonuses the gun can roll, in its listed order (Impact left out)."""
    rolls = weapon.bonus_element.elements if weapon.bonus_element else []
    return [e for e in rolls if e in ELEMENTS]


def ranked(weapon: Weapon, found: list[Ranked]) -> list[Ranked]:
    """Best Recommended score first; ties keep the gun's listed element order."""
    order = {e: i for i, e in enumerate(elements(weapon))}
    return sorted(found, key=lambda r: (-rounded(r.recommended.score), order[r.element]))


def what_if(
    data: GameData, weapon: Weapon, build: Result, element: DamageType, objective: Objective
) -> float:
    """`build`'s mods, exilus and picks with `element` as the bonus, scored by `objective`."""
    lo = build_loadout(data, weapon, build.mods, build.exilus, build.picks, element)
    return objective(lo)
