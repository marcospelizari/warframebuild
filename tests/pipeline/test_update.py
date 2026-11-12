import json
from pathlib import Path

import pytest

from app.pipeline import build_all, update
from app.pipeline.refresh import Paths, run

ROOT = Path(__file__).resolve().parents[2]
HORNET = "/Lotus/Upgrades/Mods/Pistol/WeaponDamageAmountMod"


def _build_paths(paths: Paths, tmp_path: Path) -> build_all.Paths:
    return build_all.Paths(paths.gamedata, paths.reference, tmp_path / "releases", ROOT / "app")


def _update(paths: Paths, tmp_path: Path) -> list[str]:
    return update.run(paths, _build_paths(paths, tmp_path), offline=True, workers=2, budget=1)


def test_update_refreshes_builds_and_lists_what_needs_you(paths: Paths, tmp_path: Path) -> None:
    run(paths, offline=True, fetch_images=False)
    _update(paths, tmp_path)

    upgrades = paths.raw / "de/ExportUpgrades_en.json"
    data = json.loads(upgrades.read_text())
    hornet = next(e for e in data["ExportUpgrades"] if e["uniqueName"] == HORNET)
    hornet["levelStats"][-1]["stats"] = ["+240% Damage", "[PH] +1 max Puncture stacks"]
    upgrades.write_text(json.dumps(data))
    overrides = paths.reference / "overrides.json"
    table = json.loads(overrides.read_text())
    key = next(k for k in table["entries"] if k.endswith("#Devouring Attrition"))
    table["entries"][key]["text"] = ["old text"]
    overrides.write_text(json.dumps(table))

    lines = _update(paths, tmp_path)
    text = "\n".join(lines)
    assert "Hornet Strike (mod): full -> partial" in text  # Laetum perk drops too (override off)
    assert "copied)" in text and " 0 searched" not in text
    needs = lines[lines.index("needs you:") + 1 :]
    assert f"  - rewrite override {key}: its text changed" in needs
    assert "  - Hornet Strike (mod) is now partial: an override if it matters" in needs
    full = next(line for line in lines if line.startswith("full refresh report: "))
    assert Path(full.removeprefix("full refresh report: ")).is_file()


def test_update_with_nothing_new_searches_no_gun(paths: Paths, tmp_path: Path) -> None:
    run(paths, offline=True, fetch_images=False)
    _update(paths, tmp_path)
    lines = _update(paths, tmp_path)
    assert any("(0 searched," in line for line in lines)


def test_failed_build_all_says_what_state_is_left(
    paths: Paths, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_: object) -> list[str]:
        raise RuntimeError("boom")

    monkeypatch.setattr(build_all, "run", broken)
    with pytest.raises(update.UpdateError, match=r"gamedata/ is already refreshed.*boom"):
        _update(paths, tmp_path)
