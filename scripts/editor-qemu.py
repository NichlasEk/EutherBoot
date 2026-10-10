#!/usr/bin/env python3
"""Editor integration on a disposable GPT/FAT image. Never accepts a device path."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import tomllib
import virtual_disk

ROOT=Path(__file__).resolve().parent.parent
CASES=('discard','save','invalid','readonly','after-stage','after-backup','after-install')
p=argparse.ArgumentParser()
p.add_argument('--case',choices=CASES,default='save')
p.add_argument('--width',type=int,default=1024)
p.add_argument('--height',type=int,default=768)
a=p.parse_args()
out=ROOT/'artifacts'/f'editor-{a.case}-{a.width}x{a.height}'
out.mkdir(parents=True,exist_ok=True)
CODE=Path(os.environ.get('OVMF_CODE','/usr/share/edk2/x64/OVMF_CODE.4m.fd'))
VARS=Path(os.environ.get('OVMF_VARS','/usr/share/edk2/x64/OVMF_VARS.4m.fd'))
FAULT=a.case.startswith('after-')

def run(*args,**kwargs):
    return subprocess.run(args,check=True,capture_output=True,**kwargs)

class VM:
    def __init__(self,tmp,disk,iteration,readonly=False):
        self.base=out/f'boot-{iteration}';self.base.mkdir(exist_ok=True)
        self.log=self.base/'debug.log';self.log.write_text('')
        vars_path=tmp/f'vars-{iteration}.fd';shutil.copy2(VARS,vars_path)
        qmp=tmp/f'qmp-{iteration}'
        self.err=(self.base/'qemu.log').open('w')
        args=['qemu-system-x86_64','-machine','q35','-accel','tcg','-m','256','-net','none','-no-reboot','-display','none',
              '-vga','none','-device',f'VGA,xres={a.width},yres={a.height}',
              '-drive',f'if=pflash,format=raw,readonly=on,file={CODE}',
              '-drive',f'if=pflash,format=raw,file={vars_path}',
              '-drive',f'if=virtio,format=raw,file={disk},readonly={"on" if readonly else "off"}',
              '-debugcon',f'file:{self.log}','-global','isa-debugcon.iobase=0xe9',
              '-serial',f'file:{self.base}/serial.log','-qmp',f'unix:{qmp},server=on,wait=off']
        self.proc=subprocess.Popen(args,stdout=self.err,stderr=self.err)
        self.sock=None;self.stream=None
        try:
            self.wait('MENU_READY',timeout=60)
            self.sock=socket.socket(socket.AF_UNIX);self.sock.settimeout(10);self.sock.connect(str(qmp))
            self.stream=self.sock.makefile('rwb',buffering=0);json.loads(self.stream.readline());self.command('qmp_capabilities')
        except BaseException:
            self.stop();raise
    def command(self,name,args=None):
        self.stream.write((json.dumps({'execute':name,'arguments':args or {}})+'\n').encode())
        while True:
            result=json.loads(self.stream.readline())
            if 'error' in result:raise RuntimeError(result)
            if 'return' in result:return result['return']
    def wait(self,marker,before=0,timeout=12):
        deadline=time.monotonic()+timeout
        while marker not in self.log.read_text()[before:]:
            if self.proc.poll() is not None:raise RuntimeError((self.base/'qemu.log').read_text())
            if time.monotonic()>deadline:raise AssertionError(f'Missing {marker}: {self.log.read_text()[before:]}')
            time.sleep(.03)
    def key(self,key,marker=None,delay=.08):
        before=len(self.log.read_text());self.command('human-monitor-command',{'command-line':f'sendkey {key} 30'})
        if marker:self.wait(marker,before)
        time.sleep(delay)
    def text(self,text):
        names={'\\':'backslash',' ': 'spc','.':'dot','-':'minus','_':'shift-minus',':':'shift-semicolon',"'":'apostrophe','/':'slash'}
        for c in text:
            name=names.get(c,c.lower() if c.islower() or c.isdigit() else 'shift-'+c.lower())
            self.key(name,'PROMPT_CHANGED',.045)
    def field(self,hotkey,field,value):
        self.key(hotkey,f'PROMPT_READY {field}');self.key('f4','PROMPT_CHANGED');self.text(value);self.key('ret','EDITOR_UPDATED')
    def screen(self,name):self.command('screendump',{'filename':str(self.base/f'{name}.ppm')})
    def open_editor(self):self.key('f3','EDITOR_READY')
    def draft(self):self.key('e','EDITOR_DRAFT')
    def stop(self,powercut=False):
        if self.proc.poll() is None:
            if powercut:self.proc.kill()
            else:
                try:self.command('quit')
                except Exception:self.proc.terminate()
            try:self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait()
        if self.stream:self.stream.close()
        if self.sock:self.sock.close()
        self.err.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.stop()

with tempfile.TemporaryDirectory(prefix='eutherboot-editor-') as tmp:
    tmp=Path(tmp);esp=tmp/'esp';(esp/'EFI/BOOT').mkdir(parents=True)
    for name in ('EutherBoot','Recovery','New'):(esp/'EFI'/name).mkdir()
    binary=ROOT/'artifacts'/('EutherBoot-faults.efi' if FAULT else 'EutherBoot.efi')
    shutil.copy2(binary,esp/'EFI/BOOT/BOOTX64.EFI')
    for name in ('EutherBoot/TestChild.efi','Recovery/rescue.efi','New/loader.efi'):
        shutil.copy2(ROOT/'artifacts/TestChild.efi',esp/'EFI'/name)
    original=(ROOT/'eutherboot.toml').read_bytes()+b"\n# Recovery fixture\n[[entry]]\nid='rescue'\nname='Recovery test'\ntype='efi'\npath='\\EFI\\Recovery\\rescue.efi'\n"
    (esp/'EFI/EutherBoot/eutherboot.toml').write_bytes(original)
    if FAULT:(esp/'EFI/EutherBoot/editor-fault').write_text(a.case)
    disk=virtual_disk.create(esp,tmp)
    image=f'{disk}@@1048576'
    def read_file(name):
        r=subprocess.run(['mtype','-i',image,'::/EFI/EutherBoot/'+name],capture_output=True)
        return r.stdout if r.returncode==0 else None
    def evidence(label):
        for suffix in ('','.bak','.new','.txn'):
            value=read_file('eutherboot.toml'+suffix)
            if value is not None:(out/f'{label}-config{suffix}.txt').write_bytes(value)
    with VM(tmp,disk,1,readonly=a.case=='readonly') as vm:
        vm.open_editor();vm.screen('inspection')
        vm.key('s','EDITOR_READY')  # Read-only mode ignores save.
        assert 'EDITOR_CONFIRM' not in vm.log.read_text()
        vm.draft()
        if a.case=='invalid':
            vm.field('p','path','\\EFI\\BOOT\\BOOTX64.EFI');vm.key('v','EDITOR_INVALID');vm.key('s','EDITOR_INVALID')
            assert 'EDITOR_CONFIRM' not in vm.log.read_text()
            vm.field('p','path','\\EFI\\EutherBoot\\TestChild.efi')
            vm.key('r','EDITOR_CONFIRM');vm.key('y','EDITOR_UPDATED');vm.key('s','EDITOR_INVALID')
            vm.screen('invalid-draft')
            vm.key('d','EDITOR_UPDATED');vm.key('v','EDITOR_VALID')
            vm.key('esc','EDITOR_CONFIRM');vm.key('y','EDITOR_DISCARD')
        elif a.case=='save':
            vm.key('a','PROMPT_READY id');vm.text('extra');vm.key('ret','PROMPT_READY name')
            vm.text('Added target');vm.key('ret','PROMPT_READY path');vm.key('f4','PROMPT_CHANGED')
            vm.text('\\EFI\\New\\loader.efi');vm.key('ret','EDITOR_UPDATED')
            vm.key('d','EDITOR_UPDATED');vm.field('t','timeout','4');vm.key('g','EDITOR_UPDATED')
            vm.key('up','EDITOR_READY');vm.key('up','EDITOR_READY');vm.key('r','EDITOR_CONFIRM');vm.key('y','EDITOR_UPDATED')
            vm.key('v','EDITOR_VALID');vm.key('f5','EDITOR_PREVIEW');vm.screen('preview');vm.key('spc','EDITOR_READY')
            assert 'CHILD_STARTED' not in vm.log.read_text()
            vm.key('s','EDITOR_CONFIRM');vm.screen('confirm-save');vm.key('y','EDITOR_SAVED')
            vm.wait('CONFIG_OK entries=2 default=1 timeout=4');vm.screen('saved-menu')
            time.sleep(4.3)
            assert 'TIMEOUT_ARMED' not in vm.log.read_text() and 'CHILD_STARTED' not in vm.log.read_text()
            vm.key('ret','CHILD_READY');vm.key('ret','MENU_RESUMED')
            assert 'CHAINLOAD_REQUEST id=extra path=\\EFI\\New\\loader.efi' in vm.log.read_text()
        else:
            vm.field('t','timeout','2');vm.key('v','EDITOR_VALID')
            if a.case=='discard':
                vm.key('g','EDITOR_UPDATED');vm.key('f5','EDITOR_PREVIEW');vm.screen('unsaved-preview');vm.key('spc','EDITOR_READY')
                vm.key('s','EDITOR_CONFIRM');vm.key('n','EDITOR_SAVE_CANCELLED')
                vm.key('esc','EDITOR_CONFIRM');vm.key('y','EDITOR_DISCARD')
            else:
                vm.key('s','EDITOR_CONFIRM')
                if FAULT:
                    vm.key('y',f'FAULT_WAIT {a.case}');vm.stop(powercut=True)
                else:
                    vm.key('y','EDITOR_SAVE_ERROR');vm.screen('write-error')
                    assert 'WRITE_PROTECTED' in (vm.base/'serial.log').read_text()
                    vm.key('esc','EDITOR_CONFIRM');vm.key('y','EDITOR_DISCARD')
        if not FAULT:vm.stop()
    evidence('after-first-boot')
    if a.case in ('discard','invalid','readonly'):
        assert read_file('eutherboot.toml')==original
        assert all(read_file('eutherboot.toml'+s) is None for s in ('.new','.bak','.txn'))
    elif a.case=='save':
        saved=read_file('eutherboot.toml');c=tomllib.loads(saved.decode())
        assert c['boot']=={'default':'extra','timeout':4,'theme':'text'}
        assert [e['id'] for e in c['entry']]==['rescue','extra']
        assert read_file('eutherboot.toml.bak')==original
        assert read_file('eutherboot.toml.new') is None and read_file('eutherboot.toml.txn') is None
        with VM(tmp,disk,2) as vm:
            assert 'CONFIG_OK entries=2 default=1 timeout=4' in vm.log.read_text()
            vm.open_editor();vm.screen('persisted-inspection')
            vm.key('b','EDITOR_CONFIRM');vm.key('y','EDITOR_RECOVERED');vm.wait('CONFIG_OK entries=2 default=0 timeout=0')
            vm.key('esc','EXIT_FIRMWARE')
        assert read_file('eutherboot.toml')==original and read_file('eutherboot.toml.bak')==original
    else:
        if a.case=='after-stage':assert read_file('eutherboot.toml')==original and read_file('eutherboot.toml.new') is not None
        elif a.case=='after-backup':assert read_file('eutherboot.toml') is None and read_file('eutherboot.toml.bak')==original
        else:
            assert tomllib.loads(read_file('eutherboot.toml').decode())['boot']['timeout']==2
            assert read_file('eutherboot.toml.bak')==original
        # Use the production build for recovery, not the fault-injection build.
        run('mcopy','-o','-i',image,str(ROOT/'artifacts/EutherBoot.efi'),'::/EFI/BOOT/BOOTX64.EFI')
        with VM(tmp,disk,2) as vm:
            assert 'CONFIG_ERROR Unfinished configuration save' in vm.log.read_text()
            time.sleep(2.3);assert 'TIMEOUT_ARMED' not in vm.log.read_text()
            vm.open_editor();vm.screen('recovery')
            vm.key('b' if a.case=='after-backup' else 'c','EDITOR_CONFIRM')
            vm.key('y','EDITOR_RECOVERED');vm.wait('CONFIG_OK')
            time.sleep(2.3);assert 'TIMEOUT_ARMED' not in vm.log.read_text()
            vm.key('esc','EXIT_FIRMWARE')
        assert read_file('eutherboot.toml.new') is None and read_file('eutherboot.toml.txn') is None
        final=read_file('eutherboot.toml')
        assert final==original if a.case!='after-install' else tomllib.loads(final.decode())['boot']['timeout']==2
    evidence('final')
    (out/'result.txt').write_text(f'PASS {a.case}\nOriginal SHA256: {hashlib.sha256(original).hexdigest()}\nFinal SHA256: {hashlib.sha256(read_file("eutherboot.toml")).hexdigest()}\n')
    print(f'PASS editor: {a.case} ({a.width}x{a.height}), GPT/FAT persistence verified')
