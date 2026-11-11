"""Write side of gamedata/: deterministic JSON, staged write, validated swap (E12).

Publishing uses two renames (gamedata -> .gamedata.old, staging -> gamedata). A crash
between them leaves only `.gamedata.old`; the next write restores it before anything
else, and `.old` is removed only once the new folder is in place. A lock file keeps
two writers apart.
"""

import datetime
import json
import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from pydantic import BaseModel

from app.domain.effects import Support
from app.gamedata.models import Category, Meta, ModsFile, SourceRecord
from app.gamedata.store import dataset_hash, load
from app.pipeline.build import Dataset


class StoreError(RuntimeError):
    pass


def _siblings(gamedata_dir: Path) -> tuple[Path, Path, Path]:
    name = gamedata_dir.name
    return (
        gamedata_dir.with_name(f".{name}.staging"),
        gamedata_dir.with_name(f".{name}.old"),
        gamedata_dir.with_name(f".{name}.lock"),
    )


@contextmanager
def exclusive(path: Path, job: str = "refresh") -> Iterator[None]:
    """Lock file created with O_EXCL; a second holder fails instead of waiting."""
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise StoreError(
            f"{path} exists: another {job} is running, or one crashed (then delete the file)"
        ) from None
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        path.unlink(missing_ok=True)


def backup_dir(gamedata_dir: Path) -> Path:
    return _siblings(gamedata_dir)[1]


def recover(gamedata_dir: Path) -> None:
    """Finish or undo an interrupted swap; never deletes the only copy."""
    _, old, _ = _siblings(gamedata_dir)
    if old.exists():
        if gamedata_dir.exists():
            shutil.rmtree(old)  # swap had completed; leftover backup
        else:
            old.rename(gamedata_dir)  # crash between the renames: restore


def dump(value: object) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    elif isinstance(value, list):
        value = [v.model_dump(mode="json") if isinstance(v, BaseModel) else v for v in value]
    return (json.dumps(value, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode()


def write(
    dataset: Dataset,
    sources: list[SourceRecord],
    gamedata_dir: Path,
    previous: Meta | None,
    today: str | None = None,
) -> Meta:
    """Stage, re-load through the models, then swap in. On failure gamedata/ stays as it was."""
    payloads = {
        "weapons.json": dump(dataset.weapons),
        "mods.json": dump(ModsFile(mods=dataset.mods, sets=dataset.mod_sets)),
        "arcanes.json": dump(dataset.arcanes),
        "joins.json": dump(dataset.joins),
        "incarnon.json": dump(dataset.incarnon),
        "reference_head.json": dump(dataset.reference_head),
        "enemies.json": dump(dataset.enemies),
        "factions.json": dump(dataset.factions),
    }
    digest = dataset_hash(payloads)
    fetched = max((s.retrieved for s in sources if not s.path.startswith("wiki/")), default="")
    counts = {"weapons": len(dataset.weapons)}
    counts |= {c.value: sum(w.category == c for w in dataset.weapons) for c in Category}
    counts |= {
        "excluded_weapons": len(dataset.excluded_weapons),
        "mods": len(dataset.mods),
        "mod_sets": len(dataset.mod_sets),
        "arcanes": len(dataset.arcanes),
        "incarnon_weapons": len(dataset.incarnon),
        "enemies": len(dataset.enemies),
        "factions": len(dataset.factions),
    }
    counts |= {
        f"arcanes_{c.value}": sum(a.category == c for a in dataset.arcanes) for c in Category
    }
    for kind, entries in (("mods", dataset.mods), ("arcanes", dataset.arcanes)):
        counts |= {
            f"{kind}_{level.value}": sum(e.effects.support == level for e in entries)
            for level in Support
        }
    perks = [p for i in dataset.incarnon for p in i.perks]
    counts |= {f"perks_{s.value}": sum(p.effects.support == s for p in perks) for s in Support}
    meta = Meta(
        dataset_hash=digest,
        game_update=dataset.game_update,
        fetched=fetched,
        changed_on=_changed_on(previous, digest, today or datetime.date.today().isoformat()),
        sources=sorted(sources, key=lambda s: s.path),
        counts=counts,
        excluded_weapons=dataset.excluded_weapons,
        denied_mods=dataset.denied_mods,
    )
    payloads["meta.json"] = dump(meta)

    staging, old, lock = _siblings(gamedata_dir)
    with exclusive(lock):
        recover(gamedata_dir)
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        for name, data in payloads.items():
            (staging / name).write_bytes(data)
        load(staging)  # validation: the app must be able to read what was written
        if gamedata_dir.exists():
            gamedata_dir.rename(old)
        staging.rename(gamedata_dir)
        if old.exists():
            shutil.rmtree(old)
    return meta


def _changed_on(previous: Meta | None, digest: str, today: str) -> str:
    """Date of the refresh that first produced this dataset, never moving backwards.

    The refresh date, not the download date: an offline rebuild of old downloads
    with new rules still changes the data today.
    """
    if previous is None:
        return today
    if previous.dataset_hash == digest:
        return previous.changed_on
    return max(today, previous.changed_on)
