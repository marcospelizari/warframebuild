"""gamedata/ on disk: deterministic JSON, staged write, validated swap, loader (E12).

Publishing uses two renames (gamedata -> .gamedata.old, staging -> gamedata). A crash
between them leaves only `.gamedata.old`; the next write restores it before anything
else, and `.old` is removed only once the new folder is in place. A lock file keeps
two writers apart.
"""

import hashlib
import json
import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, TypeAdapter

from app.data.build import Dataset
from app.data.models import Arcane, Category, Join, Meta, ModsFile, SourceRecord, Weapon

DATA_FILES = ("weapons.json", "mods.json", "arcanes.json", "joins.json")


class StoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class GameData:
    meta: Meta
    weapons: list[Weapon]
    mods: ModsFile
    arcanes: list[Arcane]
    joins: list[Join]


def _siblings(gamedata_dir: Path) -> tuple[Path, Path, Path]:
    name = gamedata_dir.name
    return (
        gamedata_dir.with_name(f".{name}.staging"),
        gamedata_dir.with_name(f".{name}.old"),
        gamedata_dir.with_name(f".{name}.lock"),
    )


@contextmanager
def _lock(path: Path) -> Iterator[None]:
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise StoreError(
            f"{path} exists: another refresh is running, or one crashed (then delete the file)"
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


def _dump(value: object) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    elif isinstance(value, list):
        value = [v.model_dump(mode="json") if isinstance(v, BaseModel) else v for v in value]
    return (json.dumps(value, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode()


def dataset_hash(payloads: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name in sorted(payloads):
        digest.update(name.encode() + b"\0" + payloads[name] + b"\0")
    return digest.hexdigest()[:16]


def write(
    dataset: Dataset, sources: list[SourceRecord], gamedata_dir: Path, previous: Meta | None
) -> Meta:
    """Stage, re-load through the models, then swap in. On failure gamedata/ stays as it was."""
    payloads = {
        "weapons.json": _dump(dataset.weapons),
        "mods.json": _dump(ModsFile(mods=dataset.mods, sets=dataset.mod_sets)),
        "arcanes.json": _dump(dataset.arcanes),
        "joins.json": _dump(dataset.joins),
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
    }
    meta = Meta(
        dataset_hash=digest,
        game_update=dataset.game_update,
        fetched=fetched,
        changed_on=previous.changed_on if previous and previous.dataset_hash == digest else fetched,
        sources=sorted(sources, key=lambda s: s.path),
        counts=counts,
        excluded_weapons=dataset.excluded_weapons,
        denied_mods=dataset.denied_mods,
    )
    payloads["meta.json"] = _dump(meta)

    staging, old, lock = _siblings(gamedata_dir)
    with _lock(lock):
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


def load(gamedata_dir: Path) -> GameData:
    def read(name: str) -> bytes:
        return (gamedata_dir / name).read_bytes()

    meta = Meta.model_validate_json(read("meta.json"))
    payloads = {name: read(name) for name in DATA_FILES}
    if dataset_hash(payloads) != meta.dataset_hash:
        raise ValueError(f"{gamedata_dir}: files do not match meta.json dataset_hash")
    return GameData(
        meta=meta,
        weapons=TypeAdapter(list[Weapon]).validate_json(payloads["weapons.json"]),
        mods=ModsFile.model_validate_json(payloads["mods.json"]),
        arcanes=TypeAdapter(list[Arcane]).validate_json(payloads["arcanes.json"]),
        joins=TypeAdapter(list[Join]).validate_json(payloads["joins.json"]),
    )
