# build subsystem

> 中文版本：[`README-zh.md`](README-zh.md)

This build layout moves most repo / package / system configuration out of `Containerfile` and into a small Python + TOML build subsystem.

- `TOML` describes **what** to enable or install
- `Python` describes **how** the build steps are executed

Goals:

- keep `Containerfile` shorter and easier to read
- make repos, packages, and services easier to maintain
- support `--dry-run` previews
- avoid putting all logic into one huge `RUN dnf ...` block

---

## File layout

```text
build/
├── README.md                     # this document (English)
├── README-zh.md                  # this document (Chinese)
├── config/
│   ├── repos.toml                # repo config: rpmfusion / external / setopt / copr
│   ├── packages.toml             # package groups and removal list
│   ├── extras.toml               # extra RPMs: fixed URLs / GitHub latest
│   └── system.toml               # flatpak remotes and systemd services
└── scripts/
    ├── build.py                  # top-level entrypoint: runs repos / packages / system stages
    └── lib/
        ├── common.py             # shared helpers: printing, dry-run, config loading, dnf helpers
        ├── repos.py              # repo stage: rpmfusion / external / rawhide / copr / priority
        ├── packages.py           # package stage: packages, removals, extra RPMs
        └── system.py             # system stage: flatpak, fc-cache, services, bootc lint
```

---

## Structure and responsibilities

### 1. `config/repos.toml`
Repo-related configuration:

- `rpmfusion` — release RPM URL templates (`{fedora}` is substituted)
- `external` — repo files added with `dnf config-manager addrepo`
- `setopt` — `dnf config-manager setopt <key>=<value>` options
- `disable_glob` — globs of repo files to disable (`*rawhide*`)
- `[repos.copr.groups]` — COPR projects per group, enabled in key order
- `[repos.copr.priority]` — `'owner/project' = N`, appended as `priority=N` to
  the generated `/etc/yum.repos.d/_copr:owner:project.repo` file

Typical edits:

- add / remove a COPR repo
- change COPR enable order
- add priority to a COPR repo
- adjust rpmfusion settings

---

### 2. `config/packages.toml`
Package group configuration: plain arrays of package names.

- `[packages.groups]` — one array per group, e.g. `desktop = ['niri', ...]`
- `remove` — packages removed from the base image
- `reinstall` — packages removed then re-installed from the highest-priority repo

The key order inside `[packages.groups]` is the install order (most stable
first), so a new group only needs to be placed where it belongs.

Typical edits:

- add or remove packages from a group
- move a group to adjust install order
- add a new package group
- add a package to the removal list

---

### 3. `config/extras.toml`
Extra RPM sources that are not ordinary named packages:

- fixed download URL RPMs
- GitHub latest-release RPMs
- fonts downloaded from a direct URL (raw `.ttf`/`.otf` or an archive like `.zip`/
  `.tar.gz`/`.tar.xz`/`.tar.bz2`/`.7z`), extracted into `/usr/share/fonts`

Typical edits:

- update `cc-switch`
- add a new GitHub release install entry
- adjust `FlClash` download template
- add a font from any direct download URL

A font entry looks like:

```toml
[extras.fonts.'LXGW WenKai GB']
url = 'https://github.com/lxgw/LxgwWenkaiGB/releases/download/v1.522/lxgw-wenkai-gb-v1.522.tar.gz'
dest_dir = '/usr/share/fonts/lxgw-wenkai-gb'

# a plain single file also works (no extraction):
[extras.fonts.'Some Font']
url = 'https://example.com/path/font.ttf'
dest_dir = '/usr/share/fonts/custom'
```

The table key is the display name; `url` may point to any host (not just
GitHub). Archives are detected by file extension and unpacked into `dest_dir`;
plain `.ttf`/`.otf` files are copied as-is. `fc-cache` (system stage) indexes
them afterwards. Requires `curl`, `unzip`, and `p7zip` (already in the `utils`
package group).
---

### 4. `config/system.toml`
System-level configuration:

- `[system.flatpak]` — remote name → repo URL
- `[system.services]` — `enable` / `disable` arrays of unit names

