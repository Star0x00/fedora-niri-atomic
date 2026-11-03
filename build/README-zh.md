# build 配置说明

> English version: [`README.md`](README.md)

这套构建布局把原本 `Containerfile` 里大量 repo / package / system 配置拆到了一个较小的 Python + TOML 子系统中。

- `TOML` 负责描述“装什么 / 启用什么”
- `Python` 负责描述“怎么执行”

目标包括：

- 缩短 `Containerfile`，提升可读性
- 让 repo、package、service 更容易维护
- 支持 `--dry-run` 预览
- 避免把所有逻辑都塞进一个巨大的 `RUN dnf ...` 块里

---

## 文件结构图

```text
build/
├── README.md                     # 本说明文档（英文）
├── README-zh.md                  # 本说明文档（中文）
├── config/
│   ├── repos.toml                # 仓库配置：rpmfusion / external / setopt / copr
│   ├── packages.toml             # 包分组与移除列表
│   ├── extras.toml               # 额外 RPM：固定 URL / GitHub latest
│   └── system.toml               # flatpak remote 与 systemd services
└── scripts/
    ├── build.py                  # 总入口：串联 repos / packages / system 三个阶段
    └── lib/
        ├── common.py             # 通用函数：打印、dry-run、加载配置、dnf helper
        ├── repos.py              # repo 阶段：rpmfusion / external / rawhide / copr / priority
        ├── packages.py           # package 阶段：安装包、删除包、额外 RPM
        └── system.py             # system 阶段：flatpak、fc-cache、services、bootc lint
```

---

## 结构与职责

### 1. `config/repos.toml`
负责仓库相关配置：

- `rpmfusion` — release RPM URL 模板（`{fedora}` 会被替换）
- `external` — 通过 `dnf config-manager addrepo` 添加的 repo 文件
- `setopt` — `dnf config-manager setopt <key>=<value>` 选项
- `disable_glob` — 需要禁用的 repo 文件 glob（`*rawhide*`）
- `[repos.copr.groups]` — 每个分组的 COPR 项目，按键顺序启用
- `[repos.copr.priority]` — `'owner/project' = N`，会把 `priority=N` 追加到
  生成的 `/etc/yum.repos.d/_copr:owner:project.repo` 文件中

适合修改的场景：

- 新增 / 删除 COPR
- 调整 COPR 启用顺序
- 给某个 COPR 增加 priority
- 修改 rpmfusion 配置

---

### 2. `config/packages.toml`
负责软件包分组，就是普通的名字数组：

- `[packages.groups]` — 每个分组一个数组，例如 `desktop = ['niri', ...]`
- `remove` — 要从基础镜像里移除的包
- `reinstall` — 先删除再从最高优先级仓库重装的包

`[packages.groups]` 下的键顺序就是安装顺序（稳定的在前），新增分组时把数组放到
对应的位置即可。

适合修改的场景：

- 增减某组包
- 移动分组位置以调整安装顺序
- 添加新的包分组
- 添加待移除的软件包

---

### 3. `config/extras.toml`
负责非普通命名包的额外 RPM 来源：

- 固定下载 URL 的 RPM
- 通过 GitHub latest release 动态获取 tag 的 RPM
- 从直接 URL 下载的字体（原始 `.ttf`/`.otf`，或 `.zip`/`.tar.gz`/`.tar.xz`/`.tar.bz2`/`.7z` 等压缩包，解压到 `/usr/share/fonts`）

适合修改的场景：

- 更新 `cc-switch`
- 新增 GitHub release 安装项
- 调整 `FlClash` 下载模板
- 添加任意直接下载链接中的字体

字体条目示例：

```toml
[extras.fonts.'LXGW WenKai GB']
url = 'https://github.com/lxgw/LxgwWenkaiGB/releases/download/v1.522/lxgw-wenkai-gb-v1.522.tar.gz'
dest_dir = '/usr/share/fonts/lxgw-wenkai-gb'

# 单个字体文件也可直接使用（不解压）：
[extras.fonts.'Some Font']
url = 'https://example.com/path/font.ttf'
dest_dir = '/usr/share/fonts/custom'
```

表键就是显示名称，`url` 可以指向任意主机（不限于 GitHub）。压缩包按文件扩展名识别并解压到 `dest_dir`，普通 `.ttf`/`.otf` 直接复制。随后由系统阶段的 `fc-cache` 索引。依赖 `curl`、`unzip`、`p7zip`（已在 `utils` 包组中）。
---

### 4. `config/system.toml`
负责系统级配置：

- `[system.flatpak]` — remote 名称 → repo URL
- `[system.services]` — `enable` / `disable` 两个服务名数组

适合修改的场景：

- 新增 flatpak remote
- 添加 / 删除开机启用服务

---

## 脚本职责

### `scripts/build.py`
总入口 / orchestrator。

它只负责：

