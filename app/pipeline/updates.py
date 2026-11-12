"""Updates page entries (U10, G90): what a new release changed against the current one.

Game text comes from the two releases' snapshots (stable format); builds from their build
files. A gun is listed when a Recommended or faction build gets other mods, exilus,
arcane, Incarnon evolutions, bonus element or element order, when its average kill time
moves by 1% or more, or when its own stats changed.
"""

import json
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from app.domain.effects import DamageType
from app.gamedata.builds import Build, Variant, WeaponBuilds
from app.gamedata.changes import Change, EntryChange, Kind, Snapshot, read_snapshot
from app.gamedata.updates import UPDATES, BuildChange, GunChange, Update, Updates, read_updates
from app.pipeline.changes import compare, read_previous
from app.pipeline.publish import dump

KILL_MOVE = 0.01  # relative change of the average kill time that lists a gun
LISTED = 5  # names written out in a summary sentence


def write(new: Path, previous: Path | None, release_id: str, today: str) -> None:
    """`new/updates.json`: this release's entry (if it changed anything) + the history."""
    previous = previous if previous and previous.is_dir() else None
    history = _history(previous)
    entry = _entry(new, previous, release_id, today) if previous else None
    updates = Updates(updates=[entry, *history] if entry else history)
    (new / UPDATES).write_bytes(dump(updates))
    read_updates(new)  # validation


def _history(previous: Path | None) -> list[Update]:
    if previous is None:
        return []
    try:
        return read_updates(previous).updates
    except (OSError, ValueError):
        return []  # unreadable history: the new entry still goes out


def _entry(new: Path, previous: Path, release_id: str, today: str) -> Update | None:
    before = read_previous(previous / "gamedata")
    after = read_snapshot(new / "gamedata")
    meta = json.loads((new / "gamedata/meta.json").read_bytes())
    sources = frozenset((s["path"], s["sha256_16"]) for s in meta["sources"])
    unavailable = []
    if before.snapshot is None or after is None:
        unavailable.append(f"game text: {before.unavailable or 'new release has no snapshot'}")
        entries: list[EntryChange] = []
    else:
        entries = compare(before.snapshot, after)
    names = _names(before.snapshot, after)
    stats = {c.key for c in entries if c.kind == Kind.WEAPON}
    guns, builds_note = _guns(new, previous, names, stats)
    if builds_note:
        unavailable.append(builds_note)
    text = [c for c in entries if c.kind != Kind.WEAPON]
    if not text and not guns and not unavailable:
        return None
    kind: Literal["game", "calculator"] = "game" if sources != before.sources else "calculator"
    update = Update(
        kind=kind,
        release=release_id,
        date=today,
        game_update=meta.get("game_update"),
        summary=[],
        entries=text,
        guns=guns,
        unavailable=unavailable,
    )
    return update.model_copy(update={"summary": summary(update)})


def _names(before: Snapshot | None, after: Snapshot | None) -> dict[str, str]:
    """uniqueName -> name, newest name winning."""
    out: dict[str, str] = {}
    for snap in (before, after):
        if snap:
            out |= {k: e.name for k, e in snap.entries.items()}
    return out


def _guns(
    new: Path, previous: Path, names: dict[str, str], stats: set[str]
) -> tuple[list[GunChange], str | None]:
    old_files = {p.stem: p for p in (previous / "builds").glob("*.json")}
    new_files = {p.stem: p for p in (new / "builds").glob("*.json")}
    out = []
    try:
        for slug in sorted(old_files.keys() | new_files.keys()):
            old = _load(old_files.get(slug))
            now = _load(new_files.get(slug))
            gun = now or old
            assert gun is not None
            name = names.get(gun.weapon, slug)
            if old is None or now is None:
                change = Change.NEW if old is None else Change.REMOVED
                out.append(
                    GunChange(slug=slug, name=name, change=change, stats_changed=False, builds=[])
                )
                continue
            both = old.variants and now.variants
            builds = _variant_changes(old.variants[0], now.variants[0], names) if both else []
            if builds or gun.weapon in stats:
                out.append(
                    GunChange(
                        slug=slug,
                        name=name,
                        change=Change.CHANGED,
                        stats_changed=gun.weapon in stats,
                        builds=builds,
                    )
                )
    except (OSError, ValidationError) as error:
        first = str(error).splitlines()[0]
        return [], f"builds: previous release unreadable ({first})"
    return sorted(out, key=lambda g: (g.name, g.slug)), None


