import io
import urllib.error
import urllib.request
from email.message import Message
from http.client import HTTPMessage

import pytest

from app.pipeline.sources import http
from app.pipeline.sources.http import USER_AGENT, DownloadError, PoliteClient


class FakeNet:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.requests: list[urllib.request.Request] = []
        self.sleeps: list[float] = []
        self.now = 0.0

    def opener(self, request: urllib.request.Request, timeout: float) -> object:
        self.requests.append(request)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return io.BytesIO(item)  # type: ignore[arg-type]

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def client(self) -> PoliteClient:
        return PoliteClient(opener=self.opener, sleep=self.sleep, clock=lambda: self.now)


def http_error(code: int, retry_after: str | None = None) -> urllib.error.HTTPError:
    headers = Message()
    if retry_after:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError("https://x", code, "err", headers, None)


def test_sends_user_agent_and_spaces_requests() -> None:
    net = FakeNet([b"a", b"b"])
    client = net.client()
    assert client.get("https://x/1", max_bytes=10) == b"a"
    assert client.get("https://x/2", max_bytes=10) == b"b"
    assert net.requests[0].get_header("User-agent") == USER_AGENT
    assert net.sleeps == [1.0]  # second request waits out the 1 s interval


def test_honors_retry_after_on_429() -> None:
    net = FakeNet([http_error(429, "7"), b"ok"])
    assert net.client().get("https://x", max_bytes=10) == b"ok"
    assert 7.0 in net.sleeps


def test_gives_up_on_404() -> None:
    net = FakeNet([http_error(404)])
    with pytest.raises(DownloadError, match="404"):
        net.client().get("https://x", max_bytes=10)


def test_enforces_size_cap() -> None:
    net = FakeNet([b"x" * 11])
    with pytest.raises(DownloadError, match="larger"):
        net.client().get("https://x", max_bytes=10)


def test_refuses_plain_http() -> None:
    with pytest.raises(DownloadError, match="non-https"):
        FakeNet([]).client().get("http://x", max_bytes=10)


def test_a_redirect_may_not_leave_https() -> None:
    handler = http._HttpsRedirects()
    request = urllib.request.Request("https://content.example/a")
    with pytest.raises(DownloadError, match="non-https"):
        handler.redirect_request(request, io.BytesIO(), 302, "Found", HTTPMessage(), "http://x/a")
    kept = handler.redirect_request(
        request, io.BytesIO(), 302, "Found", HTTPMessage(), "https://cdn.example/a"
    )
    assert kept is not None and kept.full_url == "https://cdn.example/a"
