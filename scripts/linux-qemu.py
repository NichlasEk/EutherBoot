#!/usr/bin/env python3
"""Actual Linux PID 1 oracle, and isolated EFI-stub failure/editor tests."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import tomllib
from qemu_test import VM
import virtual_disk
ROOT=Path(__file__).resolve().parent.parent
p=argparse.ArgumentParser()
p.add_argument('--case',choices=('stub','uki','stub-remote','uki-remote','uki-write','missing-initrd','not-linux','editor'),default='stub')
p.add_argument('--width',type=int,default=1024);p.add_argument('--height',type=int,default=768)
a=p.parse_args()
out=ROOT/'artifacts'/f'linux-{a.case}-{a.width}x{a.height}';out.mkdir(parents=True,exist_ok=True)
fixtures=ROOT/'artifacts/linux'
manifest=json.loads((fixtures/'manifest.json').read_text())
for name,expected in manifest['artifacts'].items():
    assert hashlib.sha256((fixtures/name).read_bytes()).hexdigest()==expected,f'Stale fixture {name}'
(out/'fixture-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
IDS=['11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222']
remote=a.case.endswith('-remote')
uki=a.case.startswith('uki')
mode='uki' if uki else 'stub'
cmdline=(fixtures/'stub-cmdline.txt').read_text()

def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def wait_linux(v,expected):
    serial=v.base/'serial.log';deadline=time.monotonic()+90
    while expected not in serial.read_text(errors='replace'):
        if v.proc.poll() is not None:raise AssertionError('Linux did not reach PID 1: '+serial.read_text(errors='replace')[-5000:])
        if time.monotonic()>deadline:raise AssertionError('Linux boot deadline: '+serial.read_text(errors='replace')[-5000:])
        time.sleep(.1)
    text=serial.read_text(errors='replace')
    assert 'EUTHERBOOT_LINUX_UNAME' in text and 'EUTHERBOOT_LINUX_CMDLINE' in text
    assert 'EUTHERBOOT_LINUX_PROBE_FAILED' not in text
    assert 'eutherboot_probe=owner-controlled' in text
    v.proc.wait(timeout=15)

with tempfile.TemporaryDirectory(prefix='eutherboot-linux-') as tmp:
    tmp=Path(tmp);sources=[tmp/'own',tmp/'remote']
    for s in sources:(s/'EFI/Linux').mkdir(parents=True)
    own=sources[0];(own/'EFI/BOOT').mkdir();(own/'EFI/EutherBoot').mkdir()
    shutil.copy2(ROOT/'artifacts/EutherBoot.efi',own/'EFI/BOOT/BOOTX64.EFI')
    shutil.copy2(ROOT/'artifacts/TestChild.efi',own/'EFI/EutherBoot/TestChild.efi')
    target=sources[1] if remote else own
    for file in ('kernel.efi','initrd.cpio','test.efi'):shutil.copy2(fixtures/file,target/'EFI/Linux'/file)
    if remote:
        # Poison same paths on own ESP: a guessed volume must never pass the Linux oracle.
        (own/'EFI/Linux/kernel.efi').write_bytes(b'wrong volume kernel')
        (own/'EFI/Linux/initrd.cpio').write_bytes(b'wrong volume initrd')
        (own/'EFI/Linux/test.efi').write_bytes(b'wrong volume UKI')
    if a.case=='editor':(target/'EFI/Linux/initrd.cpio').rename(target/'EFI/Linux/edited.cpio')
    if a.case=='missing-initrd':(target/'EFI/Linux/initrd.cpio').unlink()
    if a.case=='not-linux':shutil.copy2(ROOT/'artifacts/TestChild.efi',target/'EFI/Linux/kernel.efi')
    kind='efi' if uki else 'linux-efi'
    path=r'\EFI\Linux\test.efi' if uki else r'\EFI\Linux\kernel.efi'
    config=f"[boot]\ndefault='linux'\ntimeout={2 if remote else 0}\n[[entry]]\nid='linux'\nname='Linux probe'\ntype='{kind}'\npath='{path}'\n"
    if remote:config+=f"partition_guid='{IDS[1]}'\n"
    if not uki:config+=f"cmdline='{cmdline}'\ninitrd='\\EFI\\Linux\\initrd.cpio'\n"
    config+="\n[[entry]]\nid='child'\nname='Recovery child'\ntype='efi'\npath='\\EFI\\EutherBoot\\TestChild.efi'\n"
    original=config.encode();(own/'EFI/EutherBoot/eutherboot.toml').write_bytes(original)
    disk=virtual_disk.create_layout([(s,'ef00',id) for s,id in zip(sources,IDS)],tmp)
    before=digest(disk)
    if a.case=='uki-write':shutil.copyfile(disk,tmp/'before.img')
    def vm(iteration=1):return VM(tmp,disk,out,iteration,a.width,a.height,memory=768,cpu='max',readonly=uki and a.case!='uki-write')
    with vm() as v:
        v.screen('menu')
        if a.case=='editor':
            v.open_editor();v.key('f6','EDITOR_DETAILS');v.screen('linux-details');v.key('esc','EDITOR_READY');v.draft()
            # Edit and preserve Linux fields; changing kind back to efi requires confirmation.
            v.key('k','EDITOR_CONFIRM');v.key('n','EDITOR_READY')
            v.key('k','EDITOR_CONFIRM');v.key('y','EDITOR_READY');v.key('v','EDITOR_VALID')
            v.key('k','EDITOR_READY')
            v.field('c','cmdline',cmdline+' eutherboot_editor=kept')
            v.field('j','initrd',r'\EFI\Linux\edited.cpio');v.screen('linux-draft')
            v.key('v','EDITOR_VALID');v.key('s','EDITOR_CONFIRM');v.key('y','EDITOR_SAVED')
            v.wait('MENU_READY');v.screen('saved-menu')
        if not remote:v.key('ret','CHAINLOAD_LOADED' if a.case not in ('missing-initrd','not-linux') else 'MENU_RESUMED')
        if a.case in ('missing-initrd','not-linux'):
            v.screen('error')
            text=v.log.read_text();assert 'CHAINLOAD_LOADED' not in text and 'CHILD_STARTED' not in text
            assert ('NOT_FOUND' if a.case=='missing-initrd' else 'UNSUPPORTED') in text
            v.key('down','SELECT 1');v.key('ret','CHILD_READY');v.key('ret','MENU_RESUMED');v.key('esc','EXIT_FIRMWARE')
        else:
            wait_linux(v,'EUTHERBOOT_LINUX_PID1_OK '+mode)
            text=v.log.read_text()
            assert text.count('CHAINLOAD_LOADED')==1
            if uki:assert 'LOAD_OPTIONS_SET' not in text and 'LINUX_EFI_PREPARED' not in text
            else:
                assert 'LINUX_EFI_PREPARED' in text and 'LOAD_OPTIONS_SET' in text
                assert 'INITRD_INSTALLED' in text and 'INITRD_SIZE_QUERY' in text and 'INITRD_COPIED' in text
                assert 'initrd=' not in (v.base/'serial.log').read_text()
            if remote:assert 'TIMEOUT_FIRED' in text
            assert 'MENU_RESUMED' not in text # Actual Linux handoff did not return as an EFI child.
    if a.case=='editor':
        def read(name):return subprocess.run(['mtype','-i',f'{disk}@@1048576','::/EFI/EutherBoot/'+name],check=True,capture_output=True).stdout
        saved=read('eutherboot.toml');c=tomllib.loads(saved.decode())
        assert c['entry'][0]['type']=='linux-efi' and c['entry'][0]['initrd']==r'\EFI\Linux\edited.cpio'
        assert c['entry'][0]['cmdline']==cmdline+' eutherboot_editor=kept'
        assert read('eutherboot.toml.bak')==original
        (out/'saved.toml').write_bytes(saved)
        stable=digest(disk)
        with vm(2) as v:
            v.key('ret','CHAINLOAD_LOADED');wait_linux(v,'EUTHERBOOT_LINUX_PID1_OK stub')
            serial=(v.base/'serial.log').read_text()
            assert 'eutherboot_editor=kept' in serial and 'initrd=' not in serial
            assert 'INITRD_COPIED' in v.log.read_text()
        assert digest(disk)==stable
    elif a.case=='uki-write':
        # The systemd stub is an independent application: document its observed
        # seed writes instead of falsely attributing a read-only policy to it.
        subprocess.run(['mcopy','-s','-i',f'{disk}@@1048576','::/EFI',str(tmp/'after-efi')],check=True,capture_output=True)
        actual={str(f.relative_to(tmp/'after-efi')):digest(f) for f in (tmp/'after-efi').rglob('*') if f.is_file()}
        expected={str(f.relative_to(own/'EFI')):digest(f) for f in (own/'EFI').rglob('*') if f.is_file()}
        assert actual==expected,'UKI changed existing EFI payload/configuration files'
        for name in ('random-seed','boot-secret-mixin'):
            r=subprocess.run(['mtype','-i',f'{disk}@@1048576','::/loader/'+name],check=True,capture_output=True)
            assert len(r.stdout)==32
        # Preserve file names/sizes only, never export random-seed contents.
        (out/'uki-writes.txt').write_text('systemd-stub created loader/random-seed (32 bytes) and loader/boot-secret-mixin (32 bytes).\nExisting EFI files retained exact hashes.\n')
        with disk.open('rb') as after,(tmp/'before.img').open('rb') as before_file:
            after.seek(1048576+64*1024*1024);before_file.seek(1048576+64*1024*1024)
            assert hashlib.file_digest(after,'sha256').digest()==hashlib.file_digest(before_file,'sha256').digest()
    else:assert digest(disk)==before,'Unexpected virtual disk mutation'
    (out/'result.txt').write_text(f'PASS {a.case}\n'+('Linux editor persistence and reboot verified.\n' if a.case=='editor' else 'Observed systemd-stub seed writes; EFI files and other partition unchanged.\n' if a.case=='uki-write' else f'Whole disk unchanged SHA256: {before}\n'))
    print(f'PASS Linux: {a.case} ({a.width}x{a.height})')
