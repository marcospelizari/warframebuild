"""`wfb` command line."""

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

import uvicorn

from app.api.app import create_app
from app.optimize.search import MAX_EVALUATIONS
from app.pipeline import build_all, check, fixtures, frozen_data, refresh, sample, update
from app.pipeline.sources.http import PoliteClient

ROOT = Path(__file__).resolve().parents[1]


def _positive(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be 1 or more, got {value}")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wfb")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="run the app on http://127.0.0.1:8000")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument(
        "--public-origin",
        help="site address for canonical and link-preview URLs, e.g. https://example.org "
        "(default: the address each request came to)",
    )
    serve.add_argument(
        "--forwarded-allow-ips",
        help="proxy addresses whose X-Forwarded-For is trusted for the client address "
        "(rate limit); default $FORWARDED_ALLOW_IPS, else 127.0.0.1 and ::1",
    )
    sub.add_parser("openapi", help="print the OpenAPI schema (input for web/src/api/types.ts)")
    ref = sub.add_parser("refresh", help="download sources, rebuild and validate gamedata/")
    ref.add_argument("--offline", action="store_true", help="use files already in cache/raw/")
    ref.add_argument(
        "--no-images", action="store_true", help="skip gun icon, mod and arcane picture downloads"
    )
    sub.add_parser(
        "fixtures",
        help="trim cache/raw/ into tests/fixtures/raw/, gamedata/ into tests/fixtures/gamedata/",
    )
    chk = sub.add_parser("check", help="after a game update: what changed, what to re-check")
    chk.add_argument("--offline", action="store_true", help="skip the DE/WFCD source check")
    every = sub.add_parser("build-all", help="precompute every gun's builds into a new release")
    every.add_argument("--workers", type=_positive, help="worker processes (default: all CPUs)")
    every.add_argument(
        "--budget", type=_positive, default=MAX_EVALUATIONS, help="evaluations per build (E3)"
    )
    smp = sub.add_parser(
        "sample", help="search the test guns like build-all, publish nothing (minutes, not hours)"
    )
    smp.add_argument("--workers", type=_positive, help="worker processes (default: all CPUs)")
    upd = sub.add_parser(
        "update", help="after a game update: refresh, build-all (changed guns only), what needs you"
    )
    upd.add_argument("--offline", action="store_true", help="use files already in cache/raw/")
    upd.add_argument("--workers", type=_positive, help="worker processes (default: all CPUs)")
    upd.add_argument(
        "--budget", type=_positive, default=MAX_EVALUATIONS, help="evaluations per build (E3)"
    )
    args = parser.parse_args(argv)

    if args.command == "serve":
        app = create_app(public_origin=args.public_origin)
        # No access log: visitor addresses are not stored (S9); errors still go to stderr.
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            forwarded_allow_ips=args.forwarded_allow_ips,
            access_log=False,
            server_header=False,
        )
    elif args.command == "openapi":
        json.dump(create_app().openapi(), sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    elif args.command == "refresh":
        return _guarded(
            lambda: refresh.run(
                refresh.Paths.project(ROOT), offline=args.offline, fetch_images=not args.no_images
            ).lines(),
            "refresh failed, gamedata/ unchanged",
        )
    elif args.command == "check":
        return _guarded(lambda: run_check(offline=args.offline), "check failed")
    elif args.command == "sample":
        return _guarded(
            lambda: sample.run(
                ROOT / "gamedata",
                args.workers,
                progress=lambda line: print(line, file=sys.stderr, flush=True),
            )[-1:],
            "sample failed",
        )
    elif args.command == "build-all":
        return _guarded(
            lambda: build_all.run(
                build_all.Paths.project(ROOT),
                args.workers,
                args.budget,
                lambda line: print(line, file=sys.stderr, flush=True),
            ),
            "build-all failed, current release unchanged",
        )
    elif args.command == "update":
        return _guarded(
            lambda: update.run(
                refresh.Paths.project(ROOT),
                build_all.Paths.project(ROOT),
                offline=args.offline,
                workers=args.workers,
                budget=args.budget,
                progress=lambda line: print(line, file=sys.stderr, flush=True),
            ),
            "update failed",
        )
    elif args.command == "fixtures":
        fixtures.write(ROOT / "cache/raw", ROOT / "tests/fixtures/raw")
        frozen_data.write(ROOT / "gamedata", ROOT / "tests/fixtures/gamedata")
    return 0


def _guarded(task: Callable[[], list[str]], failure: str) -> int:
    """Print the task's lines; on any error print one plain line instead of a traceback."""
    try:
        lines = task()
    except KeyboardInterrupt:
        print(f"{failure}: interrupted", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"{failure}: {error}", file=sys.stderr)
        return 1
    print("\n".join(lines))
    return 0


def run_check(*, offline: bool) -> list[str]:
    paths = refresh.Paths.project(ROOT)
    current, error = refresh.load_previous(paths.gamedata)
    if current is None:
        raise RuntimeError(error or "no gamedata/ yet: run `uv run wfb refresh`")
    meta = current.meta
    changes = None if offline else check.source_changes(PoliteClient(), meta.sources)
    lines = check.source_lines(changes)
    rows = check.reference_rows(paths.reference)
    lines += check.stale_lines(check.stale_rows(rows, meta.changed_on), meta.changed_on)
    lines += check.wiki_lines(paths.raw, paths.reference)
    lines += check.export_plus_lines(paths.raw)
    lines += [f"no builds for {e.name}: {e.reason}" for e in meta.excluded_weapons]  # U7
    if changes:
        lines.append("next: `uv run wfb refresh`, then re-check the rows it lists")
    return lines


if __name__ == "__main__":
    raise SystemExit(main())
