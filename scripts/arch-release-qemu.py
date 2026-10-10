#!/usr/bin/env python3
"""Arch installation, LTS, retained-module recovery, Secure Boot and uninstall."""
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
from qemu_test import VM, VARS
from guest_console import command, wait, drain
import virtual_disk

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'artifacts/arch-release';OUT.mkdir(parents=True,exist_ok=True)
(OUT/'result.json').unlink(missing_ok=True)
FIXTURES=ROOT/'artifacts/arch'
manifest=json.loads((FIXTURES/'manifest.json').read_text())
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(*args):
    r=subprocess.run([str(a) for a in args],capture_output=True,text=True)
    if r.returncode:raise RuntimeError(r.stderr or r.stdout)
    return r.stdout
image=Path(manifest['image']);assert sha(image)==manifest['image_sha256']
for name,digest in manifest['artifacts'].items():assert sha(FIXTURES/name)==digest
GUID='eeeeeeee-1111-4111-8111-eeeeeeeeeeee'
OWNER='95ef2464-2a03-487a-bfa1-b27252629a71'
FWVARS=ROOT/'.tools/secureboot/bin/virt-fw-vars'
SECURE=Path('/usr/share/edk2/x64/OVMF_CODE.secboot.4m.fd')
SBVERIFY=Path(shutil.which('sbverify') or ROOT/'.tools/sbsigntools/usr/bin/sbverify')
accel='kvm' if os.access('/dev/kvm',os.R_OK|os.W_OK) else 'tcg'
boots=[]
with tempfile.TemporaryDirectory(prefix='eutherboot-release-') as directory:
    tmp=Path(directory)
    bootstrap=tmp/'bootstrap';target=tmp/'target'
    for path in (bootstrap/'EFI/BOOT',bootstrap/'EFI/EutherBoot',bootstrap/'EFI/Linux',target/'EFI/BOOT'):
        path.mkdir(parents=True)
    shutil.copy2(ROOT/'artifacts/EutherBoot.efi',bootstrap/'EFI/BOOT/BOOTX64.EFI')
    shutil.copy2(ROOT/'artifacts/TestChild.efi',target/'EFI/BOOT/BOOTX64.EFI')
    original_loader=sha(target/'EFI/BOOT/BOOTX64.EFI')
    for name in ('kernel.efi','initrd.img'):shutil.copy2(FIXTURES/name,bootstrap/'EFI/Linux'/name)
    cmdline=f"root=PARTUUID={manifest['root']['guid']} rw rootflags=compress=zstd:1 console=tty0 console=ttyS0,115200 systemd.mask=systemd-time-wait-sync.service"
    bootstrap_config="[boot]\ndefault='bootstrap'\ntimeout=0\n[[entry]]\nid='bootstrap'\nname='Bootstrap'\ntype='linux-efi'\npath='\\EFI\\Linux\\kernel.efi'\ninitrd='\\EFI\\Linux\\initrd.img'\ncmdline='"+cmdline+"'\n"
    (bootstrap/'EFI/EutherBoot/eutherboot.toml').write_text(bootstrap_config)
    payload=target/'EFI/TestPayload';payload.mkdir()
    shutil.copytree(ROOT/'packaging/arch',payload/'arch')
    shutil.copy2(ROOT/'tools/eutherbootctl.py',payload/'eutherbootctl.py')
    shutil.copy2(ROOT/'artifacts/release/config-check',payload/'config-check')
    shutil.copy2(ROOT/'artifacts/EutherBoot.efi',payload/'EutherBoot.efi')
    shutil.copy2(ROOT/'artifacts/release/EutherBoot.efi',payload/'Release.efi')
    shutil.copy2(ROOT/'tests/arch/release/setup.sh',payload/'setup.sh')
    (payload/'cmdline').write_text(cmdline+'\n')
    entries=[('linux','Arch Linux','linux'),('linux-lts','Arch Linux LTS','linux-lts'),
             ('previous','Previous Linux with retained modules','linux-previous'),
             ('lts-previous','Previous LTS with retained modules','linux-lts-previous'),
             ('original','Original image kernel with retained modules','recovery-linux-original')]
    config="[boot]\ndefault='linux'\ntimeout=0\n"
    for id,name,file in entries:
        config+=f"\n[[entry]]\nid='{id}'\nname='{name}'\ntype='efi'\npath='\\EFI\\EutherBoot\\kernels\\{file}.efi'\n"
    (payload/'installed.toml').write_text(config)
    run('openssl','req','-new','-x509','-newkey','rsa:2048','-sha256','-nodes','-days','2','-subj','/CN=EutherBoot disposable release test/',
        '-keyout',tmp/'owner.key','-out',tmp/'owner.crt')
    (tmp/'owner.key').chmod(0o600)
    for name in ('owner.key','owner.crt'):shutil.copy2(tmp/name,payload/name)
    enrolled=tmp/'enrolled.fd'
    run(FWVARS,'-i',VARS,'-o',enrolled,'--set-pk',OWNER,tmp/'owner.crt','--add-kek',OWNER,tmp/'owner.crt',
        '--add-db',OWNER,tmp/'owner.crt','--sb','--append-boot-filepath',r'\EFI\EutherBoot\EutherBoot.efi')
    for name in ('bootstrap-disk','target-disk'):(tmp/name).mkdir()
    first_disk=virtual_disk.create(bootstrap,tmp/'bootstrap-disk',esp_mib=128)
    disk=virtual_disk.create(target,tmp/'target-disk',esp_mib=1024)
    run('sgdisk','-u',f'1:{GUID}',disk)
    overlay=tmp/'arch.qcow2';run('qemu-img','create','-f','qcow2','-F','qcow2','-b',image,overlay)
    # Upgrade/setup, current, LTS, failed current -> recovery, LTS repair, old kernel, uninstall.
    for iteration,index in enumerate((None,0,1,2,1,4,1,1),1):
        serial_path=tmp/f'serial-{iteration}'
        extra=((overlay,'qcow2'),(disk,'raw')) if iteration==1 else ((overlay,'qcow2'),)
        kwargs={} if iteration==1 else {'secure':True,'firmware_code':SECURE,'firmware_vars':enrolled}
        if iteration==8:kwargs['ready_marker']=None
        with VM(tmp,first_disk if iteration==1 else disk,OUT,iteration,memory=3072,
                cpu='host' if accel=='kvm' else 'max',accel=accel,extra_disks=extra,
                serial_socket=serial_path,user_network=iteration==1,**kwargs) as v:
            with socket.socket(socket.AF_UNIX) as serial:
                serial.connect(str(serial_path));threading.Thread(target=drain,args=(serial,),daemon=True).start()
                if iteration==4:
                    v.key('ret','MENU_RESUMED');assert 'CHAINLOAD_ERROR' in v.log.read_text()
                if iteration!=8:
                    for _ in range(index or 0):v.key('down')
                    v.screen('menu');v.key('ret','CHAINLOAD_LOADED')
                wait(v,r'login: ',timeout=240);serial.sendall(b'arch\n');wait(v,r'Password: ');serial.sendall(b'arch\n')
                wait(v,r'\[arch@[^\r\n]+\]\$ ')
                serial.sendall(b'stty -echo; export SYSTEMD_COLORS=0 SYSTEMD_URLIFY=0 TERM=dumb\n');time.sleep(.3)
                if iteration==1:
                    command(v,serial,'sudo mkdir -p /eutherboot; sudo mount /dev/vdc1 /eutherboot; sudo bash /eutherboot/EFI/TestPayload/setup.sh',timeout=2400)
                else:
                    expected='linux-lts' if index==1 else 'linux'
                    version_file='/var/lib/eutherboot/generations/linux-original/version' if index==4 else f'/var/lib/eutherboot/test-{expected}-version'
                    log=command(v,serial,f'''test "$(uname -r)" = "$(cat {version_file})"
test "$(cat /proc/1/comm)" = systemd
test "$(findmnt -n -o SOURCE /)" = /dev/vdb3
for attempt in $(seq 1 90); do systemctl is-active --quiet multi-user.target && break; sleep 1; done
systemctl is-active --quiet multi-user.target
systemctl --failed --no-legend --no-pager
test -z "$(systemctl --failed --no-legend --no-pager)"
printf '\\nRUNNING_KERNEL=%s\\nBOOT_ID=%s\\n' "$(uname -r)" "$(cat /proc/sys/kernel/random/boot_id)"
sudo modprobe dummy
modinfo -F vermagic dummy
''',timeout=180)
                    boots.append({'iteration':iteration,'entry':entries[index][0],
                                  'kernel':re.search(r'RUNNING_KERNEL=([^\r\n]+)',log).group(1)})
                    if iteration==2:
                        command(v,serial,"sudo bash -c 'test -s /var/lib/eutherboot/linux.confirmed; package=$(find /var/cache/pacman/pkg -maxdepth 1 -name \"linux-[0-9]*-x86_64.pkg.tar.zst\" | head -1); pacman -U --noconfirm \"$package\"'",timeout=300)
                    if iteration==3:
                        command(v,serial,'''sudo bash -eu -c 'version=$(cat /var/lib/eutherboot/test-linux-version); mv "/usr/lib/modules/$version" /root/eutherboot-removed-modules; cp /eutherboot/EFI/EutherBoot/kernels/linux.efi /root/eutherboot-good.efi; printf broken > /eutherboot/EFI/EutherBoot/kernels/linux.efi; sync' ''')
                    if iteration in (4,6):
                        command(v,serial,'''systemctl is-active --quiet eutherboot-recovery.service
findmnt -M "/usr/lib/modules/$(uname -r)"
test "$(cat /usr/lib/modules/$(uname -r)/pkgbase)" = linux
if sudo /usr/local/lib/eutherboot/prepare >/tmp/refusal.log 2>&1; then exit 1; fi
grep -F 'kernel updates are disabled while booted in recovery' /tmp/refusal.log
''')
                    if iteration==5:
                        command(v,serial,'''sudo bash -eu -c 'version=$(cat /var/lib/eutherboot/test-linux-version); rmdir "/usr/lib/modules/$version"; mv /root/eutherboot-removed-modules "/usr/lib/modules/$version"; cp /root/eutherboot-good.efi /eutherboot/EFI/EutherBoot/kernels/linux.efi; sync' ''')
                    if iteration==7:
                        command(v,serial,'''sudo python /eutherboot/EFI/TestPayload/eutherbootctl.py upgrade --esp /eutherboot --esp-guid eeeeeeee-1111-4111-8111-eeeeeeeeeeee --image /eutherboot/EFI/TestPayload/Release.efi --signing-key /etc/eutherboot-test/owner.key --signing-cert /etc/eutherboot-test/owner.crt
sudo python /eutherboot/EFI/TestPayload/eutherbootctl.py upgrade --esp /eutherboot --esp-guid eeeeeeee-1111-4111-8111-eeeeeeeeeeee --image /eutherboot/EFI/TestPayload/Release.efi --signing-key /etc/eutherboot-test/owner.key --signing-cert /etc/eutherboot-test/owner.crt --apply
sudo test -s /eutherboot/EFI/EutherBoot/EutherBoot.previous.efi
sudo sed -i "s/default='linux'/default='linux-lts'/; s/timeout=0/timeout=2/" /eutherboot/EFI/EutherBoot/eutherboot.toml
sudo sync
''')
                    if iteration==8:
                        assert v.log.read_text()=='' # Distribution binary has no QEMU debug port output.
                        command(v,serial,'''sudo cp /etc/eutherboot/arch.conf /tmp/arch.conf.backup
sudo sh -c 'echo "# local change" >> /etc/eutherboot/arch.conf'
if sudo python /eutherboot/EFI/TestPayload/eutherbootctl.py remove --esp /eutherboot --esp-guid eeeeeeee-1111-4111-8111-eeeeeeeeeeee --apply >/tmp/remove-refusal.log 2>&1; then exit 1; fi
grep -F 'Locally modified file retained' /tmp/remove-refusal.log
sudo test -f /eutherboot/EFI/EutherBoot/EutherBoot.efi
sudo cp /tmp/arch.conf.backup /etc/eutherboot/arch.conf
sudo python /eutherboot/EFI/TestPayload/eutherbootctl.py remove --esp /eutherboot --esp-guid eeeeeeee-1111-4111-8111-eeeeeeeeeeee
sudo test -f /eutherboot/EFI/EutherBoot/EutherBoot.efi
sudo python /eutherboot/EFI/TestPayload/eutherbootctl.py remove --esp /eutherboot --esp-guid eeeeeeee-1111-4111-8111-eeeeeeeeeeee --apply
test ! -e /eutherboot/EFI/EutherBoot
test ! -e /etc/eutherboot/arch.conf
test ! -e /etc/pacman.d/hooks/05-eutherboot.hook
! grep -q eutherboot /etc/mkinitcpio.d/linux.preset
''',timeout=180)
                v.screen('running')
                if iteration==3:v.stop(powercut=True)
                else:serial.sendall(b'sudo systemctl poweroff\n');v.proc.wait(timeout=60)
        print(f'PASS release phase {iteration}',flush=True)
    # Ordinary firmware still starts the original fallback application after uninstall.
    with VM(tmp,disk,OUT,9,ready_marker='CHILD_READY') as v:
        v.screen('original-fallback');v.key('ret','CHILD_RETURN')
    readback=OUT/'original-loader.efi'
    run('mcopy','-o','-i',f'{disk}@@1048576','::/EFI/BOOT/BOOTX64.EFI',readback)
    assert sha(readback)==original_loader
    assert sha(image)==manifest['image_sha256']
(OUT/'result.json').write_text(json.dumps({'boots':boots,'original_image_unchanged':True,
    'original_loader_unchanged':True,'secure_boot':'disposable owner key; installed normal, LTS and recovery UKIs',
    'install_remove':'plan read-only; explicit apply; original fallback booted',
    'release_upgrade':'signed non-instrumented EFI; automatic LTS boot; empty debug trace'},indent=2)+'\n')
print('PASS: side-by-side install, LTS, Secure Boot, retained modules, repair and uninstall')
