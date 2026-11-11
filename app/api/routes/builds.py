"""GET /api/weapons/{slug}/builds: a gun's precomputed builds from the current release, each
scored by the /calc code (PLAN Q28b, option A); never a search. ETag = release id."""

from fastapi import APIRouter, Request, Response

from app.api.build_response import build_response, weapon_ref
from app.api.errors import ApiFailure
from app.api.schemas import (
    ApiError,
    BuildsResponse,
    CalcRequest,
    ElementChoice,
    StoredBuild,
    VariantBuilds,
)
from app.domain.effects import DamageType
from app.gamedata.builds import Build as Stored
from app.gamedata.release import Release
from app.gamedata.store import GameData

ERRORS: dict[int | str, dict[str, object]] = {
    404: {"model": ApiError},
    503: {"model": ApiError},
}

router = APIRouter()


@router.get("/api/weapons/{slug}/builds", response_model=BuildsResponse, responses=ERRORS)
def builds(slug: str, request: Request) -> Response:
    data: GameData = request.app.state.data
    release: Release | None = request.app.state.release
    if release is None:
        raise ApiFailure(503, "no_release", "no builds yet: run `uv run wfb build-all`")
    if release.dataset_hash != data.meta.dataset_hash:
        raise ApiFailure(503, "release_mismatch", "the release was built from other game data")
    if slug not in data.weapon_by_slug:  # also keeps `slug` from naming any other file
        raise ApiFailure(404, "unknown_weapon", "no such weapon", "slug")
    headers = {"ETag": f'"{release.id}"', "Cache-Control": "no-cache"}
    if request.headers.get("if-none-match") == headers["ETag"]:
        return Response(status_code=304, headers=headers)
    try:
        body = request.app.state.expanded_builds(slug)
    except FileNotFoundError as error:  # a later build-all pruned this server's release
        raise ApiFailure(503, "release_gone", "builds were replaced: restart the app") from error
    return Response(body, media_type="application/json", headers=headers)


def expand(data: GameData, release: Release, slug: str) -> bytes:
    """The stored builds of `slug` with every build scored by `build_response`."""
    stored = release.builds(slug)

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
            build=build_response(data, choices),
        )

    out = BuildsResponse(
        release=release.id,
        dataset_hash=release.dataset_hash,
        weapon=weapon_ref(data.weapon_by_slug[slug]),
        elements=[ElementChoice(**r.model_dump()) for r in stored.elements],
        variants=[
            VariantBuilds(
                element=v.element,
                max=scored(v.max, v.element),
                recommended=scored(v.recommended, v.element),
                factions={f: scored(b, v.element) for f, b in v.factions.items()},
                denominators=v.denominators,
            )
            for v in stored.variants
        ],
    )
    return out.model_dump_json().encode()
