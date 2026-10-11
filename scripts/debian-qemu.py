#!/usr/bin/env python3
"""Boot Debian 13 through EutherBoot on disposable disks; probe the initrd limit."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from guest_console import command, drain, wait
from qemu_test import VM
import virtual_disk

ROOT = Path(__file__).resolve().parent.parent
p = argparse.ArgumentParser()
p.add_argument('--case', choices=('normal', 'limit', 'large', 'maximum', 'empty', 'cmdline'), default='normal')
p.add_argument('--firmware', type=Path, default=ROOT/'artifacts/EutherBoot.efi')
p.add_argument('--production', action='store_true', help='No debug markers; use timed autoboot and serial oracle')
a = p.parse_args()
fixture = ROOT/'artifacts/debian'
out = fixture/('production-'+a.case if a.production else a.case)
out.mkdir(exist_ok=True)
(out/'result.json').unlink(missing_ok=True)
m = json.loads((fixture/'manifest.json').read_text())

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

assert sha(m['image']) == m['image_sha256']
for name, expected in m['artifacts'].items():
    assert sha(fixture/name) == expected
with tempfile.TemporaryDirectory(prefix='eutherboot-debian-') as directory:
    tmp = Path(directory)
    esp = tmp/'esp'
    (esp/'EFI/BOOT').mkdir(parents=True)
    (esp/'EFI/EutherBoot').mkdir()
    (esp/'EFI/Linux').mkdir()
    shutil.copy2(a.firmware, esp/'EFI/BOOT/BOOTX64.EFI')
    shutil.copy2(ROOT/'artifacts/TestChild.efi', esp/'EFI/EutherBoot/child.efi')
    for name in ('kernel.efi', 'initrd.img'):
        shutil.copy2(fixture/name, esp/'EFI/Linux'/name)
    if a.case in ('large', 'maximum', 'limit', 'empty'):
        # Linux initramfs permits zero padding between/after archives. Keep the
        # exact Debian payload; exercise the old cap and the new size boundaries.
        with (esp/'EFI/Linux/initrd.img').open('ab') as f:
            size = {'large': 128*1024**2+1, 'maximum': 512*1024**2,
                    'limit': 512*1024**2+1, 'empty': 0}[a.case]
            f.truncate(size)
    if a.case == 'cmdline':
        with (esp/'EFI/Linux/kernel.efi').open('r+b') as f:
            f.seek(0x238)
            f.write((1).to_bytes(4, 'little'))
    initrd_bytes = (esp/'EFI/Linux/initrd.img').stat().st_size
    cmdline = f"root=PARTUUID={m['root']['guid']} rw console=ttyS0,115200 init=/bin/bash"
    config = "[boot]\ndefault='debian'\ntimeout=0\n[[entry]]\nid='debian'\nname='Debian GNU/Linux'\ntype='linux-efi'\npath='\\EFI\\Linux\\kernel.efi'\ninitrd='\\EFI\\Linux\\initrd.img'\ncmdline='"+cmdline+"'\n[[entry]]\nid='recovery'\nname='Recovery child'\ntype='efi'\npath='\\EFI\\EutherBoot\\child.efi'\n"
    (esp/'EFI/EutherBoot/eutherboot.toml').write_text(config)
    if a.production:
        assert a.case in ('normal', 'large', 'maximum')
        config = config.replace('timeout=0', 'timeout=3')
        (esp/'EFI/EutherBoot/eutherboot.toml').write_text(config)
    (out/'eutherboot.toml').write_text(config)
    disk = virtual_disk.create(esp, tmp, esp_mib=1024 if a.case in ('maximum', 'limit') else 256)
    before = sha(disk)
    overlay = tmp/'root.qcow2'
    subprocess.run(['qemu-img', 'create', '-f', 'qcow2', '-F', 'qcow2', '-b', m['image'], str(overlay)], check=True, capture_output=True)
    serial_path = tmp/'serial'
    accel = 'kvm' if os.access('/dev/kvm', os.R_OK|os.W_OK) else 'tcg'
    with VM(tmp, disk, out, memory=2048, accel=accel, cpu='host' if accel=='kvm' else 'max',
            extra_disks=((overlay, 'qcow2'),), serial_socket=serial_path,
            ready_marker=None if a.production else 'MENU_READY') as v:
        v.screen('menu')
        with socket.socket(socket.AF_UNIX) as serial:
            serial.connect(str(serial_path))
            threading.Thread(target=drain, args=(serial,), daemon=True).start()
            if a.case in ('limit', 'empty', 'cmdline'):
                v.key('ret', 'MENU_RESUMED')
                log = v.log.read_text()
                assert 'Linux EFI setup: BAD_BUFFER_SIZE' in log
                if a.case == 'cmdline':
                    assert 'kernel max 1' in log
                else:
                    assert f'initrd {initrd_bytes} bytes; allowed 1..=536870912' in log
                assert 'CHAINLOAD_LOADED' not in log
                v.screen('error')
                v.key('down', 'SELECT 1')
                v.key('ret', 'CHILD_READY')
                v.key('ret', 'MENU_RESUMED')
                oracle = 'Rejected before Linux; recovery child starts and returns'
            else:
                if not a.production:
                    v.key('ret')
                wait(v, r'root@[^\r\n]*#', timeout=240)
                serial.sendall(b'stty -echo; export TERM=dumb\n')
                time.sleep(.3)
                oracle = command(v, serial, "cat /etc/os-release; uname -r; cat /proc/cmdline; test -d /sys/firmware/efi; test \"$(. /etc/os-release; echo $VERSION_ID)\" = 13; test \"$(uname -r)\" = "+m['kernel_version'])
                if not a.production:
                    assert 'INITRD_COPIED' in v.log.read_text()
                serial.sendall(b'exec /sbin/init\n')
                wait(v, r'login: ', timeout=180)
                oracle += '\nReached systemd login prompt after executing /sbin/init\n'
                v.screen('debian-booted')
    assert sha(disk) == before, 'Unexpected EFI disk mutation'
assert sha(m['image']) == m['image_sha256'], 'Original Debian image changed'
(out/'result.json').write_text(json.dumps(dict(result='PASS', case=a.case, kernel=m['kernel_version'],
    initrd_bytes=initrd_bytes, firmware_sha256=sha(a.firmware), image_sha256=m['image_sha256'],
    esp_sha256=before, oracle=oracle, network=False, production=a.production, host_disks_attached=False), indent=2)+'\n')
print(f'PASS Debian {a.case}: kernel={m["kernel_version"]}, initrd={initrd_bytes} bytes')
