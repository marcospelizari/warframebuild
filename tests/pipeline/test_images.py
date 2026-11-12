from pathlib import Path
from typing import cast

from app.gamedata.store import GameData
from app.pipeline import images
from app.pipeline.sources.http import DownloadError, PoliteClient

JPEG = b"\xff\xd8\xff\xe0 jpeg"
PNG = b"\x89PNG\r\n\x1a\n png"


class FakeClient:
    def __init__(self, answers: dict[str, bytes | DownloadError]) -> None:
        self.answers = answers
        self.asked: list[str] = []

    def get(self, url: str, max_bytes: int) -> bytes:
        self.asked.append(url)
        answer = self.answers[url.rsplit("/", 1)[-1]]
        if isinstance(answer, DownloadError):
            raise answer
        return answer


def _pictures(tmp_path: Path) -> list[images.Picture]:
    return [
        images.Picture("Good", "/good.jpg", tmp_path / "mods/a.jpg"),
        images.Picture("Wrong type", "/wrong.jpg", tmp_path / "mods/b.jpg"),
        images.Picture("Broken", "/broken.png", tmp_path / "arcanes/c.png"),
        images.Picture("Cached", "/cached.png", tmp_path / "arcanes/d.png"),
    ]


def test_fetch_checks_file_type_and_skips_cached(tmp_path: Path) -> None:
    (tmp_path / "arcanes").mkdir()
    (tmp_path / "arcanes/d.png").write_bytes(PNG)
    fake = FakeClient({"good.jpg": JPEG, "wrong.jpg": PNG, "broken.png": DownloadError("HTTP 404")})
    failures = images.fetch_missing(cast(PoliteClient, fake), _pictures(tmp_path))
    assert (tmp_path / "mods/a.jpg").read_bytes() == JPEG
    assert not (tmp_path / "mods/b.jpg").exists()
    assert failures == ["Wrong type: not a JPG", "Broken: HTTP 404"]
    assert not any(url.endswith("cached.png") for url in fake.asked)


def test_item_pictures_use_the_gamedata_names(tmp_path: Path, gamedata: GameData) -> None:
    pictures = images.item_pictures("mods", gamedata.mods.mods, tmp_path)
    names = {p.path.name for p in pictures}
    assert names == set(gamedata.picture_names["mods"])
    assert all(p.path.parent == tmp_path / "mods" for p in pictures)
