#!/usr/bin/env python3
"""Extract Debian's kernel/initrd from a checksum-verified local cloud image.

Only regular image files are used: no mounts, NBD devices or host boot writes.
Download the image and SHA512SUMS from the same official Debian directory first.
"""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'artifacts/debian'
IMAGE = OUT / 'download/debian-13-generic-amd64.qcow2'

def digest(path, algorithm='sha256'):
    with path.open('rb') as f:
        return hashlib.file_digest(f, algorithm).hexdigest()

def run(*args):
    return subprocess.run(list(map(str, args)), check=True, capture_output=True).stdout

expected = next(line.split()[0] for line in (IMAGE.parent/'SHA512SUMS').read_text().splitlines()
                if line.split()[-1] == IMAGE.name)
assert digest(IMAGE, 'sha512') == expected, 'Debian download checksum mismatch'
info = json.loads(run('qemu-img', 'info', '--output=json', IMAGE))
assert info['format'] == 'qcow2' and not info.get('backing-filename')
assert info['virtual-size'] <= 16 * 1024**3
with tempfile.TemporaryDirectory(prefix='extract-', dir=OUT) as directory:
    work = Path(directory)
    raw = work/'disk.raw'
    run('qemu-img', 'convert', '-f', 'qcow2', '-O', 'raw', IMAGE, raw)
    with raw.open('rb') as f:
        f.seek(512)
        header = f.read(512)
        assert header[:8] == b'EFI PART'
        location, count, size = struct.unpack_from('<QII', header, 72)
        assert count <= 128 and 128 <= size <= 512
        f.seek(location * 512)
        entries = f.read(count * size)
    parts = []
    for i in range(count):
        e = entries[i*size:(i+1)*size]
        if e[:16] == bytes(16):
            continue
        first, last = struct.unpack_from('<QQ', e, 32)
        assert 0 < first <= last and (last+1)*512 <= raw.stat().st_size
        parts.append(dict(number=i+1, type=str(uuid.UUID(bytes_le=e[:16])),
                          guid=str(uuid.UUID(bytes_le=e[16:32])), offset=first*512,
                          size=(last-first+1)*512))
    root = max(parts, key=lambda p: p['size'])
    partition = work/'root.ext4'
    with raw.open('rb') as source, partition.open('xb') as target:
        start = root['offset']
        end = start + root['size']
        target.truncate(root['size'])
        position = start
        while position < end:
            try:
                data = os.lseek(source.fileno(), position, os.SEEK_DATA)
            except OSError as e:
                if e.errno == 6:
                    break
                raise
            if data >= end:
                break
            hole = min(os.lseek(source.fileno(), data, os.SEEK_HOLE), end)
            source.seek(data)
            target.seek(data-start)
            while data < hole:
                n = os.copy_file_range(source.fileno(), target.fileno(), min(8*1024**2, hole-data))
                assert n > 0
                data += n
            position = hole
    listing = run('debugfs', '-R', 'ls -p /boot', partition).decode()
    (OUT/'boot-files.txt').write_text(listing)
    names = [line.split('/')[5] for line in listing.splitlines() if line.startswith('/')]
    kernel = next(name for name in names if name.startswith('vmlinuz-'))
    version = kernel.removeprefix('vmlinuz-')
    for source, target in [(kernel, 'kernel.efi'), ('initrd.img-'+version, 'initrd.img')]:
        run('debugfs', '-R', f'dump /boot/{source} {OUT/target}', partition)
        assert (OUT/target).stat().st_size > 0
    (OUT/'manifest.json').write_text(json.dumps(dict(
        source='https://cloud.debian.org/images/cloud/trixie/latest/',
        image=str(IMAGE), image_sha512=expected, image_sha256=digest(IMAGE),
        kernel_version=version, root=root, partitions=parts,
        artifacts={name: digest(OUT/name) for name in ('kernel.efi', 'initrd.img')},
        initrd_bytes=(OUT/'initrd.img').stat().st_size), indent=2)+'\n')
print('Verified Debian image and extracted kernel/initrd without mounting disks')
