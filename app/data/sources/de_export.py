"""DE Public Export: LZMA index -> hashed manifest names -> JSON exports (T1)."""

import datetime
import lzma
import re
from pathlib import Path

from app.data.http import PoliteClient
from app.data.sources import SourceFile, sha256_16

BASE_URL = "https://content.warframe.com/PublicExport"
INDEX_URL = f"{BASE_URL}/index_en.txt.lzma"
EXPORTS = (
    "ExportWeapons_en.json",
    "ExportUpgrades_en.json",
    "ExportRelicArcane_en.json",
    "ExportSentinels_en.json",
    "ExportManifest.json",
)
MAX_INDEX_BYTES = 64 * 1024
MAX_EXPORT_BYTES = 64 * 1024 * 1024
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


def download(client: PoliteClient, raw_dir: Path) -> list[SourceFile]:
    today = datetime.date.today().isoformat()
    de_dir = raw_dir / "de"
    de_dir.mkdir(parents=True, exist_ok=True)
    index_raw = client.get(INDEX_URL, max_bytes=MAX_INDEX_BYTES)
    entries = decode_index(index_raw)
    files = [_save(de_dir / "index_en.txt.lzma", index_raw, INDEX_URL, today, raw_dir)]
    for name in EXPORTS:
        url = f"{BASE_URL}/Manifest/{entries[name]}"
        data = client.get(url, max_bytes=MAX_EXPORT_BYTES)
        files.append(_save(de_dir / name, data, url, today, raw_dir))
    return files


def _save(path: Path, data: bytes, url: str, today: str, raw_dir: Path) -> SourceFile:
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(path)
    return SourceFile(path.relative_to(raw_dir).as_posix(), url, today, sha256_16(data))
