#!/usr/bin/env python3
"""Isolated OVMF runner. No host disks, network, or persistent firmware state."""
import argparse, json, os, pathlib, shutil, socket, subprocess, tempfile, time
import qemu_cases
import virtual_disk
ROOT = pathlib.Path(__file__).resolve().parent.parent
p = argparse.ArgumentParser()
p.add_argument('--test', action='store_true')
p.add_argument('--disk-image', action='store_true', help='Use disposable GPT/FAT (automatic for interactive runs)')
p.add_argument('--config-case', choices=qemu_cases.CASES, default='sample')
p.add_argument('--scenario', choices=('return', 'abort', 'exit-data', 'missing', 'invalid'), default='return')
p.add_argument('--width', type=int, default=1024)
p.add_argument('--height', type=int, default=768)
a = p.parse_args()
use_disk = a.disk_image or not a.test
code = pathlib.Path(os.environ.get('OVMF_CODE', '/usr/share/edk2/x64/OVMF_CODE.4m.fd'))
variables = pathlib.Path(os.environ.get('OVMF_VARS', '/usr/share/edk2/x64/OVMF_VARS.4m.fd'))
for path in (code, variables, ROOT/'artifacts/EutherBoot.efi', ROOT/'artifacts/TestChild.efi'):
    if not path.is_file(): p.error(f'Missing {path}; build first or set OVMF_CODE / OVMF_VARS')
