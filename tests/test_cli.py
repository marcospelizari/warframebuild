import pytest
import uvicorn

from app import cli
from app.cli import ROOT


def test_root_is_the_project_folder() -> None:
    """Step 3d moved cli.py up one level; the project root must still resolve."""
    assert (ROOT / "pyproject.toml").is_file() and (ROOT / "reference").is_dir()


def test_interrupted_task_prints_one_line(capsys: pytest.CaptureFixture[str]) -> None:
    def interrupted() -> list[str]:
        raise KeyboardInterrupt

    assert cli._guarded(interrupted, "build-all failed, current release unchanged") == 130
    assert capsys.readouterr().err == "build-all failed, current release unchanged: interrupted\n"


@pytest.mark.parametrize("flag", ["--workers", "--budget"])
@pytest.mark.parametrize("value", ["0", "-1"])
def test_build_all_rejects_counts_below_one(flag: str, value: str) -> None:
    with pytest.raises(SystemExit) as exit:
        cli.main(["build-all", flag, value])
    assert exit.value.code == 2


def test_serve_off_loopback_needs_the_public_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Page URLs would otherwise come from each request's Host header."""
    with pytest.raises(SystemExit):
        cli.main(["serve", "--host", "0.0.0.0"])
    started: list[str] = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: started.append(kw["host"]))
    cli.main(["serve", "--host", "::1"])
    cli.main(["serve", "--host", "0.0.0.0", "--public-origin", "https://example.org"])
    assert started == ["::1", "0.0.0.0"]


def test_serve_sample_serves_the_sample_release(monkeypatch: pytest.MonkeyPatch) -> None:
    served: list[object] = []
    monkeypatch.setattr(cli, "create_app", lambda **kw: served.append(kw["releases"]))
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: None)
    cli.main(["serve"])
    cli.main(["serve", "--sample"])
    assert served == [ROOT / "cache/releases", ROOT / "cache/sample/releases"]
