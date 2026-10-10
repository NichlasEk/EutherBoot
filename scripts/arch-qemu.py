#!/usr/bin/env python3
"""Boot official installed Arch twice through EutherBoot, without host mounts."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import time
import threading
import uuid
from qemu_test import VM
import virtual_disk

ROOT=Path(__file__).resolve().parent.parent
fixtures=ROOT/'artifacts/arch'
out=ROOT/'artifacts/arch-qemu';out.mkdir(parents=True,exist_ok=True)
(out/'result.json').unlink(missing_ok=True)
def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
manifest=json.loads((fixtures/'manifest.json').read_text())
image=Path(manifest['image'])
assert image.is_file() and digest(image)==manifest['image_sha256']
for name,expected in manifest['artifacts'].items():assert digest(fixtures/name)==expected
assert (fixtures/'initrd.img').stat().st_size<=128*1024**2
accel='kvm' if os.access('/dev/kvm',os.R_OK|os.W_OK) else 'tcg'
results=[]

def drain_serial(serial):
    # Read continuously: QEMU can otherwise block on an unread socket mid-line.
    try:
        while serial.recv(65536): pass
    except OSError: pass

def wait_serial(v,pattern,offset=0,timeout=180):
    deadline=time.monotonic()+timeout
    while True:
        text=(v.base/'serial.log').read_text(errors='replace')[offset:]
        match=re.search(pattern,text)
        if match:return match
        if v.proc.poll() is not None or time.monotonic()>deadline:
            raise AssertionError(f'Guest did not produce {pattern}: {text[-5000:]}')
        time.sleep(.1)

with tempfile.TemporaryDirectory(prefix='eutherboot-arch-') as directory:
    tmp=Path(directory);source=tmp/'esp'
    for folder in ('BOOT','EutherBoot','Linux'):(source/'EFI'/folder).mkdir(parents=True)
    shutil.copy2(ROOT/'artifacts/EutherBoot.efi',source/'EFI/BOOT/BOOTX64.EFI')
    for name in ('kernel.efi','initrd.img'):shutil.copy2(fixtures/name,source/'EFI/Linux'/name)
    cmdline=f"root=PARTUUID={manifest['root']['guid']} rw rootflags=compress=zstd:1 console=tty0 console=ttyS0,115200 systemd.mask=systemd-time-wait-sync.service"
    config="[boot]\ndefault='arch'\ntimeout=0\n\n[[entry]]\nid='arch'\nname='Arch Linux - installed system'\ntype='linux-efi'\npath='\\EFI\\Linux\\kernel.efi'\ninitrd='\\EFI\\Linux\\initrd.img'\ncmdline='"+cmdline+"'\n"
    (source/'EFI/EutherBoot/eutherboot.toml').write_text(config)
    (out/'eutherboot.toml').write_text(config)
    disk=virtual_disk.create(source,tmp,esp_mib=512);esp_before=digest(disk)
    overlay=tmp/'arch.qcow2'
    subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(image),str(overlay)],check=True,capture_output=True)
    token=uuid.uuid4().hex
    for iteration in (1,2):
        serial_path=tmp/f'serial-{iteration}'
        with VM(tmp,disk,out,iteration,memory=2048,cpu='host' if accel=='kvm' else 'max',
                readonly=True,extra_disks=((overlay,'qcow2'),),accel=accel,serial_socket=serial_path) as v:
            with socket.socket(socket.AF_UNIX) as serial:
                serial.connect(str(serial_path))
                threading.Thread(target=drain_serial,args=(serial,),daemon=True).start()
                v.screen('menu');v.key('ret','CHAINLOAD_LOADED')
                wait_serial(v,r'login: ')
                serial.sendall(b'arch\n');wait_serial(v,r'Password: ');serial.sendall(b'arch\n')
                wait_serial(v,r'\[arch@[^\r\n]+\][\$] ')
                serial.sendall(b'stty -echo; export SYSTEMD_COLORS=0 SYSTEMD_URLIFY=0 TERM=dumb\n');time.sleep(.3)
                # Frame output after disabling terminal echo: commands cannot satisfy the oracle.
                before=len((v.base/'serial.log').read_text(errors='replace'))
                actions=[
                    'set -e',
                    "test \"$(cat /proc/1/comm)\" = systemd",
                    '. /etc/os-release; test "$ID" = arch',
                    'test "$(findmnt -n -o FSTYPE /)" = btrfs',
                    f'test "$(lsblk -no PARTUUID /dev/vdb{manifest["root"]["number"]})" = {manifest["root"]["guid"]}',
                    f'test "$(findmnt -n -o SOURCE /)" = /dev/vdb{manifest["root"]["number"]}',
                    'for attempt in $(seq 1 90); do systemctl is-active --quiet multi-user.target && break; sleep 1; done',
                    'systemctl list-jobs --no-pager',
                    'systemctl is-active --quiet multi-user.target',
                    'pacman -Q base linux systemd',
                    'uname -r',
                    'findmnt -n -o SOURCE,FSTYPE,OPTIONS /',
                    'systemctl --failed --no-legend --no-pager',
                    'test -z "$(systemctl --failed --no-legend --no-pager)"',
                ]
                if iteration==1:actions += [f"printf '%s\\n' {token} | sudo tee /var/lib/eutherboot-persistence >/dev/null",'sync']
                actions += [f'test "$(cat /var/lib/eutherboot-persistence)" = {token}',
                            "printf '\\nARCH_BOOT_ID=%s\\n' \"$(cat /proc/sys/kernel/random/boot_id)\"",
                            f"printf 'ARCH_PASS_%s\\n' {token}"]
                serial.sendall(('( '+ '; '.join(actions)+' )\n').encode())
                wait_serial(v,rf'(?m)^ARCH_PASS_{token}\r?$',before,120)
                log=(v.base/'serial.log').read_text(errors='replace')
                boot_id=re.search(r'ARCH_BOOT_ID=([a-f0-9-]+)',log[before:]).group(1)
                debug=v.log.read_text()
                for marker in ('LINUX_EFI_PREPARED','INITRD_INSTALLED','INITRD_COPIED','CHAINLOAD_LOADED'):assert marker in debug
                results.append({'boot':iteration,'boot_id':boot_id,'persistence':True,'loadfile2':True,
                    'linux_package':re.search(r'(?m)^linux ([^\r\n]+)',log[before:]).group(1),
                    'systemd_package':re.search(r'(?m)^systemd ([^\r\n]+)',log[before:]).group(1),
                    'root':f'/dev/vdb{manifest["root"]["number"]}',
                    'filesystem':'btrfs','multi_user_target':'active','failed_units':0})
                v.screen('arch-running')
                serial.sendall(b'sudo systemctl poweroff\n');v.proc.wait(timeout=60)
        print(f'Arch cold boot {iteration}: real systemd/Btrfs root and persistence verified',flush=True)
    assert results[0]['boot_id']!=results[1]['boot_id']
    assert digest(disk)==esp_before,'Read-only EutherBoot ESP changed'
    assert digest(image)==manifest['image_sha256'],'Original Arch image changed'
(out/'result.json').write_text(json.dumps({'image':manifest,'efi_sha256':digest(ROOT/'artifacts/EutherBoot.efi'),
    'accel':accel,'network':'none','cmdline':cmdline,'original_unchanged':True,'esp_unchanged':True,'boots':results},indent=2)+'\n')
print('PASS: two installed Arch cold boots, persistent guest write, pristine original image and ESP')
