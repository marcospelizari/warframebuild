import pytest

from app.domain.effects import DamageType
from app.gamedata.models import Weapon
from app.gamedata.store import GameData
from app.optimize.scoring import best_combat, combat_objective
from app.optimize.search import rounded
from app.optimize.variants import Ranked, elements, ranked, what_if


def _weapon(data: GameData, name: str) -> Weapon:
    return next(w for w in data.weapons if w.name == name)


def _rank(data: GameData, weapon: Weapon) -> list[Ranked]:
    """One Recommended search per element, ranked (plan's first round, small budget)."""
    found = [Ranked(e, best_combat(data, weapon, bonus=e, budget=20)) for e in elements(weapon)]
    return ranked(weapon, found)


def test_kuva_gun_offers_the_six_elements(gamedata: GameData) -> None:
    hind = _weapon(gamedata, "Kuva Hind")
    found = elements(hind)
    assert DamageType.IMPACT not in found  # excluded for now (checklist)
    assert len(found) == 6
    assert elements(_weapon(gamedata, "Soma Prime")) == []


def test_elements_rank_by_their_recommended_search(gamedata: GameData) -> None:
    order = _rank(gamedata, _weapon(gamedata, "Kuva Hind"))
    scores = [rounded(r.recommended.score) for r in order]
    assert scores == sorted(scores, reverse=True)
    assert {r.element for r in order} == set(elements(_weapon(gamedata, "Kuva Hind")))


def test_what_if_keeps_the_mods_and_swaps_the_element(gamedata: GameData) -> None:
    hind = _weapon(gamedata, "Kuva Hind")
    best = _rank(gamedata, hind)[0]
    objective = combat_objective(gamedata)
    same = what_if(gamedata, hind, best.recommended, best.element, objective)
    assert same == pytest.approx(best.recommended.score)
