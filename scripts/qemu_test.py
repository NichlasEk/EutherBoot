"""QMP keyboard and capture helpers for isolated GPT/FAT integration tests."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
CODE=Path(os.environ.get('OVMF_CODE','/usr/share/edk2/x64/OVMF_CODE.4m.fd'))
VARS=Path(os.environ.get('OVMF_VARS','/usr/share/edk2/x64/OVMF_VARS.4m.fd'))

class VM:
    def __init__(self,tmp,disk,out,iteration=1,width=1024,height=768,readonly=False,memory=256,cpu=None,
                 firmware_code=CODE,firmware_vars=VARS,secure=False,
                 extra_disks=(),accel='tcg',serial_socket=None):
        self.base=out/f'boot-{iteration}';self.base.mkdir(exist_ok=True)
        self.log=self.base/'debug.log';self.log.write_text('')
        vars_path=tmp/f'vars-{iteration}.fd';shutil.copy2(firmware_vars,vars_path)
        qmp=tmp/f'qmp-{iteration}'
        self.err=(self.base/'qemu.log').open('w')
        args=['qemu-system-x86_64','-machine','q35,smm=on' if secure else 'q35','-accel',accel,'-m',str(memory),'-net','none','-no-reboot','-display','none',
              '-vga','none','-device',f'VGA,xres={width},yres={height}',
              '-drive',f'if=pflash,format=raw,readonly=on,file={firmware_code}',
              '-drive',f'if=pflash,format=raw,file={vars_path}',
              '-drive',f'if=virtio,format=raw,file={disk},readonly={"on" if readonly else "off"}',
              '-debugcon',f'file:{self.log}','-global','isa-debugcon.iobase=0xe9',
              '-serial',f'file:{self.base}/serial.log','-qmp',f'unix:{qmp},server=on,wait=off']
        for extra,fmt in extra_disks:
            if not Path(extra).is_file():raise ValueError('Extra disk must be a regular image file')
            if fmt not in ('raw','qcow2'):raise ValueError('Unsupported disk format')
            args += ['-drive',f'if=virtio,format={fmt},file={extra}']
        if serial_socket is not None:
            index=args.index('-serial');args[index+1]='chardev:guestserial'
            args += ['-chardev',f'socket,id=guestserial,path={serial_socket},server=on,wait=off,logfile={self.base}/serial.log']
        if cpu:args += ['-cpu',cpu]
        if secure:args += ['-global','driver=cfi.pflash01,property=secure,value=on']
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
        before=len(self.log.read_text())
        result=self.command('human-monitor-command',{'command-line':f'sendkey {key} 30'})
        if result.strip():raise RuntimeError(f'QEMU sendkey {key}: {result}')
        if marker:self.wait(marker,before)
        time.sleep(delay)
    def text(self,text):
        names={'\\':'backslash',' ': 'spc','.':'dot','-':'minus','_':'shift-minus',':':'shift-semicolon',"'":'apostrophe','/':'slash','=':'equal',',':'comma','"':'shift-apostrophe'}
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

