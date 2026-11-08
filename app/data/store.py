"""gamedata/ on disk: deterministic JSON, staged write, validated swap, loader (E12)."""

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, TypeAdapter

from app.data.build import Dataset
from app.data.models import Arcane, Join, Meta, ModsFile, SourceRecord, Weapon

DATA_FILES = ("weapons.json", "mods.json", "arcanes.json", "joins.json")


@dataclass(frozen=True)
class GameData:
    meta: Meta
    weapons: list[Weapon]
    mods: ModsFile
    arcanes: list[Arcane]
    joins: list[Join]


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


def write(dataset: Dataset, sources: list[SourceRecord], gamedata_dir: Path) -> Meta:
    """Write into a staging folder, re-load it through the models, then swap it in.

    On any failure the previous gamedata/ stays untouched.
    """
    payloads = {
        "weapons.json": _dump(dataset.weapons),
        "mods.json": _dump(ModsFile(mods=dataset.mods, sets=dataset.mod_sets)),
        "arcanes.json": _dump(dataset.arcanes),
        "joins.json": _dump(dataset.joins),
    }
    fetched = max((s.retrieved for s in sources if not s.path.startswith("wiki/")), default="")
    meta = Meta(
        dataset_hash=dataset_hash(payloads),
        game_update=dataset.game_update,
        fetched=fetched,
        sources=sorted(sources, key=lambda s: s.path),
        counts={
            "weapons": len(dataset.weapons),
            "primary": sum(w.category == "primary" for w in dataset.weapons),
            "secondary": sum(w.category == "secondary" for w in dataset.weapons),
            "excluded_weapons": len(dataset.excluded_weapons),
            "mods": len(dataset.mods),
            "mod_sets": len(dataset.mod_sets),
            "arcanes": len(dataset.arcanes),
        },
        excluded_weapons=dataset.excluded_weapons,
        denied_mods=dataset.denied_mods,
    )
    payloads["meta.json"] = _dump(meta)

    staging = gamedata_dir.with_name(f".{gamedata_dir.name}.staging")
    old = gamedata_dir.with_name(f".{gamedata_dir.name}.old")
    for leftover in (staging, old):
        if leftover.exists():
            shutil.rmtree(leftover)
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
