"""`wfb` command line."""

import argparse
import json
import sys
from pathlib import Path

import uvicorn

from app.api.app import create_app
from app.data import fixtures, refresh

ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wfb")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="run the app on http://127.0.0.1:8000")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    sub.add_parser("openapi", help="print the OpenAPI schema (input for web/src/api/types.ts)")
    ref = sub.add_parser("refresh", help="download sources, rebuild and validate gamedata/")
    ref.add_argument("--offline", action="store_true", help="use files already in cache/raw/")
    ref.add_argument("--no-images", action="store_true", help="skip weapon icon downloads")
    sub.add_parser("fixtures", help="trim cache/raw/ into tests/fixtures/raw/")
    args = parser.parse_args(argv)

    if args.command == "serve":
        uvicorn.run(create_app(), host=args.host, port=args.port)
    elif args.command == "openapi":
        json.dump(create_app().openapi(), sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    elif args.command == "refresh":
        try:
            report = refresh.run(
                refresh.Paths.project(ROOT), offline=args.offline, fetch_images=not args.no_images
            )
        except Exception as error:  # report any failure plainly; gamedata/ is unchanged
            print(f"refresh failed, gamedata/ unchanged: {error}", file=sys.stderr)
            return 1
        print("\n".join(report.lines()))
    elif args.command == "fixtures":
        fixtures.write(ROOT / "cache/raw", ROOT / "tests/fixtures/raw")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
