#!/usr/bin/env python3
"""Fail on a missing device, required package, or wrong-board image metadata."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REQUIRED = {
    'luci', 'luci-compat', 'luci-app-store', 'fwxd', 'kmod-fwx',
    'luci-app-fwx-appfilter', 'luci-app-fwx-dashboard',
    'luci-app-fwx-traffic-stat', 'luci-app-fwx-app-center',
    'ipq-wifi-xiaomi_redmi-ax5400',
}
EXCLUDED = {'dockerd', 'docker', 'docker-compose', 'luci-app-dockerman',
            'samba4-server', 'kmod-fs-ksmbd', 'kmod-usb-storage'}


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def verify_config(root):
    lines = set((root / '.config').read_text().splitlines())
    for symbol in ['TARGET_qualcommax', 'TARGET_qualcommax_ipq50xx',
                   'TARGET_qualcommax_ipq50xx_DEVICE_xiaomi_redmi-ax5400',
                   'TARGET_ROOTFS_INITRAMFS', 'TARGET_ROOTFS_SQUASHFS']:
        require(f'CONFIG_{symbol}=y' in lines, f'Missing target option: {symbol}')
    devices = [line for line in lines if line.startswith('CONFIG_TARGET_')
               and '_DEVICE_' in line and line.endswith('=y')]
    require(len(devices) == 1, f'Expected exactly one target device: {devices}')
    for pkg in REQUIRED:
        require(f'CONFIG_PACKAGE_{pkg}=y' in lines, f'Missing built-in package: {pkg}')
    for pkg in EXCLUDED:
        require(f'CONFIG_PACKAGE_{pkg}=y' not in lines and
                f'CONFIG_PACKAGE_{pkg}=m' not in lines,
                f'Unwanted package selected: {pkg}')
    print('RA74 target and package selections verified.')


def verify_image(root, output):
    images = root / 'bin/targets/qualcommax/ipq50xx'
    upgrade = list(images.glob('*-xiaomi_redmi-ax5400-squashfs-sysupgrade.bin'))
    initramfs = list(images.glob('*-xiaomi_redmi-ax5400-initramfs-factory.ubi'))
    require(len(upgrade) == 1 and len(initramfs) == 1,
            'Expected exactly one RA74 sysupgrade and one initramfs-factory image')
    with tempfile.TemporaryDirectory() as tmp:
        metadata = Path(tmp) / 'metadata.json'
        subprocess.run([str(root / 'staging_dir/host/bin/fwtool'), '-i',
                        str(metadata), str(upgrade[0])], check=True)
        data = json.loads(metadata.read_text())
    require('xiaomi,redmi-ax5400' in data.get('supported_devices', []),
            'Image metadata does not support xiaomi,redmi-ax5400')
    manifests = list(images.glob('*-xiaomi_redmi-ax5400.manifest'))
    require(len(manifests) == 1, 'Expected one RA74 manifest')
    packages = {line.split()[0] for line in manifests[0].read_text().splitlines() if line.strip()}
    require(REQUIRED <= packages, f'Packages absent from image: {REQUIRED - packages}')
    require(not (EXCLUDED & packages), f'Unwanted packages in image: {EXCLUDED & packages}')
    output.mkdir(parents=True, exist_ok=True)
    selected = upgrade + initramfs + manifests
    for name in ['config.buildinfo', 'feeds.buildinfo', 'version.buildinfo', 'profiles.json']:
        p = images / name
        if p.exists():
            selected.append(p)
    checksums = []
    for p in selected:
        shutil.copy2(p, output / p.name)
        checksums.append(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}')
    (output / 'SHA256SUMS').write_text('\n'.join(checksums) + '\n')
    (output / 'image-metadata.json').write_text(json.dumps(data, indent=2) + '\n')
    (output / 'VALIDATION.txt').write_text(
        'Build and image metadata checks passed.\n'
        'Experimental RA74 backport: NOT tested on physical hardware.\n'
        'No flashing operation was performed.\n')
    print('Image identity, package manifest and SHA256 checks completed; hardware untested.')


if __name__ == '__main__':
    require(len(sys.argv) >= 3, 'Usage: verify.py config|image BUILD_DIR [OUTPUT_DIR]')
    mode, build = sys.argv[1], Path(sys.argv[2]).resolve()
    if mode == 'config':
        verify_config(build)
    elif mode == 'image' and len(sys.argv) == 4:
        verify_config(build)
        verify_image(build, Path(sys.argv[3]).resolve())
    else:
        raise SystemExit('Invalid verification mode')