out = ROOT/'artifacts'/f'qemu-{a.width}x{a.height}-{a.scenario}-{a.config_case}'
if use_disk: out = out.with_name(out.name+'-disk')
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='eutherboot-') as tmp:
    tmp = pathlib.Path(tmp)
    esp = tmp/'esp'; (esp/'EFI/BOOT').mkdir(parents=True)
    shutil.copy2(ROOT/'artifacts/EutherBoot.efi', esp/'EFI/BOOT/BOOTX64.EFI')
    (esp/'EFI/EutherBoot').mkdir()
    if a.scenario in ('return', 'abort', 'exit-data'):
        shutil.copy2(ROOT/'artifacts/TestChild.efi', esp/'EFI/EutherBoot/TestChild.efi')
    elif a.scenario == 'invalid':
        (esp/'EFI/EutherBoot/TestChild.efi').write_bytes(b'Not a PE/COFF EFI executable.\n')
    qemu_cases.prepare(esp, ROOT, a.config_case)
    disk = virtual_disk.create(esp,tmp) if use_disk else None
    disk_arg = f'if=virtio,format=raw,file={disk}' if disk else f'format=raw,file=fat:rw:{esp}'
    shutil.copy2(variables, tmp/'vars.fd')
    log = out/'debug.log'; log.write_text('')
    args = ['qemu-system-x86_64', '-machine', 'q35', '-accel', 'tcg', '-m', '256',
            '-net', 'none', '-no-reboot', '-vga', 'none', '-device', f'VGA,xres={a.width},yres={a.height}',
            '-drive', f'if=pflash,format=raw,readonly=on,file={code}',
            '-drive', f'if=pflash,format=raw,file={tmp}/vars.fd',
            '-drive', disk_arg,
            '-debugcon', f'file:{log}', '-global', 'isa-debugcon.iobase=0xe9',
            '-qmp', f'unix:{tmp}/qmp,server=on,wait=off', '-serial', f'file:{out}/serial.log']
    if a.test: args += ['-display', 'none']
    with (out/'qemu.log').open('w') as err:
        proc = subprocess.Popen(args, stdout=err, stderr=err)
        try:
            if not a.test:
                print("Disposable QEMU disk: configuration changes are discarded when the VM closes.", flush=True)
                proc.wait()
            else:
                deadline = time.monotonic()+60
                while 'MENU_READY' not in log.read_text():
                    if proc.poll() is not None: raise RuntimeError((out/'qemu.log').read_text())
                    if time.monotonic()>deadline: raise TimeoutError('UEFI menu did not start')
                    time.sleep(.1)
                menu_ready_at = time.monotonic()
                sock = socket.socket(socket.AF_UNIX); sock.settimeout(10); sock.connect(str(tmp/'qmp'))
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
                def wait_marker(marker, before):
                    deadline=time.monotonic()+10
                    while marker not in log.read_text()[before:]:
                        if proc.poll() is not None: raise RuntimeError('QEMU exited during test')
                        if time.monotonic()>deadline: raise AssertionError(f'missing {marker}: {log.read_text()[before:]}')
                        time.sleep(.05)
                def key(name, marker):
                    before=len(log.read_text())
                    command('human-monitor-command', {'command-line':f'sendkey {name}'})
                    wait_marker(marker, before)
                    time.sleep(.2)
                if a.config_case != 'sample':
                    qemu_cases.run(a.config_case, out, log, screen, key, wait_marker, a.width, a.height, menu_ready_at)
                else:
                    screen('first-light')
                    with (out/'first-light.ppm').open('rb') as ppm:
                        assert ppm.readline().strip() == b'P6'
                        assert ppm.readline().strip() == f'{a.width} {a.height}'.encode()
                        assert ppm.readline().strip() == b'255'
                        pixels=ppm.read()
                    assert len(pixels) == a.width*a.height*3
                    assert pixels.count(bytes((9,15,24))) > a.width*a.height//2, 'Missing navy canvas'
                    assert pixels.count(bytes((208,184,125))) > 500, 'Missing emblem/borders'
                    assert pixels.count(bytes((238,229,205))) > 100, 'Missing title/menu text'
                    assert 'CHILD_STARTED' not in log.read_text(), 'Unexpected automatic boot'
                    key('up','SELECT 2'); key('down','SELECT 0')
                    key('left','SELECT 2'); key('right','SELECT 0')
                    def chainload(attempt, text_mode=False):
                        before=len(log.read_text())
                        serial_before=(out/'serial.log').stat().st_size
                        if a.scenario in ('return', 'abort', 'exit-data'):
                            key('ret','CHILD_READY')
                            screen(f'child-{attempt}')
                            child_pixels=(out/f'child-{attempt}.ppm').read_bytes().split(b'\n',3)[3]
                            assert child_pixels.count(bytes((9,15,24))) < a.width*a.height//2
                            assert 'EUTHERBOOT EFI TEST CHILD' in (out/'serial.log').read_text()
                            key('ret' if a.scenario == 'return' else 'd' if a.scenario == 'exit-data' else 'esc', 'MENU_RESUMED')
                        else:
                            key('ret','MENU_RESUMED')
                        fresh=log.read_text()[before:]
                        assert fresh.count('CHAINLOAD_REQUEST') == 1
                        assert 'EXIT_FIRMWARE' not in fresh
                        if a.scenario == 'return':
                            assert 'CHILD_CONTEXT_OK' in fresh and 'CHILD_RETURN_SUCCESS' in fresh
                            assert 'CHAINLOAD_RETURN_SUCCESS' in fresh and 'CHAINLOAD_ERROR' not in fresh
                        elif a.scenario == 'exit-data':
                            assert 'CHILD_EXIT_DATA' in fresh and 'EXIT_DATA_FREED bytes=28' in fresh and 'Start(ABORTED)' in fresh
                        elif a.scenario == 'abort':
                            assert 'CHILD_RETURN_ABORTED' in fresh and 'Start(ABORTED)' in fresh
                        elif a.scenario == 'missing':
                            assert 'Load(NOT_FOUND)' in fresh, fresh
                        else:
                            assert 'Load(LOAD_ERROR)' in fresh or 'Load(UNSUPPORTED)' in fresh, fresh
                        if a.scenario in ('return','abort','exit-data'):
                            assert 'CHAINLOAD_RELEASED' in fresh or 'CHAINLOAD_UNLOADED' in fresh
                        else:
                            assert 'CHILD_STARTED' not in fresh and 'CHAINLOAD_LOADED' not in fresh
                        screen(f'resumed-{attempt}')
                        resumed=(out/f'resumed-{attempt}.ppm').read_bytes().split(b'\n',3)[3]
                        if text_mode:
                            serial=(out/'serial.log').read_bytes()[serial_before:]
                            assert b'EUTHERBOOT | SYSTEM REGIS' in serial, 'Missing restored text menu'
                            assert b'EFI test application' in serial
                            assert 'TEXT_READY' in fresh
                            assert resumed.count(bytes((9,15,24))) < a.width*a.height//2
                        else:
                            # Child clears the display: verify the actual menu is redrawn,
                            # not just that a trace says it resumed. Notice/footer may differ.
                            assert resumed[:(a.height-110)*a.width*3] == pixels[:(a.height-110)*a.width*3]
                    chainload(1)
                    key('down','SELECT 1'); key('up','SELECT 0'); chainload(2)
                    key('f2','TEXT_READY'); screen('text-fallback')
                    fallback=(out/'text-fallback.ppm').read_bytes().split(b'\n',3)[3]
                    assert fallback.count(bytes((9,15,24))) < a.width*a.height//2, 'Graphical canvas remained after F2'
                    chainload(3, text_mode=True)
                    key('down','SELECT 1')
                    key('down','SELECT 2'); key('ret','EXIT_FIRMWARE')
                command('quit'); proc.wait(timeout=5)
                print(f'PASS: {a.scenario}/{a.config_case} ({a.width}x{a.height})')
        finally:
            if proc.poll() is None:
                proc.terminate()
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait()
