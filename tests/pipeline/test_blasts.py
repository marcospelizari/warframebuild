from typing import Any

import pytest

from app.gamedata.models import Weapon
from app.gamedata.store import GameData
from app.pipeline.build import blasts
from app.pipeline.errors import RefreshError

TODAY = "2026-11-13"


def _gun(data: GameData, name: str) -> Weapon:
    return next(w for w in data.weapons if w.name == name)


def _row(gun: Weapon, chosen: list[str], **extra: Any) -> dict[str, Any]:
    row = {"name": gun.name, "blasts": chosen, "reason": "r", "source": "s", "verified": TODAY}
    return {**row, **extra}


def test_blasts_come_from_the_wiki_modules_parent_links(gamedata: GameData) -> None:
    """Ogris: the rocket's explosion is a child of the rocket; Tenet Tetra's grenade blast
    belongs to its alt-fire grenade, not the normal attack."""
    guns = [_gun(gamedata, n) for n in ("Ogris", "Tenet Tetra", "Soma Prime")]
    out, missing = blasts.apply({}, guns, gamedata.incarnon, set())
    assert [w.blasts for w in out] == [["Rocket Explosion"], [], []]
    assert missing == []


def test_a_row_replaces_the_derived_blasts_and_may_name_the_primer_shot(
    gamedata: GameData,
) -> None:
    epitaph = _gun(gamedata, "Epitaph Prime")
    shot = ["Uncharged Direct Hit", "Uncharged AoE"]
    table = {"weapons": {epitaph.unique_name: _row(epitaph, ["Uncharged AoE"], shot=shot)}}
    [out], _ = blasts.apply(table, [epitaph], gamedata.incarnon, set())
    assert (out.blasts, out.primer_shot) == (["Uncharged AoE"], shot)


def test_a_gun_missing_from_the_modules_is_listed(gamedata: GameData) -> None:
    ogris = _gun(gamedata, "Ogris")
    unlisted = ogris.model_copy(
        update={"attacks": [a.model_copy(update={"forced_procs": None}) for a in ogris.attacks]}
    )
    out, missing = blasts.apply({}, [unlisted], gamedata.incarnon, set())
    assert out[0].blasts == [] and missing == ["Ogris"]


def test_an_aoe_attack_with_no_parent_link_is_listed_until_a_row_names_it(
    gamedata: GameData,
) -> None:
    """Trumna: the module links Auto AoE to no attack, so whose blast it is stays open."""
    ogris = _gun(gamedata, "Ogris")
    unlinked = ogris.model_copy(
        update={"attacks": [a.model_copy(update={"parent": None}) for a in ogris.attacks]}
    )
    out, missing = blasts.apply({}, [unlinked], gamedata.incarnon, set())
    assert out[0].blasts == [] and missing == ["Ogris"]
    table = {"weapons": {ogris.unique_name: _row(ogris, ["Rocket Explosion"])}}
    out, missing = blasts.apply(table, [unlinked], gamedata.incarnon, set())
    assert out[0].blasts == ["Rocket Explosion"] and missing == []


@pytest.mark.parametrize(
    ("chosen", "extra", "error"),
    [
        (["Rocket Impact"], {}, "`blasts` must name"),
        (["Rocket Explosion"], {"verified": None}, "verified"),
        (["Rocket Explosion"], {"radius": 3}, "keys must be"),
        (["Rocket Explosion"], {"shot": ["Rocket Impact"]}, "`shot` must list"),
        (["Rocket Explosion"], {"shot": ["Nope", "Rocket Explosion"]}, "`shot` must list"),
    ],
)
def test_bad_rows_stop_the_refresh(
    gamedata: GameData, chosen: list[str], extra: dict[str, Any], error: str
) -> None:
    ogris = _gun(gamedata, "Ogris")
    table = {"weapons": {ogris.unique_name: _row(ogris, chosen, **extra)}}
    with pytest.raises(RefreshError, match=error):
        blasts.apply(table, [ogris], gamedata.incarnon, set())


def test_rows_of_unknown_guns_stop_the_refresh_but_excluded_guns_keep_theirs(
    gamedata: GameData,
) -> None:
    with pytest.raises(RefreshError, match="unknown guns"):
        blasts.apply({"weapons": {"/Lotus/Gone": {}}}, [], gamedata.incarnon, set())
    blasts.apply({"weapons": {"/Lotus/New": {}}}, [], gamedata.incarnon, {"/Lotus/New"})
