"""Step 5 checkpoint: arsenal numbers read in game (2026-11-09), normal form, perks as
installed. The arsenal shows values before quantization and rounds what it displays."""

import pytest

from app.domain.effects import DamageType as D
from app.gamedata.models import Mod
from app.gamedata.store import GameData
from app.optimize.evaluate import Evaluation, evaluate

SOMA_PERKS = ["Fortifying Bloodshed", "Kinetic Battle", "Fresh Havoc"]
LEX_PERKS = ["Hoplite Virtue", "Extended Volley", "Critical Parallel"]


def _run(data: GameData, gun: str, mods: list[str], perks: list[str]) -> Evaluation:
    weapon = next(w for w in data.weapons if w.name == gun)
    by_name = {m.name: m for m in data.mods.mods}
    chosen: list[Mod] = [by_name[n] for n in mods]
    incarnon = data.incarnon_by_id[weapon.unique_name]
    return evaluate(weapon, chosen, incarnon=incarnon, perks=perks, form="normal")


def test_soma_prime_unmodded(gamedata: GameData) -> None:
    e = _run(gamedata, "Soma Prime", [], SOMA_PERKS)
    assert e.hit.arsenal_damage[D.IMPACT] == pytest.approx(2.2, abs=0.05)


def test_soma_prime_modded(gamedata: GameData) -> None:
    mods = ["Serration", "Split Chamber", "Point Strike", "Vital Sense", "Hellfire"]
    e = _run(gamedata, "Soma Prime", mods, SOMA_PERKS)
    assert e.hit.multishot == pytest.approx(1.9)
    assert e.hit.critical_chance == pytest.approx(0.75)
    assert e.hit.critical_multiplier == pytest.approx(6.6)
    assert e.hit.arsenal_damage[D.HEAT] == pytest.approx(52.5, abs=0.05)


def test_lex_prime_modded(gamedata: GameData) -> None:
    mods = [
        "Hornet Strike",
        "Barrel Diffusion",
        "Pistol Gambit",
        "Target Cracker",
        "Convulsion",
        "Pathogen Rounds",
    ]
    e = _run(gamedata, "Lex Prime", mods, LEX_PERKS)
    assert e.hit.multishot == pytest.approx(2.2)
    assert e.hit.critical_chance == pytest.approx(0.968, abs=0.0005)
    assert e.hit.critical_multiplier == pytest.approx(3.8, abs=0.05)
    assert e.hit.arsenal_damage[D.CORROSIVE] == pytest.approx(1152, abs=0.5)
