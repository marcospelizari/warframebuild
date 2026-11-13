"""`wfb fixtures`: a frozen slice of gamedata/ for logic tests (G90 U9). A refresh never
touches it, so a balance change in the game does not fail tests of calculator rules."""

import json
import shutil
from pathlib import Path
from typing import Any

from app.gamedata import store

# Guns the optimizer tests use; every mod, arcane, enemy and faction is kept.
GUNS = (
    "Aksondol",
    "Atomos",
    "Braton Prime",
    "Burston Prime",
    "Cedo Prime",
    "Cernos Prime",
    "Furis",
    "Hek",
    "Ignis Wraith",
    "Komorex",
    "Kunai",
    "Kuva Hind",
    "Laetum",
    "Latron Prime",
    "Lenz",
    "Lex Prime",
    "Nataruk",
    "Nunchasa",
    "Onos",
    "Opticor",
    "Paris Prime",
    "Rubico Prime",
    "Soma Prime",
    "Torid",
    "Vectis Prime",
    "Vulkar Wraith",
)
TRIMMED = ("weapons.json", "joins.json", "incarnon.json")  # filtered to GUNS


def write(gamedata_dir: Path, out_dir: Path) -> None:
    """Copy the data files with only GUNS left in TRIMMED, recompute the dataset hash and
    load the result; the old copy is replaced only on success."""
    staging = out_dir.with_name(f".{out_dir.name}.staging")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        ids = _gun_ids(gamedata_dir)
        payloads = {name: _payload(gamedata_dir / name, name, ids) for name in store.DATA_FILES}
        for name, data in payloads.items():
            (staging / name).write_bytes(data)
        meta = json.loads((gamedata_dir / "meta.json").read_text(encoding="utf-8"))
        meta["dataset_hash"] = store.dataset_hash(payloads)
        (staging / "meta.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
        store.load(staging)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    shutil.rmtree(out_dir, ignore_errors=True)
    staging.rename(out_dir)


def _gun_ids(gamedata_dir: Path) -> set[str]:
    rows = json.loads((gamedata_dir / "weapons.json").read_text(encoding="utf-8"))
    ids = {r["unique_name"] for r in rows if r["name"] in GUNS}
    found = {r["name"] for r in rows if r["unique_name"] in ids}
    if found != set(GUNS) or len(ids) != len(GUNS):
        raise ValueError(
            f"frozen gamedata: guns missing or named twice: {sorted(set(GUNS) ^ found)}"
        )
    return ids


def _payload(path: Path, name: str, ids: set[str]) -> bytes:
    if name not in TRIMMED:
        return path.read_bytes()
    rows: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    kept = [r for r in rows if r["unique_name"] in ids]
    return (json.dumps(kept, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
