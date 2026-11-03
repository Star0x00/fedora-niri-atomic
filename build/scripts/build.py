#!/usr/bin/env python3
"""Top-level orchestrator for the fedora-niri-atomic image build.

The Containerfile calls this once per stage so each stage stays its own layer:

    python3 -B /tmp/build/scripts/build.py /tmp/build --stage repo
    python3 -B /tmp/build/scripts/build.py /tmp/build --stage packages --group desktop
    python3 -B /tmp/build/scripts/build.py /tmp/build --stage finalize
    python3 -B /tmp/build/scripts/build.py /tmp/build --stage system

Add --dry-run to print the commands instead of running them.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

from common import load_config, resolve_project_root  # noqa: E402
from packages import (  # noqa: E402
    finalize_packages,
    install_package_group,
    install_package_groups,
)
from repos import run_repo_stage  # noqa: E402
from system import run_system_stage  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one stage of the image build pipeline.",
    )
    parser.add_argument(
        "build_root",
        nargs="?",
        default=None,
        help="directory containing config/ (default: /tmp/build, build, or ./build)",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="print commands instead of running them",
    )
    parser.add_argument(
        "--stage",
        default="all",
        choices=["repo", "packages", "finalize", "system", "all"],
        help="pipeline stage to run (default: all)",
    )
    parser.add_argument(
        "--group",
        default="",
        help="single package group to install (with --stage packages)",
    )
    args = parser.parse_args()

    root = Path(args.build_root) if args.build_root else resolve_project_root()
    cfg = load_config(root)
    groups = cfg["packages"]["groups"]
    dry = args.dry_run

    print(f"==> using build root: {root}")
    if dry:
        print("==> mode: dry-run")
    print(f"==> stage: {args.stage}")

    if args.stage in ("repo", "all"):
        run_repo_stage(dry, cfg["repos"])

    if args.stage in ("packages", "all"):
        if args.group:
            install_package_group(dry, groups, args.group)
        else:
            install_package_groups(dry, groups)

    if args.stage in ("finalize", "all"):
        finalize_packages(dry, cfg["packages"], cfg["extras"])

    if args.stage in ("system", "all"):
        run_system_stage(dry, cfg["system"])


if __name__ == "__main__":
    main()
