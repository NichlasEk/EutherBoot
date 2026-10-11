#!/usr/bin/env python3
"""Test current rescue launchers inside existing ISO; no host disks or credentials.
This does not rebuild or change the delivered USB/ISO.
"""
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
    for iteration in (1,):
        base=out/f'codex-start-fixed-{iteration}';base.mkdir(exist_ok=True)
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
                    import base64,shlex
                    # Inject only the reviewed launchers into the disposable RAM overlay.
                    for source,destination in [
                        (ROOT/'scripts/rescue-codex-smoke.py','/tmp/probe.py'),
                        (ROOT/'rescue/overlay/usr/local/bin/codex','/usr/local/bin/codex'),
                        (ROOT/'rescue/overlay/usr/local/bin/rescue-start','/usr/local/bin/rescue-start')]:
                        data=base64.b64encode(source.read_bytes()).decode()
                        command(v,serial,": > /tmp/transfer.b64")
                        for start in range(0,len(data),1000):
                            command(v,serial,"printf %s "+shlex.quote(data[start:start+1000])+" >> /tmp/transfer.b64")
                        command(v,serial,"base64 -d /tmp/transfer.b64 > /tmp/transfer; sudo install -m 755 /tmp/transfer "+destination)
                    command(v,serial,'test ! -d "$HOME/.codex"; python /tmp/probe.py rescue-start',timeout=150)
                    command(v,serial,"""test -d "$HOME/.codex"
test "$(stat -c %a "$HOME/.codex")" = 700
test ! -e "$HOME/.codex/auth.json"
test ! -d "$HOME/.codex/packages/app-server-daemon"
rescue-start --version
codex login status > /tmp/login-status 2>&1 && exit 1
grep -q 'Not logged in' /tmp/login-status
df -h /
""")
                    # Capture actual firmware/console framebuffer via QMP.
                    with socket.socket(socket.AF_UNIX) as qmp:
                        qmp.connect(str(qmp_path));stream=qmp.makefile('rwb',buffering=0);json.loads(stream.readline())
                        for name,args in [('qmp_capabilities',{}),('screendump',{'filename':str(base/'rescue.ppm')})]:
                            stream.write((json.dumps({'execute':name,'arguments':args})+'\n').encode())
                            while True:
                                response=json.loads(stream.readline())
                                if 'error' in response:raise RuntimeError(response)
                                if 'return' in response:break
                    results.append({'boot':iteration,'onboarding_reached':True,'state_mode':'700','daemon_installed':False,'authenticated_session':False,'launchers_injected':True})
                    serial.sendall(b'sudo systemctl poweroff\n');proc.wait(timeout=60)
                print(f'PASS rescue-start onboarding, fresh state and argument forwarding',flush=True)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:proc.kill();proc.wait()

(out/'codex-start-fixed-result.json').write_text(json.dumps({'iso_sha256':hashlib.file_digest(iso.open('rb'),'sha256').hexdigest(),'tests':results,'launchers':{name:hashlib.sha256((ROOT/'rescue/overlay/usr/local/bin'/name).read_bytes()).hexdigest() for name in ['codex','rescue-start']}},indent=2)+'\n')
