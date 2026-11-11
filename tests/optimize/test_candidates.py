from app.gamedata.models import Weapon
from app.gamedata.store import GameData
from app.optimize.candidates import pool


def _weapon(data: GameData, name: str) -> Weapon:
    return next(w for w in data.weapons if w.name == name)


def test_pool_holds_fitting_fully_modelled_mods(gamedata: GameData) -> None:
    names = {
        m.name
        for m in pool(_weapon(gamedata, "Soma Prime"), gamedata.mods.mods, gamedata.mods.sets).mods
    }
    assert {"Serration", "Galvanized Aptitude", "Tainted Mag"} <= names
    assert "Shell Shock" not in names  # shotgun mod
    assert "Hornet Strike" not in names  # pistol mod
    assert "Lasting Purity" not in names  # partial support (R6), and a Vulkar augment


def test_pool_keeps_mods_whose_damage_is_their_set_bonus(gamedata: GameData) -> None:
    """Vigilante Supplies: no damage of its own, but a Vigilante set piece (exilus)."""
    names = {
        m.name
        for m in pool(_weapon(gamedata, "Soma Prime"), gamedata.mods.mods, gamedata.mods.sets).mods
    }
    assert "Vigilante Supplies" in names
    assert "Aero Periphery" not in names  # Hawk set bonus is not modelled


def test_equivalent_mods_collapse_to_the_lowest_drain(gamedata: GameData) -> None:
    """G47: same effects, tags and polarity, no family or set: one candidate."""
    caliber = next(m for m in gamedata.mods.mods if m.name == "Heavy Caliber")
    twin = caliber.model_copy(
        update={"unique_name": "/Test/HeavyCaliberTwin", "base_drain": caliber.base_drain + 2}
    )
    p = pool(_weapon(gamedata, "Soma Prime"), [*gamedata.mods.mods, twin], gamedata.mods.sets)
    assert twin.unique_name not in {m.unique_name for m in p.mods}
    assert p.alternatives[caliber.unique_name] == [twin.unique_name]
