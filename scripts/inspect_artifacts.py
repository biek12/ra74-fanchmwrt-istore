#!/usr/bin/env python3
"""Read-only RA74 FIT/DTB/UBI structural checks; no extraction to device paths.

Layouts: dtc/libfdt/fdt.h; Linux drivers/mtd/ubi/ubi-media.h and
fs/squashfs/squashfs_fs.h. These checks do not establish hardware safety.
"""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tarfile
import zlib


def check(ok, message):
    if not ok:
        raise ValueError(message)


def cells(data):
    check(len(data) % 4 == 0, 'Unaligned cell property')
    return struct.unpack('>' + 'I' * (len(data) // 4), data)


def strings(data):
    return data.rstrip(b'\0').decode('utf-8').split('\0')


def fdt(data):
    check(len(data) >= 40, 'Truncated FDT header')
    magic, size, off, names, _, version, compat, _, names_size, tree_size = struct.unpack_from('>10I', data)
    check(magic == 0xd00dfeed and version >= 17 and compat <= 17, 'Unsupported FDT header')
    check(40 <= off <= off + tree_size <= size <= len(data), 'Invalid FDT structure bounds')
    check(40 <= names <= names + names_size <= size, 'Invalid FDT strings bounds')
    name_block = data[names:names + names_size]
    end = off + tree_size
    nodes, stack = {}, []
    while off + 4 <= end:
        tag = struct.unpack_from('>I', data, off)[0]
        off += 4
        if tag == 1:
            nul = data.find(b'\0', off, end)
            check(nul >= off, 'Unterminated FDT node')
            stack.append(data[off:nul].decode('utf-8'))
            path = '/' + '/'.join(stack[1:])
            check(path not in nodes, 'Duplicate FDT node')
            nodes[path] = {}
            off = (nul + 4) & ~3
        elif tag == 2:
            check(bool(stack), 'Unbalanced FDT node end')
            stack.pop()
        elif tag == 3:
            check(stack and off + 8 <= end, 'Invalid FDT property')
            length, name_off = struct.unpack_from('>II', data, off)
            off += 8
            nul = name_block.find(b'\0', name_off)
            check(0 <= name_off < len(name_block) and nul >= name_off, 'Invalid FDT property name')
            check(off + length <= end, 'Truncated FDT property')
            nodes['/' + '/'.join(stack[1:])][name_block[name_off:nul].decode()] = data[off:off + length]
            off = (off + length + 3) & ~3
        elif tag == 4:
            continue
        elif tag == 9:
            check(not stack, 'Unclosed FDT node')
            return nodes, size
        else:
            raise ValueError(f'Unknown FDT tag {tag}')
    raise ValueError('Missing FDT end token')


def inspect_fit(data):
    fit, fit_size = fdt(data)
    embedded = []
    for path, props in fit.items():
        if not path.startswith('/images/') or 'type' not in props:
            continue
        image_type = strings(props['type'])[0]
        if image_type == 'kernel':
            check(strings(props.get('arch', b'')) == ['arm64'], 'FIT kernel is not ARM64')
        if image_type != 'flat_dt':
            continue
        blob = props.get('data')
        if blob is None:
            length, = cells(props['data-size'])
            if 'data-position' in props:
                start, = cells(props['data-position'])
            else:
                offset, = cells(props['data-offset'])
                start = ((fit_size + 3) & ~3) + offset
            blob = data[start:start + length]
            check(len(blob) == length, 'Truncated FIT device tree')
        tree, tree_size = fdt(blob)
        check('xiaomi,redmi-ax5400' in strings(tree['/'].get('compatible', b'')), 'Wrong embedded board')
        partitions = {}
        for node in tree.values():
            if 'label' in node and 'reg' in node:
                label = strings(node['label'])[0]
                if label in ('0:art', 'ubi_kernel', 'rootfs'):
                    partitions[label] = cells(node['reg'])
                    if label == '0:art':
                        check('read-only' in node, 'ART calibration partition is not read-only')
        check(partitions == {'0:art': (0x780000, 0x100000),
                             'ubi_kernel': (0xa80000, 0x2400000),
                             'rootfs': (0x2e80000, 0x5180000)}, 'Unexpected RA74 partition layout')
        embedded.append({'model': strings(tree['/']['model'])[0],
                         'dtb_sha256': hashlib.sha256(blob[:tree_size]).hexdigest(),
                         'partitions': partitions})
    check(len(embedded) == 1, 'Expected exactly one RA74 device tree in FIT')
    return embedded[0]


def ubi_kernel(data):
    block_size = 128 * 1024
    check(data and len(data) % block_size == 0, 'UBI image is not 128 KiB aligned')
    chunks = {}
    geometry = set()
    for start in range(0, len(data), block_size):
        block = data[start:start + block_size]
        check(block[:5] == b'UBI#\x01', 'Invalid UBI EC header')
        crc, = struct.unpack_from('>I', block, 60)
        check((zlib.crc32(block[:60]) ^ 0xffffffff) == crc, 'UBI EC header CRC mismatch')
        vid, payload, seq = struct.unpack_from('>III', block, 16)
        check(64 <= vid < payload < block_size and payload % 2048 == 0, 'Unexpected UBI page geometry')
        geometry.add((vid, payload, seq))
        if block[vid:vid + 4] == b'\xff' * 4:
            continue
        header = block[vid:vid + 64]
        check(header[:5] == b'UBI!\x01', 'Invalid UBI VID header')
        crc, = struct.unpack_from('>I', header, 60)
        check((zlib.crc32(header[:60]) ^ 0xffffffff) == crc, 'UBI VID header CRC mismatch')
        vol_id, lnum = struct.unpack_from('>II', header, 8)
        if vol_id == 0:
            check(lnum not in chunks, 'Duplicate kernel logical eraseblock')
            chunks[lnum] = block[payload:]
    check(len(geometry) == 1 and chunks, 'Inconsistent UBI geometry or absent kernel volume')
    check(sorted(chunks) == list(range(len(chunks))), 'Missing kernel logical eraseblock')
    return b''.join(chunks[i] for i in range(len(chunks)))


def inspect(directory):
    upgrades = list(directory.glob('*-xiaomi_redmi-ax5400-squashfs-sysupgrade.bin'))
    installers = list(directory.glob('*-xiaomi_redmi-ax5400-initramfs-factory.ubi'))
    check(len(upgrades) == len(installers) == 1, 'Expected one matching image pair')
    with tarfile.open(upgrades[0], 'r:*') as archive:
        kernels = [m for m in archive.getmembers() if m.isfile() and m.name.endswith('/kernel')]
        roots = [m for m in archive.getmembers() if m.isfile() and m.name.endswith('/root')]
        check(len(kernels) == len(roots) == 1, 'Unexpected sysupgrade archive layout')
        check(kernels[0].size < 0x2400000 and roots[0].size < 0x5180000, 'Image exceeds declared partition')
        kernel = archive.extractfile(kernels[0]).read()
        root = archive.extractfile(roots[0]).read()
    check(len(root) >= 96 and root[:4] == b'hsqs', 'Root filesystem is not SquashFS')
    major, minor = struct.unpack_from('<HH', root, 28)
    used, = struct.unpack_from('<Q', root, 40)
    check((major, minor) == (4, 0) and 96 <= used <= len(root), 'Invalid SquashFS superblock')
    installed = inspect_fit(kernel)
    installer = inspect_fit(ubi_kernel(installers[0].read_bytes()))
    check(installed['dtb_sha256'] == installer['dtb_sha256'], 'Installer and upgrade use different device trees')
    return {'sysupgrade': upgrades[0].name, 'installer': installers[0].name,
            'embedded_board': installed, 'rootfs_bytes_used': used,
            'status': 'Structural checks passed; hardware remains untested'}


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: inspect_artifacts.py ARTIFACT_DIRECTORY')
    try:
        print(json.dumps(inspect(Path(sys.argv[1])), indent=2))
    except (ValueError, KeyError, struct.error, tarfile.TarError) as error:
        raise SystemExit(str(error))
