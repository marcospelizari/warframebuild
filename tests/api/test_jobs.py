"""jobs.run: a job queued on a runner closed for a newer release (U11 review)."""

import asyncio

import pytest

from app.api import jobs
from app.api.errors import ApiFailure
from app.api.runner import Runner


def _ok() -> tuple[bytes, None]:
    return b"ok", None


def test_a_job_on_a_closed_runner_runs_on_the_current_one() -> None:
    async def main() -> bytes:
        old, new = Runner(1, 1, 5, False), Runner(1, 1, 5, False)
        old.shutdown()
        try:
            return await jobs.run(old, _ok, current=lambda: new)
        finally:
            new.shutdown()

    assert asyncio.run(main()) == b"ok"


def test_without_a_newer_runner_it_answers_503_restarted() -> None:
    async def main() -> bytes:
        old = Runner(1, 1, 5, False)
        old.shutdown()
        return await jobs.run(old, _ok, current=lambda: old)

    with pytest.raises(ApiFailure) as raised:
        asyncio.run(main())
    assert raised.value.error.code == "restarted"
