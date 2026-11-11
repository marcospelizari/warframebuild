"""Jobs the runner's workers execute, and the one helper routes await them through.

A worker holds the game data the app serves: spawned processes load it from the app's
`gamedata/` folder, threads (tests that inject data) get the object. A job returns the
response JSON or an error tuple, since ApiFailure does not cross a process boundary.
"""

from typing import Any

from fastapi import Request

from app.api.build_response import build_response
from app.api.builds_response import expand
from app.api.errors import ApiFailure
from app.api.runner import Busy, Restarted, Runner, TimedOut
from app.api.schemas import CalcRequest
from app.gamedata.release import Release
from app.gamedata.store import GameData, load

Outcome = tuple[bytes, None] | tuple[None, tuple[int, str, str, str | None]]

_data: GameData | None = None


def load_data(source: Any) -> None:
    """Worker initializer: a gamedata/ folder (processes) or the GameData itself (threads)."""
    global _data
    _data = source if isinstance(source, GameData) else load(source)


def _worker_data() -> GameData:
    if _data is None:
        raise RuntimeError("worker started without its game data")
    return _data


def calc(body: str) -> Outcome:
    try:
        built = build_response(_worker_data(), CalcRequest.model_validate_json(body))
    except ApiFailure as failure:
        e = failure.error
        return None, (failure.status, e.code, e.message, e.field)
    return built.model_dump_json().encode(), None


def builds(release: Release, slug: str) -> Outcome:
    try:
        return expand(_worker_data(), release, slug), None
    except FileNotFoundError:  # a later build-all pruned this server's release
        return None, (503, "release_gone", "builds were replaced: restart the app", None)


async def run(request: Request, job: Any, *args: Any) -> bytes:
    """Run `job` on the app's runner; Busy/TimedOut/job errors become API errors."""
    runner: Runner = request.app.state.runner
    try:
        body, error = await runner.run(job, *args)
    except Busy:
        raise ApiFailure(503, "busy", "too many requests in progress", retry_after=1) from None
    except TimedOut:
        raise ApiFailure(503, "timeout", "the request took too long", retry_after=1) from None
    except Restarted:
        raise ApiFailure(503, "restarted", "workers restarted, try again", retry_after=1) from None
    if error is not None:
        status, code, message, field = error
        raise ApiFailure(status, code, message, field)
    assert body is not None
    return bytes(body)
