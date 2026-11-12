"""A small release shared by the API tests."""

from pathlib import Path

import pytest

from app.gamedata.store import GameData
from app.optimize.builds import weapon_builds
from app.pipeline import release

ROOT = Path(__file__).resolve().parents[2]
GUNS = ("Soma Prime", "Kuva Hind")


@pytest.fixture(scope="session")
def releases(tmp_path_factory: pytest.TempPathFactory, gamedata: GameData) -> Path:
    """A release holding only GUNS, at a small budget."""
    folder = tmp_path_factory.mktemp("releases")
    weapons = [w for w in gamedata.weapons if w.name in GUNS]
    key = release.Key(gamedata.meta.dataset_hash, "ref", "calc", 20)
    stored = [weapon_builds(gamedata, w, 20) for w in weapons]
    slugs = {w.slug for w in weapons}
    release.publish(folder, key, ROOT / "gamedata", ROOT / "reference", stored, slugs)
    return folder
