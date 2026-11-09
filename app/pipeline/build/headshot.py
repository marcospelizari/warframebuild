"""reference/headshot.json: the forms aimed at heads (R5). A class row covers every form of
every gun of that WFCD weapon type; a weapon row lists its forms. `source` is a saved page
stem (stored as its canonical title) or "project decision" (stored as None)."""

from typing import Any

from app.gamedata.models import Headshot, Weapon
from app.pipeline.build.inputs import require_verified
from app.pipeline.errors import RefreshError

FILE = "headshot.json"
FORMS = ("normal", "incarnon")
PROJECT_DECISION = "project decision"
CLASS_KEYS = {"reason", "source", "verified"}
ROW_KEYS = CLASS_KEYS | {"name", "forms"}


def apply(
    table: dict[str, Any], guns: list[Weapon], incarnon: set[str], titles: dict[str, str]
) -> list[Weapon]:
    """`titles`: saved page stem -> canonical wiki title (reference/wiki_pages.json)."""
    classes: dict[str, Any] = table.get("classes", {})
    rows: dict[str, Any] = table.get("weapons", {})
    by_id = {w.unique_name: w for w in guns}
    types = {w.weapon_type for w in guns}
    keyed = [(k, r, CLASS_KEYS) for k, r in classes.items()]
    keyed += [(k, r, ROW_KEYS) for k, r in rows.items()]
    for key, row, allowed_keys in keyed:
        extra = sorted(row.keys() - allowed_keys)
        if extra:
            raise RefreshError(f"reference/{FILE} {key}: unknown keys {extra}")
        require_verified(row, FILE, key)
        if not isinstance(row.get("reason"), str):
            raise RefreshError(f"reference/{FILE} {key}: `reason` is required")
        if row.get("source") != PROJECT_DECISION and row.get("source") not in titles:
            raise RefreshError(f"reference/{FILE} {key}: source must be a saved page stem")
    unknown_types = sorted(classes.keys() - types)
    unknown_guns = sorted(rows.keys() - by_id.keys())
    if unknown_types or unknown_guns:
        raise RefreshError(
            f"reference/{FILE}: unknown classes {unknown_types}, guns {unknown_guns}"
        )
    for uid, row in rows.items():
        gun = by_id[uid]
        forms = row.get("forms")
        allowed = FORMS if uid in incarnon else FORMS[:1]
        if gun.weapon_type in classes:
            raise RefreshError(f"reference/{FILE} {gun.name}: already covered by class row")
        if row.get("name") != gun.name:
            raise RefreshError(f"reference/{FILE} {uid}: name {row.get('name')!r} is {gun.name!r}")
        if not (isinstance(forms, list) and forms and len(set(forms)) == len(forms)) or not set(
            forms
        ) <= set(allowed):
            raise RefreshError(f"reference/{FILE} {gun.name}: forms must be a subset of {allowed}")
    out = []
    for w in guns:
        row = rows.get(w.unique_name) or classes.get(w.weapon_type)
        if row is None:
            out.append(w)
            continue
        picked: list[Any] = row.get("forms") or list(
            FORMS if w.unique_name in incarnon else FORMS[:1]
        )
        source = titles.get(row["source"])
        marks = [Headshot(form=f, reason=row["reason"], source=source) for f in picked]
        out.append(w.model_copy(update={"headshot": marks}))
    return out
