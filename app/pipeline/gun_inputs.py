"""Per-gun input keys for an incremental build-all (G90 U3).

A gun's key hashes everything its search reads: the gun, every mod and arcane that fits it
(with the sets of those mods), its Incarnon perks, the enemies, faction modifiers, the
reference head, the status rules, the Archon Shards and the auras, plus the calculator version and
the budget. A gun whose key matches the current release's copies its builds from there;
any other gun is searched again.
"""

import hashlib
import json
from collections.abc import Sequence

from pydantic import BaseModel

from app.gamedata.store import GameData
from app.optimize.candidates import arcane_fits, fits

INPUTS = "inputs.json"
# GameData fields: read whole by every gun's search (hashed whole), filtered per gun below,
# or never read by the search. A test fails when a new field is in none of them.
SHARED = ("enemies", "factions", "reference_head", "status_rules", "archon_shards", "auras")
PER_GUN = frozenset({"weapons", "mods", "arcanes", "incarnon"})
HASHED = PER_GUN | set(SHARED)
NOT_READ = frozenset({"meta", "joins"})  # provenance and name joins
# Pictures are not search inputs: a new picture must not rebuild a gun.
_SKIP = {"texture_location"}


def gun_keys(data: GameData, calculator: str, budget: int) -> dict[str, str]:
    shared = _digest([calculator, budget, *(_dump(getattr(data, f)) for f in SHARED)])
    sets = {s.unique_name: s for s in data.mods.sets}
    keys = {}
    for gun in data.weapons:
        mods = sorted((m for m in data.mods.mods if fits(gun, m)), key=lambda m: m.unique_name)
        used_sets = sorted({m.mod_set for m in mods if m.mod_set})
        arcanes = sorted(
            (a for a in data.arcanes if arcane_fits(gun, a)), key=lambda a: a.unique_name
        )
        incarnon = data.incarnon_by_id.get(gun.unique_name)
        keys[gun.slug] = _digest(
            [
                shared,
                _dump(gun),
                _dump(mods),
                _dump([sets[s] for s in used_sets if s in sets]),
                _dump(arcanes),
                _dump(incarnon) if incarnon else None,
            ]
        )
    return keys


def _dump(value: BaseModel | Sequence[BaseModel]) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude=_SKIP & set(type(value).model_fields))
    return [_dump(v) for v in value]


def _digest(parts: list[object]) -> str:
    text = json.dumps(parts, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()[:16]
