#!/usr/bin/env python3
"""Real offline single-UKI install/update on disposable 1 GiB ESP and Btrfs root."""
import hashlib,json,os,shutil,socket,subprocess,tempfile,threading,time
from pathlib import Path
from guest_console import command,wait,drain
from qemu_test import VM
import virtual_disk
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'artifacts/single-qemu';OUT.mkdir(exist_ok=True)
(OUT/'result.json').unlink(missing_ok=True)
fixture=ROOT/'artifacts/arch';m=json.loads((fixture/'manifest.json').read_text())
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(*args):subprocess.run([str(x) for x in args],check=True,capture_output=True)
assert sha(m['image'])==m['image_sha256']
for name,digest in m['artifacts'].items():assert sha(fixture/name)==digest
with tempfile.TemporaryDirectory(prefix='eutherboot-single-') as d:
    tmp=Path(d);bootstrap=tmp/'bootstrap';target=tmp/'target'
    (bootstrap/'EFI/BOOT').mkdir(parents=True);(bootstrap/'EFI/EutherBoot').mkdir()
    (bootstrap/'EFI/Linux').mkdir()
    shutil.copy2(ROOT/'artifacts/EutherBoot.efi',bootstrap/'EFI/BOOT/BOOTX64.EFI')
    for a,b in [('kernel.efi','kernel.efi'),('initrd.img','initrd')]:shutil.copy2(fixture/a,bootstrap/'EFI/Linux'/b)
    cmd=f"root=PARTUUID={m['root']['guid']} rw console=ttyS0,115200 systemd.mask=systemd-time-wait-sync.service"
    (bootstrap/'EFI/EutherBoot/eutherboot.toml').write_text("[boot]\ndefault='test'\ntimeout=0\n[[entry]]\nid='test'\nname='Bootstrap'\ntype='linux-efi'\npath='\\EFI\\Linux\\kernel.efi'\ninitrd='\\EFI\\Linux\\initrd'\ncmdline='"+cmd+"'\n")
    payload=target/'EFI/TestPayload';payload.mkdir(parents=True)
    for name in ('eutherboot-single.py','eutherbootctl.py'):shutil.copy2(ROOT/'tools'/name,payload/name)
    for a,b in [('kernel.efi','kernel'),('initrd.img','initrd')]:shutil.copy2(fixture/a,payload/b)
    shutil.copytree(ROOT/'packaging/arch-single',payload/'hooks')
    shutil.copy2(ROOT/'artifacts/release/EutherBoot.efi',payload/'EutherBoot.efi')
    shutil.copy2(ROOT/'artifacts/release/eutherboot-source.tar.gz',payload/'source.tar.gz')
    shutil.copy2(ROOT/'LICENSE',payload/'LICENSE')
    shutil.copy2(ROOT/'tests/arch/single/setup.sh',payload/'setup.sh')
    shutil.copy2('/var/cache/pacman/pkg/linux-7.2.9.arch1-1-x86_64.pkg.tar.zst',payload/'linux.pkg.tar.zst')
    (payload/'deps').mkdir()
    for filename in ('python-3.14.7-1-x86_64.pkg.tar.zst','gdbm-1.26-2-x86_64.pkg.tar.zst','mpdecimal-4.0.1-3-x86_64.pkg.tar.zst','libnsl-2.0.1-2-x86_64.pkg.tar.zst'):
        shutil.copy2(Path('/var/cache/pacman/pkg')/filename,payload/'deps'/filename)
    (payload/'cmdline').write_text(cmd+' rootflags=subvol=@ eutherboot.internal=single-v1\n')
    for name in ('first','second'):(tmp/name).mkdir()
    first=virtual_disk.create(bootstrap,tmp/'first',esp_mib=128)
    disk=virtual_disk.create(target,tmp/'second',esp_mib=1024)
    run('sgdisk','-u','1:eeeeeeee-1111-4111-8111-eeeeeeeeeeee',disk)
    overlay=tmp/'root.qcow2';run('qemu-img','create','-f','qcow2','-F','qcow2','-b',m['image'],overlay)
    accel='kvm' if os.access('/dev/kvm',os.R_OK|os.W_OK) else 'tcg'
    boots=[]
    for i in (1,2,3):
        serial_path=tmp/f'serial-{i}'
        extra=((overlay,'qcow2'),(disk,'raw')) if i==1 else ((overlay,'qcow2'),)
        with VM(tmp,first if i==1 else disk,OUT,i,memory=3072,extra_disks=extra,accel=accel,cpu='host' if accel=='kvm' else 'max',serial_socket=serial_path,ready_marker='MENU_READY' if i==1 else None) as v:
            with socket.socket(socket.AF_UNIX) as serial:
                serial.connect(str(serial_path));threading.Thread(target=drain,args=(serial,),daemon=True).start()
                if i==1:v.key('ret','CHAINLOAD_LOADED')
                wait(v,'login: ',timeout=240);serial.sendall(b'arch\n');wait(v,'Password: ');serial.sendall(b'arch\n');wait(v,r'\[arch@[^\r\n]+\]\$ ')
                serial.sendall(b'stty -echo; export TERM=dumb SYSTEMD_COLORS=0\n');time.sleep(.3)
                if i==1:
                    command(v,serial,'sudo mount /dev/vdc1 /boot; sudo bash /boot/EFI/TestPayload/setup.sh',timeout=600)
                else:
                    log=command(v,serial,'''test "$(findmnt -n -o FSROOT /)" = /@
test "$(findmnt -n -o FSTYPE /boot)" = vfat
grep -F eutherboot.internal=single-v1 /proc/cmdline
sudo modprobe dummy
systemctl is-active --quiet multi-user.target
systemctl --failed --no-legend --no-pager
test -z "$(systemctl --failed --no-legend --no-pager)"
uname -r
sudo cat /var/lib/eutherboot-single/last-publish.json
''')
                    boots.append(log)
                    if i==2:
                        command(v,serial,'sudo pacman -U --noconfirm /root/single-payload/linux.pkg.tar.zst; sudo test ! -e /boot/initramfs-linux.img; sudo test ! -e /boot/initramfs-linux-fallback.img',timeout=600)
                    else:command(v,serial,'test "$(uname -r)" = 7.2.9-arch1-1; sudo test ! -d /boot/grub; ! pacman -Q grub')
                serial.sendall(b'sudo systemctl poweroff\n');v.proc.wait(timeout=60)
assert sha(m['image'])==m['image_sha256']
(OUT/'result.json').write_text(json.dumps({'install':True,'normal_boot':True,'real_kernel_upgrade_boot':True,'invalid_uki_preserves_active':True,'failed_build_preserves_active':True,'real_pacman_capacity_abort':True,'driver_package_trigger':True,'esp_mib':1024,'root':'Btrfs /@','network':False,'host_disks_attached':False,'boots':boots},indent=2)+'\n')
print('PASS: single UKI install, error preservation, real package upgrade and two cold boots')
