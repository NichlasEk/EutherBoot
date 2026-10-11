#!/usr/bin/env python3
"""Build Archiso as root inside disposable QEMU; host requires no sudo."""
from pathlib import Path
from types import SimpleNamespace
import argparse,hashlib,json,os,shlex,shutil,socket,subprocess,threading,time
from guest_console import drain,wait,command
parser=argparse.ArgumentParser();parser.add_argument('--resume',action='store_true');parser.add_argument('--reuse-transfer',action='store_true');parser.add_argument('--fresh-work',action='store_true');args_cli=parser.parse_args()
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'artifacts/rescue';out.mkdir(exist_ok=True)
manifest=json.loads((ROOT/'artifacts/arch/manifest.json').read_text())
image=Path(manifest['image'])
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert sha(image)==manifest['image_sha256']
for name,digest in manifest['artifacts'].items():assert sha(ROOT/'artifacts/arch'/name)==digest
base=out/'builder';base.mkdir(exist_ok=True)
overlay=base/'root.qcow2'
if overlay.exists() and not args_cli.resume:raise SystemExit('Existing overlay retained; use --resume after inspection')
if not overlay.exists():subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(image),str(overlay)],check=True)
source=base/'transfer';source.mkdir(exist_ok=True)
disk=base/'transfer.fat'
if not args_cli.reuse_transfer:
    subprocess.run(['tar','-czf',str(source/'profile.tar.gz'),'-C',str(out),'profile'],check=True)
    if disk.exists():disk.rename(base/f'transfer-{int(time.time())}.fat')
    subprocess.run(['mkfs.fat','-C','-F','32',str(disk),str(6*1024*1024)],check=True)
    subprocess.run(['mcopy','-i',str(disk),str(source/'profile.tar.gz'),'::/profile.tar.gz'],check=True)
assert disk.is_file()
for logname in ['serial.log','qemu.log']:
    previous=base/logname
    if previous.exists():previous.rename(base/f'{logname}.{int(time.time())}')
serial_path=Path('/tmp')/f'euther-rescue-build-{os.getpid()}.sock'
args=['qemu-system-x86_64','-machine','q35','-accel','kvm','-cpu','host','-smp','6','-m','8192','-display','none','-no-reboot',
      '-kernel',str(base/'bootstrap-kernel.efi' if args_cli.resume else ROOT/'artifacts/arch/kernel.efi'),
      '-initrd',str(base/'bootstrap.img' if args_cli.resume else ROOT/'artifacts/arch/initrd.img'),
      '-append',f"root=PARTUUID={manifest['root']['guid']} rw console=ttyS0,115200 systemd.mask=systemd-time-wait-sync.service",
      '-drive',f'if=virtio,format=qcow2,file={overlay}', '-drive',f'if=virtio,format=raw,file={disk}',
      '-nic','user,model=virtio-net-pci','-chardev',f'socket,id=serial,path={serial_path},server=on,wait=off,logfile={base}/serial.log','-serial','chardev:serial']
with (base/'qemu.log').open('w') as err:
    proc=subprocess.Popen(args,stdout=err,stderr=err)
    v=SimpleNamespace(proc=proc,base=base)
    try:
        for _ in range(100):
            if serial_path.exists():break
            if proc.poll() is not None:raise RuntimeError((base/'qemu.log').read_text())
            time.sleep(.1)
        with socket.socket(socket.AF_UNIX) as serial:
            serial.connect(str(serial_path));threading.Thread(target=drain,args=(serial,),daemon=True).start()
            wait(v,r'login: ');serial.sendall(b'arch\n');wait(v,r'Password: ');serial.sendall(b'arch\n')
            wait(v,r'\[arch@[^\r\n]+\]\$ ')
            serial.sendall(b'stty -echo; export SYSTEMD_COLORS=0 SYSTEMD_URLIFY=0 TERM=dumb\n');time.sleep(.3)
            command(v,serial,'sudo mkdir -p /transfer; sudo mount -o uid=1000,gid=1000 /dev/vdb /transfer; sudo mkdir -p /build; sudo rm -rf /build/profile; sudo tar -xzf /transfer/profile.tar.gz -C /build')
            print('Guest booted; upgrading build tools inside disposable overlay',flush=True)
            if not args_cli.resume:command(v,serial,"sudo pacman -Syu --noconfirm archiso",timeout=1800)
            if args_cli.fresh_work:command(v,serial,'sudo rm -rf /build/work')
            print('Building rescue ISO inside guest',flush=True)
            command(v,serial,'sudo mkarchiso -v -w /build/work -o /transfer /build/profile 2>&1 | tee /transfer/mkarchiso.log',timeout=3600)
            command(v,serial,'sudo cp /build/work/iso/arch/pkglist.x86_64.txt /transfer/; sync')
            serial.sendall(b'sudo systemctl poweroff\n');proc.wait(timeout=180)
        subprocess.run(['mcopy','-o','-i',str(disk),'::/euther-rescue-0.1.2-x86_64.iso',str(out/'euther-rescue-0.1.2-x86_64.iso')],check=True)
        subprocess.run(['mcopy','-o','-i',str(disk),'::/mkarchiso.log',str(out/'mkarchiso.log')],check=True)
        result={'iso':str(out/'euther-rescue-0.1.2-x86_64.iso'),'sha256':sha(out/'euther-rescue-0.1.2-x86_64.iso'),'source_image_unchanged':sha(image)==manifest['image_sha256'],'host_disks_attached':False,'network':'QEMU NAT, no port forwarding','builder':'disposable official Arch qcow2 overlay'}
        (out/'build-result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
        serial_path.unlink(missing_ok=True)
        # Preserve failed build logs and overlay for diagnosis without rebuilding.
        subprocess.run(['mcopy','-o','-i',str(disk),'::/mkarchiso.log',str(out/'mkarchiso.log')],capture_output=True)
