from app.gamedata.models import Mod, Weapon
from app.gamedata.store import GameData
from app.optimize.forma import forma_layout, piece


def _weapon(data: GameData, name: str) -> Weapon:
    return next(w for w in data.weapons if w.name == name)


def _mods(data: GameData, *names: str) -> list[Mod]:
    by_name = {m.name: m for m in data.mods.mods}
    return [by_name[n] for n in names]


def test_serration_drain(gamedata: GameData) -> None:
    (serration,) = _mods(gamedata, "Serration")
    assert piece(serration).drain == 14


def test_full_rifle_build_needs_forma(gamedata: GameData) -> None:
    names = (
        "Serration",
        "Split Chamber",
        "Point Strike",
        "Vital Sense",
        "Hellfire",
        "Cryo Rounds",
        "Infected Clip",
        "Stormbringer",
    )
    soma = _weapon(gamedata, "Soma Prime")
    layout = forma_layout(soma, _mods(gamedata, *names), None)
    assert layout is not None
    assert layout.capacity == 60 and layout.used <= 60
    assert layout.forma > 0
    assert len(layout.regular) == 8


def test_kuva_guns_have_capacity_80(gamedata: GameData) -> None:
    layout = forma_layout(_weapon(gamedata, "Kuva Hind"), [], None)
    assert layout is not None and layout.capacity == 80 and layout.forma == 0
