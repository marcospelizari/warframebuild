import pytest
from pydantic import ValidationError

from app.domain.effects import DamageType as D
from app.domain.status_rules import StatusRules

# The numbers the code held before they moved to reference/status_rules.json (U13).
DURATIONS = {
    D.IMPACT: 6.0,
    D.PUNCTURE: 10.0,
    D.SLASH: 6.0,
    D.COLD: 6.0,
    D.ELECTRICITY: 6.0,
    D.HEAT: 6.0,
    D.TOXIN: 6.0,
    D.BLAST: 1.5,
    D.CORROSIVE: 8.0,
    D.GAS: 6.0,
    D.MAGNETIC: 6.0,
    D.RADIATION: 12.0,
    D.VIRAL: 6.0,
    D.VOID: 3.0,
    D.TAU: 8.0,
}
STACKING = {
    D.CORROSIVE: (0.26, 0.06, 10),
    D.VIRAL: (1.0, 0.25, 10),
    D.MAGNETIC: (1.0, 0.25, 10),
    D.PUNCTURE: (0.05, 0.05, 5),
    D.COLD: (0.1, 0.05, 9),
}
DOT = {D.SLASH: (0.35, 1.0), D.HEAT: (0.5, 1.0), D.TOXIN: (0.5, 1.0)}
DOT |= {D.ELECTRICITY: (0.5, 0.0), D.GAS: (0.5, 0.0)}


def test_rules_match_the_numbers_the_code_held(rules: StatusRules) -> None:
    assert {t: rules.duration(t) for t in D} == DURATIONS
    for t, (first, step, cap) in STACKING.items():
        s = rules.stacking(t)
        assert (s.first, s.step, s.cap) == (first, step, cap)
    dots = {t: rules.dot(t) for t in D}
    assert {t: (d.coefficient, d.first_tick_s) for t, d in dots.items() if d} == DOT
    assert rules.heat_strip.steps == (0.15, 0.30, 0.40, 0.50)
    assert rules.heat_strip.step_s == 0.5
    assert (rules.blast.cap, rules.blast.proc, rules.blast.radial) == (10, 0.3, 10.0)


def test_extra_stacks_raise_stacking_and_blast_caps(rules: StatusRules) -> None:
    more = rules.with_extra_stacks({D.CORROSIVE: 2, D.BLAST: 1, D.SLASH: 1})
    assert more.stacking(D.CORROSIVE).cap == 12
    assert more.blast.cap == 11
    assert more.dot(D.SLASH) == rules.dot(D.SLASH)  # no cap to raise
    assert rules.with_extra_stacks({}) is rules


def test_every_type_and_each_mechanic_where_the_model_uses_it(rules: StatusRules) -> None:
    types = dict(rules.types)
    del types[D.TAU]
    with pytest.raises(ValidationError, match="no rule"):
        StatusRules(types=types)
    types = dict(rules.types)
    types[D.SLASH] = types[D.SLASH].model_copy(update={"stacking": rules.stacking(D.VIRAL)})
    with pytest.raises(ValidationError, match="stacking only"):
        StatusRules.model_validate({"types": {t: r.model_dump() for t, r in types.items()}})
