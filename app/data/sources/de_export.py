"""DE Public Export adapter (T1): LZMA index, hashed manifests, DE encodings."""

import lzma
import re

from app.data.http import PoliteClient
from app.data.models import Category, DamageType
from app.data.sources import Fetched

BASE_URL = "https://content.warframe.com/PublicExport"
INDEX_URL = f"{BASE_URL}/index_en.txt.lzma"
INDEX_PATH = "de/index_en.txt.lzma"
EXPORTS = (
    "ExportWeapons_en.json",
    "ExportUpgrades_en.json",
    "ExportRelicArcane_en.json",
    "ExportSentinels_en.json",
    "ExportManifest.json",
)
MAX_INDEX_BYTES = 64 * 1024
MAX_EXPORT_BYTES = 64 * 1024 * 1024

# `damagePerShot` is positional (20 slots). Slots 0-14 confirmed against WFCD attack
# data (gas: Cyanex, tau: Haalvu); 15-19 are never set on a gun and are rejected.
DAMAGE_SLOTS: tuple[DamageType, ...] = (
    DamageType.IMPACT,
    DamageType.PUNCTURE,
    DamageType.SLASH,
    DamageType.HEAT,
    DamageType.COLD,
    DamageType.ELECTRICITY,
    DamageType.TOXIN,
    DamageType.BLAST,
    DamageType.RADIATION,
    DamageType.GAS,
    DamageType.MAGNETIC,
    DamageType.VIRAL,
    DamageType.CORROSIVE,
    DamageType.VOID,
    DamageType.TAU,
)
DAMAGE_SLOT_COUNT = 20

# Our category -> DE ExportWeapons `productCategory`, DE ExportUpgrades `type`.
CATEGORIES: dict[Category, tuple[str, str]] = {
    Category.PRIMARY: ("LongGuns", "PRIMARY"),
    Category.SECONDARY: ("Pistols", "SECONDARY"),
}
WEAPON_CATEGORY = {de: ours for ours, (de, _) in CATEGORIES.items()}
MOD_CATEGORY = {de: ours for ours, (_, de) in CATEGORIES.items()}

_UNKNOWN_SIZE = 2**64 - 1
_INDEX_LINE = re.compile(r"(?P<name>Export\w+\.json)!00_[A-Za-z0-9+\-_]{20,30}")


class IndexError_(RuntimeError):
    pass


def decode_index(raw: bytes) -> dict[str, str]:
    """Return {export name: hashed manifest name}.

    DE's .lzma has a declared size but no valid end marker, so a strict decoder
    fails on the last bytes. Decode incrementally and accept the result only when
    at most the final line break is missing and every line is well formed.
    """
    if len(raw) < 13:
        raise IndexError_("index too short")
    declared = int.from_bytes(raw[5:13], "little")
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
    out = bytearray()
    for i in range(len(raw)):
        try:
            out += decoder.decompress(raw[i : i + 1])
        except lzma.LZMAError:
            break
    if declared == _UNKNOWN_SIZE:
        if not decoder.eof:
            raise IndexError_("index has no size and no end marker")
    elif not 0 <= declared - len(out) <= 2:
        raise IndexError_(f"index decoded to {len(out)} of {declared} bytes")
    entries: dict[str, str] = {}
    for line in out.decode("utf-8").replace("\r", "").split("\n"):
        if not line:
            continue
        match = _INDEX_LINE.fullmatch(line)
        if not match:
            raise IndexError_(f"malformed index line: {line!r}")
        entries[match["name"]] = line
    missing = [name for name in EXPORTS if name not in entries]
    if missing:
        raise IndexError_(f"index lacks {', '.join(missing)}")
    return entries


def resolve(client: PoliteClient) -> tuple[Fetched, list[Fetched]]:
    """Download the index only; return it and the export URLs (no export data)."""
    index = client.get(INDEX_URL, max_bytes=MAX_INDEX_BYTES)
    entries = decode_index(index)
    exports = [Fetched(f"de/{n}", f"{BASE_URL}/Manifest/{entries[n]}", None) for n in EXPORTS]
    return Fetched(INDEX_PATH, INDEX_URL, index), exports


def fetch(client: PoliteClient) -> list[Fetched]:
    index, exports = resolve(client)
    return [index] + [
        Fetched(e.path, e.url, client.get(e.url, max_bytes=MAX_EXPORT_BYTES)) for e in exports
    ]
