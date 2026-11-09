from app.domain.effects import Operation, Stat, Support, Trigger
from app.parse.incarnon import parse_perk


def test_base_stat_lines() -> None:
    parsed, form = parse_perk(
        ["Increase Base Critical Chance by +19%.", "Increase Base Damage by +20."], []
    )
    assert form == "both"
    assert parsed.support == Support.FULL
    assert [(e.stat, e.value, e.operation) for e in parsed.effects] == [
        (Stat.CRITICAL_CHANCE, 0.19, Operation.BASE),
        (Stat.DAMAGE, 20.0, Operation.BASE),
    ]


def test_known_condition_keeps_trigger_and_timing() -> None:
    parsed, _ = parse_perk(["On Kill: Increase Base Damage by +6 for 8 seconds."], [])
    (effect,) = parsed.effects
    assert (effect.trigger, effect.duration_s) == (Trigger.ON_KILL, 8.0)


def test_unknown_condition_is_not_modelled() -> None:
    parsed, _ = parse_perk(["On Shield Break: Increase Base Damage by +80 for 8 seconds."], [])
    assert parsed.effects == []
    assert parsed.support == Support.UNSUPPORTED


def test_form_scope() -> None:
    assert parse_perk(["+50% Reload Speed"], ["Does not affect Incarnon Form"])[1] == "normal"
    assert parse_perk(["Increase Base Status Chance by 10% for Incarnon Form."], [])[1] == (
        "incarnon"
    )


def test_stacking_note_keeps_perk_partial() -> None:
    parsed, _ = parse_perk(
        ["+20% Status Chance"], ["Bonuses are added after mods as a flat value."]
    )
    assert parsed.support == Support.PARTIAL
