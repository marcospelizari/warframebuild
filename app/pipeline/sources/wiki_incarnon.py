"""Incarnon perks from saved wiki pages (T2): `Incarnon_Evolutions` (Genesis tables, one
column per variant) and the native weapons' own pages. Wiki-derived: CC BY-NC-SA 3.0.

Rows: perk name, description bullets, per-variant values ("X = 24<br>Y = 30"), notes.
EVO1 (the form itself) is skipped; Incarnon Form stats come from WFCD attacks.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from app.pipeline.errors import RefreshError

GENESIS = "Incarnon_Evolutions"
NATIVE = ("Felarx", "Innodem", "Laetum", "Onos", "Phenmor", "Praedos", "Ruvox", "Thalys")
SUFFIX = ".wikitext"

_BLOCK = re.compile(
    r"\{\{CustomCollapsible\|([^|}]+)\|.*?\n(.*?)\{\{CustomCollapsible/End\}\}", re.S
)
_NATIVE_TABLE = re.compile(r"===\s*Evolutions\s*===.*?\n(\{\|.*?\n\|\})", re.S)
_VARIANT = re.compile(r"^!.*\{\{Weapon\|([^|}]+)")
_TIER = re.compile(r"^!.*EVO\s*(\d)")
_CELL = re.compile(r"^\|(?![-}+])\s*(?:(?P<attrs>[^|\[{]*=[^|\[{]*)\|)?(?P<body>.*)$")
_COLSPAN = re.compile(r'colspan="?(\d+)')
_VALUE = re.compile(r"\b([XYZ]) = ([^<\n]+)", re.I)
_TEMPLATE = re.compile(r"\{\{([^{}]*)\}\}")


@dataclass(frozen=True)
class RawPerk:
    weapon: str  # display name of one variant
    tier: int
    name: str
    lines: list[str]
    notes: list[str]


def load(wiki_dir: Path) -> list[RawPerk]:
    out = genesis(_read(wiki_dir, GENESIS))
    for stem in NATIVE:
        out += native(stem.replace("_", " "), _read(wiki_dir, stem))
    return out


def genesis(text: str) -> list[RawPerk]:
    out: list[RawPerk] = []
    for block, body in _BLOCK.findall(text):
        out += _table(block, body, None)
    return out


def native(weapon: str, text: str) -> list[RawPerk]:
    table = _NATIVE_TABLE.search(text)
    if table is None:
        raise RefreshError(f"{weapon}: no Evolutions table")
    return _table(weapon, table.group(1), weapon)


def clean(text: str) -> str:
    text = re.sub(r"\[\[File:[^\]]*\]\]", "", text)
    text = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]*)\]\]", r"\1", text)
    while _TEMPLATE.search(text):
        text = _TEMPLATE.sub(lambda m: m.group(1).split("|")[-1], text)
    text = re.sub(r"<[^>]+>", " ", text).replace("'''", "").replace("''", "")
    return re.sub(r"\s+", " ", text).strip()


def _read(wiki_dir: Path, stem: str) -> str:
    return (wiki_dir / f"{stem}{SUFFIX}").read_text(encoding="utf-8")


def _table(block: str, body: str, single: str | None) -> list[RawPerk]:
    rows = re.split(r"\n\|-", body)
    variants = [single] if single else [m for r in rows[:2] for m in _variants(r)]
    if not variants:
        raise RefreshError(f"Incarnon {block}: no weapon columns")
    out: list[RawPerk] = []
    tier = 0
    for row in rows:
        lines = row.strip("\n").split("\n")
        for line in lines:
            if m := _TIER.match(line):
                tier = int(m.group(1))
        cells = _cells(lines)
        if tier < 2 or len(cells) < 2:
            continue
        name, desc = clean(cells[0][1]), cells[1][1]
        values: list[dict[str, str]] = []
        rest = cells[2:]
        if not single:
            while rest and len(values) < len(variants):
                span, text = rest.pop(0)
                found = {k.upper(): v for k, v in _VALUE.findall(text)}
                if not found and clean(text) != "-":
                    raise RefreshError(f"Incarnon {block} {name}: value cell {clean(text)!r}")
                values += [found] * span
            if len(values) != len(variants):
                raise RefreshError(f"Incarnon {block} {name}: {len(values)} value cells")
        notes = _bullets(rest[0][1]) if rest else []
        for i, weapon in enumerate(variants):
            filled = _fill(desc, values[i] if values else {})
            out.append(RawPerk(str(weapon), tier, name, _bullets(filled), notes))
    return out


def _variants(row: str) -> list[str]:
    return [m.group(1).strip() for ln in row.split("\n") if (m := _VARIANT.match(ln))]


def _cells(lines: list[str]) -> list[tuple[int, str]]:
    """(colspan, raw body) per `|` cell; continuation lines belong to the cell above."""
    cells: list[tuple[int, str]] = []
    for line in lines:
        if line.startswith("|}"):
            break
        if line.startswith("!"):
            continue
        m = _CELL.match(line)
        if m:
            colspan = _COLSPAN.search(m.group("attrs") or "")
            cells.append((int(colspan.group(1)) if colspan else 1, m.group("body")))
        elif cells:
            span, text = cells[-1]
            cells[-1] = (span, f"{text}\n{line}")
    return cells


def _fill(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = re.sub(rf"(?<![A-Za-z]){key}(?![A-Za-z])", value.strip(), text)
    return text.replace("%%", "%")


def _bullets(text: str) -> list[str]:
    out = [clean(ln.lstrip("*")) for ln in text.split("\n") if ln.startswith("*")]
    if not out and clean(text) not in ("", "-"):
        out = [clean(text)]
    return [ln for ln in out if ln]