Typical edits:

- add a flatpak remote
- add or remove an enabled service

---

## Script responsibilities

### `scripts/build.py`
Top-level orchestrator.

It only:

1. finds the `build/` root
2. loads the four `toml` config files
3. runs the stages, orderable per invocation:
   - repo stage
   - package stage (all groups, or a single `--group`)
   - finalize stage (removals / reinstalls / extras / font download)
   - system stage

It supports `--stage` and an optional `--group` so the `Containerfile`
can split work across multiple `RUN` layers (see “Layer ordering”).

Supported `--stage` values:

- `repo` — repo stage only
- `packages` — install package groups; if `--group <name>` is given,
  install that single group only, otherwise all groups in table order
- `finalize` — removals / reinstalls / static & github-latest RPMs / fonts
- `system` — flatpak / font cache / services / bootc lint
- `all` (default) — repo → packages → finalize → system

---

### `scripts/lib/common.py`
Shared utilities.

Includes helpers such as:

- `print_step`
- `print_bullets`
- `run_cmd`
- `resolve_project_root`
- `load_config`
- `dnf_clean`
- `dnf_install_lean`
- `strip_version_prefix`

---

### `scripts/lib/repos.py`
Repo stage only:

- rpmfusion
- external repo files
- `dnf config-manager setopt`
- disable rawhide
- COPR enable + priority override

---

### `scripts/lib/packages.py`
Package stage only:

- install package groups (or a single group via `install_package_group`)
- remove packages
- reinstall packages (base-image replacement mechanism)
- install fixed URL RPMs
- install GitHub latest RPMs
- `dnf clean` after each group so layers stay lean

---

### `scripts/lib/system.py`
System post-processing:

- flatpak remotes
- `fc-cache -fv`
- `systemd-sysusers`
- `systemctl enable`
- `bootc container lint`

---

## Execution flow

```text
build.py
  ├─ load repos.toml        → cfg["repos"]
  ├─ load packages.toml     → cfg["packages"]
  ├─ load extras.toml       → cfg["extras"]
  ├─ load system.toml       → cfg["system"]
  │
  ├─ (--stage repo)
  │   run_repo_stage
  │     ├─ install rpmfusion
  │     ├─ add external repo files
  │     ├─ set dnf config-manager options
  │     ├─ disable rawhide repos
  │     ├─ enable copr groups
  │     └─ apply repo priorities
  │
  ├─ (--stage packages)
  │   install_package_groups (or install_package_group with --group <name>)
  │     └─ dnf install each group in table order (stable first)
  │
  ├─ (--stage finalize)
  │   finalize_packages
  │     ├─ remove packages
  │     ├─ reinstall packages
  │     ├─ install static rpms
  │     ├─ install github latest rpms
  │     └─ install fonts
  │
  └─ (--stage system)
      run_system_stage
        ├─ configure flatpak remotes
        ├─ refresh font cache
        ├─ enable services
        └─ run bootc container lint
```

## Layer ordering

The `Containerfile` no longer runs the whole pipeline in one `RUN`.
Instead it splits work across several `RUN` steps — each becomes its own
image layer — ordered from **most stable to most frequently changing**
so unchanged layers are cached and only the layers after a change rebuild:

```dockerfile
RUN python3 -B build.py --stage repo
RUN python3 -B build.py --stage packages --group system
RUN python3 -B build.py --stage packages --group fonts
RUN python3 -B build.py --stage packages --group utils
RUN python3 -B build.py --stage packages --group desktop
RUN python3 -B build.py --stage packages --group gaming
RUN python3 -B build.py --stage finalize
RUN python3 -B build.py --stage system
```

If you add a new package group, decide where it sits on the stability
axis, add its `[packages.groups.<name>]` table at the matching position in
`config/packages.toml`, and add a matching `RUN ... --group <name>` line.

---

## Common commands

### 1. Dry-run from the repository root

```bash
python3 build/scripts/build.py build --dry-run
```

Or:

```bash
python3 build/scripts/build.py build -n
```

