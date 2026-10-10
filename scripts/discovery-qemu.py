#!/usr/bin/env python3
"""Discovery on disposable multiple GPT/FAT partitions; hashes assert no disk writes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import virtual_disk

ROOT=Path(__file__).resolve().parent.parent
p=argparse.ArgumentParser()
p.add_argument('--case', choices=('multiple','duplicate','empty','limit','failure','bad-config'), default='multiple')
p.add_argument('--width',type=int,default=1024)
p.add_argument('--height',type=int,default=768)
a=p.parse_args()
out=ROOT/'artifacts'/f'discovery-{a.case}-{a.width}x{a.height}'
out.mkdir(parents=True,exist_ok=True)
ids=['11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222','33333333-3333-4333-8333-333333333333']
code=Path(os.environ.get('OVMF_CODE','/usr/share/edk2/x64/OVMF_CODE.4m.fd'))
variables=Path(os.environ.get('OVMF_VARS','/usr/share/edk2/x64/OVMF_VARS.4m.fd'))

def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

with tempfile.TemporaryDirectory(prefix='eutherboot-discovery-') as tmp:
    tmp=Path(tmp)
    sources=[tmp/f'esp-{i}' for i in range(3)]
    child=(ROOT/'artifacts/TestChild.efi').read_bytes()
    for source in sources:
        (source/'EFI/Tools').mkdir(parents=True)
        if a.case not in ('empty',):
            (source/'EFI/Tools/shared.efi').write_bytes(child)
    (sources[0]/'EFI/BOOT').mkdir()
    (sources[0]/'EFI/EutherBoot').mkdir()
    shutil.copy2(ROOT/'artifacts/EutherBoot.efi',sources[0]/'EFI/BOOT/BOOTX64.EFI')
    config=(ROOT/'eutherboot.toml').read_text().replace('timeout = 0','timeout = 3')
    if a.case=='bad-config':config='[boot]\nunknown = true\ntimeout = 1\n'
    (sources[0]/'EFI/EutherBoot/eutherboot.toml').write_text(config)
    # Exact self-copy on a different ESP must be excluded even with an arbitrary name.
    shutil.copy2(ROOT/'artifacts/EutherBoot.efi',sources[1]/'EFI/Tools/renamed.efi')
    (sources[1]/'EFI/Tools/not-pe.efi').write_bytes(b'not an EFI image')
    pe=int.from_bytes(child[0x3c:0x40],'little')
    for name,offset,value in [('driver.efi',pe+24+68,11),('arm.efi',pe+4,0xaa64)]:
        bad=bytearray(child);bad[offset:offset+2]=value.to_bytes(2,'little')
        (sources[1]/'EFI/Tools'/name).write_bytes(bad)
    if a.case=='limit':
        for i in range(70):(sources[1]/'EFI/Tools'/f'app-{i:02}.efi').write_bytes(child)
    if a.case=='failure':
        # Valid classification header, invalid PE section extent: firmware must reject it.
        bad=bytearray(child)
        optional_size=int.from_bytes(bad[pe+20:pe+22],'little')
        section=pe+24+optional_size
        bad[section+20:section+24]=(0xfffff000).to_bytes(4,'little')
        (sources[1]/'EFI/Tools/shared.efi').write_bytes(bad)
    if a.case=='duplicate':ids[1]=ids[0]
    disk=virtual_disk.create_layout([(s,'ef00' if i<2 else '0700',ids[i]) for i,s in enumerate(sources)],tmp)
    original=digest(disk)
    shutil.copy2(variables,tmp/'vars.fd')
    log=out/'debug.log';log.write_text('')
    qmp=tmp/'qmp'
    args=['qemu-system-x86_64','-machine','q35','-accel','tcg','-m','256','-net','none','-no-reboot','-display','none',
          '-vga','none','-device',f'VGA,xres={a.width},yres={a.height}',
          '-drive',f'if=pflash,format=raw,readonly=on,file={code}',
          '-drive',f'if=pflash,format=raw,file={tmp}/vars.fd',
          '-drive',f'if=virtio,format=raw,file={disk}',
          '-debugcon',f'file:{log}','-global','isa-debugcon.iobase=0xe9',
          '-serial',f'file:{out}/serial.log','-qmp',f'unix:{qmp},server=on,wait=off']
    with (out/'qemu.log').open('w') as err:
        proc=subprocess.Popen(args,stdout=err,stderr=err)
        sock=None
        try:
            def wait(marker,before=0,timeout=12):
                deadline=time.monotonic()+timeout
                while marker not in log.read_text()[before:]:
                    if proc.poll() is not None:raise RuntimeError((out/'qemu.log').read_text())
                    if time.monotonic()>deadline:raise AssertionError(f'Missing {marker}: {log.read_text()[before:]}')
                    time.sleep(.03)
            wait('MENU_READY',timeout=60)
            sock=socket.socket(socket.AF_UNIX);sock.settimeout(10);sock.connect(str(qmp))
            stream=sock.makefile('rwb',buffering=0);json.loads(stream.readline())
            def command(name,args=None):
                stream.write((json.dumps({'execute':name,'arguments':args or {}})+'\n').encode())
                while True:
                    result=json.loads(stream.readline())
                    if 'error' in result:raise RuntimeError(result)
                    if 'return' in result:return result['return']
            command('qmp_capabilities')
            def key(name,marker):
                before=len(log.read_text())
                command('human-monitor-command',{'command-line':f'sendkey {name} 30'})
                wait(marker,before);time.sleep(.1)
            def screen(name):command('screendump',{'filename':str(out/f'{name}.ppm')})
            key('f4','DISCOVERY_READY')
            screen('discovered')
            time.sleep(3.3)
            text=log.read_text()
            assert 'TIMEOUT_FIRED' not in text and 'CHILD_STARTED' not in text
            if a.case=='bad-config':assert 'CONFIG_ERROR' in text and 'TIMEOUT_ARMED' not in text
            else:assert 'TIMEOUT_CANCELLED' in text
            targets=[line for line in text.splitlines() if line.startswith('DISCOVERY_TARGET ')]
            assert all(ids[2] not in t for t in targets), targets
            assert not any(name in t for name in ('BOOTX64','renamed','not-pe','driver','arm') for t in targets),targets
            if a.case in ('duplicate','empty'):
                assert not targets,targets
                assert 'DISCOVERY_READY targets=0' in text
                if a.case=='duplicate':assert 'DISCOVERY_DUPLICATE_GUID' in text and 'partial=true' in text
                key('ret','DISCOVERY_READY');assert 'DISCOVERY_CONFIRM' not in log.read_text()
                key('down','DISCOVERY_READY');key('up','DISCOVERY_READY')
            elif a.case=='limit':
                assert len(targets)==64, len(targets)
                assert 'partial=true' in text
                key('up','selected=63');screen('last-page')
                key('ret','DISCOVERY_CONFIRM');key('n','DISCOVERY_READY')
            else:
                assert targets==[f'DISCOVERY_TARGET {id} \\EFI\\Tools\\shared.efi' for id in ids[:2]],targets
                assert 'partial=false' in text
                # First entry cancellation never invokes LoadImage.
                key('ret','DISCOVERY_CONFIRM');screen('confirmation');key('n','DISCOVERY_CANCELLED')
                assert 'DISCOVERY_BOOT' not in log.read_text()
                key('down','selected=1');key('ret','DISCOVERY_CONFIRM')
                before=len(log.read_text())
                if a.case=='failure':
                    key('y','DISCOVERY_RETURN');wait('DISCOVERY_READY',before)
                    assert 'CHILD_STARTED' not in log.read_text()[before:]
                    assert 'LoadImage:' in log.read_text()[before:]
                else:
                    key('y','CHILD_READY')
                    assert f'CHILD_VOLUME {ids[1]}' in log.read_text()[before:],log.read_text()[before:]
                    key('ret','DISCOVERY_RETURN');wait('DISCOVERY_READY',before)
                screen('returned')
                # A subsequent explicit launch of the same path on the first ESP must use that ESP.
                key('up','selected=0');key('ret','DISCOVERY_CONFIRM')
                before=len(log.read_text());key('y','CHILD_READY')
                assert f'CHILD_VOLUME {ids[0]}' in log.read_text()[before:]
                key('esc','DISCOVERY_RETURN');wait('DISCOVERY_READY',before)
                assert 'ABORTED' in log.read_text()[before:]
            before=len(log.read_text());key('r','DISCOVERY_READY')
            assert [t for t in log.read_text()[before:].splitlines() if t.startswith('DISCOVERY_TARGET ')]==targets
            key('esc','DISCOVERY_CLOSED');wait('SELECT')
            time.sleep(3.3)
            assert 'TIMEOUT_FIRED' not in log.read_text()
            screen('menu-returned');key('esc','EXIT_FIRMWARE')
            command('quit');proc.wait(timeout=5)
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()
            if sock:sock.close()
    final=digest(disk)
    assert original==final,'Discovery or the child modified the disposable disk'
    (out/'result.txt').write_text(f'PASS {a.case}\nWhole disk before/after SHA256: {original}\n')
    print(f'PASS discovery: {a.case} ({a.width}x{a.height}), complete GPT/FAT disk unchanged')
