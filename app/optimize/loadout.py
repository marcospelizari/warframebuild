"""A checked build, ready to shoot: build rules, effects in slot order, shot parts per form.

Shared by `evaluate` (arsenal and hit DPS), the conditions and the combat timeline.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.domain import compatibility, families
from app.domain.effects import DamageType, Trigger
from app.domain.elements import ELEMENTS
from app.domain.hit import AttackStats, Bonus
from app.domain.stats import value_for
from app.gamedata.models import (
    Arcane,
    Attack,
    Effects,
    Headshot,
    Incarnon,
    Mod,
    ModSet,
    Perk,
    Weapon,
)
from app.optimize.head import HEAD_TRIGGERS
from app.optimize.shot import Form, Shot, shot

MAX_SLOTS = 8
ZOOM = "Zoom bonus"


class BuildError(ValueError):
    def __init__(self, code: str, message: str, field: str) -> None:
        super().__init__(message)
        self.code, self.message, self.field = code, message, field


def check(
    weapon: Weapon, mods: Sequence[Mod], bonus: DamageType | None, arcane: Arcane | None = None
) -> None:
    """Build rules: arcane class, slots, duplicates, category, compatibility tags (G56),
    families, bonus element."""
    if arcane and (
        arcane.category != weapon.category or arcane.weapon_type not in (None, weapon.weapon_type)
    ):
        raise BuildError("incompatible_arcane", f"{arcane.name} does not fit", "arcane")
    if len(mods) > MAX_SLOTS:
        raise BuildError("too_many_mods", f"at most {MAX_SLOTS} mods", "mods")
    seen: set[str] = set()
    for i, m in enumerate(mods):
        if m.unique_name in seen:
            raise BuildError("duplicate_mod", f"{m.name} equipped twice", f"mods[{i}]")
        seen.add(m.unique_name)
        if m.category != weapon.category:
            raise BuildError("incompatible_mod", f"{m.name} is a {m.category} mod", f"mods[{i}]")
        if not compatibility.fits(
            weapon.compatibility_tags, m.compatibility_tags, m.incompatibility_tags
        ):
            raise BuildError(
                "incompatible_mod", f"{m.name} does not fit {weapon.name}", f"mods[{i}]"
            )
    clash = families.clashes((m.unique_name, m.family) for m in mods)
    if clash:
        names = {m.unique_name: m.name for m in mods}
        a, b = clash[0]
        raise BuildError("family_clash", f"{names[a]} and {names[b]} clash", "mods")
    if bonus is not None:
        allowed = weapon.bonus_element.elements if weapon.bonus_element else []
        if bonus not in allowed:
            raise BuildError(
                "no_bonus_element", f"{weapon.name} has no {bonus} bonus", "bonus_element"
            )
        if bonus not in ELEMENTS:
            raise BuildError("not_supported", f"{bonus} bonus not modelled yet", "bonus_element")


def bonuses(
    weapon: Weapon,
    entries: Sequence[Effects],
    *,
    aiming: bool = False,
    triggers: frozenset[Trigger] = frozenset(),
) -> list[Bonus]:
    """Effects in slot order, max rank (Q33). By default unconditional and hip-fire: what the
    arsenal shows. `triggers`: conditions counted as met, their effects at max stacks (R2)."""
    out: list[Bonus] = []
    for entry in entries:
        for e in entry.effects:
            if e.while_aiming and not aiming:
                continue
            if e.trigger == Trigger.ALWAYS:
                out.append((e, value_for(e, weapon.weapon_type)))
            elif e.trigger in triggers:
                out.append((e, value_for(e, weapon.weapon_type, e.max_stacks)))
    return out


def chosen_perks(incarnon: Incarnon | None, names: Sequence[str]) -> list[Perk]:
    if names and incarnon is None:
        raise BuildError("no_perks", "not an Incarnon weapon", "perks")
    by_name = {p.name: p for p in incarnon.perks} if incarnon else {}
    out: list[Perk] = []
    for i, name in enumerate(names):
        perk = by_name.get(name)
        if perk is None:
            raise BuildError("unknown_perk", f"no perk {name!r}", f"perks[{i}]")
        if any(p.tier == perk.tier for p in out):
            raise BuildError("perk_tier_clash", f"two perks in EVO{perk.tier}", f"perks[{i}]")
        out.append(perk)
    return out


def _parts(
    weapon: Weapon, incarnon: Incarnon | None, form: Form
) -> list[tuple[AttackStats, Attack | None]]:
    """(stats, attack) per part of one shot; normal form = the DE summary + first attack."""
    if form == "normal":
        stats = AttackStats(
            damage=weapon.damage,
            critical_chance=weapon.critical_chance,
            critical_multiplier=weapon.critical_multiplier,
            status_chance=weapon.status_chance,
            multishot=weapon.multishot,
        )
        return [(stats, weapon.attacks[0] if weapon.attacks else None)]  # main attack: step 8
    if incarnon is None:
        raise ValueError(f"{weapon.name} has no Incarnon Form")
    attacks = {a.name: a for a in weapon.attacks}
    return [
        (
            AttackStats(
                damage=a.damage,
                critical_chance=a.critical_chance,
                critical_multiplier=a.critical_multiplier,
                status_chance=a.status_chance,
                multishot=a.multishot or weapon.multishot,
            ),
            a,
        )
        for a in (attacks[n] for n in incarnon.attacks)
    ]


def set_entries(mods: Sequence[Mod], sets: Mapping[str, ModSet]) -> list[tuple[str, Effects]]:
    """One entry per mod set on the gun: the bonus for the pieces equipped on it (DE set
    stats, index = pieces - 1; Vigilante +5% crit tier per piece, saved Critical_Hit:415)."""
    out = []
    for uid, n in sorted(Counter(m.mod_set for m in mods if m.mod_set).items()):
        s = sets.get(uid)
        if s is None:
            raise ValueError(f"mod set {uid} not given")
        name = uid.rsplit("/", 1)[-1].removesuffix("SetMod")
        out.append((f"{name} set ({n}/{s.num_upgrades})", s.bonuses[min(n, len(s.bonuses)) - 1]))
    return out


@dataclass(frozen=True)
class Loadout:
    """A checked build, ready to shoot: shared by `evaluate` and the combat timeline."""

    weapon: Weapon
    form: Form
    picked: list[Perk]
    active: list[Perk]
    named: list[tuple[str, Effects]]  # mods + active perks + arcane + set bonuses
    parts: list[tuple[AttackStats, Attack | None]]
    no_multishot: set[str]
    bonus_element: tuple[DamageType, float] | None
    mark: Headshot | None  # this form is aimed at heads
    sets: list[str]  # mod set entries in `named`
    note: str | None  # main_attack.json limit for this form

    def body_bonuses(self) -> list[Bonus]:
        return bonuses(self.weapon, [e for _, e in self.named])

    def aimed(self) -> list[tuple[str, Effects]]:
        """Entries counted on a form aimed at heads: + the sniper's highest zoom."""
        zoom = self.weapon.zoom
        return self.named + ([(ZOOM, zoom)] if zoom else [])

    def head_bonuses(self, triggered: bool) -> list[Bonus]:
        entries = [e for _, e in self.aimed()]
        triggers = HEAD_TRIGGERS if triggered else frozenset()
        return bonuses(self.weapon, entries, aiming=True, triggers=triggers)

    def shot(self, b: list[Bonus]) -> Shot:
        return shot(self.weapon, self.parts, self.no_multishot, b, self.bonus_element, self.form)


