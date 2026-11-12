"""CPU work off the event loop, bounded (PLAN E6/E7, C5).

A job takes a permit; the permit is released only when the job really ends, never at the
request timeout or on a client disconnect, so `size` jobs run at most. At most `queue` jobs
wait for a permit; more is `Busy` (503 + Retry-After). A request stops waiting at `timeout`;
a job still running at `HARD_FACTOR` x `timeout` restarts the pool, which ends it.
"""

import asyncio
from collections.abc import Callable
from concurrent.futures import (
    BrokenExecutor,
    Executor,
    Future,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
)
from multiprocessing import get_context
from typing import Any

HARD_FACTOR = 2


class Busy(Exception):
    """No permit free and the waiting queue is full."""


class TimedOut(Exception):
    """The request stopped waiting; the job keeps its permit until it ends."""


class Restarted(Exception):
    """The job's worker pool died (a stuck job's restart, or a crashed worker)."""


class Runner:
    def __init__(
        self,
        size: int,
        queue: int,
        timeout: float,
        processes: bool,
        initializer: Callable[..., None] | None = None,
        initargs: tuple[Any, ...] = (),
    ) -> None:
        self.size, self.queue, self.timeout = size, queue, timeout
        self._processes, self._init = processes, (initializer, initargs)
        self._pool: Executor | None = None
        self._free = size
        self._waiting = 0
        self._wake: asyncio.Event | None = None
        self._closed = False  # shut down (old release, U11): new jobs go to the new runner
        self.restarts = 0

    @property
    def running(self) -> int:
        return self.size - self._free

    async def run(self, fn: Callable[..., Any], *args: Any) -> Any:
        loop = asyncio.get_running_loop()
        if self._wake is None:
            self._wake = asyncio.Event()
        if self._free == 0 and self._waiting >= self.queue:
            raise Busy
        self._waiting += 1
        try:
            while self._free == 0:
                self._wake.clear()
                await self._wake.wait()
        finally:
            self._waiting -= 1
        if self._closed:
            raise Restarted
        self._free -= 1
        try:
            job = self._submit(fn, args)
        except BaseException:
            self._release()
            raise
        job.add_done_callback(lambda _: self._release_from(loop))
        try:
            return await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(job)), self.timeout)
        except TimeoutError:
            loop.call_later(self.timeout * (HARD_FACTOR - 1), self._check_stuck, job)
            raise TimedOut from None
        except BrokenExecutor:
            raise Restarted from None

    def shutdown(self) -> None:
        """Running jobs finish and deliver their results; no new job starts here."""
        self._closed = True
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)
            self._pool = None

    def _submit(self, fn: Callable[..., Any], args: tuple[Any, ...]) -> Future[Any]:
        """A pool broken by a crashed worker is replaced once, so the app keeps serving."""
        try:
            return self._executor().submit(fn, *args)
        except BrokenExecutor:
            self._pool = None
            return self._executor().submit(fn, *args)

    def _release_from(self, loop: asyncio.AbstractEventLoop) -> None:
        """Done-callback, on a pool thread: release on the loop that took the permit."""
        try:
            loop.call_soon_threadsafe(self._release)
        except RuntimeError:  # that loop is closed: nobody waits on it any more
            self._release()

    def _release(self) -> None:
        self._free += 1
        if self._wake is not None:
            self._wake.set()

    def _executor(self) -> Executor:
        if self._pool is None:
            initializer, initargs = self._init
            if self._processes:
                self._pool = ProcessPoolExecutor(
                    self.size, get_context("spawn"), initializer, initargs
                )
            else:
                self._pool = ThreadPoolExecutor(self.size, "runner", initializer, initargs)
        return self._pool

    def _check_stuck(self, job: Future[Any]) -> None:
        """Past the hard limit: kill the pool's processes; their jobs end with an error,
        which releases their permits. Threads cannot be killed: their permit stays."""
        if job.done() or not isinstance(self._pool, ProcessPoolExecutor):
            return
        pool, self._pool = self._pool, None
        self.restarts += 1
        # ProcessPoolExecutor has no public kill before Python 3.14 (terminate_workers).
        for process in list(pool._processes.values()):
            process.kill()
        pool.shutdown(wait=False, cancel_futures=True)
