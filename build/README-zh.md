# build 配置说明

> English version: [`README.md`](README.md)

这套构建布局把原本 `Containerfile` 里大量 repo / package / system 配置拆到了一个较小的 Nu + NUON 子系统中。

- `NUON` 负责描述“装什么 / 启用什么”
- `Nu` 负责描述“怎么执行”

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
│   ├── repos.nuon                # 仓库配置：rpmfusion / terra / copr / priority
│   ├── packages.nuon             # 包分组与移除列表
│   ├── extras.nuon               # 额外 RPM：固定 URL / GitHub latest
│   └── system.nuon               # flatpak remote 与 systemd services
└── scripts/
    ├── build.nu                  # 总入口：串联 repos / packages / system 三个阶段
    └── lib/
        ├── common.nu             # 通用函数：打印、dry-run、加载配置、dnf helper
        ├── repos.nu              # repo 阶段：rpmfusion / rawhide / terra / copr / priority
        ├── packages.nu           # package 阶段：安装包、删除包、额外 RPM
        └── system.nu             # system 阶段：flatpak、fc-cache、services、bootc lint
```

---

## 结构与职责

### 1. `config/repos.nuon`
负责仓库相关配置：

- rpmfusion release URL 模板
- `dnf config-manager setopt`
- 禁用 `*rawhide*` repo
- terra repo 与 `terra-release`
- 所有 COPR 分组
- repo `priority=1` 覆盖

适合修改的场景：

- 新增 / 删除 COPR
- 调整 repo 启用顺序
- 给某个 repo 增加 priority
- 修改 terra / rpmfusion 配置

---

### 2. `config/packages.nuon`
负责软件包分组：

- `desktop`
- `gaming`
- `utils`
- `fonts`
- `system`
- `remove`

适合修改的场景：

- 增减某组包
- 调整安装顺序
- 添加新的包分组
- 添加待移除的软件包

---

### 3. `config/extras.nuon`
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

```nuon
fonts: [
  {
    name: "LXGW WenKai GB"
    url: "https://github.com/lxgw/LxgwWenkaiGB/releases/download/v1.522/lxgw-wenkai-gb-v1.522.tar.gz"
    dest_dir: "/usr/share/fonts/lxgw-wenkai-gb"
  }
]

# 单个字体文件也可直接使用（不解压）：
fonts: [
  {
    name: "Some Font"
    url: "https://example.com/path/font.ttf"
    dest_dir: "/usr/share/fonts/custom"
  }
]
```

`url` 可以指向任意主机（不限于 GitHub）。压缩包按文件扩展名识别并解压到 `dest_dir`，普通 `.ttf`/`.otf` 直接复制。随后由系统阶段的 `fc-cache` 索引。依赖 `curl`、`unzip`、`p7zip`（已在 `utils` 包组中）。
---

### 4. `config/system.nuon`
负责系统级配置：

- flatpak remotes
- 需要 `systemctl enable` 的服务

适合修改的场景：

- 新增 flatpak remote
- 添加 / 删除开机启用服务

---

## 脚本职责

### `scripts/build.nu`
总入口 / orchestrator。

它只负责：

1. 定位 `build/` 根目录
2. 加载所有 `nuon` 配置文件
3. 按顺序执行三个阶段：
   - repo stage
   - package stage
   - system stage

---

### `scripts/lib/common.nu`
公共工具层。

包括：

- `print-step`
- `print-bullets`
- `run-cmd`
- `resolve-project-root`
- `load-config`
- `dnf-clean`
- `dnf-install-lean`
- `strip-version-prefix`

---

### `scripts/lib/repos.nu`
只负责 repo 阶段：

- rpmfusion
- `dnf config-manager setopt`
- 禁用 rawhide
- terra release
- COPR enable
- repo priority override

---

### `scripts/lib/packages.nu`
只负责 package 阶段：

- 安装包分组
- 删除包
- 安装固定 URL RPM
- 安装 GitHub latest RPM

---

### `scripts/lib/system.nu`
只负责系统后处理：

- flatpak remotes
- `fc-cache -fv`
- `systemd-sysusers`
- `systemctl enable`
- `bootc container lint`

---

## 执行流程图

```text
build.nu
  ├─ load repos.nuon
  ├─ load packages.nuon
  ├─ load extras.nuon
  ├─ load system.nuon
  │
  ├─ run-repo-stage
  │   ├─ install rpmfusion
  │   ├─ set dnf config-manager options
  │   ├─ disable rawhide repos
  │   ├─ install terra-release
  │   ├─ enable copr groups
  │   └─ apply repo priorities
  │
  ├─ run-package-stage
  │   ├─ install package groups
  │   ├─ remove packages
  │   ├─ install static rpms
  │   └─ install github latest rpms
  │
  └─ run-system-stage
      ├─ configure flatpak remotes
      ├─ refresh font cache
      ├─ enable services
      └─ run bootc container lint
```

---

## 常用命令

### 1. 在仓库根目录 dry-run

```bash
nu build/scripts/build.nu build --dry-run
```

或者：

```bash
nu build/scripts/build.nu build -n
```

---

### 2. 在 zmx session 中 dry-run

```bash
zmx run system-oci -- nu build/scripts/build.nu build --dry-run
```

---

### 3. 在容器构建时执行

`Containerfile` 当前使用：

```dockerfile
COPY build /tmp/build
RUN nu /tmp/build/scripts/build.nu /tmp/build
```

注意这里传入的是 **build 根目录**，不是单独的配置文件路径。

---

## 为什么 `Containerfile` 里仍然保留 bootstrap 步骤

在任何 `.nu` 脚本运行之前，镜像里必须先有 `nushell`。

所以 `Containerfile` 仍需要一个较小的 bootstrap 步骤来：

1. 安装 rpmfusion
2. 启用 `atim/nushell` COPR
3. 安装 `nushell`

只有这样，后续主 repo / package / system 流程才能交给 Nu。

---

## 维护建议

### 改包
优先改：

- `config/packages.nuon`

### 改仓库
优先改：

- `config/repos.nuon`

### 改额外 RPM 来源
优先改：

- `config/extras.nuon`

### 改系统服务或 flatpak remote
优先改：

- `config/system.nuon`

### 改执行逻辑
优先改：

- `scripts/lib/*.nu`
- `scripts/build.nu`

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
nu build/scripts/build.nu build --dry-run
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
