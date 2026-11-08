"""WFCD warframe-items JSON (MIT): polarities, class, attacks, falloff, images (G2)."""

import datetime
from pathlib import Path

from app.data.http import PoliteClient
from app.data.sources import SourceFile, sha256_16

BASE_URL = "https://raw.githubusercontent.com/WFCD/warframe-items/master/data/json"
FILES = ("Primary.json", "Secondary.json")
MAX_BYTES = 32 * 1024 * 1024


def download(client: PoliteClient, raw_dir: Path) -> list[SourceFile]:
    today = datetime.date.today().isoformat()
    out_dir = raw_dir / "wfcd"
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for name in FILES:
        url = f"{BASE_URL}/{name}"
        data = client.get(url, max_bytes=MAX_BYTES)
        tmp = out_dir / f"{name}.part"
        tmp.write_bytes(data)
        tmp.replace(out_dir / name)
        files.append(SourceFile(f"wfcd/{name}", url, today, sha256_16(data)))
    return files