def _load(path: Path | None) -> WeaponBuilds | None:
    return WeaponBuilds.model_validate_json(path.read_bytes()) if path else None


def _variant_changes(old: Variant, new: Variant, names: dict[str, str]) -> list[BuildChange]:
    pairs = [("recommended", old.recommended, new.recommended)]
    pairs += [(f, old.factions[f], new.factions[f]) for f in new.factions if f in old.factions]
    out = []
    for label, a, b in pairs:
        change = _build_change(label, a, b, old.element, new.element, names)
        if change:
            out.append(change)
    return out


def _build_change(
    label: str,
    old: Build,
    new: Build,
    old_el: DamageType | None,
    new_el: DamageType | None,
    names: dict[str, str],
) -> BuildChange | None:
    def parts(b: Build, element: DamageType | None) -> list[str]:
        picked = [*b.mods, *(x for x in (b.exilus, b.arcane) if x)]
        bonus = [f"{element} bonus"] if element else []
        return [names.get(x, x) for x in picked] + list(b.perks) + bonus

    before, after = parts(old, old_el), parts(new, new_el)
    kill_before, kill_after = _kill(old), _kill(new)
    moved = (
        kill_before is not None
        and kill_after is not None
        and abs(kill_after - kill_before) >= KILL_MOVE * kill_before
    )
    if before == after and not moved:  # order kept: element order counts
        return None
    kept_before = [x for x in before if x in after]
    kept_after = [x for x in after if x in before]
    return BuildChange(
        build=label,
        removed=[x for x in before if x not in after],
        added=[x for x in after if x not in before],
        reordered=kept_before != kept_after,
        kill_before=kill_before,
        kill_after=kill_after,
    )


def _kill(b: Build) -> float | None:
    return 1 / b.score if b.score > 0 else None  # combat scores are 1 / average kill time


# ---------- summary ----------

_KIND_WORDS = {Kind.MOD: "mod", Kind.ARCANE: "arcane", Kind.PERK: "Incarnon evolution"}


def summary(u: Update) -> list[str]:
    out = []
    if u.kind == "calculator":
        out.append("Builds changed by our calculation, not by the game.")
    for kind, word in _KIND_WORDS.items():
        for change in (Change.CHANGED, Change.NEW, Change.REMOVED):
            found = [c.name for c in u.entries if c.kind == kind and c.change == change]
            if found:
                out.append(_sentence(found, word, change))
    stats = [g.name for g in u.guns if g.stats_changed]
    if stats:
        out.append(f"{_count(len(stats), 'gun')} with changed stats: {_list(stats)}.")
    for change in (Change.NEW, Change.REMOVED):
        found = [g.name for g in u.guns if g.change == change]
        if found:
            out.append(f"{_count(len(found), f'{change} gun')}: {_list(found)}.")
    for level, words in (("partial", "only partly calculated"), ("unsupported", "not calculated")):
        found = [c.name for c in u.entries if c.support_dropped and c.support_after == level]
        if found:
            out.append(f"Now {words}: {_list(found)}.")
    rebuilt = [g for g in u.guns if g.builds]
    if rebuilt:
        out.append(_builds_sentence(rebuilt))
    return out


def _sentence(names: list[str], word: str, change: Change) -> str:
    if change == Change.CHANGED:
        return f"{_count(len(names), word)} changed: {_list(names)}."
    return f"{_count(len(names), f'{change} {word}')}: {_list(names)}."


def _builds_sentence(guns: list[GunChange]) -> str:
    faster = slower = 0
    for g in guns:
        main = next((b for b in g.builds if b.build == "recommended"), None)
        if main and main.kill_before is not None and main.kill_after is not None:
            if main.kill_after < main.kill_before * (1 - KILL_MOVE):
                faster += 1
            elif main.kill_after > main.kill_before * (1 + KILL_MOVE):
                slower += 1
    text = f"{_count(len(guns), 'gun')} with changed builds"
    moves = [m for n, m in ((faster, f"{faster} kill faster"), (slower, f"{slower} slower")) if n]
    return f"{text}: {', '.join(moves)}." if moves else f"{text}."


def _count(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _list(names: list[str]) -> str:
    if len(names) <= LISTED:
        return ", ".join(names)
    return f"{', '.join(names[:LISTED])} and {len(names) - LISTED} more"
