# fedora-niri-atomic

> Chinese version: [README-zh.md](README-zh.md)

A personal Fedora Atomic desktop image repository built on [bootc](https://bootc.dev/).

The current goals are roughly:

- base the image on `quay.io/fedora/fedora-kinoite:44`
- provide a usable Wayland desktop environment
- keep parts of the Hyprland / KDE ecosystem available
- manage repos, packages, and system configuration with `Containerfile + Python + TOML`

---

## Repository layout

```text
.
├── README.md                     # repository overview and usage (English)
├── README-zh.md                  # repository overview and usage (Chinese)
├── AGENTS.md                     # instructions for coding agents / automation tools
├── Containerfile                 # OCI / bootc image build entrypoint
├── config.toml                   # user, timezone, locale, and related customization
├── mise.toml                     # local toolchain management
├── .github/
│   └── workflows/
│       └── build.yml             # GitHub Actions workflow for build and push
├── build/
│   ├── README.md                 # build subsystem documentation (English)
│   ├── README-zh.md              # build subsystem documentation (Chinese)
│   ├── config/
│   │   ├── repos.toml            # repo config: rpmfusion / external / setopt / copr
│   │   ├── packages.toml         # package groups and remove list
│   │   ├── extras.toml           # extra RPMs / GitHub latest release entries
│   │   └── system.toml           # flatpak remotes / systemd services
│   └── scripts/
│       ├── build.py              # top-level Python entrypoint
│       └── lib/
│           ├── common.py         # shared helpers
│           ├── repos.py          # repo stage logic
│           ├── packages.py       # package stage logic
│           └── system.py         # system stage logic
└── rootfs/                       # files copied directly into the image filesystem
    ├── etc/
    └── usr/
```

---

## What each part is responsible for

### `Containerfile`
Responsible for:

- defining the multi-stage image build
- downloading font assets
- bootstrapping `rpmfusion` (the pipeline itself only needs the base image's `python3`)
- invoking `build/scripts/build.py`
- producing the final bootc/OCI image

It now acts mainly as a thin orchestration entrypoint instead of holding a very long inline `RUN dnf ...` chain.

---

### `build/`
Responsible for the config-driven build system:

- `TOML` files describe **what** to install or enable
- `Python` scripts describe **how** to execute the build steps

See also:

- [`build/README.md`](build/README.md)
- [`build/README-zh.md`](build/README-zh.md)

---

### `rootfs/`
Responsible for static filesystem content copied into the image:

- systemd configuration
- environment files
- application configuration
- anything else that should be shipped via `COPY rootfs/ /`

If something is fundamentally “filesystem content inside the image”, it should usually live here rather than be generated dynamically by a script.

---

### `config.toml`
Responsible for system customization such as:

- user
- timezone
- locale
- keyboard layout

Current values include:

- user `cyrene`
- timezone `Asia/Shanghai`
- language `zh_CN.UTF-8`

---

### `.github/workflows/build.yml`
Responsible for CI:

- build on push
- scheduled build
- manual dispatch
- build an unchunked image with `podman`
- rechunk it with `rpm-ostree compose build-chunked-oci` (per-RPM layers)
- push the chunked image to `ghcr.io/star122013/fedora-niri-atomic:latest`

Runs on a GitHub-hosted `ubuntu-26.04` runner; `rpm-ostree` is taken from
inside the built `fedora-bootc` image, so no Fedora runner is required.

---

## Build subsystem layout

```text
build/
├── config/
│   ├── repos.toml
│   ├── packages.toml
│   ├── extras.toml
│   └── system.toml
└── scripts/
    ├── build.py
    └── lib/
        ├── common.py
        ├── repos.py
        ├── packages.py
        └── system.py
```

Responsibilities:

- `repos.toml`: repo sources and priorities (one table header per entry)
- `packages.toml`: package groups (arrays of names) and removal list
- `extras.toml`: extra RPMs and GitHub latest-release logic
- `system.toml`: flatpak and service configuration
- `build.py`: top-level orchestration
- `lib/*.py`: logic split by stage to keep files manageable

---

## Usage

### 1. Preview the build plan first

After changing `build/config/*.toml`, run a dry-run first:

```bash
python3 build/scripts/build.py build --dry-run
```

Short form:

```bash
python3 build/scripts/build.py build -n
```

This prints:

- which repos will be enabled
- which packages will be installed
- which packages will be removed
- which flatpak remotes will be added
- which systemd services will be enabled

It does **not** actually run `dnf`, `systemctl`, or `bootc`.

---

### 2. Build the image locally

```bash
podman build -t ghcr.io/star122013/fedora-niri-atomic:latest -f Containerfile .
```

For local testing, you can also use a local tag:

```bash
podman build -t fedora-niri-atomic:dev -f Containerfile .
```

---

### 3. Manually run the real build pipeline

This is usually **not** recommended directly on the host, because it will actually invoke:

- `dnf`
- `flatpak`
- `systemctl`
- `bootc`

But in a suitable container or test environment, you can run:

```bash
python3 build/scripts/build.py build
```

Inside the image build, `Containerfile` already does this automatically:

```dockerfile
COPY build /tmp/build
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage repo
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage packages --group system
# ... one RUN per package group, then finalize and system stages
```

---

### 4. Inspect a specific config section

Config files are plain TOML, so read them with anything that speaks TOML.

Show package groups:

```bash
python3 -c 'import tomllib; print(list(tomllib.load(open("build/config/packages.toml","rb"))["packages"]["groups"]))'
```

Show the desktop group:

```bash
python3 -c 'import tomllib; print(list(tomllib.load(open("build/config/packages.toml","rb"))["packages"]["groups"]["desktop"]))'
```

Show all COPR groups:

```bash
python3 -c 'import tomllib; print(list(tomllib.load(open("build/config/repos.toml","rb"))["repos"]["copr"]))'
```

---

## Common maintenance tasks

### Add a COPR repo
Edit:

- `build/config/repos.toml`

Common places:

- `[repos.copr.groups]`
- `[repos.copr.priority]`

---

### Add a normal package
Edit:

- `build/config/packages.toml`

Put it into the appropriate array inside `[packages.groups]`, for example
`desktop`, `gaming`, `utils`, `fonts`, or `system`.

---

### Add a GitHub release RPM
Edit:

- `build/config/extras.toml`

If it uses a fixed version URL, add it to:

- `[extras.static]`

If it should always use the latest GitHub release, add it to:

- `[extras.github_latest]`

---

### Add an enabled service
Edit:

- `build/config/system.toml`

Location:

- `[system.services]` → `enable` array

---

### Add a flatpak remote
Edit:

- `build/config/system.toml`

Location:

- `[system.flatpak]`

---

---

## Recommended workflow

### When changing config

1. Edit `build/config/*.toml`
2. Run a dry-run:

```bash
python3 build/scripts/build.py build --dry-run
```

3. Verify the output
4. Run a real build:

```bash
podman build -t fedora-niri-atomic:dev -f Containerfile .
```

---

### When changing build logic

Prefer editing:

- `build/scripts/lib/common.py`
- `build/scripts/lib/repos.py`
- `build/scripts/lib/packages.py`
- `build/scripts/lib/system.py`

Then run dry-run again.

---

## Why the bootstrap step still exists

`build.py` is stdlib-only Python, and the Fedora base image already ships
`python3` (verified against `quay.io/fedora/fedora-kinoite:45`).

So `Containerfile` only keeps a small bootstrap step that:

1. installs rpmfusion
2. installs `python3` (already present — the line just documents the dependency)

Then it hands over to the Python pipeline. No third-party repo is needed to
get the orchestrator itself, and nothing extra ships in the image for it.

---

## CI / publishing

GitHub Actions workflow:

- `.github/workflows/build.yml`

It currently:

- builds on `push`
- builds on schedule
- supports manual dispatch
- builds the image with `podman`, then rechunks it with
  `rpm-ostree compose build-chunked-oci` so the published image is split into
  per-RPM layers; bootc updates then only download the layers whose packages
  changed
- pushes to:

```text
ghcr.io/star122013/fedora-niri-atomic:latest       # chunked (per-RPM layers)
ghcr.io/star122013/fedora-niri-atomic:raw          # unchunked Containerfile build
ghcr.io/star122013/fedora-niri-atomic:raw-<sha>    # unchunked, per-commit
```

The job runs on a GitHub-hosted `ubuntu-26.04` runner. `rpm-ostree` is not
installed on the host; it is executed from inside the freshly built
`fedora-bootc` image (which ships it) against the image rootfs, so no
self-hosted Fedora runner is needed.

---

## Further reading

- [`README-zh.md`](README-zh.md)
- [`build/README.md`](build/README.md)
- [`build/README-zh.md`](build/README-zh.md)
- `Containerfile`

- [`https://bootc.dev/bootc/`](bootc-docs)
- [`https://blue-build.org/`](bluebuild)
