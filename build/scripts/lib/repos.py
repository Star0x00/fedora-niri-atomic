"""Repo stage: rpmfusion, external repo files, COPRs, priority overrides."""

from __future__ import annotations

import glob
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence

from common import Config, dnf_clean, print_bullets, print_step, run_cmd

REPO_DIR = "/etc/yum.repos.d"
COPR_REPO_PREFIX = "_copr:copr.fedorainfracloud.org"


def rpm_installed(package: str) -> bool:
    return subprocess.run(["rpm", "-q", package], capture_output=True).returncode == 0


def fedora_version() -> str:
    result = subprocess.run(
        ["rpm", "-E", "%fedora"], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def install_rpmfusion(dry_run: bool, templates: Sequence[str]) -> None:
    # The Containerfile bootstrap already installs rpmfusion, so skip when
    # present instead of downloading it twice.
    if rpm_installed("rpmfusion-free-release"):
        print_step("rpmfusion already installed (bootstrap), skipping")
        return

    fedora = fedora_version()
    urls = [template.replace("{fedora}", fedora) for template in templates]

    print_step("enabling rpmfusion")
    print_bullets(urls)
    run_cmd(dry_run, "dnf", ["install", "-y", *urls])


def enable_config_manager_options(dry_run: bool, options: Sequence[str]) -> None:
    print_step("configuring dnf config-manager options")
    print_bullets(options)

    for option in options:
        run_cmd(dry_run, "dnf", ["config-manager", "setopt", option])


def disable_matching_repos(dry_run: bool, patterns: Sequence[str]) -> None:
    for pattern in patterns:
        repo_files = sorted(glob.glob(f"{REPO_DIR}/{pattern}"))

        print_step(f"disabling repos matching {pattern}")

        if not repo_files:
            print("  - no matching repos found")
            continue

        print_bullets(repo_files)

        for repo_file in repo_files:
            run_cmd(dry_run, "sed", ["-i", "s/^enabled=1/enabled=0/g", repo_file])


def add_external_repos(dry_run: bool, repos: Sequence[str]) -> None:
    if not repos:
        return

    print_step("adding external repos via dnf config-manager")
    print_bullets(repos)

    for url in repos:
        run_cmd(dry_run, "dnf", ["config-manager", "addrepo", "--from-repofile", url])


def enable_copr_groups(dry_run: bool, groups: Mapping[str, Sequence[str]]) -> None:
    for group, projects in groups.items():
        print_step(f"enabling copr group: {group}")
        print_bullets(projects)

        for project in projects:
            run_cmd(dry_run, "dnf", ["copr", "enable", "-y", project])


def apply_priority_overrides(dry_run: bool, overrides: Mapping[str, int]) -> None:
    print_step("applying repo priority overrides")

    for project, value in overrides.items():
        owner, name = project.split("/", 1)
        repo_path = Path(REPO_DIR) / f"{COPR_REPO_PREFIX}:{owner}:{name}.repo"

        print(f"  - {repo_path.name} => priority={value}")

        if dry_run:
            print(f"DRY-RUN: append priority={value} -> {repo_path}")
        elif not repo_path.exists():
            sys.exit(f"missing repo file: {repo_path}")
        else:
            with repo_path.open("a") as handle:
                handle.write(f"\npriority={value}\n")


def run_repo_stage(dry_run: bool, repos_cfg: Config) -> None:
    install_rpmfusion(dry_run, repos_cfg["rpmfusion"])
    # external repos must exist before config-manager setopt runs, since setopt
    # targets repo ids defined inside those repo files.
    add_external_repos(dry_run, repos_cfg["external"])
    enable_config_manager_options(dry_run, repos_cfg["setopt"])
    disable_matching_repos(dry_run, repos_cfg["disable_glob"])
    enable_copr_groups(dry_run, repos_cfg["copr"]["groups"])
    apply_priority_overrides(dry_run, repos_cfg["copr"]["priority"])
    dnf_clean(dry_run)
