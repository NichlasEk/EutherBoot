#!/usr/bin/env python3
"""Read real UKI metadata from disposable copies; never boot or attach host disks."""
import json
from pathlib import Path
import shutil
import tempfile
from qemu_test import VM
import virtual_disk

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'artifacts/kernel-version'
OUT.mkdir(parents=True, exist_ok=True)

def metadata_fixture(version):
    data = bytearray(2048)
    data[0x202:0x206] = b'HdrS'
    data[0x206:0x208] = (0x20f).to_bytes(2, 'little')
    data[0x20e:0x210] = (0x200).to_bytes(2, 'little')
    data[1024:1024+len(version)+1] = version.encode()+b'\0'
    return data

with tempfile.TemporaryDirectory(prefix='eutherboot-version-') as temporary:
    tmp = Path(temporary)
    esp = tmp/'esp'
    (esp/'EFI/BOOT').mkdir(parents=True)
    directory = esp/'EFI/EutherBoot'
    directory.mkdir()
    shutil.copy2(ROOT/'artifacts/EutherBoot.efi', esp/'EFI/BOOT/BOOTX64.EFI')
    shutil.copy2(ROOT/'artifacts/TestChild.efi', directory/'child.efi')
    (directory/'direct.efi').write_bytes(metadata_fixture('6.12.99-test-amd64'))
    # Use installed images only as read-only sources for disposable test copies.
    paths = [Path('/boot/EFI/Linux/arch-normal.efi'), Path('/boot/EFI/Linux/arch-lts.efi')]
    names = ['Arch Linux', 'Arch Linux LTS (reserv)', 'Debian Linux', 'EFI tool']
    files = ['normal.efi', 'lts.efi', 'direct.efi', 'child.efi']
    for path, name in zip(paths, files):
        shutil.copy2(path, directory/name)
    checks = []
    for iteration, (width, height, theme) in enumerate([(640,480,'system-regis'), (1024,768,'system-regis-light'), (1280,960,'high-contrast')]):
        cfg = f"[boot]\ndefault='e0'\ntimeout=0\ntheme='{theme}'\nlanguage='sv'\n"
        for i, (name, file) in enumerate(zip(names, files)):
            cfg += f"\n[[entry]]\nid='e{i}'\nname='{name}'\ntype='efi'\npath='\\EFI\\EutherBoot\\{file}'\n"
        (directory/'eutherboot.toml').write_text(cfg)
        diskdir = tmp/f'disk-{iteration}'
        diskdir.mkdir()
        disk = virtual_disk.create(esp, diskdir, esp_mib=1024)
        with VM(tmp, disk, OUT, iteration, width=width, height=height) as vm:
            log = vm.log.read_text()
            for i in range(3):
                assert f'KERNEL_VERSION e{i} ' in log, log
            assert 'KERNEL_VERSION e3' not in log
            vm.screen('versions')
            vm.key('right', 'GRAPHICS_READY')
            vm.key('right', 'GRAPHICS_READY')
            vm.screen('direct')
            vm.key('right', 'GRAPHICS_READY')
            vm.key('ret', 'CHILD_READY')
            vm.key('ret', 'MENU_RESUMED')
            vm.key('f2', 'TEXT_READY')
            vm.screen('text')
            checks.append({'resolution': [width,height], 'theme': theme,
                           'versions': [line for line in log.splitlines() if line.startswith('KERNEL_VERSION')]})
        disk.unlink()
        (diskdir/'fat.img').unlink()
        print('PASS', width, height, theme, flush=True)
    (OUT/'result.json').write_text(json.dumps(checks, indent=2)+'\n')
