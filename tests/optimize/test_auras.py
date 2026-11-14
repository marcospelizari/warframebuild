from functools import partial

import pytest

from app.gamedata.models import Mod
from app.gamedata.store import GameData
from app.optimize import auras
from app.optimize.loadout import Loadout, loadout
from app.optimize.scoring import enemies_objective, max_objective

PROJECTION = "/Lotus/Upgrades/Mods/Aura/EnemyArmorReductionAuraMod"
SHOTGUN_AMP = "/Lotus/Upgrades/Mods/Aura/PlayerShellDamageAuraMod"
RIFLE_AMP = "/Lotus/Upgrades/Mods/Aura/PlayerRifleDamageAuraMod"


def _gun(data: GameData, name: str, *mods: str) -> Loadout:
    by_name: dict[str, Mod] = {m.name: m for m in data.mods.mods}
    weapon = next(w for w in data.weapons if w.name == name)
    return loadout(weapon, [by_name[n] for n in mods])


def test_corrosive_projection_strips_armor_on_the_combat_score_only(gamedata: GameData) -> None:
    """Saved Corrosive_Projection:38-46: armor x 0.82, on top of the status strips; Max hits
    a neutral target (G80), so it gains nothing there."""
    lo = _gun(gamedata, "Soma Prime", "Serration")
    combat = partial(enemies_objective, gamedata)
    base = combat(gamedata.enemies)(lo)
    gains = {g.aura: g.score for g in auras.advice(lo, gamedata.auras, gamedata.enemies, combat)}
    assert gains[PROJECTION] > base
    flat = partial(max_objective, gamedata)
    on_max = {g.aura: g.score for g in auras.advice(lo, gamedata.auras, gamedata.enemies, flat)}
    assert on_max[PROJECTION] == pytest.approx(flat([])(lo), rel=1e-3)
    assert on_max[RIFLE_AMP] > flat([])(lo)


def test_only_auras_that_fit_the_gun_best_first(gamedata: GameData) -> None:
    """Saved Rifle_Amp:29: shotguns do not benefit from Rifle Amp."""
    lo = _gun(gamedata, "Hek", "Point Blank")
    combat = partial(enemies_objective, gamedata)
    gains = auras.advice(lo, gamedata.auras, gamedata.enemies, combat)
    names = [g.aura for g in gains]
    assert SHOTGUN_AMP in names and RIFLE_AMP not in names
    assert [g.score for g in gains] == sorted((g.score for g in gains), reverse=True)
