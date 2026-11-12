import json
import shutil
from pathlib import Path

from app.gamedata.builds import Build, Variant, WeaponBuilds
from app.gamedata.changes import Change
from app.gamedata.store import load
from app.gamedata.updates import read_updates
from app.pipeline import release
from app.pipeline.refresh import Paths, run

HORNET = "/Lotus/Upgrades/Mods/Pistol/WeaponDamageAmountMod"
SERRATION = "/Lotus/Upgrades/Mods/Rifle/WeaponDamageAmountMod"
LEX = "/Lotus/Weapons/Tenno/Pistols/PrimeLex/PrimeLex"


def _build(mods: list[str], kill: float) -> Build:
    return Build(
        mods=mods,
        exilus=None,
        arcane=None,
        perks=[],
        score=1 / kill,
        status="best_found",
        search_scope=[],
        evaluations=1,
        forma=None,
        costs={},
    )


def _gun(mods: list[str], kill: float, grineer: float | None = None) -> WeaponBuilds:
    b = _build(mods, kill)
    factions = {"Grineer": _build(mods, grineer or kill)}
    variant = Variant(element=None, max=b, recommended=b, factions=factions, denominators={})
    return WeaponBuilds(weapon=LEX, slug="lex-prime", variants=[variant], elements=[])


def _publish(releases: Path, gamedata: Path, calc: str, gun: WeaponBuilds, day: str) -> Path:
    reference = releases.parent / "reference"
    reference.mkdir(exist_ok=True)
    key = release.Key(load(gamedata).meta.dataset_hash, "ref", calc, 1)
    return release.publish(releases, key, gamedata, reference, [gun], {gun.slug}, today=day)


def _hornet_ph(paths: Paths) -> None:
    path = paths.raw / "de/ExportUpgrades_en.json"
    data = json.loads(path.read_text())
    hornet = next(e for e in data["ExportUpgrades"] if e["uniqueName"] == HORNET)
    hornet["levelStats"][-1]["stats"] = ["+240% Damage", "[PH] +1 max Puncture stacks"]
    path.write_text(json.dumps(data))


def test_game_update_lists_text_builds_and_summary(paths: Paths, tmp_path: Path) -> None:
    run(paths, offline=True, fetch_images=False)
    first = tmp_path / "first-gamedata"
    shutil.copytree(paths.gamedata, first)
    _hornet_ph(paths)
    run(paths, offline=True, fetch_images=False)
    # The game files changed: the source record differs (an offline run keeps the same files,
    # so mark one source as re-downloaded).
    meta_path = first / "meta.json"
    meta = json.loads(meta_path.read_text())
    meta["sources"][0]["sha256_16"] = "0" * 16
    meta_path.write_text(json.dumps(meta))

    releases = tmp_path / "releases"
    _publish(releases, first, "calc", _gun([SERRATION], 2.0), "2026-11-12")
    folder = _publish(releases, paths.gamedata, "calc", _gun([HORNET], 1.5), "2026-11-13")

    (update,) = read_updates(folder).updates
    assert (update.kind, update.date) == ("game", "2026-11-13")
    assert [c.name for c in update.entries] == ["Hornet Strike"]
    (gun,) = update.guns
    assert (gun.name, gun.change, gun.stats_changed) == ("Lex Prime", Change.CHANGED, False)
    recommended = gun.builds[0]
    assert recommended.build == "recommended"
    assert (recommended.removed, recommended.added) == (["Serration"], ["Hornet Strike"])
    assert (recommended.kill_before, recommended.kill_after) == (2.0, 1.5)
    assert update.summary == [
        "1 mod changed: Hornet Strike.",
        "Now only partly calculated: Hornet Strike.",
        "1 gun with changed builds: 1 kill faster.",
    ]


def test_calculator_update_and_the_one_percent_rule(tmp_path: Path) -> None:
    gamedata = Path(__file__).resolve().parents[2] / "gamedata"
    releases = tmp_path / "releases"
    _publish(releases, gamedata, "v1", _gun([HORNET], 2.0), "2026-11-12")
    same = _publish(releases, gamedata, "v2", _gun([HORNET], 2.019), "2026-11-13")
    assert read_updates(same).updates == []  # under 1%: nothing listed, no entry

    moved = _publish(releases, gamedata, "v3", _gun([HORNET], 2.019, grineer=2.5), "2026-11-14")
    (update,) = read_updates(moved).updates
    assert update.kind == "calculator"
    assert update.summary == [
        "Builds changed by our calculation, not by the game.",
        "1 gun with changed builds.",
    ]
    (grineer,) = update.guns[0].builds
    assert (grineer.build, grineer.removed, grineer.added) == ("Grineer", [], [])


def test_history_is_carried_newest_first(tmp_path: Path) -> None:
    gamedata = Path(__file__).resolve().parents[2] / "gamedata"
    releases = tmp_path / "releases"
    first = _publish(releases, gamedata, "v1", _gun([HORNET], 2.0), "2026-11-12")
    assert read_updates(first).updates == []  # nothing to compare with
    _publish(releases, gamedata, "v2", _gun([HORNET], 1.0), "2026-11-13")
    last = _publish(releases, gamedata, "v3", _gun([SERRATION], 1.0), "2026-11-14")
    assert [u.date for u in read_updates(last).updates] == ["2026-11-14", "2026-11-13"]