1. 定位 `build/` 根目录
2. 加载四份 `toml` 配置文件
3. 按 `--stage` 执行对应阶段：
   - repo stage
   - package stage（全部分组，或 `--group` 指定的单个分组）
   - finalize stage（remove / reinstall / extras / 字体下载）
   - system stage

---

### `scripts/lib/common.py`
公共工具层。

包括：

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
只负责 repo 阶段：

- rpmfusion
- external repo 文件
- `dnf config-manager setopt`
- 禁用 rawhide
- COPR enable + priority override

---

### `scripts/lib/packages.py`
只负责 package 阶段：

- 安装包分组
- 删除包
- 安装固定 URL RPM
- 安装 GitHub latest RPM

---

### `scripts/lib/system.py`
只负责系统后处理：

- flatpak remotes
- `fc-cache -fv`
- `systemd-sysusers`
- `systemctl enable`
- `bootc container lint`

---

## 执行流程图

```text
build.py
  ├─ load repos.toml
  ├─ load packages.toml
  ├─ load extras.toml
  ├─ load system.toml
  │
  ├─ (--stage repo) run_repo_stage
  │   ├─ install rpmfusion
  │   ├─ add external repo files
  │   ├─ set dnf config-manager options
  │   ├─ disable rawhide repos
  │   ├─ enable copr groups
  │   └─ apply repo priorities
  │
  ├─ (--stage packages) install_package_groups / install_package_group
  │   └─ 按表顺序安装分组（稳定的在前）
  │
  ├─ (--stage finalize) finalize_packages
  │   ├─ remove packages
  │   ├─ reinstall packages
  │   ├─ install static rpms
  │   ├─ install github latest rpms
  │   └─ install fonts
  │
  └─ (--stage system) run_system_stage
      ├─ configure flatpak remotes
      ├─ refresh font cache
      ├─ enable services
      └─ run bootc container lint
```

---

## 常用命令

### 1. 在仓库根目录 dry-run

```bash
python3 build/scripts/build.py build --dry-run
```

或者：

```bash
python3 build/scripts/build.py build -n
```

---

### 2. 在 zmx session 中 dry-run

```bash
zmx run system-oci -- python3 build/scripts/build.py build --dry-run
```

---

### 3. 在容器构建时执行

`Containerfile` 当前使用：

```dockerfile
COPY build /tmp/build
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage repo
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage packages --group system
# ...每组一层，最后：
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage finalize
RUN python3 -B /tmp/build/scripts/build.py /tmp/build --stage system
```

注意这里传入的是 **build 根目录**，不是单独的配置文件路径。

---

## 为什么 `Containerfile` 里仍然保留 bootstrap 步骤

`build.py` 只用标准库，除了 `python3` 之外不需要装任何东西，而 Fedora 基础镜像
本身就带 `python3`。

所以 `Containerfile` 的 bootstrap 只剩安装 rpmfusion（外加一句 `dnf install -y
python3` 作为显式声明），之后直接从 `/tmp/build` 跑流水线。

用发行版自带的 `python3` 而不是某个 COPR 提供的解释器，bootstrap 就不依赖第三方
仓库，镜像里也不会多一个只为构建服务的包。

---

## 维护建议

### 改包
优先改：

- `config/packages.toml`

### 改仓库
优先改：

- `config/repos.toml`

### 改额外 RPM 来源
优先改：

- `config/extras.toml`

### 改系统服务或 flatpak remote
优先改：

- `config/system.toml`

### 改执行逻辑
优先改：

- `scripts/lib/*.py`
- `scripts/build.py`

---

## sing-box（手动启用）

镜像里已内置 sing-box 代理（为 dae 提供 SOCKS5 上游），但**默认不 enable**，需要手动启用：

```bash
# 1. 启用手动更新节点配置的服务 + 定时器（每天 20:00 拉取 node.json 并重启 singbox）
sudo systemctl enable --now singbox-update.timer

# 2. 启动 sing-box 本体（配置目录 /etc/singbox：base.json + node.json 自动合并）
sudo systemctl enable --now singbox.service
```

相关文件：

- `rootfs/etc/singbox/base.json` — 静态配置（SOCKS5 inbound :2080、outbound selector、路由规则）
- `rootfs/usr/lib/systemd/system/singbox.service` — 运行 `sing-box run -C /etc/singbox`
- `rootfs/usr/lib/systemd/system/singbox-update.service` — 从 SubStore 拉取节点配置
- `rootfs/usr/lib/systemd/system/singbox-update.timer` — 每日 20:00 刷新

> 注意：官方 sing-box RPM 自带 `sing-box.service`，这里用 `singbox`（无连字符）命名避免被覆盖。

---

## 推荐习惯

每次改完配置，先运行：

```bash
python3 build/scripts/build.py build --dry-run
```

确认：

- 安装顺序正确
- 包分组正确
- repo priority 正确
- GitHub latest 模板正确
- services 和 flatpak remotes 正确

再进行真实镜像构建。

---

## 相关文档

- [`README.md`](README.md)
- [`../README.md`](../README.md)
- [`../README-zh.md`](../README-zh.md)
