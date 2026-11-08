import shutil
from pathlib import Path

import pytest

from app.pipeline.refresh import Paths
from app.pipeline.sources import wiki_local

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_RAW = ROOT / "tests/fixtures/raw"
# Saved wiki copies stay private (G23): tests use this hand-written module in the format
# of Module:Weapons/data/<slot>, with the values of the saved pages for two guns.
MODULE_STUBS = {
    "Module_Weapons_data_primary": """return {
\t["Lanka"] = {
\t\tAttacks = {
\t\t\t{ AttackName = "Partially Charged Shot", ChargeTime = 0.33, FireRate = math.huge },
\t\t\t{ AttackName = "Charged Shot", ChargeTime = 1, FireRate = math.huge },
\t\t},
\t\tInternalName = "/Lotus/Weapons/ClanTech/Energy/Railgun",
\t\tName = "Lanka",
\t\tSniperComboMin = 2,
\t},
}
""",
    "Module_Weapons_data_secondary": """return {
\tEpitaph = {
\t\tAttacks = {
\t\t\t{ AttackName = "Charged Shot", ChargeTime = 0.36, FireRate = 1.5,
\t\t\t\tForcedProcs = { "Impact" } },
\t\t\t{ AttackName = "Uncharged Direct Hit", FireRate = 1.5, ForcedProcs = { "Impact" } },
\t\t\t{ AttackName = "Uncharged AoE", FireRate = 1.5, ForcedProcs = { "Cold" } }, -- AoE
\t\t},
\t\tInternalName = "/Lotus/Weapons/Tenno/Pistols/TnWraitheSidearm/TnWraitheSidearmWeapon",
\t\tName = "Epitaph",
\t},
}
""",
}


@pytest.fixture
def paths(tmp_path: Path) -> Paths:
    """Fixture raw data + stub wiki pages + the real reference/ files, in a temp project."""
    raw = tmp_path / "cache/raw"
    shutil.copytree(FIXTURE_RAW, raw)
    (raw / "wiki").mkdir()
    reference = tmp_path / "reference"
    shutil.copytree(ROOT / "reference", reference)
    for page in wiki_local.pages(reference):
        stub = MODULE_STUBS.get(page.stem, "return {}") if page.format == "lua" else "stub"
        (raw / "wiki" / page.filename).write_text(stub, encoding="utf-8")
    return Paths(
        raw=raw, reference=reference, gamedata=tmp_path / "gamedata", img=tmp_path / "cache/img"
    )
