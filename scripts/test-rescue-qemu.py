#!/usr/bin/env python3
"""Boot only rescue ISO and disposable data disk, twice; no host disks or credentials."""
from pathlib import Path
from types import SimpleNamespace
import argparse,hashlib,json,os,shutil,socket,subprocess,tempfile,threading,time
from guest_console import drain,wait,command
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'artifacts/rescue';iso=out/'euther-rescue-0.1.0-x86_64.iso'
parser=argparse.ArgumentParser();parser.add_argument('--usb-image',type=Path);options=parser.parse_args()
assert iso.is_file()
results=[]
with tempfile.TemporaryDirectory(prefix='euther-rescue-test-') as directory:
    tmp=Path(directory);data=tmp/'data.img'
    with data.open('wb') as f:f.truncate(1024**3)
    subprocess.run(['mkfs.ext4','-q','-L','EUTHERDATA',str(data)],check=True)
    if options.usb_image:
        usb_overlay=tmp/'usb.qcow2'
        subprocess.run(['qemu-img','create','-f','qcow2','-F','raw','-b',str(options.usb_image.resolve()),str(usb_overlay)],check=True)
    for iteration in (1,2):
        base=out/f"{'usb' if options.usb_image else 'iso'}-test-boot-{iteration}";base.mkdir(exist_ok=True)
        vars=tmp/f'vars-{iteration}.fd';shutil.copy2('/usr/share/edk2/x64/OVMF_VARS.4m.fd',vars)
        serial_path=tmp/f'serial-{iteration}';qmp_path=tmp/f'qmp-{iteration}'
        args=['qemu-system-x86_64','-machine','q35','-accel','kvm','-cpu','host','-smp','4','-m','4096','-display','none','-no-reboot',
              '-drive','if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd',
              '-drive',f'if=pflash,format=raw,file={vars}',
              '-nic','user,model=virtio-net-pci',
              '-chardev',f'socket,id=serial,path={serial_path},server=on,wait=off,logfile={base}/serial.log','-serial','chardev:serial',
              '-qmp',f'unix:{qmp_path},server=on,wait=off']
        if options.usb_image:
            args += ['-device','qemu-xhci','-drive',f'if=none,id=stick,format=qcow2,file={usb_overlay}','-device','usb-storage,drive=stick,bootindex=1']
        else:args += ['-cdrom',str(iso),'-boot','d','-drive',f'if=virtio,format=raw,file={data}']
        with (base/'qemu.log').open('w') as err:
            proc=subprocess.Popen(args,stdout=err,stderr=err);v=SimpleNamespace(proc=proc,base=base)
            try:
                for _ in range(100):
                    if serial_path.exists():break
                    if proc.poll() is not None:raise RuntimeError((base/'qemu.log').read_text())
                    time.sleep(.1)
                with socket.socket(socket.AF_UNIX) as serial:
                    serial.connect(str(serial_path));threading.Thread(target=drain,args=(serial,),daemon=True).start()
                    wait(v,r'rescue@euther-rescue.*\$',timeout=240)
                    serial.sendall(b'stty -echo; export SYSTEMD_COLORS=0 SYSTEMD_URLIFY=0 TERM=dumb\n');time.sleep(.3)
                    log=command(v,serial,'''test "$(id -un)" = rescue
sudo -n true
test "$(cat /proc/1/comm)" = systemd
findmnt /
for tool in codex arch-chroot mkinitcpio btrfs fsck.fat efibootmgr git rg python rustup tmux; do command -v "$tool"; done
codex --version
codex --help >/tmp/codex-help
codex login status >/tmp/codex-auth 2>&1 && exit 1
! test -f "$HOME/.codex/auth.json"
test -s /usr/local/share/euther-rescue/EutherBoot/HANDOFF.md
test -s /usr/local/share/euther-rescue/eutherboot-source.tar.gz
test -x /opt/codex/codex-resources/bwrap
test -x /opt/codex/bin/codex-code-mode-host
unshare -Ur true
if test -d /usr/local/share/euther-rescue/known-good; then
cd /usr/local/share/euther-rescue/known-good
sha256sum --quiet -c SHA256SUMS
fi
cd "$HOME"
rescue-data DATA_DEVICE
findmnt /mnt/rescue-data
'''.replace('DATA_DEVICE','/dev/sda3' if options.usb_image else '/dev/vda'))
                    assert 'codex-cli 0.162.1' in log
                    if iteration==1:
                        command(v,serial,'''if test -d /usr/local/share/euther-rescue/known-good/usb/EFI; then
truncate -s 128M /tmp/restore-esp.fat
mkfs.fat -F 32 /tmp/restore-esp.fat
mcopy -s -i /tmp/restore-esp.fat /usr/local/share/euther-rescue/known-good/usb/EFI ::/
mkdir /tmp/restored
mcopy -s -i /tmp/restore-esp.fat ::/EFI /tmp/restored/
diff -qr /usr/local/share/euther-rescue/known-good/usb/EFI /tmp/restored/EFI
fsck.fat -n /tmp/restore-esp.fat
fi''')
                        command(v,serial,"printf 'rescue-persistence-ok\\n' > /mnt/rescue-data/work/persistence-test; sync")
                        command(v,serial,'for i in $(seq 1 30); do curl -fsS --max-time 10 https://archlinux.org/ -o /tmp/network-ok && break; sleep 1; done; test -s /tmp/network-ok',timeout=360)
                    else:command(v,serial,"test \"$(cat /mnt/rescue-data/work/persistence-test)\" = rescue-persistence-ok")
                    # Capture actual firmware/console framebuffer via QMP.
                    with socket.socket(socket.AF_UNIX) as qmp:
                        qmp.connect(str(qmp_path));stream=qmp.makefile('rwb',buffering=0);json.loads(stream.readline())
                        for name,args in [('qmp_capabilities',{}),('screendump',{'filename':str(base/'rescue.ppm')})]:
                            stream.write((json.dumps({'execute':name,'arguments':args})+'\n').encode())
                            while True:
                                response=json.loads(stream.readline())
                                if 'error' in response:raise RuntimeError(response)
                                if 'return' in response:break
                    results.append({'boot':iteration,'codex_cli':'0.162.1','no_credentials':True,'data_mounted':True,'persistence_verified':iteration==2,'network_verified':iteration==1})
                    serial.sendall(b'sudo systemctl poweroff\n');proc.wait(timeout=60)
                print(f'PASS rescue boot {iteration}',flush=True)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:proc.kill();proc.wait()
with iso.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
(out/('usb-test-result.json' if options.usb_image else 'test-result.json')).write_text(json.dumps({'usb_image_sha256':hashlib.file_digest(options.usb_image.open('rb'),'sha256').hexdigest() if options.usb_image else None,'iso_sha256':digest,'boots':results,'internal_disk_attached':False,'physical_boot_verified':False,'authenticated_codex_session_verified':False},indent=2)+'\n')
