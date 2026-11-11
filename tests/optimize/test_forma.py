from app.gamedata.models import Mod, Weapon
from app.gamedata.store import GameData
from app.optimize.forma import fits, forma_layout, piece


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


def test_fits_agrees_with_the_solver(gamedata: GameData) -> None:
    """Cedo Prime Max of release 3261ef2f087d71be: 8 mods + Vigilante Supplies had no layout."""
    cedo = _weapon(gamedata, "Cedo Prime")
    mods = _mods(
        gamedata,
        "Primed Blunderbuss",
        "Primed Ravage",
        "Galvanized Hell",
        "Shotgun Barrage",
        "Galvanized Savvy",
        "Primed Chilling Grasp",
        "Contagious Spread",
        "Primed Charged Shell",
    )
    (supplies,) = _mods(gamedata, "Vigilante Supplies")
    assert forma_layout(cedo, mods, supplies) is None and not fits(cedo, mods, supplies)
    assert forma_layout(cedo, mods, None) is not None and fits(cedo, mods, None)
