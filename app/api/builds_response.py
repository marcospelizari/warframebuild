"""A gun's stored builds -> the /builds response, each build scored by `build_response`
(PLAN Q28b, option A)."""

from app.api.build_response import build_response, weapon_ref
from app.api.schemas.build import CalcRequest
from app.api.schemas.stored import (
    AuraChoice,
    BuildsResponse,
    ElementChoice,
    NotModelled,
    Primer,
    StoredBuild,
    VariantBuilds,
)
from app.domain.effects import DamageType
from app.gamedata.builds import Build as Stored
from app.gamedata.builds import PrimerNumbers
from app.gamedata.release import Release
from app.gamedata.store import GameData
from app.optimize.candidates import unmodelled
from app.optimize.primer import assumptions


def expand(data: GameData, release: Release, slug: str) -> bytes:
    """The stored builds of `slug` with every build scored by `build_response`."""
    stored = release.builds(slug)
    weapon = data.weapon_by_slug[slug]
    aura_names = {a.unique_name: a.name for a in data.auras.auras}

    def scored(b: Stored, element: DamageType | None) -> StoredBuild:
        choices = CalcRequest(
            weapon=slug,
            mods=b.mods,
            exilus=b.exilus,
            arcane=b.arcane,
            perks=b.perks,
            bonus_element=element,
        )
        return StoredBuild(
            status=b.status,
            search_scope=b.search_scope,
            evaluations=b.evaluations,
            score=b.score,
            forma=b.forma,
            without=b.without,
            shards=b.shards,
            auras=None
            if b.auras is None
            else [
                AuraChoice(unique_name=a.aura, name=aura_names[a.aura], score=a.score)
                for a in b.auras
            ],
            build=build_response(data, choices),
        )

    out = BuildsResponse(
        release=release.id,
        dataset_hash=release.dataset_hash,
        weapon=weapon_ref(weapon),
        elements=[ElementChoice(**r.model_dump()) for r in stored.elements],
        variants=[
            VariantBuilds(
                element=v.element,
                max=scored(v.max, v.element),
                recommended=scored(v.recommended, v.element),
                factions={f: scored(b, v.element) for f, b in v.factions.items()},
                denominators=v.denominators,
                primer=_primer(scored(v.primer, v.element), v.primer_numbers)
                if v.primer and v.primer_numbers
                else None,
            )
            for v in stored.variants
        ],
        good_primer=slug in release.good_primers,
        not_modelled=[
            NotModelled(
                kind=u.kind,
                name=u.name,
                support=u.effects.support,
                text=[*u.effects.unparsed, *([u.effects.note] if u.effects.note else [])],
            )
            for u in unmodelled(data, weapon)
        ],
    )
    return out.model_dump_json().encode()


def _primer(build: StoredBuild, n: PrimerNumbers) -> Primer:
    return Primer(build=build, **n.model_dump(), assumptions=assumptions())
