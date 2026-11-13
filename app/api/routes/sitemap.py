"""GET /robots.txt and /sitemap.xml (PLAN G88): the home page and every gun's page, dated
by the served game data."""

from html import escape

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, Response

from app.api.pages import site
from app.api.serving import served

router = APIRouter()


@router.get("/robots.txt", include_in_schema=False)
def robots(request: Request) -> PlainTextResponse:
    return PlainTextResponse(f"User-agent: *\nAllow: /\nSitemap: {site(request)}/sitemap.xml\n")


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap(request: Request) -> Response:
    data = served(request).data
    origin, date = site(request), data.meta.fetched
    paths = ["/", *(f"/w/{w.slug}" for w in sorted(data.weapons, key=lambda w: w.slug))]
    urls = "".join(
        f"<url><loc>{escape(origin + p)}</loc><lastmod>{date}</lastmod></url>\n" for p in paths
    )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}</urlset>\n"
    )
    return Response(body, media_type="application/xml")
