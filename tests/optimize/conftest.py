"""Optimizer tests check calculator rules: they read the frozen tests/fixtures/gamedata/
(`wfb fixtures`), so a game balance change does not fail them (G90 U9). Live-data checks
stay in tests/golden/, tests/api/ and tests/pipeline/."""

import pytest

from app.gamedata.store import GameData, load
from tests.conftest import ROOT


@pytest.fixture(scope="session")
def gamedata() -> GameData:
    return load(ROOT / "tests/fixtures/gamedata")
