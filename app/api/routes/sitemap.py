"""GET /robots.txt and /sitemap.xml (PLAN G88): the home page, every gun's page and good
primers' Primer pages (G49), dated by the served game data."""

from html import escape

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, Response

from app.api.pages import PRIMER, site
from app.api.serving import served

router = APIRouter()


@router.get("/robots.txt", include_in_schema=False)
def robots(request: Request) -> PlainTextResponse:
    return PlainTextResponse(f"User-agent: *\nAllow: /\nSitemap: {site(request)}/sitemap.xml\n")


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap(request: Request) -> Response:
    now = served(request)
    data = now.data
    origin, date = site(request), data.meta.fetched
    good = now.release.good_primers if now.release else frozenset()
    paths = ["/"]
    for w in sorted(data.weapons, key=lambda w: w.slug):
        paths.append(f"/w/{w.slug}")
        if w.slug in good:  # a good primer's Primer tab (G49)
            paths.append(f"/w/{w.slug}/{PRIMER}")
    urls = "".join(
        f"<url><loc>{escape(origin + p)}</loc><lastmod>{date}</lastmod></url>\n" for p in paths
    )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}</urlset>\n"
    )
    return Response(body, media_type="application/xml")
