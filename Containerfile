# vim: set filetype=dockerfile
# ================================================================
# Fedora 45 with bootc
# https://bootc.dev/bootc/
# Philosophy: the image provides hardware support + a working
# niri session.
#
# File placement rules (bootc):
#   /usr/lib/   — read-only distro defaults (modprobe.d, dracut, systemd, sddm)
#   /etc/       — mutable admin config (containers policy, skel, locale)
#   /var/       — runtime state only; never ship files here; use tmpfiles.d
# ================================================================

FROM quay.io/fedora/fedora-silverblue:45

COPY build /tmp/build

# ================================================================
# Layer ordering strategy (stable -> changing) for better caching:
#   L1  bootstrap (rpmfusion + python3)
#   L2  repo stage (rpmfusion / terra / COPR / priority)
#   L3  system group      (mesa)            -- foundational, rarely churn
#   L4  fonts group       (noto)            -- stable
#   L5  services group    (daemons/virt/net)-- stable-ish
#   L6  utils group       (toolchain, etc.) -- stable-ish
#   L7  desktop group     (niri, hyprland)  -- changes most often
#   L8  gaming group
#   L9  finalize (removals / extras / font download / clean)
#   L10 system stage (flatpak / services / bootc lint)
# Each RUN is its own layer, so unchanged packages are cached and
# only the layers after a change are rebuilt.
# ================================================================

# L1: bootstrap rpmfusion; the pipeline itself only needs python3, which the
# Fedora base image already ships (stdlib tomllib + subprocess, no venv).
#
# No mirrorlist pinning: the Fedora repos keep their `metalink=` and RPMFusion
# is installed from its official release RPM, so dnf asks MirrorManager for the
# nearest mirror. Run the build through a proxy (http_proxy / https_proxy) and
# that selection follows the proxy's egress IP.
RUN set -eux; \
    dnf install -y \
      'dnf5-command(copr)' \
      python3 \
      "https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm" \
      "https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm"; \
    dnf clean all

# L2: repo stage
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage repo

# L3-L8: install package groups, stable first
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage packages --group system
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage packages --group fonts
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage packages --group services
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage packages --group utils
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage packages --group desktop
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage packages --group gaming

# L9: removals / reinstalls / static & github-latest RPMs / font download + clean
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage finalize

# pre-copy custom systemd units so systemctl enable can find them
COPY rootfs/usr/lib/systemd/system/ /usr/lib/systemd/system/

# L10: flatpak remotes / font cache / systemd services / bootc lint
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage system

# re-apply rootfs after package install so RPM-shipped /etc defaults
# (e.g. dae's empty /etc/dae/config.dae) do not clobber our config
COPY rootfs/ /

# dae requires config.dae to be 0600. git does not preserve full file
# modes (only the executable bit), so a fresh checkout may yield 0644;
# enforce 0600 at build time instead of relying on the source mode.
RUN chmod 0600 /etc/dae/config.dae
