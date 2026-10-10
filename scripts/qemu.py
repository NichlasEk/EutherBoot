#!/usr/bin/env python3
"""Isolated OVMF runner. No host disks, network, or persistent firmware state."""
import argparse, json, os, pathlib, shutil, socket, subprocess, tempfile, time
ROOT = pathlib.Path(__file__).resolve().parent.parent
p = argparse.ArgumentParser()
p.add_argument('--test', action='store_true')
p.add_argument('--width', type=int, default=1024)
p.add_argument('--height', type=int, default=768)
a = p.parse_args()
code = pathlib.Path(os.environ.get('OVMF_CODE', '/usr/share/edk2/x64/OVMF_CODE.4m.fd'))
variables = pathlib.Path(os.environ.get('OVMF_VARS', '/usr/share/edk2/x64/OVMF_VARS.4m.fd'))
for path in (code, variables, ROOT/'artifacts/EutherBoot.efi'):
    if not path.is_file(): p.error(f'Missing {path}; build first or set OVMF_CODE / OVMF_VARS')
out = ROOT/'artifacts'/f'qemu-{a.width}x{a.height}'
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='eutherboot-') as tmp:
    tmp = pathlib.Path(tmp)
    esp = tmp/'esp'; (esp/'EFI/BOOT').mkdir(parents=True)
    shutil.copy2(ROOT/'artifacts/EutherBoot.efi', esp/'EFI/BOOT/BOOTX64.EFI')
    shutil.copy2(variables, tmp/'vars.fd')
    log = out/'debug.log'; log.write_text('')
    args = ['qemu-system-x86_64', '-machine', 'q35', '-accel', 'tcg', '-m', '256',
            '-net', 'none', '-no-reboot', '-vga', 'none', '-device', f'VGA,xres={a.width},yres={a.height}',
            '-drive', f'if=pflash,format=raw,readonly=on,file={code}',
            '-drive', f'if=pflash,format=raw,file={tmp}/vars.fd',
            '-drive', f'format=raw,file=fat:rw:{esp}',
            '-debugcon', f'file:{log}', '-global', 'isa-debugcon.iobase=0xe9',
            '-qmp', f'unix:{tmp}/qmp,server=on,wait=off', '-serial', f'file:{out}/serial.log']
    if a.test: args += ['-display', 'none']
    with (out/'qemu.log').open('w') as err:
        proc = subprocess.Popen(args, stdout=err, stderr=err)
        try:
            if not a.test:
                proc.wait()
            else:
                deadline = time.monotonic()+60
                while 'MENU_READY' not in log.read_text():
                    if proc.poll() is not None: raise RuntimeError((out/'qemu.log').read_text())
                    if time.monotonic()>deadline: raise TimeoutError('UEFI menu did not start')
                    time.sleep(.1)
                sock = socket.socket(socket.AF_UNIX); sock.connect(str(tmp/'qmp'))
                stream = sock.makefile('rwb', buffering=0)
                json.loads(stream.readline())
                def command(name, arguments=None):
                    stream.write((json.dumps({'execute':name, 'arguments':arguments or {}})+'\n').encode())
                    while True:
                        reply=json.loads(stream.readline())
                        if 'error' in reply: raise RuntimeError(reply)
                        if 'return' in reply: return reply['return']
                command('qmp_capabilities')
                def screen(name): command('screendump', {'filename': str(out/f'{name}.ppm')})
                def key(name, marker):
                    before=len(log.read_text())
                    command('human-monitor-command', {'command-line':f'sendkey {name}'})
                    deadline=time.monotonic()+5
                    while marker not in log.read_text()[before:]:
                        if time.monotonic()>deadline: raise AssertionError(f'{name}: missing {marker}')
                        time.sleep(.05)
                    time.sleep(.2)
                screen('first-light')
                with (out/'first-light.ppm').open('rb') as ppm:
                    assert ppm.readline().strip() == b'P6'
                    assert ppm.readline().strip() == f'{a.width} {a.height}'.encode()
                    assert ppm.readline().strip() == b'255'
                    pixels=ppm.read()
                assert len(pixels) == a.width*a.height*3
                assert pixels.count(bytes((8,21,35))) > a.width*a.height//2, 'Missing navy canvas'
                assert pixels.count(bytes((184,161,105))) > 500, 'Missing emblem/borders'
                assert pixels.count(bytes((218,225,229))) > 100, 'Missing title/menu text'
                key('up','SELECT 2'); key('down','SELECT 0')
                key('ret','ACTIVATE')
                assert 'EXIT_FIRMWARE' not in log.read_text()
                key('down','SELECT 1'); key('ret','ACTIVATE'); screen('preview')
                key('f2','TEXT_READY'); screen('text-fallback')
                fallback=(out/'text-fallback.ppm').read_bytes().split(b'\n',3)[3]
                assert fallback.count(bytes((8,21,35))) < a.width*a.height//2, 'Graphical canvas remained after F2'
                assert 'EUTHERBOOT | SYSTEM REGIS' in (out/'serial.log').read_text(), 'Missing text console output'
                key('down','SELECT 2'); key('ret','EXIT_FIRMWARE')
                command('quit'); proc.wait(timeout=5)
                print(f'PASS: first light, wrap, selection, preview, text fallback, firmware return ({a.width}x{a.height})')
        finally:
            if proc.poll() is None:
                proc.terminate()
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait()
