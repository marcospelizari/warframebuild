from dataclasses import replace

import pytest

from app.gamedata.models import Arcane, Mod, Weapon
from app.gamedata.store import GameData
from app.optimize.conditions import Resolved, resolve
from app.optimize.loadout import Loadout, loadout


def _weapon(data: GameData, name: str) -> Weapon:
    return next(w for w in data.weapons if w.name == name)


def _mods(data: GameData, *names: str) -> list[Mod]:
    by_name = {m.name: m for m in data.mods.mods}
    return [by_name[n] for n in names]


def _arcane(data: GameData, name: str) -> Arcane:
    return next(a for a in data.arcanes if a.name == name)


def _lo(
    data: GameData,
    gun: str,
    mods: tuple[str, ...] = (),
    perks: tuple[str, ...] = (),
    arcane: str | None = None,
    form: str | None = None,
) -> Loadout:
    w = _weapon(data, gun)
    return loadout(
        w,
        _mods(data, *mods),
        None,
        data.incarnon_by_id.get(w.unique_name),
        perks,
        form,  # type: ignore[arg-type]
        _arcane(data, arcane) if arcane else None,
        data.set_by_id,
    )


def _with_crit(lo: Loadout, chance: float) -> Loadout:
    parts = [(replace(s, critical_chance=chance), a) for s, a in lo.parts]
    return replace(lo, parts=parts)


def _body(lo: Loadout) -> Resolved:
    return resolve(lo, on_head=False)


@pytest.mark.parametrize("chance", [0.99, 1.0, 1.5])
def test_laetum_devouring_attrition_only_below_full_crit(gamedata: GameData, chance: float) -> None:
    """R2/C1: x21 at 50% on non-crits = x11 on that branch; no non-crit from 100% crit."""
    lo = _with_crit(_lo(gamedata, "Laetum", perks=("Devouring Attrition",)), chance)
    hit = _body(lo).shot.hits[0]
    crit = 1 + chance * (hit.critical_multiplier - 1)  # linear across tiers
    plain = max(0.0, 1 - chance)
    assert hit.hit_factor() == pytest.approx(crit + plain * (11 - 1))
    assert hit.damage_multiplier == 1  # never a plain damage bonus


def test_laetum_overwhelming_attrition_needs_plain_hits(gamedata: GameData) -> None:
    """+400% for 10 s, 3 stacks, on hits that neither crit nor proc: 3 stacks while such
    hits come at least once per 10 s, a share of one stack when rarer, none from 100% crit."""
    lo = _lo(gamedata, "Laetum", perks=("Overwhelming Attrition",))
    assert _body(lo).shot.hits[0].damage_multiplier == pytest.approx(1 + 3 * 4.0)
    rare = _body(_with_crit(lo, 0.99))
    stacks = rare.held[0][1]
    assert 0 < stacks < 1
    assert rare.shot.hits[0].damage_multiplier == pytest.approx(1 + stacks * 4.0)
    for chance in (1.0, 1.5):
        assert _body(_with_crit(lo, chance)).shot.hits[0].damage_multiplier == 1


def test_kill_stacks_at_max(gamedata: GameData) -> None:
    """Primary Merciless: +30% x 12 stacks joins Serration (Primary_Merciless:38)."""
    res = _body(_lo(gamedata, "Soma Prime", ("Serration",), arcane="Primary Merciless"))
    assert res.shot.hits[0].damage_multiplier == pytest.approx(1 + 1.65 + 3.6)
    assert res.needs_kills == ("Primary Merciless",)


def test_weak_point_kill_stacks_only_on_forms_aimed_at_heads(gamedata: GameData) -> None:
    aimed = _lo(gamedata, "Rubico Prime", arcane="Primary Deadhead")
    assert resolve(aimed, on_head=True).shot.hits[0].damage_multiplier == pytest.approx(4.6)
    body = _body(_lo(gamedata, "Braton Prime", arcane="Primary Deadhead", form="normal"))
    assert body.shot.hits[0].damage_multiplier == 1
    assert body.inactive == ("Primary Deadhead",)


def test_melee_kill_buffs_never_count(gamedata: GameData) -> None:
    res = _body(_lo(gamedata, "Braton Prime", arcane="Primary Dexterity", form="normal"))
    assert res.shot.hits[0].damage_multiplier == 1
    assert res.inactive == ("Primary Dexterity",)


def test_status_buff_needs_its_own_status(gamedata: GameData) -> None:
    """Primary Frostbite stacks on Cold procs: none without Cold on the gun."""
    plain = _body(_lo(gamedata, "Braton Prime", arcane="Primary Frostbite", form="normal"))
    cold = _body(
        _lo(
            gamedata,
            "Braton Prime",
            ("Primed Cryo Rounds",),
            arcane="Primary Frostbite",
            form="normal",
        )
    )
    base = _body(_lo(gamedata, "Braton Prime", ("Primed Cryo Rounds",), form="normal"))
    assert plain.held == (("Primary Frostbite", 0.0, 40),)
    assert cold.held == (("Primary Frostbite", 40.0, 40),)
    assert cold.shot.hits[0].multishot == pytest.approx(base.shot.hits[0].multishot + 0.9)


def test_first_shot_bonus_by_its_share_of_the_magazine(gamedata: GameData) -> None:
    """Primed Chamber x2 on the first of Rubico Prime's 5 shots = x1.2 on average."""
    res = resolve(_lo(gamedata, "Rubico Prime", ("Primed Chamber",)), on_head=True)
    assert res.shot.hits[0].damage_multiplier == pytest.approx(1.2)


def test_galvanized_bonus_is_kept_for_the_timeline(gamedata: GameData) -> None:
    """+40% per status type x 2 kill stacks, applied per shot by the status types on the
    target, never as a plain damage bonus."""
    res = _body(_lo(gamedata, "Braton Prime", ("Galvanized Aptitude",), form="normal"))
    assert res.direct == pytest.approx(0.8)
    assert res.shot.hits[0].damage_multiplier == 1
    assert res.needs_kills == ("Galvanized Aptitude",)


def test_forced_proc_mods_are_handed_to_the_timeline(gamedata: GameData) -> None:
    res = _body(_lo(gamedata, "Braton Prime", ("Hunter Munitions",), form="normal"))
    assert [e.value for e in res.forced] == [0.3]


def test_head_hit_buff_on_a_body_fight_is_inactive(gamedata: GameData) -> None:
    """Rubico Prime is aimed at heads; a fight scored on the body never meets the trigger."""
    res = _body(_lo(gamedata, "Rubico Prime", ("Galvanized Scope",)))
    assert res.inactive == ("Galvanized Scope",)
    assert res.held == ()