def loadout(
    weapon: Weapon,
    mods: Sequence[Mod],
    bonus: DamageType | None = None,
    incarnon: Incarnon | None = None,
    perks: Sequence[str] = (),
    form: Form | None = None,
    arcane: Arcane | None = None,
    sets: Mapping[str, ModSet] | None = None,
) -> Loadout:
    """`form` defaults to Incarnon Form for Incarnon guns (Q11); `sets`: every mod set of
    `mods` by uniqueName."""
    check(weapon, mods, bonus, arcane)
    picked = chosen_perks(incarnon, perks)
    form = form or ("incarnon" if incarnon else "normal")
    active = [p for p in picked if p.form in ("both", form)]
    share = weapon.bonus_element.max_share if bonus and weapon.bonus_element else None
    set_named = set_entries(mods, sets or {})
    return Loadout(
        weapon=weapon,
        form=form,
        picked=picked,
        active=active,
        named=[(m.name, m.effects) for m in mods]
        + [(p.name, p.effects) for p in active]
        + ([(arcane.name, arcane.effects)] if arcane else [])
        + set_named,
        parts=_parts(weapon, incarnon, form),
        no_multishot=set(incarnon.no_multishot) if incarnon and form == "incarnon" else set(),
        bonus_element=(bonus, share) if bonus is not None and share is not None else None,
        mark=next((h for h in weapon.headshot if h.form == form), None),
        sets=[n for n, _ in set_named],
        note=incarnon.note if incarnon and form == "incarnon" else None,
    )
