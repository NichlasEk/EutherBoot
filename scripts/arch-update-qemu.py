#!/usr/bin/env python3
"""Full Arch guest upgrade and UKI reboot; host firmware/disks are never attached."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import uuid
from qemu_test import VM
import virtual_disk

ROOT=Path(__file__).resolve().parent.parent
fixtures=ROOT/'artifacts/arch'
out=ROOT/'artifacts/arch-update-qemu';out.mkdir(parents=True,exist_ok=True)
(out/'result.json').unlink(missing_ok=True)
def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
manifest=json.loads((fixtures/'manifest.json').read_text());image=Path(manifest['image'])
assert digest(image)==manifest['image_sha256']
for name,expected in manifest['artifacts'].items():assert digest(fixtures/name)==expected
accel='kvm' if os.access('/dev/kvm',os.R_OK|os.W_OK) else 'tcg'
ESP_GUID='eeeeeeee-1111-4111-8111-eeeeeeeeeeee'

def drain(serial):
    try:
        while serial.recv(65536):pass
    except OSError:pass

def wait(v,pattern,before=0,timeout=180):
    deadline=time.monotonic()+timeout
    while True:
        log=(v.base/'serial.log').read_text(errors='replace')[before:]
        if match:=re.search(pattern,log):return match
        if v.proc.poll() is not None or time.monotonic()>deadline:
            raise AssertionError(f'Missing {pattern}: {log[-3500:]}')
        time.sleep(.1)

def command(v,serial,script,timeout=180):
    marker=uuid.uuid4().hex
    before=len((v.base/'serial.log').read_text(errors='replace'))
    # A child shell gives set -e its normal semantics; completion is not terminal echo.
    import shlex
    line=f"bash -eu -o pipefail -c {shlex.quote(script)}; printf '\\nCOMMAND_{marker}=%s\\n' \"$?\"\n"
    serial.sendall(line.encode())
    result=wait(v,rf'(?m)^COMMAND_{marker}=(\d+)\r?$',before,timeout)
    log=(v.base/'serial.log').read_text(errors='replace')[before:]
    assert result.group(1)=='0',log[-5000:]
    return log

results=[]
# Each run gets fresh disposable disks; logs survive cleanup.
with tempfile.TemporaryDirectory(prefix='eutherboot-update-') as directory:
    tmp=Path(directory);source=tmp/'esp'
    for folder in ('BOOT','EutherBoot','Linux'):(source/'EFI'/folder).mkdir(parents=True)
    shutil.copy2(ROOT/'artifacts/EutherBoot.efi',source/'EFI/BOOT/BOOTX64.EFI')
    for name in ('kernel.efi','initrd.img'):shutil.copy2(fixtures/name,source/'EFI/Linux'/name)
    payload=source/'EFI/EutherBoot/TestPayload';shutil.copytree(ROOT/'tests/arch/update',payload)
    cmdline=f"root=PARTUUID={manifest['root']['guid']} rw rootflags=compress=zstd:1 console=tty0 console=ttyS0,115200 systemd.mask=systemd-time-wait-sync.service"
    (payload/'cmdline').write_text(cmdline+'\n')
    (payload/'update.conf').write_text(f"ESP_GUID='{ESP_GUID}'\nESP_MOUNT='/eutherboot'\n")
    final="[boot]\ndefault='arch'\ntimeout=0\n\n[[entry]]\nid='arch'\nname='Arch Linux - automatic UKI'\ntype='efi'\npath='\\EFI\\Linux\\arch-linux.efi'\n"
    initial=final.replace("default='arch'","default='bootstrap'")+"\n[[entry]]\nid='bootstrap'\nname='Arch bootstrap fixture'\ntype='linux-efi'\npath='\\EFI\\Linux\\kernel.efi'\ninitrd='\\EFI\\Linux\\initrd.img'\ncmdline='"+cmdline+"'\n"
    (source/'EFI/EutherBoot/eutherboot.toml').write_text(initial)
    (payload/'final.toml').write_text(final)
    disk=virtual_disk.create(source,tmp,esp_mib=1024)
    subprocess.run(['sgdisk','-u',f'1:{ESP_GUID}',str(disk)],check=True,capture_output=True)
    overlay=tmp/'arch.qcow2'
    subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(image),str(overlay)],check=True,capture_output=True)
    for iteration in (1,2,3):
        serial_path=tmp/f'serial-{iteration}'
        with VM(tmp,disk,out,iteration,memory=3072,cpu='host' if accel=='kvm' else 'max',
                extra_disks=((overlay,'qcow2'),),accel=accel,serial_socket=serial_path,user_network=iteration==1) as v:
            with socket.socket(socket.AF_UNIX) as serial:
                serial.connect(str(serial_path));threading.Thread(target=drain,args=(serial,),daemon=True).start()
                v.screen('menu');v.key('ret','CHAINLOAD_LOADED')
                wait(v,r'login: ');serial.sendall(b'arch\n');wait(v,r'Password: ');serial.sendall(b'arch\n')
                wait(v,r'\[arch@[^\r\n]+\]\$ ')
                serial.sendall(b'stty -echo; export SYSTEMD_COLORS=0 SYSTEMD_URLIFY=0 TERM=dumb\n');time.sleep(.3)
                if iteration==1:
                    command(v,serial,'sudo mkdir -p /eutherboot; sudo mount /dev/vda1 /eutherboot; sudo bash /eutherboot/EFI/EutherBoot/TestPayload/setup.sh',timeout=1800)
                    command(v,serial,'sudo cp /eutherboot/EFI/EutherBoot/TestPayload/final.toml /eutherboot/EFI/EutherBoot/eutherboot.toml; sync')
                else:
                    log=command(v,serial,"""test "$(cat /proc/1/comm)" = systemd
