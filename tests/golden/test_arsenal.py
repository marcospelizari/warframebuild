"""Golden builds (PLAN E11, G90 U6): arsenal numbers read in game vs the calculator on the
committed gamedata/. A failure names the build to re-check in game."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from app.domain.effects import DamageType
from app.gamedata.store import GameData
from app.optimize.evaluate import Evaluation, evaluate_loadout
from app.optimize.loadout import loadout

GOLDEN = json.loads((Path(__file__).parent / "arsenal.json").read_text(encoding="utf-8"))
STATS = {  # arsenal row -> calculator value
    "multishot": lambda e: e.hit.multishot,
    "critical_chance": lambda e: e.hit.critical_chance,
    "critical_multiplier": lambda e: e.hit.critical_multiplier,
    "status_chance": lambda e: e.hit.status_chance,
    "fire_rate": lambda e: e.fire_rate,
    "magazine": lambda e: e.magazine,
    "reload_time": lambda e: e.reload_time,
    "total": lambda e: e.hit.arsenal_total,
}


def shown(text: str) -> tuple[float, float]:
    """An arsenal number as displayed -> (value, allowed difference: half the last digit)."""
    scale = Decimal("0.01") if text.endswith("%") else Decimal(1)
    digits = Decimal(text.rstrip("%xs"))
    half = Decimal(1).scaleb(digits.as_tuple().exponent) / 2  # type: ignore[arg-type]
    return float(digits * scale), float(half * scale)


def _evaluate(data: GameData, b: dict[str, Any]) -> Evaluation:
    weapon = next(w for w in data.weapons if w.name == b["gun"])
    mods = {m.name: m for m in data.mods.mods}
    arcane = next((a for a in data.arcanes if a.name == b.get("arcane")), None)
    lo = loadout(
        weapon,
        [mods[n] for n in b["mods"]],
        DamageType(b["bonus_element"]) if b.get("bonus_element") else None,
        data.incarnon_by_id.get(weapon.unique_name),
        b.get("perks", []),
        b["form"],
        arcane,
        data.set_by_id,
        mods[b["exilus"]] if b.get("exilus") else None,
    )
    return evaluate_loadout(lo)


def _value(e: Evaluation, row: str) -> float | None:
    if row in STATS:
        value: float | None = STATS[row](e)
        return value
    return e.hit.arsenal_damage.get(DamageType(row), 0.0)


@pytest.mark.parametrize("b", GOLDEN["builds"], ids=lambda b: b["id"])
def test_calculator_shows_what_the_arsenal_showed(gamedata: GameData, b: dict[str, Any]) -> None:
    e = _evaluate(gamedata, b)
    off = []
    for row, text in b["shows"].items():
        expected, allowed = shown(text)
        got = _value(e, row)
        if got is None or abs(got - expected) > allowed + 1e-9:
            calc = "none" if got is None else f"{got:.6g}"
            off.append(f"{row}: arsenal {text}, calculator {calc}")
    assert not off, f"re-check {b['gun']} ({b['id']}, read {b['read']}) in game: " + "; ".join(off)


def test_shown_reads_the_display_precision() -> None:
    assert shown("96.8%") == pytest.approx((0.968, 0.0005))
    assert shown("3.8x") == pytest.approx((3.8, 0.05))
    assert shown("1152") == pytest.approx((1152, 0.5))
    assert shown("0.6s") == pytest.approx((0.6, 0.05))
