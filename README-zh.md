# fedora-niri-atomic

> English version: [README.md](README.md)

基于 [bootc](https://bootc.dev/) 的个人 Fedora Atomic 桌面镜像仓库。

当前目标大致是：

- 以 `quay.io/fedora/fedora-kinoite:44` 为基础
- 提供一个可用的 Wayland 桌面环境
- 保留部分 Hyprland / KDE 生态软件
- 用 `Containerfile + Python + TOML` 管理仓库、软件包和系统配置

---

## 仓库结构图

```text
.
├── README.md                     # 仓库总说明与 usage（英文）
├── README-zh.md                  # 仓库总说明与 usage（中文）
├── AGENTS.md                     # 给 agent / 自动化工具的仓库说明
├── Containerfile                 # OCI / bootc 镜像构建入口
├── config.toml                   # 用户、时区、locale 等系统定制
├── mise.toml                     # 本地工具链管理
├── .github/
│   └── workflows/
│       └── build.yml             # GitHub Actions：构建并推送镜像
├── build/
│   ├── README.md                 # build 子系统说明（英文）
│   ├── README-zh.md              # build 子系统说明（中文）
│   ├── config/
│   │   ├── repos.toml            # 仓库配置：rpmfusion / external / setopt / copr
│   │   ├── packages.toml         # 软件包分组与 remove 列表
│   │   ├── extras.toml           # 额外 rpm / GitHub latest release
│   │   └── system.toml           # flatpak remotes / systemd services
│   └── scripts/
│       ├── build.py              # Python 总入口
│       └── lib/
│           ├── common.py         # 公共函数
│           ├── repos.py          # 仓库阶段逻辑
│           ├── packages.py       # 软件包阶段逻辑
│           └── system.py         # 系统阶段逻辑
└── rootfs/                       # 构建时直接复制进镜像文件系统的内容
    ├── etc/
    └── usr/
```

---

## 各部分职责

### `Containerfile`
负责：

- 定义多阶段镜像构建
- 下载字体资源
- bootstrap `rpmfusion`（流水线本身只需要基础镜像自带的 `python3`）
- 调用 `build/scripts/build.py`
- 产出最终 bootc/OCI 镜像

它现在主要是一个较薄的编排入口，而不是把所有 repo/package 逻辑都塞进超长的 `RUN dnf ...`。

---

### `build/`
负责整个配置驱动的构建系统：

- `TOML` 文件描述“装什么 / 启用什么”
- `Python` 脚本描述“怎么执行”

另见：

- [`build/README.md`](build/README.md)
- [`build/README-zh.md`](build/README-zh.md)

---

### `rootfs/`
负责静态文件树：

- systemd 配置
- 环境文件
- 程序配置
- 其它需要通过 `COPY rootfs/ /` 放入镜像的内容

如果某个东西本质上是“镜像里的文件系统内容”，通常更适合放在这里，而不是由脚本动态生成。

---

### `config.toml`
负责系统自定义参数，例如：

- 用户
- 时区
- locale
- 键盘布局

当前内容包括：

- 用户 `cyrene`
- 时区 `Asia/Shanghai`
- 语言 `zh_CN.UTF-8`

---

### `.github/workflows/build.yml`
负责 CI：

- push 时构建
- 定时构建
- 手动触发构建
- 用 `podman` 构建未分块的镜像
- 用 `rpm-ostree compose build-chunked-oci` 重新分块（按 RPM 边界分层）
- 推送分块后的镜像到 `ghcr.io/star122013/fedora-niri-atomic:latest`

运行在 GitHub 托管的 `ubuntu-26.04` runner 上；`rpm-ostree` 取自构建出的
`fedora-bootc` 镜像内部，因此不需要 Fedora runner。

---

## build 子系统结构图

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

职责拆分：

- `repos.toml`：仓库来源与优先级
- `packages.toml`：包分组与移除列表
- `extras.toml`：额外 rpm 与 GitHub latest release 逻辑
- `system.toml`：flatpak / services
- `build.py`：总入口
- `lib/*.py`：按阶段拆分逻辑，避免脚本过长

---

## Usage

### 1. 先预览构建计划

修改完 `build/config/*.toml` 后，推荐先 dry-run：

```bash
python3 build/scripts/build.py build --dry-run
```

短参数：

```bash
python3 build/scripts/build.py build -n
```

这个命令会打印：

- 将启用哪些 repo
- 将安装哪些包
- 将删除哪些包
- 将添加哪些 flatpak remote
- 将启用哪些 systemd service

但**不会真的执行 `dnf` / `systemctl` / `bootc`**。

---

### 2. 在 zmx session 里预览

如果你已经有一个 session，比如 `system-oci`：

```bash
zmx run system-oci -- python3 build/scripts/build.py build --dry-run
```

这很适合远程或 agent 驱动的验证。

---

### 3. 本地构建镜像

```bash
podman build -t ghcr.io/star122013/fedora-niri-atomic:latest -f Containerfile .
```

如果只是本地测试，也可以用本地 tag：

```bash
podman build -t fedora-niri-atomic:dev -f Containerfile .
```

---

### 4. 手动运行真实构建流程

通常不建议直接在宿主机上执行，因为它会真的调用：

- `dnf`
- `flatpak`
- `systemctl`
- `bootc`

但如果你在合适的容器或测试环境里，可以运行：

```bash
python3 build/scripts/build.py build
```

在镜像构建里，`Containerfile` 会自动做这件事：

```dockerfile
COPY build /tmp/build
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage repo
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage packages --group system
# ……每组一层，最后 finalize + system
```

---

### 5. 查看某一类配置

配置文件就是普通 TOML，用任何能读 TOML 的工具都行。

查看包分组：

```bash
python3 -c 'import tomllib; print(list(tomllib.load(open("build/config/packages.toml","rb"))["packages"]["groups"]))'
```

查看桌面组：

```bash
python3 -c 'import tomllib; print(list(tomllib.load(open("build/config/packages.toml","rb"))["packages"]["groups"]["desktop"]))'
```

查看所有 COPR 分组：

```bash
python3 -c 'import tomllib; print(list(tomllib.load(open("build/config/repos.toml","rb"))["repos"]["copr"]))'
```

---

## 常见维护动作

### 新增一个 COPR
改：

- `build/config/repos.toml`

常见位置：

- `[repos.copr.groups]`
- `[repos.copr.priority]`

---

### 新增一个普通包
改：

- `build/config/packages.toml`

按语义放进 `[packages.groups]` 里对应的数组，例如 `desktop`、`gaming`、
`utils`、`fonts`、`system`。

---

### 新增一个 GitHub release RPM
改：

- `build/config/extras.toml`

如果是固定版本 URL，放到：

- `[extras.static]`

如果希望每次都取 latest release，放到：

- `[extras.github_latest]`

---

### 新增一个开机启用服务
改：

- `build/config/system.toml`

位置：

- `[system.services]` 的 `enable` 数组

---

### 新增一个 flatpak remote
改：

- `build/config/system.toml`

位置：

- `[system.flatpak]`

---

---

## 推荐工作流

### 改配置时

1. 修改 `build/config/*.toml`
2. 运行 dry-run：

```bash
python3 build/scripts/build.py build --dry-run
```

3. 检查输出是否符合预期
4. 再执行真实构建：

```bash
podman build -t fedora-niri-atomic:dev -f Containerfile .
```

---

### 改脚本逻辑时

优先修改：

- `build/scripts/lib/common.py`
- `build/scripts/lib/repos.py`
- `build/scripts/lib/packages.py`
- `build/scripts/lib/system.py`

改完后同样先跑 dry-run。

---

## 为什么还需要 bootstrap 步骤

`build.py` 只用标准库，除了 `python3` 之外不需要装任何东西，而 Fedora 基础镜像
本身就带 `python3`（已在 `quay.io/fedora/fedora-kinoite:45` 里验证过）。

所以 `Containerfile` 里的 bootstrap 只剩：

1. 安装 rpmfusion
2. 安装 `python3`（本来就有，这一行只是把依赖写明）

之后就把流程交给 Python 流水线。拿到编排器本身不需要任何第三方仓库，镜像里也不会
为它多留一个包。

---

## CI / 发布

GitHub Actions 工作流：

- `.github/workflows/build.yml`

当前会：

- 在 `push` 时构建
- 定时构建
- 支持手动触发
- 先用 `podman` 构建镜像，再用 `rpm-ostree compose build-chunked-oci`
  重新分块，使发布的镜像按 RPM 边界拆成多层；之后 bootc 更新只下载
  变动包对应的层
- 推送到：

```text
ghcr.io/star122013/fedora-niri-atomic:latest       # 分块（按 RPM 分层）
ghcr.io/star122013/fedora-niri-atomic:raw          # 未分块的 Containerfile 构建
ghcr.io/star122013/fedora-niri-atomic:raw-<sha>    # 未分块，按 commit
```

该 job 运行在 GitHub 托管的 `ubuntu-26.04` runner 上。宿主上不装
`rpm-ostree`，而是用构建出的 `fedora-bootc` 镜像内部自带的 `rpm-ostree`
对镜像 rootfs 进行处理，因此不需要自托管 Fedora runner。

---

## 延伸阅读

- [`README.md`](README.md)
- [`build/README.md`](build/README.md)
- [`build/README-zh.md`](build/README-zh.md)
- `Containerfile`
- `rootfs/`
- `config.toml`