. /etc/os-release; test "$ID" = arch
test "$(findmnt -n -o SOURCE /)" = /dev/vdb3
test "$(uname -r)" = "$(cat /var/lib/eutherboot/kernel-expected)"
test "$(uname -r)" != "$(cat /var/lib/eutherboot/kernel-before)"
sudo sha256sum -c /var/lib/eutherboot/uki-after.sha256
for attempt in $(seq 1 90); do systemctl is-active --quiet multi-user.target && break; sleep 1; done
systemctl is-active --quiet multi-user.target
test -z "$(systemctl --failed --no-legend --no-pager)"
printf '\nRUNNING_KERNEL=%s\nBOOT_ID=%s\n' "$(uname -r)" "$(cat /proc/sys/kernel/random/boot_id)"
pacman -Q linux systemd
""")
                    assert 'INITRD_INSTALLED' not in v.log.read_text(),'UKI must carry its own initrd'
                    results.append({'boot':iteration,'kernel':re.search(r'RUNNING_KERNEL=([^\r\n]+)',log).group(1),
                                    'boot_id':re.search(r'BOOT_ID=([^\r\n]+)',log).group(1)})
                    if iteration==2:command(v,serial,'sudo cp /eutherboot/EFI/EutherBoot/TestPayload/failures.sh /run/eutherboot-failures.sh; sudo bash /run/eutherboot-failures.sh',timeout=240)
                v.screen('arch-running')
                if iteration==2:
                    v.stop(powercut=True)
                else:
                    serial.sendall(b'sudo systemctl poweroff\n');v.proc.wait(timeout=60)
        print(f'PASS Arch upgrade phase {iteration}',flush=True)
    assert results[0]['boot_id']!=results[1]['boot_id']
    assert digest(image)==manifest['image_sha256']
    # Independently read back the generated UKI and untouched loader from the ESP.
    for name,path in [('updated-arch.efi','EFI/Linux/arch-linux.efi'),('loader.efi','EFI/BOOT/BOOTX64.EFI')]:
        subprocess.run(['mcopy','-o','-i',f'{disk}@@1048576',f'::/{path}',str(out/name)],check=True,capture_output=True)
    assert digest(out/'loader.efi')==digest(ROOT/'artifacts/EutherBoot.efi')
(out/'result.json').write_text(json.dumps({'source':manifest,'accel':accel,'boots':results,
    'original_unchanged':True,'loader_unchanged':True,'updated_uki_sha256':digest(out/'updated-arch.efi'),
    'network':'QEMU user NAT during upgrade only; no forwarding or shared folders'},indent=2)+'\n')
print('PASS: full guest upgrade, automatic UKI publication, failure checks, two new-kernel boots')
