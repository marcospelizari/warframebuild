"""Polite HTTP downloads (V15/S5): fixed User-Agent, <= 1 request/s, retries, size caps."""

import time
import urllib.error
import urllib.request
from collections.abc import Callable
from email.utils import parsedate_to_datetime
from http.client import HTTPMessage
from importlib.metadata import version
from typing import IO

REPO_URL = "https://gitlab.com/warframebuild/warframebuild"
USER_AGENT = f"warframeBuild/{version('warframebuild')} (+{REPO_URL})"
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
MAX_RETRY_AFTER_S = 120.0


class DownloadError(RuntimeError):
    pass


class _HttpsRedirects(urllib.request.HTTPRedirectHandler):
    """A redirect may not leave https (get() checks only the first URL)."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        if not newurl.startswith("https://"):
            raise DownloadError(f"GET {req.full_url}: redirect to non-https {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_HttpsRedirects)


def _default_opener(request: urllib.request.Request, timeout: float) -> object:
    return _OPENER.open(request, timeout=timeout)  # https only, see get()


class PoliteClient:
    def __init__(
        self,
        *,
        min_interval_s: float = 1.0,
        retries: int = 4,
        timeout_s: float = 60.0,
        opener: Callable[[urllib.request.Request, float], object] = _default_opener,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._min_interval_s = min_interval_s
        self._retries = retries
        self._timeout_s = timeout_s
        self._opener = opener
        self._sleep = sleep
        self._clock = clock
        self._last_request: float | None = None

    def get(self, url: str, *, max_bytes: int) -> bytes:
        if not url.startswith("https://"):
            raise DownloadError(f"refusing non-https URL: {url}")
        for attempt in range(self._retries + 1):
            self._wait_turn()
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            try:
                response = self._opener(request, self._timeout_s)
                with response as body:  # type: ignore[attr-defined]
                    data: bytes = body.read(max_bytes + 1)
            except urllib.error.HTTPError as error:
                if error.code not in RETRY_STATUSES or attempt == self._retries:
                    raise DownloadError(f"GET {url}: HTTP {error.code}") from error
                self._sleep(self._retry_delay(error, attempt))
                continue
            except (urllib.error.URLError, TimeoutError) as error:
                if attempt == self._retries:
                    raise DownloadError(f"GET {url}: {error}") from error
                self._sleep(2.0**attempt)
                continue
            if len(data) > max_bytes:
                raise DownloadError(f"GET {url}: larger than {max_bytes} bytes")
            return data
        raise DownloadError(f"GET {url}: retries exhausted")  # pragma: no cover

    def _wait_turn(self) -> None:
        now = self._clock()
        if self._last_request is not None:
            wait = self._min_interval_s - (now - self._last_request)
            if wait > 0:
                self._sleep(wait)
                now += wait
        self._last_request = now

    @staticmethod
    def _retry_delay(error: urllib.error.HTTPError, attempt: int) -> float:
        header = error.headers.get("Retry-After") if error.headers else None
        if header:
            try:
                return min(float(header), MAX_RETRY_AFTER_S)
            except ValueError:
                try:
                    delta = parsedate_to_datetime(header).timestamp() - time.time()
                    return min(max(delta, 0.0), MAX_RETRY_AFTER_S)
                except (TypeError, ValueError):
                    pass
        return float(2.0**attempt)
