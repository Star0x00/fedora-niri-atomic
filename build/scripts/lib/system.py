"""System stage: flatpak remotes, font cache, services, bootc lint."""

from __future__ import annotations

from typing import Mapping, Sequence

from common import Config, print_bullets, print_step, run_cmd


def configure_flatpak(dry_run: bool, remotes: Mapping[str, str]) -> None:
    print_step("configuring flatpak remotes")

    for name, url in remotes.items():
        print(f"  - {name} => {url}")
        run_cmd(dry_run, "flatpak", ["remote-add", "--if-not-exists", name, url])


def refresh_font_cache(dry_run: bool) -> None:
    print_step("refreshing font cache")
    run_cmd(dry_run, "fc-cache", ["-fv"])


def enable_services(dry_run: bool, services: Sequence[str]) -> None:
    print_step("enabling system services")
    run_cmd(dry_run, "systemd-sysusers", [])
    run_cmd(dry_run, "grpck", ["-s"])
    run_cmd(dry_run, "pwck", ["-s"])
    print_bullets(services)

    for service in services:
        run_cmd(dry_run, "systemctl", ["enable", service])


def disable_services(dry_run: bool, services: Sequence[str]) -> None:
    print_step("masking unwanted system services")
    print_bullets(services)

    for service in services:
        run_cmd(dry_run, "systemctl", ["mask", service])


def run_bootc_lint(dry_run: bool) -> None:
    print_step("running bootc container lint")
    run_cmd(dry_run, "bootc", ["container", "lint"])


def run_system_stage(dry_run: bool, system_cfg: Config) -> None:
    configure_flatpak(dry_run, system_cfg["flatpak"])
    refresh_font_cache(dry_run)
    enable_services(dry_run, system_cfg["services"]["enable"])
    disable_services(dry_run, system_cfg["services"]["disable"])
    run_bootc_lint(dry_run)
