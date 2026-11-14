"""Patch-day changes (U1, G90): snapshot of what each entry shows, comparison with the
previous dataset's snapshot, the terminal summary and the full Markdown report."""

import difflib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.gamedata.changes import (
    CHANGES,
    SNAPSHOT,
    Change,
    Changes,
    EntryChange,
    Kind,
    Shown,
    Snapshot,
    read_changes,
    read_snapshot,
)
from app.gamedata.meta import Meta
from app.gamedata.models import Effects, Model
from app.pipeline.build import Dataset
from app.pipeline.build.effects import SwitchedOff

_PLURAL = {Kind.WEAPON: "weapons", Kind.MOD: "mods", Kind.ARCANE: "arcanes", Kind.PERK: "perks"}
_KIND_ORDER = list(_PLURAL)
_CHANGE_ORDER = [Change.CHANGED, Change.NEW, Change.REMOVED]
# Identity, picture and parsed effects are not compared; text comes first, then the fields.
_SKIP = {"unique_name", "slug", "name", "texture_location", "effects", "level_stats"}
_SKIP_MOD = _SKIP | {"description"}
_SKIP_PERK = _SKIP | {"text"}


# ---------- snapshot ----------


def snapshot(dataset: Dataset) -> Snapshot:
    entries: dict[str, Shown] = {}
    for w in dataset.weapons:
        entries[w.unique_name] = Shown(
            kind=Kind.WEAPON, name=w.name, lines=_fields(w, _SKIP), support=None, unparsed=[]
        )
    for m in dataset.mods:
        text = ([m.description] if m.description else []) + _max_rank(m.level_stats)
        entries[m.unique_name] = _shown(Kind.MOD, m.name, text + _fields(m, _SKIP_MOD), m.effects)
    for a in dataset.arcanes:
        text = _max_rank(a.level_stats) + _fields(a, _SKIP)
        entries[a.unique_name] = _shown(Kind.ARCANE, a.name, text, a.effects)
    for i in dataset.incarnon:
        for p in i.perks:
            key = f"{i.unique_name}#{p.name}"
            if key in entries:  # same name on two tiers
                key = f"{key} (tier {p.tier})"
            text = p.text + _fields(p, _SKIP_PERK)
            entries[key] = _shown(Kind.PERK, f"{i.name}: {p.name}", text, p.effects)
    return Snapshot(entries=entries)


def _fields(entry: BaseModel, skip: set[str]) -> list[str]:
    return _flat({k: v for k, v in entry.model_dump(mode="json").items() if k not in skip}, "")


def _shown(kind: Kind, name: str, lines: list[str], effects: Effects) -> Shown:
    return Shown(
        kind=kind, name=name, lines=lines, support=effects.support, unparsed=effects.unparsed
    )


def _max_rank(level_stats: list[list[str]]) -> list[str]:
    return list(level_stats[-1]) if level_stats else []


def _flat(value: Any, path: str) -> list[str]:
    """`attacks[Normal Attack].damage.impact: 18.0`; lists of plain values on one line."""
    if isinstance(value, dict):
        out: list[str] = []
        for k, v in sorted(value.items()):  # source key order is not a change
            out += _flat(v, f"{path}.{k}" if path else k)
        return out
    if isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
        out = []
        for i, v in enumerate(value):
            label = v.get("name", v.get("form", i))
            out += _flat({k: x for k, x in v.items() if k != "name"}, f"{path}[{label}]")
        return out
    if isinstance(value, list):
        return [f"{path}: {', '.join(map(str, value)) or '-'}"]
    return [f"{path}: {'-' if value is None else value}"]


# ---------- comparison ----------


@dataclass(frozen=True)
class Previous:
    """What the dataset being replaced leaves to compare with (read before publishing)."""

    exists: bool
    dataset_hash: str | None
    sources: frozenset[tuple[str, str]]
    snapshot: Snapshot | None
    changes: Changes | None
    unavailable: str | None  # why its snapshot cannot be used


def read_previous(gamedata_dir: Path) -> Previous:
    """Plain read of meta.json (stable keys), so a schema change keeps the comparison."""
    meta_path = gamedata_dir / "meta.json"
    if not meta_path.exists():
        return Previous(False, None, frozenset(), None, None, None)
    try:
        raw = json.loads(meta_path.read_bytes())
        digest = str(raw["dataset_hash"])
        sources = frozenset((str(s["path"]), str(s["sha256_16"])) for s in raw["sources"])
    except (OSError, ValueError, KeyError, TypeError) as error:
        return Previous(True, None, frozenset(), None, None, f"meta.json unreadable ({error})")
    try:
        shown = read_snapshot(gamedata_dir)
    except (OSError, ValueError) as error:
        return Previous(True, digest, sources, None, None, f"{SNAPSHOT} unreadable ({error})")
    try:
        carried = read_changes(gamedata_dir)
    except (OSError, ValueError):
        carried = None  # only lost when the data is unchanged; recomputed otherwise
    missing = None if shown else f"no {SNAPSHOT} (dataset made before the patch report)"
    return Previous(True, digest, sources, shown, carried, missing)


