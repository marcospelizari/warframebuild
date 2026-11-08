import shutil
from pathlib import Path

import pytest

from app.data.refresh import Paths
from app.data.sources import wiki_local

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_RAW = ROOT / "tests/fixtures/raw"


@pytest.fixture
def paths(tmp_path: Path) -> Paths:
    """Fixture raw data + stub wiki pages + the real reference/ files, in a temp project."""
    raw = tmp_path / "cache/raw"
    shutil.copytree(FIXTURE_RAW, raw)
    (raw / "wiki").mkdir()
    reference = tmp_path / "reference"
    shutil.copytree(ROOT / "reference", reference)
    for page in wiki_local.pages(reference):
        (raw / "wiki" / f"{page.stem}.wikitext").write_text("stub", encoding="utf-8")
    return Paths(
        raw=raw, reference=reference, gamedata=tmp_path / "gamedata", img=tmp_path / "cache/img"
    )
