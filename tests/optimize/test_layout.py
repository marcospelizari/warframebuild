from app.gamedata.models import Mod
from app.gamedata.store import GameData
from app.optimize.layout import element_of, orders


def _mods(data: GameData, *names: str) -> list[Mod]:
    by_name = {m.name: m for m in data.mods.mods}
    return [by_name[n] for n in names]


def test_four_elements_pair_three_ways(gamedata: GameData) -> None:
    mods = _mods(gamedata, "Hellfire", "Cryo Rounds", "Stormbringer", "Infected Clip", "Serration")
    found = orders(mods)
    assert len(found) == 3
    assert all(o[0].name == "Serration" for o in found)


def test_three_elements_leave_one_alone_three_ways(gamedata: GameData) -> None:
    assert len(orders(_mods(gamedata, "Hellfire", "Cryo Rounds", "Stormbringer"))) == 3


def test_two_elements_or_none_have_one_order(gamedata: GameData) -> None:
    assert len(orders(_mods(gamedata, "Hellfire", "Cryo Rounds"))) == 1
    assert len(orders(_mods(gamedata, "Serration"))) == 1
    assert orders([]) == [[]]


def test_element_of(gamedata: GameData) -> None:
    hellfire, serration = _mods(gamedata, "Hellfire", "Serration")
    assert element_of(hellfire) == "heat"
    assert element_of(serration) is None
