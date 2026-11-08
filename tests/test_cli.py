from app.cli import ROOT


def test_root_is_the_project_folder() -> None:
    """Step 3d moved cli.py up one level; the project root must still resolve."""
    assert (ROOT / "pyproject.toml").is_file() and (ROOT / "reference").is_dir()
