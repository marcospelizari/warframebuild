"""HTML for page URLs (PLAN G88): index.html with the page's title, description,
canonical URL and link-preview tags, so crawlers and chat previews see each gun without
running JavaScript. An unknown gun or faction gets a real 404 (the app shows its own page)."""

import re
from dataclasses import dataclass
from html import escape
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.api.serving import served
from app.gamedata.builds import Build, Variant, WeaponBuilds
from app.gamedata.models import Weapon
from app.gamedata.release import Release
from app.gamedata.store import GameData

# web/index.html marks the block this module replaces.
BLOCK = re.compile(r"<!-- page-meta -->.*?<!-- /page-meta -->", re.DOTALL)
SITE = "warframeBuild"
SCORED = "Calculated against level 120 Steel Path enemies."
PRIMER = "primer"  # /w/<slug>/primer; no faction has this name
PRIMED = "Statuses that make follow-up hits stronger, against level 120 Steel Path enemies."

router = APIRouter()


@dataclass(frozen=True)
class Meta:
    title: str
    description: str
    path: str  # canonical path
    image: str | None = None
    noindex: bool = False


ORIGIN = re.compile(r"https?://[A-Za-z0-9.-]+(:[0-9]{1,5})?")


def origin(value: str) -> str:
    """The site's public address (scheme + host), checked at startup."""
    value = value.rstrip("/")
    if not ORIGIN.fullmatch(value):
        raise ValueError(f"public origin must look like https://example.org, got {value!r}")
    return value


def faction_slug(name: str) -> str:
    return name.lower().replace(" ", "-")


def render(page: str, meta: Meta, site: str) -> str:
    url = site + meta.path
    tags = [
        f"<title>{escape(meta.title)}</title>",
        f'<meta name="description" content="{escape(meta.description)}" />',
        f'<link rel="canonical" href="{escape(url)}" />',
        '<meta property="og:type" content="website" />',
        f'<meta property="og:site_name" content="{SITE}" />',
        f'<meta property="og:title" content="{escape(meta.title)}" />',
        f'<meta property="og:description" content="{escape(meta.description)}" />',
        f'<meta property="og:url" content="{escape(url)}" />',
        '<meta name="twitter:card" content="summary" />',
    ]
    if meta.image:
        tags.append(f'<meta property="og:image" content="{escape(site + meta.image)}" />')
    if meta.noindex:
        tags.append('<meta name="robots" content="noindex" />')
    block = "<!-- page-meta -->\n    " + "\n    ".join(tags) + "\n    <!-- /page-meta -->"
    return BLOCK.sub(lambda _: block, page, count=1)


def _summary(data: GameData, build: Build) -> str:
    names = [data.mod_by_id[m].name for m in build.mods if m in data.mod_by_id]
    shown = ", ".join(names[:3])
    more = f" and {len(names) - 3} more mods" if len(names) > 3 else ""
    forma = f", {build.forma.forma} forma" if build.forma else ""
    arcane = data.arcane_by_id.get(build.arcane or "")
    return f"{shown}{more}{forma}{f', {arcane.name}' if arcane else ''}."


def _stored(release: Release | None, slug: str) -> WeaponBuilds | None:
    if release is None:
        return None
    try:
        return release.builds(slug)
    except (OSError, ValueError):
        return None


def weapon_meta(
    data: GameData, release: Release | None, gun: Weapon, faction: str | None
) -> Meta | None:
    """None: no such faction among the gun's stored builds. `faction` "primer": the Primer
    build (G49)."""
    stored = _stored(release, gun.slug)
    variant = stored.variants[0] if stored and stored.variants else None
    image = f"/img/weapons/{gun.slug}.png"
    if faction == PRIMER:
        return _primer_meta(data, gun, variant, image)
    if faction is None:
        line = (
            f"Recommended {gun.name} build: {_summary(data, variant.recommended)} "
            if variant
            else ""
        )
        return Meta(
            f"{gun.name} build: mods, forma, arcane | {SITE}",
            f"{line}{SCORED}".strip(),
            f"/w/{gun.slug}",
            image,
        )
    if variant is None:  # no builds to check the faction against: the app explains
        return Meta(f"{gun.name} build | {SITE}", SCORED, f"/w/{gun.slug}/{faction}", image)
    name = next((f for f in variant.factions if faction_slug(f) == faction), None)
    if name is None:
        return None
    return Meta(
        f"{gun.name} build against {name} | {SITE}",
        f"{gun.name} build against {name}: {_summary(data, variant.factions[name])} {SCORED}",
        f"/w/{gun.slug}/{faction}",
        image,
    )


def _primer_meta(data: GameData, gun: Weapon, variant: Variant | None, image: str) -> Meta | None:
    if variant is None:
        return Meta(f"{gun.name} primer build | {SITE}", PRIMED, f"/w/{gun.slug}/{PRIMER}", image)
    if variant.primer is None or variant.primer_numbers is None:
        return None
    n = variant.primer_numbers
    reach = f"about {n.enemies:.0f} enemies" if n.enemies >= 1.5 else "one enemy"
    line = f"Primes {reach}: follow-up hits do {n.boost:.1f}x damage."
    return Meta(
        f"{gun.name} primer build: status mods | {SITE}",
        f"{gun.name} primer build: {_summary(data, variant.primer)} {line} {PRIMED}",
        f"/w/{gun.slug}/{PRIMER}",
        image,
    )


def site(request: Request) -> str:
    # Behind a proxy the request's own scheme/host can be wrong or forged: prefer the
    # configured address; the request's is for local runs.
    return request.app.state.public_origin or str(request.base_url).rstrip("/")


def _page(request: Request, slug: str, faction: str | None) -> HTMLResponse:
    index: Path = request.app.state.web_dist / "index.html"
    page = index.read_text(encoding="utf-8")
    now = served(request)
    data: GameData = now.data
    gun = data.weapon_by_slug.get(slug)
    meta = weapon_meta(data, now.release, gun, faction) if gun else None
    address = site(request)
    if meta is None:
        missing = Meta(f"Page not found | {SITE}", "No such gun or faction.", "/", noindex=True)
        return HTMLResponse(render(page, missing, address), status_code=404)
    noindex = "b" in request.query_params  # an edited build: index the plain page only
    meta = Meta(meta.title, meta.description, meta.path, meta.image, noindex)
    return HTMLResponse(render(page, meta, address))


UPDATES = Meta(
    f"Game updates | {SITE}",
    "What each Warframe update and each calculator change did to the gun builds.",
    "/updates",
)


@router.get("/updates", include_in_schema=False)
def updates_page(request: Request) -> HTMLResponse:
    index: Path = request.app.state.web_dist / "index.html"
    return HTMLResponse(render(index.read_text(encoding="utf-8"), UPDATES, site(request)))


@router.get("/w/{slug}", include_in_schema=False)
def weapon_page(request: Request, slug: str) -> HTMLResponse:
    return _page(request, slug, None)


@router.get("/w/{slug}/{faction}", include_in_schema=False)
def faction_page(request: Request, slug: str, faction: str) -> HTMLResponse:
    return _page(request, slug, faction)
