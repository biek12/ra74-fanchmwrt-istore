# 构建 #2 验证记录

**结论：固件已成功编译并通过离线检查，仍是待实机验证的实验版本。**

- [GitHub Actions 运行 #2](https://github.com/biek12/ra74-fanchmwrt-istore/actions/runs/42779712583)
- 构建仓库提交：`e935eb9f0be747ea8fa055e42ca5702a9a9622dd`
- 北京时间：2026-11-10 16:03 开始，17:34 完成，约 90 分钟。
- 源码：FanchmWrt `11b65ca6a58dc7fad27eef196b391789195393b8`，基于 OpenWrt 25.12.6。
- 内核：6.12.112；目标：`qualcommax/ipq50xx`；机型：`xiaomi,redmi-ax5400`。
- 固件内包含 325 个包，包括 `fwxd 1.0.5`、`kmod-fwx`、`luci-app-store 0.2.1` 和 FanchmWrt 的应用过滤、仪表盘、流量统计。
- IPQ5018/QCN9074 无线固件、AHB/PCI ath11k 模块与 RA74 板级数据均在清单中。
- 已排除 Docker、Samba4 服务端、ksmbd 和 USB 存储包。

## 文件与 SHA256

| 文件 | 字节数 | SHA256 |
| --- | ---: | --- |
| `openwrt-qualcommax-ipq50xx-xiaomi_redmi-ax5400-initramfs-factory.ubi` | 22413312 | `6e384a0c4b4a75d0eb6146336b802566d32e9471a2abd3aaaec3865f47f3d975` |
| `openwrt-qualcommax-ipq50xx-xiaomi_redmi-ax5400-squashfs-sysupgrade.bin` | 20644120 | `cc950907264e61a93a58baa2ac0661f1385e56e92022cb0dd47dea6f4632e74a` |

文件名的 `openwrt` 前缀来自上游构建系统，不代表这是未修改的 OpenWrt 官方发布镜像。

## 实际检查

云端完成：配置解析、必需/排除包检查、完整编译、fwtool 机型元信息与软件包清单核验。
下载后完成：所有 SHA256 与云端清单一致；两份镜像嵌入相同 RA74 设备树，DTB SHA256 为
`ef34202fbccb2e2b9d36b79a1ef825881680228f1f323e579d8e2182f37cf16c`。

确认 ARM64 内核 FIT、只读 ART、预期分区地址、UBI 的 128 KiB 块布局和 EC/VID 头 CRC、连续内核逻辑块、SquashFS v4 及大小边界。
离线检查器还用独立的 ImmortalWrt RA74 initramfs 作为格式参考，验证损坏头 CRC、截断块、错误机型会被拒绝。
这些格式检查不会替代 U-Boot 启动或真机驱动验证。

日志中的三处 `Error 2 (ignored)` 均发生于构建主机工具的清理步骤（libtool/elfutils）；后续编译、打包与整个 Actions 均成功。
第一次运行 #1 暴露的依赖循环和 iStore tar/xz 选择问题已在 #2 修复。

## 尚未验证

没有连接或刷写路由器。WAN、各 LAN、双频 Wi-Fi、吞吐、应用识别、规则控制、iStore 联网安装、重启持久化和长期稳定性均待实机验证。
源码 backport 保留上游 UBI 迁移机制；首次安装前须读取实际分区与启动槽、完整备份并确认恢复方案。
不能直接把 sysupgrade 文件上传到小米原厂升级页面。

Actions 产物默认保留 14 天。源码和构建脚本保存在仓库；请另存固件和校验文件。
