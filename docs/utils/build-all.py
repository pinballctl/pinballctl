#!/usr/bin/env python3
"""Build docs site, then build screenshots."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

UTILS_DIR = Path(__file__).resolve().parent
DEFAULT_ROOT = UTILS_DIR.parent
DEFAULT_WEBSITE_ROOT = DEFAULT_ROOT.parent / "website"


def _run(cmd: list[str]) -> None:
    print("$ " + " ".join(cmd))
    subprocess.run(cmd, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run build-docs.py then build-screenshots.py")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Docs repo root")
    parser.add_argument(
        "--website-root",
        type=Path,
        default=DEFAULT_WEBSITE_ROOT,
        help="Website repo root used by build-docs.py for shared style.css",
    )
    parser.add_argument("--domain", default="http://127.0.0.1:8888", help="Default screenshot domain")
    parser.add_argument("--username", default="admin", help="Default screenshot username")
    parser.add_argument("--password", default="password", help="Default screenshot password")
    parser.add_argument("--timeout-ms", type=int, default=10000, help="Screenshot timeout")
    parser.add_argument("--headed", action="store_true", help="Run screenshot browser headed")
    parser.add_argument("--dry-run", action="store_true", help="Screenshot dry-run")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing screenshots")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    website_root = args.website_root.resolve()

    build_docs = [
        sys.executable,
        str(UTILS_DIR / "build-docs.py"),
        "--root",
        str(root),
    ]
    if website_root.exists():
        build_docs += ["--website-root", str(website_root)]

    build_shots = [
        sys.executable,
        str(UTILS_DIR / "build-screenshots.py"),
        "--root",
        str(root),
        "--domain",
        args.domain,
        "--username",
        args.username,
        "--password",
        args.password,
        "--timeout-ms",
        str(args.timeout_ms),
    ]
    if args.headed:
        build_shots.append("--headed")
    if args.dry_run:
        build_shots.append("--dry-run")
    if args.overwrite:
        build_shots.append("--overwrite")

    _run(build_docs)
    _run(build_shots)


if __name__ == "__main__":
    main()

