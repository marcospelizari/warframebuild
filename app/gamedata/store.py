"""Read side of gamedata/: the loader the app and the pipeline share (E12).

A dataset is valid only when its files match meta.json's dataset_hash and its
schema version is the one this code reads.
"""

import hashlib
import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from pydantic import TypeAdapter

from app.gamedata.models import Arcane, Incarnon, Join, Meta, Mod, ModsFile, Weapon

DATA_FILES = ("weapons.json", "mods.json", "arcanes.json", "joins.json", "incarnon.json")


@dataclass(frozen=True)
class GameData:
    meta: Meta
    weapons: list[Weapon]
    mods: ModsFile
    arcanes: list[Arcane]
    joins: list[Join]
    incarnon: list[Incarnon]

    @cached_property
    def weapon_by_slug(self) -> dict[str, Weapon]:
        return {w.slug: w for w in self.weapons}

    @cached_property
    def incarnon_by_id(self) -> dict[str, Incarnon]:
        return {i.unique_name: i for i in self.incarnon}

    @cached_property
    def mod_by_id(self) -> dict[str, Mod]:
        return {m.unique_name: m for m in self.mods.mods}


def dataset_hash(payloads: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name in sorted(payloads):
        digest.update(name.encode() + b"\0" + payloads[name] + b"\0")
    return digest.hexdigest()[:16]


def load(gamedata_dir: Path) -> GameData:
    def read(name: str) -> bytes:
        return (gamedata_dir / name).read_bytes()

    raw_meta = json.loads(read("meta.json"))
    version = raw_meta.get("schema_version") if isinstance(raw_meta, dict) else None
    expected = Meta.model_fields["schema_version"].default
    if version != expected:
        raise ValueError(f"{gamedata_dir}: schema version {version}, this code reads {expected}")
    meta = Meta.model_validate(raw_meta)
    payloads = {name: read(name) for name in DATA_FILES}
    if dataset_hash(payloads) != meta.dataset_hash:
        raise ValueError(f"{gamedata_dir}: files do not match meta.json dataset_hash")
    return GameData(
        meta=meta,
        weapons=TypeAdapter(list[Weapon]).validate_json(payloads["weapons.json"]),
        mods=ModsFile.model_validate_json(payloads["mods.json"]),
        arcanes=TypeAdapter(list[Arcane]).validate_json(payloads["arcanes.json"]),
        joins=TypeAdapter(list[Join]).validate_json(payloads["joins.json"]),
        incarnon=TypeAdapter(list[Incarnon]).validate_json(payloads["incarnon.json"]),
    )
