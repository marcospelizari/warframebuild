import json
import re
from pathlib import Path

from app.gamedata.store import load
from app.pipeline import frozen_data
from tests.conftest import ROOT


def test_freeze_keeps_the_test_guns_and_every_mod(tmp_path: Path) -> None:
    out = tmp_path / "gamedata"
    frozen_data.write(ROOT / "gamedata", out)
    frozen, live = load(out), load(ROOT / "gamedata")
    assert {w.name for w in frozen.weapons} == set(frozen_data.GUNS)
    assert len(frozen.mods.mods) == len(live.mods.mods)
    assert {i.unique_name for i in frozen.incarnon} <= {w.unique_name for w in frozen.weapons}


def test_frozen_guns_cover_every_gun_the_optimizer_tests_name() -> None:
    """U9: a new optimizer test on another gun needs it in frozen_data.GUNS + `wfb fixtures`."""
    names = {w["name"] for w in json.loads((ROOT / "gamedata/weapons.json").read_text())}
    used = {
        s
        for p in (ROOT / "tests/optimize").glob("*.py")
        for s in re.findall(r'"([^"\n]+)"', p.read_text(encoding="utf-8"))
        if s in names
    }
    assert used <= set(frozen_data.GUNS), (
        f"add to frozen_data.GUNS: {sorted(used - set(frozen_data.GUNS))}"
    )
