import copy
import json
from typing import Any

import pytest

from app.gamedata.store import GameData
from app.pipeline.build import auras
from app.pipeline.errors import RefreshError
from app.pipeline.refresh import Paths

TITLES = {"Rifle_Amp": "Rifle_Amp", "Corrosive_Projection": "Corrosive_Projection"}
AMP = "/Lotus/Upgrades/Mods/Aura/PlayerRifleDamageAuraMod"
DE = [{"uniqueName": AMP, "levelStats": [{"stats": ["Squad receives +27% Rifle Damage"]}]}]


def _row(paths: Paths) -> dict[str, Any]:
    table = json.loads((paths.reference / auras.FILE).read_text())
    return {"auras": {AMP: table["auras"][AMP]}}


def test_every_row_matches_the_committed_game_text(gamedata: GameData) -> None:
    """The committed gamedata/ keeps all seven gun auras (none left out by a text change)."""
    names = {a.name for a in gamedata.auras.auras}
    assert {"Rifle Amp", "Corrosive Projection", "Worthy Comradery"} <= names
    assert len(names) == 7
    types = {w.weapon_type for w in gamedata.weapons}
    for a in gamedata.auras.auras:
        assert set(a.weapon_types or []) <= types, a.name  # no misspelt type


def test_a_changed_game_text_leaves_the_aura_out_and_lists_it(paths: Paths) -> None:
    built, changed = auras.build(_row(paths), DE, {"Rifle"}, TITLES)
    assert [a.name for a in built.auras] == ["Rifle Amp"] and changed == []
    moved = [{**DE[0], "levelStats": [{"stats": ["Squad receives +30% Rifle Damage"]}]}]
    built, changed = auras.build(_row(paths), moved, {"Rifle"}, TITLES)
    assert built.auras == [] and changed == ["Rifle Amp"]
    assert auras.build(_row(paths), [], {"Rifle"}, TITLES)[1] == ["Rifle Amp"]  # gone


@pytest.mark.parametrize(
    ("change", "error"),
    [
        (lambda r: r.update(weapon_types=["Spear"]), "no gun has a type"),
        (lambda r: r.pop("verified"), "keys"),
        (lambda r: r.update(source=["Nope:1"]), "saved page"),
        (lambda r: r.update(armor_kept=0.8), "exactly one"),
    ],
)
def test_bad_rows_stop_the_refresh(paths: Paths, change: Any, error: str) -> None:
    table = copy.deepcopy(_row(paths))
    change(table["auras"][AMP])
    with pytest.raises(RefreshError, match=error):
        auras.build(table, DE, {"Rifle", "Bow", "Sniper", "Launcher"}, TITLES)
