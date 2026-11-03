"""Package stage: group installs, removals, extras (RPMs and fonts)."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Mapping, Sequence

from common import (
    Config,
    dnf_clean,
    dnf_install_lean,
    print_bullets,
    print_step,
    run_cmd,
    strip_version_prefix,
)

GITHUB_USER_AGENT = "fedora-niri-atomic-build"


def extract_font_archive(archive: str, dest: str) -> None:
    if archive.endswith(".zip"):
        run_cmd(False, "unzip", ["-q", "-o", archive, "-d", dest])
    elif archive.endswith((".tar.gz", ".tgz")):
        run_cmd(False, "tar", ["-xzf", archive, "-C", dest])
    elif archive.endswith(".tar.xz"):
        run_cmd(False, "tar", ["-xJf", archive, "-C", dest])
    elif archive.endswith(".tar.bz2"):
        run_cmd(False, "tar", ["-xjf", archive, "-C", dest])
    elif archive.endswith(".tar"):
        run_cmd(False, "tar", ["-xf", archive, "-C", dest])
    elif archive.endswith(".7z"):
        run_cmd(False, "7z", ["x", "-y", f"-o{dest}", archive])
    else:
        # plain font file
        run_cmd(False, "cp", [archive, str(Path(dest) / Path(archive).name)])


def install_fonts(dry_run: bool, fonts: Mapping[str, Config]) -> None:
    if not fonts:
        return

    print_step("installing fonts")

    for name, font in fonts.items():
        url = font["url"]
        dest = font["dest_dir"]
        filename = url.rsplit("/", 1)[-1]

        print(f"  - {name}")
        print(f"    url: {url}")
        print(f"    dest: {dest}")

        if dry_run:
            print("    note: download + extract skipped in dry-run")
            continue

        tmp = f"/tmp/{name}"
        run_cmd(False, "mkdir", ["-p", tmp, dest])
        run_cmd(
            False,
            "curl",
            ["-L", "--fail", "--silent", "--show-error", "-o", f"{tmp}/{filename}", url],
        )
        extract_font_archive(f"{tmp}/{filename}", dest)
        run_cmd(False, "rm", ["-rf", tmp])


def install_package_group(
    dry_run: bool, groups: Mapping[str, Sequence[str]], group: str
) -> None:
    packages = groups[group]

    print_step(f"installing package group: {group}")
    dnf_install_lean(dry_run, packages)
    # keep each group's layer lean; also safe to run between RUN steps
    dnf_clean(dry_run)


def install_package_groups(
    dry_run: bool, groups: Mapping[str, Sequence[str]]
) -> None:
    for group in groups:
        install_package_group(dry_run, groups, group)


def remove_packages(dry_run: bool, packages: Sequence[str]) -> None:
    if not packages:
        return

    print_step("removing packages")
    print_bullets(packages)
    run_cmd(dry_run, "dnf", ["remove", "-y", *packages])


def reinstall_packages(dry_run: bool, packages: Sequence[str]) -> None:
    if not packages:
        return

    print_step("reinstalling packages (remove then install)")
    print_bullets(packages)
    run_cmd(dry_run, "dnf", ["remove", "-y", *packages])
    run_cmd(
        dry_run,
        "dnf",
        ["install", "-y", "--setopt=install_weak_deps=False", "--nodocs", *packages],
    )


def install_static_rpms(dry_run: bool, rpms: Mapping[str, Config]) -> None:
    print_step("installing static rpm urls")

    for name, rpm in rpms.items():
        print(f"  - {name}")
        print(f"    url: {rpm['url']}")
        run_cmd(dry_run, "dnf", ["install", "-y", rpm["url"]])


def install_github_latest_rpms(dry_run: bool, rpms: Mapping[str, Config]) -> None:
    print_step("installing github latest rpms")

    for name, rpm in rpms.items():
        if dry_run:
            print(f"  - {name}")
            print(f"    repo: {rpm['repo']}")
            print(f"    url-template: {rpm['url_template']}")
            print("    note: latest tag lookup skipped in dry-run")
            continue

        request = urllib.request.Request(
            f"https://api.github.com/repos/{rpm['repo']}/releases/latest",
            headers={"User-Agent": GITHUB_USER_AGENT},
        )
        with urllib.request.urlopen(request) as response:
            tag = json.load(response)["tag_name"].strip()

        version = strip_version_prefix(tag, rpm.get("version_prefix_to_strip", ""))
        url = rpm["url_template"].replace("{tag}", tag).replace("{version}", version)

        print(f"  - {name}")
        print(f"    tag: {tag}")
        print(f"    url: {url}")
        run_cmd(False, "dnf", ["install", "-y", url])


def finalize_packages(dry_run: bool, packages_cfg: Config, extras_cfg: Config) -> None:
    print_step("finalizing packages (remove / reinstall / extras)")
    remove_packages(dry_run, packages_cfg["remove"])
    reinstall_packages(dry_run, packages_cfg["reinstall"])
    install_static_rpms(dry_run, extras_cfg["static"])
    install_github_latest_rpms(dry_run, extras_cfg["github_latest"])
    install_fonts(dry_run, extras_cfg["fonts"])
    dnf_clean(dry_run)
