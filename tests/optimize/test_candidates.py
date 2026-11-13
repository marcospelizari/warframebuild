from app.domain.effects import Support
from app.gamedata.models import Weapon
from app.gamedata.store import GameData
from app.optimize.candidates import fits, pool, unmodelled


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


def test_unmodelled_lists_what_the_gun_can_use_but_the_search_leaves_out(
    gamedata: GameData,
) -> None:
    """U5: every fitting partial/unsupported perk, mod and arcane; never a full or unfit one."""
    weapon = _weapon(gamedata, "Soma Prime")
    found = unmodelled(gamedata, weapon)
    names = {u.name for u in found}
    assert "Lasting Purity" not in names  # Vulkar augment: does not fit
    assert "Serration" not in names  # fully modelled
    assert all(u.effects.support != Support.FULL for u in found)
    mods = [u for u in found if u.kind == "mod"]
    assert mods and all(fits(weapon, m) for m in gamedata.mods.mods if m.name in names)
    kinds = [u.kind for u in found]
    assert kinds == sorted(kinds, key=["perk", "mod", "arcane"].index)
