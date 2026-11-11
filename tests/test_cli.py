import pytest

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
