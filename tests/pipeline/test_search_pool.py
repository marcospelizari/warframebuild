from pathlib import Path

from app.gamedata.store import load
from app.optimize.builds import weapon_builds
from app.pipeline import search_pool
from tests.conftest import ROOT

FROZEN = ROOT / "tests/fixtures/gamedata"


def test_split_tasks_give_the_same_builds_as_one_process() -> None:
    """A gun's searches spread over workers (G16: same bytes as a sequential run)."""
    data = load(FROZEN)
    slugs = ["kuva-hind", "soma-prime", "lenz"]
    busy: dict[str, float] = {}
    pooled = search_pool.search(data, FROZEN, slugs, 3, 30, list, busy)
    by_slug = {b.slug: b.model_dump_json() for b in pooled}
    for slug in slugs:
        alone = weapon_builds(data, data.weapon_by_slug[slug], 30).model_dump_json()
        assert by_slug[slug] == alone, slug
    assert set(busy) == set(slugs) and all(t > 0 for t in busy.values())


def test_no_guns_no_pool(tmp_path: Path) -> None:
    data = load(FROZEN)
    assert search_pool.search(data, tmp_path / "missing", [], 2, 1, list) == []
