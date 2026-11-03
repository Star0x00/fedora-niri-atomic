"""Shared helpers for the image build pipeline."""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, Iterable, Sequence

Config = dict[str, Any]

SECTIONS = ("repos", "packages", "extras", "system")


def print_step(message: str) -> None:
    print(f"\n==> {message}")


def print_bullets(items: Iterable[str]) -> None:
    for item in items:
        print(f"  - {item}")


def run_cmd(dry_run: bool, cmd: str, args: Sequence[str] = ()) -> None:
    """Run an external command, or print it when dry-run is set.

    A non-zero exit aborts the build, matching the old nushell pipeline.
    """
    if dry_run:
        print("DRY-RUN: " + " ".join([cmd, *args]))
        return

    subprocess.run([cmd, *args], check=True)


def resolve_project_root() -> Path:
    candidates = ["/tmp/build", "build", "./build"]

    for candidate in candidates:
        if Path(candidate).exists():
            return Path(candidate)

    sys.exit(f"unable to locate build directory, tried: {', '.join(candidates)}")


def load_config(build_root: Path) -> Config:
    """Load every config file, keyed by its top-level TOML section."""
    config = {}

    for section in SECTIONS:
        path = build_root / "config" / f"{section}.toml"
        config[section] = tomllib.loads(path.read_text())[section]

    return config


def dnf_clean(dry_run: bool) -> None:
    run_cmd(dry_run, "dnf", ["clean", "all"])


def ensure_opt_is_dir(dry_run: bool) -> None:
    """Turn /opt into a plain directory.

    The base image ships /opt as a symlink to var/opt, which does not exist, so
    rpm cannot unpack packages that install into /opt. With composefs enabled
    /opt is read-only at runtime and lifecycled with the image, which is what
    the ostree docs recommend for such packages.
    """
    if Path("/opt").is_symlink():
        run_cmd(dry_run, "rm", ["-f", "/opt"])
        run_cmd(dry_run, "mkdir", ["-p", "/opt"])


def dnf_install_lean(dry_run: bool, packages: Sequence[str]) -> None:
    if not packages:
        return

    ensure_opt_is_dir(dry_run)
    print(f"  package-count: {len(packages)}")
    print_bullets(packages)
    run_cmd(
        dry_run,
        "dnf",
        ["install", "-y", "--setopt=install_weak_deps=False", "--nodocs", *packages],
    )


def strip_version_prefix(tag: str, prefix: str) -> str:
    if not prefix:
        return tag
    return tag.removeprefix(prefix)
