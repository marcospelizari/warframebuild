"""WARFRAME Wiki pages saved by hand (T2): never fetched, only read from cache/raw/wiki/."""

import datetime
from pathlib import Path

from app.data.sources import SourceFile, sha256_16

WIKI_URL = "https://wiki.warframe.com/w"
# Pages the data layer needs today; later steps add theirs (G41 list).
REQUIRED_PAGES = (
    "Archon_Shard",
    "Armor",
    "Calculating_Bonuses",
    "Calculation",
    "Critical_Hit",
    "Damage",
    "Enemy_Level_Scaling",
    "Faction_Damage_Mods",
    "Incarnon_Evolutions",
    "Multishot",
    "Overview_Table",
    "Polarity",
    "Riven_Mods",
    "Sandbox2",
    "Status_Effect",
    "The_Steel_Path",
    "Corpus",
    "Corrupted",
    "Grineer",
    "Infested",
    "Scaldra",
    "Sentient",
    "Techrot",
    "The_Murmur",
)


class MissingWikiPages(RuntimeError):
    pass


def scan(raw_dir: Path, required: tuple[str, ...] = REQUIRED_PAGES) -> list[SourceFile]:
    wiki_dir = raw_dir / "wiki"
    missing = [p for p in required if not (wiki_dir / f"{p}.wikitext").is_file()]
    if missing:
        hint = ", ".join(f"{WIKI_URL}/{p}?action=raw" for p in missing)
        raise MissingWikiPages(f"save these wiki pages into {wiki_dir}/<Page>.wikitext: {hint}")
    files = []
    for path in sorted(wiki_dir.glob("*.wikitext")):
        saved = datetime.date.fromtimestamp(path.stat().st_mtime).isoformat()
        files.append(
            SourceFile(
                f"wiki/{path.name}", f"{WIKI_URL}/{path.stem}", saved, sha256_16(path.read_bytes())
            )
        )
    return files
