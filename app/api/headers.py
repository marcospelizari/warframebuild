"""Response headers on every answer (PLAN S6, G88): security headers, compression, and
long caching for the built frontend's hashed files."""

from fastapi import FastAPI, Request, Response
from starlette.middleware.gzip import GZipMiddleware

# Fonts are inlined by Vite as data: URLs; React sets styles through the DOM (no inline
# <style> or style="" in the HTML); no other origin is ever contacted.
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
    "font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'none'"
)
SECURITY = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",  # frame-ancestors for old browsers
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
}
HSTS = "max-age=31536000"  # sent only when the public origin is https (behind TLS)
ASSETS = "/assets/"  # Vite output: file names carry a content hash
CACHE_FOREVER = "public, max-age=31536000, immutable"


def install(app: FastAPI, https: bool) -> None:
    @app.middleware("http")
    async def headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response: Response = await call_next(request)
        response.headers.update(SECURITY)
        if https:
            response.headers["Strict-Transport-Security"] = HSTS
        if request.url.path.startswith(ASSETS) and response.status_code == 200:
            response.headers["Cache-Control"] = CACHE_FOREVER
        return response

    app.add_middleware(GZipMiddleware, minimum_size=1024)
