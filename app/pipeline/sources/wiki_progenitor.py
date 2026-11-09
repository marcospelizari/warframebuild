"""Kuva / Tenet / Coda bonus element from the saved `<Family>_Weapons` pages (T2).

Guns: the page's "Obtained" checklist. Element choices and share range: its "Elemental
Bonus" section. Wiki-derived: CC BY-NC-SA 3.0 (NOTICE).
"""

import re
from dataclasses import dataclass
from pathlib import Path

from app.domain.effects import DamageType
from app.pipeline.errors import RefreshError

PAGES = ("Kuva_Weapons", "Tenet_Weapons", "Coda_Weapons")
SUFFIX = ".wikitext"

_OBTAINED = re.compile(r"=== *Obtained *===\s*\{\{Checklist\|(.*?)\n\}\}", re.S)
_BONUS = re.compile(r"=== *Elemental Bonus *===(.*?)\n=", re.S)
_WEAPON = re.compile(r"\{\{Weapon\|([^}|]+)")
_TYPE = re.compile(r"\{\{D\|([^}|]+)\}\}")
_RANGE = re.compile(r"ranging from (\d+)-(\d+)%")


@dataclass(frozen=True)
class Progenitor:
    page: str
    guns: frozenset[str]  # display names
    elements: tuple[DamageType, ...]
    max_share: float  # of base damage


def load(wiki_dir: Path) -> dict[str, Progenitor]:
    """Gun name -> its family's bonus element rule."""
    out: dict[str, Progenitor] = {}
    for stem in PAGES:
        p = parse(stem, (wiki_dir / f"{stem}{SUFFIX}").read_text(encoding="utf-8"))
        for gun in p.guns:
            if gun in out:
                raise RefreshError(f"{stem}: {gun} listed on two family pages")
            out[gun] = p
    return out


def parse(stem: str, text: str) -> Progenitor:
    obtained = _OBTAINED.search(text)
    bonus = _BONUS.search(text)
    if not obtained or not bonus:
        raise RefreshError(f"{stem}: no 'Obtained' checklist or 'Elemental Bonus' section")
    guns = frozenset(n.strip() for n in _WEAPON.findall(obtained.group(1)))
    shares = _RANGE.search(bonus.group(1))
    if not guns or not shares:
        raise RefreshError(f"{stem}: no guns or no bonus range")
    try:
        elements = tuple(DamageType(t.strip().lower()) for t in _TYPE.findall(bonus.group(1)))
    except ValueError as error:
        raise RefreshError(f"{stem}: unknown bonus type ({error})") from error
    if not elements:
        raise RefreshError(f"{stem}: no bonus types")
    return Progenitor(stem, guns, elements, int(shares.group(2)) / 100)