---

### 2. Dry-run inside a zmx session

```bash
zmx run system-oci -- python3 build/scripts/build.py build --dry-run
```

---

### 3. Run during container build

`Containerfile` currently uses several staged `RUN` steps (see
“Layer ordering”), each loading the build config and running one step:

```dockerfile
COPY build /tmp/build
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage repo
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage packages --group system
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage packages --group fonts
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage packages --group utils
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage packages --group desktop
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage packages --group gaming
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage finalize
# ... then systemd units are copied, then:
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage system
```

Note that the argument is the **build root**, not a single config file.

---

## Why the bootstrap step still exists in `Containerfile`

The `build.py` entrypoint is stdlib-only Python, so it needs nothing installed
beyond `python3` — which the Fedora base image already ships.

So `Containerfile` only needs a small bootstrap step that installs rpmfusion
(plus a `dnf install -y python3` no-op for documentation), then the repo /
package / system flow runs straight from `/tmp/build`.

Using the distro `python3` instead of a COPR-provided interpreter keeps the
bootstrap free of third-party repos and keeps the shipped image smaller: the
orchestrator is a base-image package, not an extra one.

---

## Maintenance guidance

### Change packages
Prefer editing:

- `config/packages.toml`

### Change repos
Prefer editing:

- `config/repos.toml`

### Change extra RPM sources
Prefer editing:

- `config/extras.toml`

### Change services or flatpak remotes
Prefer editing:

- `config/system.toml`

### Change execution logic
Prefer editing:

- `scripts/lib/*.py`
- `scripts/build.py`

### Shadow entries for image-only accounts

`rootfs/usr/libexec/plasmalogin-shadow-fix` + `rootfs/usr/lib/systemd/system/plasmalogin-shadow-fix.service`

Accounts defined only in `/usr/lib/passwd` (nss-altfiles) have nowhere immutable to keep
their `/etc/shadow` entry: nss-altfiles covers passwd/group only, and bootc's `/etc`
merge copies the locally modified `/etc/shadow` wholesale over the new image's copy on
every upgrade/rebase, dropping entries the new image introduced. `systemd-sysusers` does
not recreate them (the account already resolves via NSS), so PAM fails with
`PAM_AUTHINFO_UNAVAIL` — the plasmalogin greeter then cannot start (black screen).

The unit re-adds the entries idempotently on every boot and supersedes Fedora's
stamp-based `fedora-kinoite-plasmalogin-workaround.service` (masked in `system.toml`).
Upstream: https://forge.fedoraproject.org/kde/tracker/issues/684

---

## sing-box (manual enable)

The image ships a sing-box proxy (SOCKS5 upstream for dae) but it is **not enabled by default** — enable it manually:

```bash
# 1. enable the node-config updater service + timer (daily 20:00 fetch of node.json, then restart singbox)
sudo systemctl enable --now singbox-update.timer

# 2. start sing-box itself (config dir /etc/singbox: base.json + node.json auto-merged)
sudo systemctl enable --now singbox.service
```

Relevant files:

- `rootfs/etc/singbox/base.json` — static config (SOCKS5 inbound :2080, outbound selectors, routing rules)
- `rootfs/usr/lib/systemd/system/singbox.service` — runs `sing-box run -C /etc/singbox`
- `rootfs/usr/lib/systemd/system/singbox-update.service` — pulls node config from SubStore
- `rootfs/usr/lib/systemd/system/singbox-update.timer` — daily refresh at 20:00

> Note: the official sing-box RPM ships its own `sing-box.service`; we use `singbox` (no hyphen) to avoid being overwritten.

---

## Recommended habit

After changing config, always run:

```bash
python3 build/scripts/build.py build --dry-run
```

Check that:

- install order is correct
- package groups are correct
- repo priorities are correct
- GitHub latest templates are correct
- services and flatpak remotes are correct

Then do a real image build.

---

## Related docs

- [`README-zh.md`](README-zh.md)
- [`../README.md`](../README.md)
- [`../README-zh.md`](../README-zh.md)
