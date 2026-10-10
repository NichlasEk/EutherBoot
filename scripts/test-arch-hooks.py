#!/usr/bin/env python3
"""Exercise actual libalpm path triggers in an offline disposable Arch guest."""
import hashlib,json,os,shutil,socket,subprocess,tempfile,threading,time
from pathlib import Path
from guest_console import command,wait,drain
from qemu_test import VM
import virtual_disk
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'artifacts/arch-hooks';OUT.mkdir(exist_ok=True)
(OUT/'result.json').unlink(missing_ok=True)
fixtures=ROOT/'artifacts/arch';manifest=json.loads((fixtures/'manifest.json').read_text())
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert sha(manifest['image'])==manifest['image_sha256']
for name,digest in manifest['artifacts'].items():assert sha(fixtures/name)==digest
with tempfile.TemporaryDirectory(prefix='eutherboot-hooks-') as directory:
    tmp=Path(directory);source=tmp/'esp'
    for name in ('BOOT','EutherBoot','Linux','Hooks'):(source/'EFI'/name).mkdir(parents=True)
    shutil.copy2(ROOT/'artifacts/EutherBoot.efi',source/'EFI/BOOT/BOOTX64.EFI')
    for name in ('kernel.efi','initrd.img'):shutil.copy2(fixtures/name,source/'EFI/Linux'/name)
    for name in ('05-eutherboot.hook','99-eutherboot.hook'):shutil.copy2(ROOT/'packaging/arch'/name,source/'EFI/Hooks'/name)
    shutil.copy2(ROOT/'tests/arch/release/hooks.sh',source/'EFI/Hooks/run.sh')
    cmdline=f"root=PARTUUID={manifest['root']['guid']} rw console=ttyS0,115200 systemd.mask=systemd-time-wait-sync.service"
    (source/'EFI/EutherBoot/eutherboot.toml').write_text("[boot]\ndefault='test'\ntimeout=0\n[[entry]]\nid='test'\nname='Offline hook test'\ntype='linux-efi'\npath='\\EFI\\Linux\\kernel.efi'\ninitrd='\\EFI\\Linux\\initrd.img'\ncmdline='"+cmdline+"'\n")
    disk=virtual_disk.create(source,tmp,esp_mib=128);before=sha(disk)
    overlay=tmp/'root.qcow2'
    subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',manifest['image'],str(overlay)],check=True,capture_output=True)
    accel='kvm' if os.access('/dev/kvm',os.R_OK|os.W_OK) else 'tcg'
    serial_path=tmp/'serial'
    with VM(tmp,disk,OUT,memory=2048,readonly=True,extra_disks=((overlay,'qcow2'),),accel=accel,cpu='host' if accel=='kvm' else 'max',serial_socket=serial_path) as v:
        with socket.socket(socket.AF_UNIX) as serial:
            serial.connect(str(serial_path));threading.Thread(target=drain,args=(serial,),daemon=True).start()
            v.key('ret','CHAINLOAD_LOADED');wait(v,'login: ');serial.sendall(b'arch\n');wait(v,'Password: ');serial.sendall(b'arch\n')
            wait(v,r'\[arch@[^\r\n]+\]\$ ')
            serial.sendall(b'stty -echo; export TERM=dumb SYSTEMD_COLORS=0\n');time.sleep(.3)
            command(v,serial,'sudo mkdir /hook-esp; sudo mount -o ro /dev/vda1 /hook-esp; sudo bash /hook-esp/EFI/Hooks/run.sh',timeout=240)
            serial.sendall(b'sudo systemctl poweroff\n');v.proc.wait(timeout=60)
    assert sha(disk)==before
assert sha(manifest['image'])==manifest['image_sha256']
(OUT/'result.json').write_text(json.dumps({'path_trigger':'external module directory','pre_post':True,'abort_preserves_installed_package':True,'network':'none','original_image_unchanged':True,'esp_unchanged':True},indent=2)+'\n')
print('PASS: real pacman external-module path trigger and pre-transaction refusal')
