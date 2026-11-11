"""C5: permits follow the job, not the request."""

import asyncio
import os
import time

import pytest

from app.api.runner import Busy, Restarted, Runner, TimedOut


def _double(x: int) -> int:
    return 2 * x


async def _until(condition: object, limit: float = 10.0) -> None:
    end = time.monotonic() + limit
    while not condition():  # type: ignore[operator]
        assert time.monotonic() < end, "condition not reached"
        await asyncio.sleep(0.02)


def test_runs_a_job_in_a_process() -> None:
    async def main() -> int:
        runner = Runner(1, 0, 30, processes=True)
        try:
            return int(await runner.run(_double, 21))
        finally:
            runner.shutdown()

    assert asyncio.run(main()) == 42


def test_full_queue_is_busy() -> None:
    async def main() -> None:
        runner = Runner(1, 0, 5, processes=False)
        first = asyncio.ensure_future(runner.run(time.sleep, 0.3))
        await _until(lambda: runner.running == 1)
        with pytest.raises(Busy):
            await runner.run(_double, 1)
        await first
        runner.shutdown()

    asyncio.run(main())


def test_waiting_job_runs_when_a_permit_frees() -> None:
    async def main() -> None:
        runner = Runner(1, 1, 5, processes=False)
        first = asyncio.ensure_future(runner.run(time.sleep, 0.2))
        await _until(lambda: runner.running == 1)
        assert await runner.run(_double, 2) == 4
        await first
        runner.shutdown()

    asyncio.run(main())


def test_timed_out_job_keeps_its_permit_until_it_ends() -> None:
    async def main() -> None:
        runner = Runner(1, 0, 0.1, processes=False)
        with pytest.raises(TimedOut):
            await runner.run(time.sleep, 0.5)
        assert runner.running == 1  # still running: no second job may start
        with pytest.raises(Busy):
            await runner.run(_double, 1)
        await _until(lambda: runner.running == 0)
        runner.shutdown()

    asyncio.run(main())


def test_disconnect_does_not_free_the_permit_early() -> None:
    async def main() -> None:
        runner = Runner(1, 0, 5, processes=False)
        request = asyncio.ensure_future(runner.run(time.sleep, 0.4))
        await _until(lambda: runner.running == 1)
        request.cancel()  # what a client disconnect does to the handler
        await asyncio.sleep(0.05)
        assert runner.running == 1
        await _until(lambda: runner.running == 0)
        runner.shutdown()

    asyncio.run(main())


def test_stuck_process_job_restarts_the_pool() -> None:
    async def main() -> None:
        runner = Runner(1, 0, 0.3, processes=True)
        assert await runner.run(_double, 1) == 2  # pool started
        with pytest.raises(TimedOut):
            await runner.run(time.sleep, 60)
        await _until(lambda: runner.restarts == 1 and runner.running == 0)
        assert await runner.run(_double, 3) == 6  # a fresh pool serves again
        runner.shutdown()

    asyncio.run(main())


def _crash() -> None:
    os._exit(1)  # a worker dying, e.g. out of memory


def test_jobs_in_a_killed_pool_end_as_restarted_and_a_fresh_pool_serves() -> None:
    """Timeout 1 s: the stuck job times out at 1 s and its pool is killed at 2 s; a job
    started at 1.5 s for 0.9 s is still running then and ends as Restarted."""

    async def main() -> None:
        runner = Runner(2, 0, 1.0, processes=True)
        await asyncio.gather(runner.run(time.sleep, 0.5), runner.run(time.sleep, 0.5))  # 2 up
        with pytest.raises(TimedOut):
            await runner.run(time.sleep, 60)
        await asyncio.sleep(0.5)
        with pytest.raises(Restarted):
            await runner.run(time.sleep, 0.9)
        await _until(lambda: runner.restarts == 1 and runner.running == 0)
        assert await runner.run(_double, 4) == 8
        runner.shutdown()

    asyncio.run(main())


def test_crashed_worker_does_not_break_the_runner_for_good() -> None:
    async def main() -> None:
        runner = Runner(1, 0, 10, processes=True)
        with pytest.raises(Restarted):
            await runner.run(_crash)
        await _until(lambda: runner.running == 0)
        assert await runner.run(_double, 5) == 10
        runner.shutdown()

    asyncio.run(main())
