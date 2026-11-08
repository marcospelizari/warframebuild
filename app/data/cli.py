"""`wfb` command line: serve the app, print the OpenAPI schema."""

import argparse
import json
import sys

import uvicorn

from app.api.app import create_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wfb")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="run the app on http://127.0.0.1:8000")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    sub.add_parser("openapi", help="print the OpenAPI schema (input for web/src/api/types.ts)")
    args = parser.parse_args(argv)

    if args.command == "serve":
        uvicorn.run(create_app(), host=args.host, port=args.port)
    elif args.command == "openapi":
        json.dump(create_app().openapi(), sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
