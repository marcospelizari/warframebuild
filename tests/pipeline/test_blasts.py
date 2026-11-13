from typing import Any

import pytest

from app.gamedata.models import Weapon
from app.gamedata.store import GameData
from app.pipeline.build import blasts
from app.pipeline.errors import RefreshError


def _gun(data: GameData, name: str) -> Weapon:
    return next(w for w in data.weapons if w.name == name)


def _row(gun: Weapon, blast: str | None, **extra: Any) -> dict[str, Any]:
    row = {"name": gun.name, "blast": blast, "source": "WFCD attack list", "verified": "2026-11-13"}
    return {**row, **extra}


def test_a_row_names_the_primary_fire_blast(gamedata: GameData) -> None:
    torid, lenz, soma = (_gun(gamedata, n) for n in ("Torid", "Lenz", "Soma Prime"))
    table = {"weapons": {torid.unique_name: _row(torid, "Poison Cloud")}}
    out, missing = blasts.apply(table, [torid, lenz, soma], gamedata.incarnon, set())
    assert [w.blast for w in out] == ["Poison Cloud", None, None]
    assert missing == ["Lenz"]  # an AoE attack and no row; Soma has none


def test_null_blast_and_rows_of_excluded_guns_are_kept(gamedata: GameData) -> None:
    torid = _gun(gamedata, "Torid")
    table = {"weapons": {torid.unique_name: _row(torid, None), "/Lotus/New": {}}}
    out, missing = blasts.apply(table, [torid], gamedata.incarnon, {"/Lotus/New"})
    assert out[0].blast is None and missing == []


@pytest.mark.parametrize(
    ("blast", "extra", "error"),
    [
        ("Grenade Impact", {}, "not one of its normal-form AoE attacks"),
        ("Incarnon Form", {}, "not one of its normal-form AoE attacks"),
        ("Poison Cloud", {"verified": None}, "verified"),
        ("Poison Cloud", {"radius": 3}, "keys must be"),
    ],
)
def test_bad_rows_stop_the_refresh(
    gamedata: GameData, blast: str, extra: dict[str, Any], error: str
) -> None:
    torid = _gun(gamedata, "Torid")
    table = {"weapons": {torid.unique_name: _row(torid, blast, **extra)}}
    with pytest.raises(RefreshError, match=error):
        blasts.apply(table, [torid], gamedata.incarnon, set())


def test_a_row_for_an_unknown_gun_stops_the_refresh(gamedata: GameData) -> None:
    with pytest.raises(RefreshError, match="unknown guns"):
        blasts.apply({"weapons": {"/Lotus/Gone": {}}}, [], gamedata.incarnon, set())


def test_a_row_may_name_the_primer_shot(gamedata: GameData) -> None:
    torid = _gun(gamedata, "Torid")
    shot = ["Grenade Impact", "Poison Cloud"]
    table = {"weapons": {torid.unique_name: _row(torid, "Poison Cloud", shot=shot)}}
    [out], _ = blasts.apply(table, [torid], gamedata.incarnon, set())
    assert out.primer_shot == shot
    for bad in (["Grenade Impact"], ["Incarnon Form", "Poison Cloud"], ["Nope"]):
        table = {"weapons": {torid.unique_name: _row(torid, "Poison Cloud", shot=bad)}}
        with pytest.raises(RefreshError, match="`shot`"):
            blasts.apply(table, [torid], gamedata.incarnon, set())
