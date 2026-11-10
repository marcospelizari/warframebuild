"""Build objectives (PLAN G4): Max = damage per second on a neutral target (G80)."""

from app.domain.combat import neutral_dps
from app.domain.headshot import Head
from app.gamedata.models import Mod, Weapon
from app.gamedata.store import GameData
from app.optimize.candidates import pool
from app.optimize.conditions import resolve
from app.optimize.loadout import Loadout, loadout
from app.optimize.search import MAX_EVALUATIONS, Result, search
from app.optimize.timeline import Timeline


def max_score(lo: Loadout, head: Head) -> float:
    """Conditions held as mid-mission (G78); forms aimed at heads hit `head` (the reference
    head), body forms the body."""
    on_head = head if lo.mark is not None else None
    return neutral_dps(Timeline(lo, resolve(lo, on_head is not None), on_head, None).events())


def best_max(data: GameData, weapon: Weapon, budget: int = MAX_EVALUATIONS) -> Result:
    """The Max build: mods and exilus (arcane and Incarnon perks are not searched yet)."""
    ref = data.reference_head
    head = Head(ref.multiplier, critical=ref.critical)
    incarnon = data.incarnon_by_id.get(weapon.unique_name)

    def score(mods: list[Mod], exilus: Mod | None) -> float:
        lo = loadout(weapon, mods, incarnon=incarnon, sets=data.set_by_id, exilus=exilus)
        return max_score(lo, head)

    return search(pool(weapon, data.mods.mods).mods, score, budget)
