from pathlib import Path

import pytest

from app.data import store
from app.data.refresh import Paths, run


def test_crash_between_renames_loses_nothing(paths: Paths, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review bug 4: a crash mid-swap, then another refresh, keeps the good copy."""
    good = run(paths, offline=True, fetch_images=False).meta
    real_rename = Path.rename

    def crash_on_publish(self: Path, target: Path) -> Path:
        if self.name.endswith(".staging"):
            raise OSError("simulated crash")
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", crash_on_publish)
    with pytest.raises(OSError, match="simulated crash"):
        run(paths, offline=True, fetch_images=False)
    assert not paths.gamedata.exists()  # the window the review found
    monkeypatch.setattr(Path, "rename", real_rename)

    again = run(paths, offline=True, fetch_images=False).meta  # recovers, then publishes
    assert again.dataset_hash == good.dataset_hash
    assert store.load(paths.gamedata).meta.dataset_hash == good.dataset_hash
    assert not store.backup_dir(paths.gamedata).exists()


def test_previous_dataset_readable_during_crash_window(
    paths: Paths, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.data.refresh import load_previous

    run(paths, offline=True, fetch_images=False)
    paths.gamedata.rename(store.backup_dir(paths.gamedata))
    previous, error = load_previous(paths.gamedata)
    assert previous is not None and error is None


def test_second_writer_is_refused(paths: Paths) -> None:
    lock = paths.gamedata.with_name(f".{paths.gamedata.name}.lock")
    lock.write_text("123")
    with pytest.raises(store.StoreError, match="another refresh"):
        run(paths, offline=True, fetch_images=False)
    assert lock.read_text() == "123"  # someone else's lock is left alone