def changes(previous: Previous, shown: Snapshot, meta: Meta) -> Changes:
    sources = frozenset((s.path, s.sha256_16) for s in meta.sources)
    sources_changed = not previous.exists or sources != previous.sources
    if previous.dataset_hash == meta.dataset_hash and previous.changes is not None:
        return previous.changes  # same data: keep the record of how it arrived
    entries = [] if previous.snapshot is None else compare(previous.snapshot, shown)
    return Changes(
        from_hash=previous.dataset_hash,
        to_hash=meta.dataset_hash,
        sources_changed=sources_changed,
        unavailable=previous.unavailable,
        entries=entries,
    )


def compare(before: Snapshot, after: Snapshot) -> list[EntryChange]:
    out = []
    for key in before.entries.keys() | after.entries.keys():
        b, a = before.entries.get(key), after.entries.get(key)
        if a == b:
            continue
        change = Change.NEW if b is None else Change.REMOVED if a is None else Change.CHANGED
        shown = a or b
        assert shown is not None
        out.append(
            EntryChange(
                key=key,
                kind=shown.kind,
                name=shown.name,
                change=change,
                before=b.lines if b else [],
                after=a.lines if a else [],
                support_before=b.support if b else None,
                support_after=a.support if a else None,
                unparsed=a.unparsed if a else [],
            )
        )
    return sorted(out, key=_order)


def _order(c: EntryChange) -> tuple[bool, int, int, str, str]:
    return (
        not c.support_dropped,
        _KIND_ORDER.index(c.kind),
        _CHANGE_ORDER.index(c.change),
        c.name,
        c.key,
    )


@dataclass
class EntryDiff:
    """Names per kind and every touched uniqueName, for the reference-row check (G48)."""

    new: dict[str, list[str]] = field(default_factory=dict)  # kind -> names
    changed: dict[str, list[str]] = field(default_factory=dict)
    removed: dict[str, list[str]] = field(default_factory=dict)
    ids: set[str] = field(default_factory=set)  # every new/changed/removed uniqueName
    unavailable: str | None = None  # previous dataset could not be compared

    @property
    def empty(self) -> bool:
        return self.unavailable is None and not self.ids


def entry_diff(found: Changes) -> EntryDiff:
    if found.unavailable is not None:
        return EntryDiff(unavailable=found.unavailable)
    diff = EntryDiff()
    parts = {Change.NEW: diff.new, Change.CHANGED: diff.changed, Change.REMOVED: diff.removed}
    for change, part in parts.items():
        for kind, plural in _PLURAL.items():
            part[plural] = sorted(
                c.name for c in found.entries if c.kind == kind and c.change == change
            )
    for c in found.entries:
        diff.ids.add(c.key)
        if c.kind == Kind.PERK:
            diff.ids.add(c.key.split("#", 1)[0])  # the gun's rows may read its perks
    return diff


def beside(previous: Previous, shown: Snapshot) -> Callable[[Meta], dict[str, Model]]:
    """Files publish writes next to the dataset, outside its hash."""

    def files(meta: Meta) -> dict[str, Model]:
        return {SNAPSHOT: shown, CHANGES: changes(previous, shown, meta)}

    return files


# ---------- report text ----------


def summary_lines(found: Changes, report: Path | None, off: list[SwitchedOff]) -> list[str]:
    out = []
    if off:
        out.append(f"overrides switched off ({len(off)}): their text changed, rewrite them:")
        out += [f"  {o.key}" for o in off]
    dropped = [c for c in found.entries if c.support_dropped]
    if dropped:
        out.append(f"support dropped ({len(dropped)}), first in the patch report:")
    for c in dropped:
        out.append(f"  {c.name} ({c.kind}): {c.support_before} -> {c.support_after}")
        out += [f"      not modelled: {line}" for line in c.unparsed]
    if report:
        out.append(f"full patch report: {report}")
    return out


def report_markdown(found: Changes, date: str, off: list[SwitchedOff]) -> str:
    out = [
        f"# Patch report {date}",
        "",
        f"Dataset {found.from_hash or '-'} -> {found.to_hash}; "
        f"game files changed: {'yes' if found.sources_changed else 'no'}.",
    ]
    if found.unavailable:
        out += ["", f"No comparison: {found.unavailable}."]
    for o in off:
        out += ["", f"## Override switched off: {o.key}", "", "Written for -> now:"]
        out += _diff(o.written_for, o.now)
    for c in found.entries:
        title = f"{c.name} ({c.kind}, {c.change})"
        if c.support_before != c.support_after and c.support_before and c.support_after:
            title += f": {c.support_before} -> {c.support_after}"
        out += ["", f"## {title}", ""]
        out += [f"Not modelled: {line}" for line in c.unparsed]
        out += _diff(c.before, c.after)
    return "\n".join(out) + "\n"


def _diff(before: list[str], after: list[str]) -> list[str]:
    lines = [d for d in difflib.ndiff(before, after) if d[:2] in ("- ", "+ ")]
    return ["```diff", *lines, "```"] if lines else ["(text unchanged)"]


def write_report(found: Changes, cache_dir: Path, date: str, off: list[SwitchedOff]) -> Path | None:
    """`cache/patch-report-<date>-<hash>.md` when something changed or was not compared."""
    if not found.entries and not found.unavailable and not off:
        return None
    path = cache_dir / f"patch-report-{date}-{found.to_hash}.md"  # two updates a day: two files
    path.write_text(report_markdown(found, date, off), encoding="utf-8")
    return path
