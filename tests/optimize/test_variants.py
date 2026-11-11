import pytest

from app.domain.effects import DamageType
from app.gamedata.models import Weapon
from app.gamedata.store import GameData
from app.optimize.scoring import combat_objective
from app.optimize.search import rounded
from app.optimize.variants import elements, rank, what_if


def _weapon(data: GameData, name: str) -> Weapon:
    return next(w for w in data.weapons if w.name == name)


def test_kuva_gun_offers_the_six_elements(gamedata: GameData) -> None:
    hind = _weapon(gamedata, "Kuva Hind")
    found = elements(hind)
    assert DamageType.IMPACT not in found  # excluded for now (checklist)
    assert len(found) == 6
    assert elements(_weapon(gamedata, "Soma Prime")) == []


def test_elements_rank_by_their_recommended_search(gamedata: GameData) -> None:
    ranked = rank(gamedata, _weapon(gamedata, "Kuva Hind"), budget=20)
    scores = [rounded(r.recommended.score) for r in ranked]
    assert scores == sorted(scores, reverse=True)
    assert {r.element for r in ranked} == set(elements(_weapon(gamedata, "Kuva Hind")))


def test_what_if_keeps_the_mods_and_swaps_the_element(gamedata: GameData) -> None:
    hind = _weapon(gamedata, "Kuva Hind")
    best = rank(gamedata, hind, budget=20)[0]
    objective = combat_objective(gamedata)
    same = what_if(gamedata, hind, best.recommended, best.element, objective)
    assert same == pytest.approx(best.recommended.score)
