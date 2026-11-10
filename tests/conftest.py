import json
import shutil
from pathlib import Path

import pytest

from app.gamedata.store import GameData, load
from app.pipeline.refresh import Paths
from app.pipeline.sources import wiki_incarnon, wiki_local

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_RAW = ROOT / "tests/fixtures/raw"
# Saved wiki copies stay private (G23): tests use this hand-written module in the format
# of Module:Weapons/data/<slot>, with the values of the saved pages for a few guns.
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
\t\tZoom = { "3x (+20% Critical Chance)", "8x (+50% Critical Chance)" },
\t},
\t["Convectrix"] = {
\t\tAttacks = {
\t\t\t{ AttackName = "Normal Attack" },
\t\t\t{ AttackName = "Alt-Fire" },
\t\t},
\t\tInternalName = "/Lotus/Weapons/Corpus/LongGuns/CrpSplitLaser/CrpSplitLaser",
\t\tMagazine = 70,
\t\tName = "Convectrix",
\t},
\t["Nataruk"] = {
\t\tAttacks = {
\t\t\t{ AttackName = "Quick Shot" },
\t\t\t{ AttackName = "Charged Shot", ChargeTime = 1 },
\t\t\t{ AttackName = "Perfect Shot", ChargeTime = 0.7, ExtraHeadshotDmg = -2 },
\t\t},
\t\tInternalName = "/Lotus/Weapons/Tenno/Bows/Omicrus/OmicrusPlayerWep",
\t\tMagazine = 1,
\t\tName = "Nataruk",
\t\tReload = 0.6,
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
\tGrimoire = {
\t\tAttacks = {
\t\t\t{ AttackName = "Normal Attack" },
\t\t\t{ AttackName = "Normal Radial Attack" },
\t\t\t{ AttackName = "Active Attack", ForcedProcs = { "Electricity" } },
\t\t\t{ AttackName = "Active Radial Attack", ForcedProcs = { "Electricity" } },
\t\t},
\t\tInternalName = "/Lotus/Weapons/Tenno/Grimoire/TnGrimoire",
\t\tMagazine = 0,
\t\tName = "Grimoire",
\t},
}
""",
    # Module:Enemies/data/<faction>: saved values for two representative enemies.
    "Module_Enemies_grineer": """return {
\t["Lancer"] = {
\t\tGeneral = {
\t\t\tFaction = "Grineer",
\t\t\tInternalName = "/Lotus/Types/Enemies/Grineer/AIWeek/RifleLancer",
\t\t},
\t\tStats = { Health = 100, Armor = 100, BaseLevel = 1 },
\t},
}
""",
    "Module_Enemies_corpus": """return {
\t["Crewman"] = {
\t\tGeneral = {
\t\t\tFaction = "Corpus",
\t\t\tInternalName = "/Lotus/Types/Enemies/Corpus/Spaceman/AIWeek/RifleSpacemanAgent",
\t\t},
\t\tStats = { Health = 90, Shield = 120, BaseLevel = 1 },
\t},
}
""",
}
FIXTURE_ENEMIES = {"Lancer", "Crewman"}


def _body_parts_page() -> str:
    """Enemy_Body_Parts rows of the fixture enemies at their saved line numbers."""
    lines = [""] * 470
    lines[321] = "| {{E|Lancer}} || Body (1x) || Head (3x) ||"
    lines[469] = "| {{E|Crewman}} || Body (1x) || Head (3x)* ||"
    return "\n".join(lines) + "\n"


def _efficacy(faction: str) -> str:
    return "{{Quote|'''DAMAGE EFFICACY'''<br/>\n'''{{text|green|x1.5}}''' damage to " + faction


def _family_page(gun: str) -> str:
    return (
        "=== Obtained ===\n{{Checklist|\n*{{Weapon|" + gun + "}}\n}}\n"
        "===Elemental Bonus===\nbonus damage of one damage type which can either be "
        "{{D|Impact}}, {{D|Heat}} or {{D|Radiation}}, ranging from 25-60% of base damage.\n=="
    )


# Incarnon tables in the shape of the saved pages (values from them).
NATIVE_STUB = "===Evolutions===\n{|\n|}\n"
LAETUM_STUB = """===Evolutions===
{| class="wikitable"
! rowspan="3" | EVO5
| '''Devouring Attrition'''
|
* '''50%''' chance to deal '''+2000%''' damage on non-critical hits
|
* Damage bonus is '''multiplicative''' to base damage bonuses such as {{M|Hornet Strike}}.
|-
| '''Overwhelming Attrition'''
|
* On Hit that is neither Critical nor applies a Status Effect: '''+400%''' damage for 10 seconds.
|
* Damage bonus is '''additive''' to base damage bonuses such as {{M|Hornet Strike}}.
|-
|}
"""
GENESIS_STUB = """{{CustomCollapsible|Lex|Lex|expand=false|notlist=true}}
{| class="wikitable sortable stickyHeader"
! colspan="3" | Evolution
! class=unsortable | {{Weapon|Lex}}
! class=unsortable | {{Weapon|Lex Prime}}
! class=unsortable | Notes
|-
! rowspan="3" | EVO4
| style="text-align:center" | '''Critical Parallel'''
|
*Increase Base Critical Chance by '''+X'''.
*Increase Base Critical Damage Multiplier by '''+0.4x'''.
| style="text-align:center" | X = 20%
| style="text-align:center" | X = 19%
|
|-
| style="text-align:center" | '''Executioner's Dawn'''
|
*On Equip: '''+100%''' Headshot Damage for '''4s'''.
| colspan="2" style="text-align:center" | -
|
*The bonus does not apply to the Incarnon form.
|}
{{CustomCollapsible/End}}
"""

# Family pages in the shape of the saved Kuva/Tenet/Coda_Weapons pages.
PAGE_STUBS = {
    "Incarnon_Evolutions": GENESIS_STUB,
    "Laetum": LAETUM_STUB,
    "Kuva_Weapons": _family_page("Kuva Hind"),
    "Tenet_Weapons": _family_page("Tenet Example"),
    "Coda_Weapons": _family_page("Coda Example"),
    "Enemy_Body_Parts": _body_parts_page(),
    "Impact_Damage": _efficacy("Grineer"),
    "Puncture_Damage": _efficacy("Corpus"),
}


@pytest.fixture
def paths(tmp_path: Path) -> Paths:
    """Fixture raw data + stub wiki pages + the real reference/ files, in a temp project."""
    raw = tmp_path / "cache/raw"
    shutil.copytree(FIXTURE_RAW, raw)
    (raw / "wiki").mkdir()
    reference = tmp_path / "reference"
    shutil.copytree(ROOT / "reference", reference)
    _keep_fixture_guns(raw, reference / "galvanized_behaviour.json")
    _keep_fixture_guns(raw, reference / "headshot.json")
    _keep_fixture_guns(raw, reference / "weapon_tags.json")
    _keep_rows(reference / "main_attack.json", {"Lex Prime", "Laetum"})
    _keep_overrides(raw, reference / "overrides.json", {"ZarimanHeavyPistol", "PrimeLex"})
    _keep_enemies(reference / "enemies.json")
    for page in wiki_local.pages(reference):
        if page.format == "lua":
            stub = MODULE_STUBS.get(page.stem, "return {}")
        else:
            native = page.stem in wiki_incarnon.NATIVE
            stub = PAGE_STUBS.get(page.stem, NATIVE_STUB if native else "stub")
        (raw / "wiki" / page.filename).write_text(stub, encoding="utf-8")
    return Paths(
        raw=raw, reference=reference, gamedata=tmp_path / "gamedata", img=tmp_path / "cache/img"
    )


def _keep_rows(table: Path, names: set[str]) -> None:
    """Rows only for the guns the stub pages give perks."""
    data = json.loads(table.read_text())
    data["weapons"] = {u: r for u, r in data["weapons"].items() if r["name"] in names}
    table.write_text(json.dumps(data))


def _keep_overrides(raw: Path, table: Path, perk_guns: set[str]) -> None:
    """Zoom entries for fixture guns; perk entries only for the guns the stub pages cover."""
    guns = {
        w["uniqueName"]
        for name in ("Primary.json", "Secondary.json")
        for w in json.loads((raw / "wfcd" / name).read_text())
    }
    data = json.loads(table.read_text())

    def keep(key: str) -> bool:
        uid, _, part = key.partition("#")
        if not part:
            return True
        if part == "zoom":
            return uid in guns
        return uid.rsplit("/", 1)[-1] in perk_guns

    data["entries"] = {k: v for k, v in data["entries"].items() if keep(k)}
    table.write_text(json.dumps(data))


def _keep_enemies(table: Path) -> None:
    """Rows only for the enemies the stub modules hold; the rest are checked against the
    committed gamedata/ by tests/pipeline/test_enemies.py."""
    data = json.loads(table.read_text())
    data["enemies"] = {u: r for u, r in data["enemies"].items() if r["name"] in FIXTURE_ENEMIES}
    table.write_text(json.dumps(data))


def _keep_fixture_guns(raw: Path, table: Path) -> None:
    """The real table names ~70 guns; the fixtures hold a few. Rows for other guns are
    checked against the committed gamedata/ by tests/pipeline/test_direct_bonus.py."""
    guns = {
        w["uniqueName"]
        for name in ("Primary.json", "Secondary.json")
        for w in json.loads((raw / "wfcd" / name).read_text())
    }
    data = json.loads(table.read_text())
    for key in ("weapons", "flat_heads", "separate_extra"):
        if key in data:
            data[key] = {u: row for u, row in data[key].items() if u in guns}
    table.write_text(json.dumps(data))


@pytest.fixture(scope="session")
def gamedata() -> GameData:
    """The committed gamedata/ (Q26: domain, optimizer and API tests read it)."""
    return load(ROOT / "gamedata")
