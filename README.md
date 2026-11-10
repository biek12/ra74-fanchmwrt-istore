# RA74：FanchmWrt + iStore 云端构建方案

面向 **Redmi AX5400 普通版 RA74**。不是电竞版 RB04，也不是其他 AX5400。
目标是家庭使用：FanchmWrt 的应用识别、终端与流量管理，加上独立的 iStore 软件中心。
不移植 iStoreOS 的 Docker、NAS、QuickStart 整套组件。

**状态：实验性源码移植。云端配置校验已通过，完整编译进行中，尚未实机刷入。不能作为稳定固件使用。**
本工具包不会连接路由器，也不会执行刷写操作。

构建仓库：[biek12/ra74-fanchmwrt-istore](https://github.com/biek12/ra74-fanchmwrt-istore)。
当前运行：[完整构建 #2](https://github.com/biek12/ra74-fanchmwrt-istore/actions/runs/42779712583)。

## 已完成与待完成

- 固定 FanchmWrt、FanchmWrt 插件与 iStore 源码提交。
- 从 OpenWrt 已合入的 RA74 补丁制作针对该 FanchmWrt 提交的适配补丁。
- 准备只需手动触发的 GitHub Actions、精简配置、配置/镜像核验和日志归档。
- 本机完成补丁反向匹配、diff 格式检查、修改过的 shell 脚本语法检查。
- Linux 上 `make defconfig` 及 RA74 / DPI / iStore 必需项、排除项检查已在运行 #2 中通过。
- 尚待完整编译与镜像核验。
- 尚待实机验证 WAN、各 LAN、双频 Wi-Fi、管控有效性、性能和长期稳定性。

首次云端构建已执行，停在配置检查阶段，没有产出固件。
该次日志暴露了固定 feeds 的 WeeChat 虚拟包循环依赖，以及 iStore 所需 GNU tar/xz 的配置约束。
现在用 `0002-luci-weechat-provider.patch` 选择具体的 WeeChat provider，并显式选择 `xz-utils`/`tar`。
不编译 WeeChat；修复其包定义是为了让全局 Kconfig 正常解析。运行 #2 已通过配置检查，正在完整构建。

本机不启动完整编译：2026-11-10 检查时 Mac 只有约 17 GiB 可用空间，Docker/Colima 未运行。
当前 XERJ 因磁盘水位拒绝索引，本次以直接源码核对为依据。

## 如何在 GitHub Actions 编译

1. 新建一个构建仓库。将**本目录内容**作为仓库根目录上传，包含隐藏的 `.github` 目录。
   不要把本目录外的电脑管理工作区上传，也不要上传 `.work` 或 `artifacts`。
2. 默认分支存在 `.github/workflows/build-ra74.yml` 后，打开仓库 **Actions**。
3. 选择 **Build experimental RA74 FanchmWrt + iStore**，点击 **Run workflow**。
4. 首次可以选择 `configure-only`，核对机型、软件包和依赖；随后选择 `full` 完整编译。
5. 完成后从该次运行的 **Artifacts** 下载 `ra74-experimental-编号`。

完整构建时间取决于 runner 和下载速度，可能持续数小时。流程没有定时任务，不会反复自动构建。
工作流仅有 `contents: read` 权限；不会发布 Release，不需要路由器密码或个人访问令牌。
它会在临时 Ubuntu runner 上移除不用的 Android/.NET/GHC/CodeQL SDK 以释放编译空间。
私有仓库的运行可能消耗账户 Actions 额度；请以账户实际套餐为准。

## 正常情况下的产物

- `…xiaomi_redmi-ax5400-initramfs-factory.ubi`：首次安装流程所需的过渡镜像。
- `…xiaomi_redmi-ax5400-squashfs-sysupgrade.bin`：匹配的系统升级镜像。
- `SHA256SUMS`、镜像元信息、软件包 manifest、完整配置和源码版本记录。
- 下载/构建日志；失败时也会保存尽可能完整的诊断资料。

只有机型元信息正确、必需软件包存在且已排除 Docker/SMB 存储包，镜像才会进入产物目录。
检查通过只证明构建与镜像身份，不能证明网口、无线和 DPI 在真机上工作正常。
不要把 `.bin` 当成小米原厂网页可以直接接受的安装包。

## 适配做了什么

基底：`fanchmwrt-25.12.6`，提交见 `sources.lock.env`。

`patches/0001-ra74-backport.patch` 基于 OpenWrt RA74 支持提交
[`09e55e10087726424a6f42f773a2a0f8f7dbbefe`](https://github.com/openwrt/openwrt/commit/09e55e10087726424a6f42f773a2a0f8f7dbbefe)。
原作者及提交说明保留在 `reference/openwrt-pr-23374.patch`。相对原补丁调整：

- 设备树移到此分支使用的 `files/arch/arm64/boot/dts/qcom/`。
- 无线板级数据注册按此分支 Makefile 上下文重定位。
- RA74 单独声明 LAN/WAN 与 CPU conduit，保持上游的双 CPU 连接方案；其他机型配置不变。
- 将 RA74 同时加入 Xiaomi 的 initramfs 预处理与正式升级分支；使用匹配 DTS 的 `ubi_kernel` / `rootfs` 布局。
- LED、无线校准、环境变量及镜像定义沿用上游适配。

**高风险待验证项**：QCA8337 双 CPU 连接及 WAN 可用性、DTS 依赖与无线内存占用、首次安装时的 UBI 迁移。
这里没有引入社区 NSS 实验补丁，也没有更换 U-Boot。不要通过改型号或强制升级绕过匹配检查。

FanchmWrt 当前已有相同 IPQ5018 基础驱动和 QCA8K 支持，但这不等于 RA74 移植已验证。
安装/回退流程必须在实际设备分区、启动槽及完整备份核实后另行制定。

## 自己在 Linux 上运行

使用普通用户、Ubuntu 24.04，安装依赖参考工作流中的 apt 命令。
建议预留至少 25 GiB 可用空间及足够内存；本脚本以两线程编译控制峰值占用。

```bash
bash scripts/prepare.sh
bash scripts/build.sh
```

`prepare.sh` 只接受全新的 `.work/fanchmwrt`，不会清除已有目录。
失败后先保留日志排查，使用一个新的工具包副本重试。
更换上游版本后须重做补丁与构建验证，不能仅修改 commit 后直接刷机。

## 刷机前的实机验证阶段

构建完成后，先检查备份与恢复路径，再安排有线连接的测试窗口。
通过匹配的首次安装流程启动后，依次检查 WAN 拨号/DHCP、三个 LAN、2.4G/5G、吞吐、重启持久化及 iStore 插件依赖。
应用识别和管控必须用真实终端流量验证，并确认加速设置不会绕过管控。
持续运行观察后才能决定是否替代家庭主路由；这里不附带自动刷机脚本。

## 来源与授权

- [FanchmWrt 源码](https://github.com/fanchmwrt/fanchmwrt)
- [RA74 原始适配 PR](https://github.com/openwrt/openwrt/pull/23374)
- [iStore 集成说明](https://github.com/istoreos/istore)
- [OpenWrt 构建说明](https://openwrt.org/docs/guide-developer/toolchain/use-buildsystem)

补丁中的上游代码保留原作者版权，适用其上游许可证。本目录新增构建脚本按 GPL-2.0-only 提供，许可证见 `LICENSE`。
FanchmWrt 功能及特征库须遵守其项目声明；不要把本构建方案解释为改变了上游授权。
