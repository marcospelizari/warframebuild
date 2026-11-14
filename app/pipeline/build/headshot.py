"""reference/headshot.json: the forms aimed at heads (R5). A class row covers every form of
every gun of that WFCD weapon type; a weapon row lists its forms; a `flat_heads` row marks
headshot forms whose heads take 1x; a `separate_extra` row marks a gun whose own headshot
bonus (wiki module ExtraHeadshotDmg) multiplies on top. `source` is a saved page stem (stored
as its canonical title) or "project decision" (stored as None)."""

from typing import Any

from pydantic import ValidationError

from app.gamedata.enemies import ReferenceHead
from app.gamedata.models import Headshot, Weapon
from app.pipeline.build.inputs import require_verified
from app.pipeline.errors import RefreshError

FILE = "headshot.json"
FORMS = ("normal", "incarnon")
PROJECT_DECISION = "project decision"
CLASS_KEYS = {"reason", "source", "verified"}
ROW_KEYS = CLASS_KEYS | {"name", "forms"}
EXTRA_KEYS = CLASS_KEYS | {"name"}
HEAD_KEYS = {"name", "multiplier", "critical", "source", "verified"}


def apply(
    table: dict[str, Any],
    guns: list[Weapon],
    incarnon: set[str],
    titles: dict[str, str],
    excluded: set[str],
) -> tuple[list[Weapon], ReferenceHead]:
    """`titles`: saved page stem -> canonical wiki title (reference/wiki_pages.json);
    rows of `excluded` guns are kept for when they are built."""
    classes: dict[str, Any] = table.get("classes", {})
    rows: dict[str, Any] = table.get("weapons", {})
    flats: dict[str, Any] = table.get("flat_heads", {})
    separate: dict[str, Any] = table.get("separate_extra", {})
    by_id = {w.unique_name: w for w in guns}
    keyed = [(k, r, CLASS_KEYS) for k, r in classes.items()]
    keyed += [(k, r, ROW_KEYS) for k, r in [*rows.items(), *flats.items()]]
    keyed += [(k, r, EXTRA_KEYS) for k, r in separate.items()]
    for key, row, allowed_keys in keyed:
        _check_row(key, row, allowed_keys, titles)
    unknown_types = sorted(classes.keys() - {w.weapon_type for w in guns})
    unknown_guns = sorted((rows.keys() | flats.keys() | separate.keys()) - by_id.keys() - excluded)
    if unknown_types or unknown_guns:
        raise RefreshError(
            f"reference/{FILE}: unknown classes {unknown_types}, guns {unknown_guns}"
        )
    rows, flats, separate = (
        {k: r for k, r in t.items() if k in by_id} for t in (rows, flats, separate)
    )
    for uid in rows:
        if by_id[uid].weapon_type in classes:
            raise RefreshError(f"reference/{FILE} {by_id[uid].name}: already covered by class row")
    for table_rows in (rows, flats):
        for uid, row in table_rows.items():
            _check_forms(by_id[uid], row, FORMS if uid in incarnon else FORMS[:1])
    out = []
    for w in guns:
        row = rows.get(w.unique_name) or classes.get(w.weapon_type)
        if row is None:
            out.append(w)
            continue
        picked: list[Any] = row.get("forms") or list(
            FORMS if w.unique_name in incarnon else FORMS[:1]
        )
        flat = set(flats.get(w.unique_name, {}).get("forms", []))
        source = titles.get(row["source"])
        marks = [
            Headshot(
                form=f,
                reason=row["reason"],
                source=source,
                flat=f in flat,
                separate_extra=w.unique_name in separate,
            )
            for f in picked
        ]
        out.append(w.model_copy(update={"headshot": marks}))
    marked = {w.unique_name: {h.form for h in w.headshot} for w in out}
    for uid, row in flats.items():
        if not set(row["forms"]) <= marked[uid]:
            raise RefreshError(f"reference/{FILE} {row['name']}: flat head on a body form")
    for uid, row in separate.items():
        gun = by_id[uid]
        if row.get("name") != gun.name:
            raise RefreshError(f"reference/{FILE} {uid}: name {row.get('name')!r} is {gun.name!r}")
        if not marked[uid] or not any((a.extra_headshot or 0) > 0 for a in gun.attacks):
            raise RefreshError(
                f"reference/{FILE} {gun.name}: separate_extra needs a headshot gun with a "
                "positive ExtraHeadshotDmg"
            )
    return out, _reference_head(table.get("reference_head"), titles)


def _check_row(key: str, row: Any, allowed_keys: set[str], titles: dict[str, str]) -> None:
    if not isinstance(row, dict):
        raise RefreshError(f"reference/{FILE} {key}: expected an object")
    extra = sorted(row.keys() - allowed_keys)
    if extra:
        raise RefreshError(f"reference/{FILE} {key}: unknown keys {extra}")
    require_verified(row, FILE, key)
    if not isinstance(row.get("reason"), str):
        raise RefreshError(f"reference/{FILE} {key}: `reason` is required")
    if row.get("source") != PROJECT_DECISION and row.get("source") not in titles:
        raise RefreshError(f"reference/{FILE} {key}: source must be a saved page stem")


def _check_forms(gun: Weapon, row: dict[str, Any], allowed: tuple[str, ...]) -> None:
    forms = row.get("forms")
    if row.get("name") != gun.name:
        raise RefreshError(
            f"reference/{FILE} {gun.unique_name}: name {row.get('name')!r} is {gun.name!r}"
        )
    if not (
        isinstance(forms, list)
        and forms
        and len(set(forms)) == len(forms)
        and set(forms) <= set(allowed)
    ):
        raise RefreshError(f"reference/{FILE} {gun.name}: forms must be a subset of {allowed}")


def _reference_head(row: Any, titles: dict[str, str]) -> ReferenceHead:
    if not isinstance(row, dict) or row.keys() != HEAD_KEYS:
        raise RefreshError(f"reference/{FILE}: reference_head needs exactly {sorted(HEAD_KEYS)}")
    require_verified(row, FILE, "reference_head")
    if row["source"] not in titles:
        raise RefreshError(f"reference/{FILE} reference_head: source must be a saved page stem")
    try:
        return ReferenceHead(
            name=row["name"],
            multiplier=row["multiplier"],
            critical=row["critical"],
            source=titles[row["source"]],
        )
    except ValidationError as error:
        raise RefreshError(f"reference/{FILE} reference_head: {error}") from error
