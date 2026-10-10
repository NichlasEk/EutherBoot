#!/usr/bin/env python3
"""Secure Boot tests using throwaway keys, enrolled OVMF copies and virtual disks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from qemu_test import VM, VARS
import virtual_disk

ROOT = Path(__file__).resolve().parent.parent
OWNER = '95ef2464-2a03-487a-bfa1-b27252629a71'
p = argparse.ArgumentParser()
p.add_argument('--width', type=int, default=1024)
p.add_argument('--height', type=int, default=768)
p.add_argument('--uki', action='store_true', help='Also boot an existing local diagnostic Linux UKI')
a = p.parse_args()
out = ROOT/'artifacts'/f'secureboot-{a.width}x{a.height}{"-uki" if a.uki else ""}'
out.mkdir(parents=True, exist_ok=True)
(out/'result.json').unlink(missing_ok=True)
code = Path(os.environ.get('OVMF_SECURE_CODE', '/usr/share/edk2/x64/OVMF_CODE.secboot.4m.fd'))

def tool(name, local):
    result = shutil.which(name) or str(ROOT/local)
    if not Path(result).is_file():p.error(f'Missing {name}; see README Secure Boot tests')
    return result

sbsign = tool('sbsign', '.tools/sbsigntools/usr/bin/sbsign')
sbverify = tool('sbverify', '.tools/sbsigntools/usr/bin/sbverify')
fwvars = tool('virt-fw-vars', '.tools/secureboot/bin/virt-fw-vars')

def run(*args, good=True):
    r = subprocess.run([str(x) for x in args], capture_output=True, timeout=30)
    if good and r.returncode:
        raise RuntimeError(f'{Path(str(args[0])).name} failed: {r.stderr.decode(errors="replace")}')
    return r

def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f, 'sha256').hexdigest()

inputs = {str(path): sha(path) for path in (code, VARS, ROOT/'artifacts/EutherBoot.efi', ROOT/'artifacts/TestChild.efi')}
if a.uki:
    fixtures = ROOT/'artifacts/linux'
    manifest = json.loads((fixtures/'manifest.json').read_text())
    uki = fixtures/'test.efi'
    assert sha(uki) == manifest['artifacts']['test.efi'], 'Stale Linux UKI fixture'
    inputs[str(uki)] = sha(uki)

with tempfile.TemporaryDirectory(prefix='eutherboot-secure-') as directory:
    tmp = Path(directory)
    # All private keys live only in this mode-0700 temporary directory, never artifacts.
    for name in ('trusted', 'unknown', 'revoked'):
        run('openssl', 'req', '-new', '-x509', '-newkey', 'rsa:2048', '-sha256', '-nodes',
            '-days', '2', '-subj', f'/CN=EutherBoot disposable {name}/',
            '-keyout', tmp/f'{name}.key', '-out', tmp/f'{name}.crt')
        (tmp/f'{name}.key').chmod(0o600)
    enrolled = tmp/'enrolled.fd'
    run(fwvars, '-i', VARS, '-o', enrolled, '--set-pk', OWNER, tmp/'trusted.crt',
        '--add-kek', OWNER, tmp/'trusted.crt', '--add-db', OWNER, tmp/'trusted.crt',
        '--add-db', OWNER, tmp/'revoked.crt', '--add-dbx-cert', OWNER, tmp/'revoked.crt', '--sb')
    # Exact fixture identities and public certificate fingerprints; no key/seed data.
    evidence = {'inputs': inputs, 'certificates': {}, 'sbsign': run(sbsign, '--version').stdout.decode().strip()}
    for name in ('trusted', 'unknown', 'revoked'):
        evidence['certificates'][name] = run('openssl', 'x509', '-in', tmp/f'{name}.crt',
                                           '-noout', '-fingerprint', '-sha256').stdout.decode().strip()
    esp = tmp/'esp'
    (esp/'EFI/BOOT').mkdir(parents=True)
    files = esp/'EFI/EutherBoot';files.mkdir()
    def sign(source, target, name='trusted'):
        run(sbsign, '--key', tmp/f'{name}.key', '--cert', tmp/f'{name}.crt', '--output', target, source)
        run(sbverify, '--cert', tmp/f'{name}.crt', target)
    sign(ROOT/'artifacts/EutherBoot.efi', esp/'EFI/BOOT/BOOTX64.EFI')
    child = ROOT/'artifacts/TestChild.efi'
    sign(child, files/'signed.efi')
    shutil.copy2(child, files/'unsigned.efi')
    sign(child, files/'unknown.efi', 'unknown')
    sign(child, files/'revoked.efi', 'revoked')
    data = bytearray((files/'signed.efi').read_bytes())
    # Change one authenticated DOS-stub byte, preserving executable sections/PE layout.
    assert int.from_bytes(data[0x3c:0x40], 'little') > 0x40
    data[0x40] ^= 1
    (files/'tampered.efi').write_bytes(data)
    assert run(sbverify, '--cert', tmp/'trusted.crt', files/'tampered.efi', good=False).returncode != 0
    names = ['signed', 'unsigned', 'unknown', 'tampered', 'revoked']
    if a.uki:
        sign(uki, files/'linux.efi');names += ['linux']
    config = "[boot]\ndefault='unsigned'\ntimeout=2\n"
    for name in names:
        config += f"\n[[entry]]\nid='{name}'\nname='{name}'\ntype='efi'\npath='\\EFI\\EutherBoot\\{name}.efi'\n"
    (files/'eutherboot.toml').write_text(config)
    evidence['payloads'] = {str(f.relative_to(esp)): sha(f) for f in esp.rglob('*') if f.is_file()}
    disk = virtual_disk.create(esp, tmp);before = sha(disk)
    with VM(tmp, disk, out, width=a.width, height=a.height, firmware_code=code,
            firmware_vars=enrolled, secure=True, memory=768 if a.uki else 256,
            cpu='max' if a.uki else None, readonly=a.uki) as v:
        # Untrusted default must fail once, never fall back or rearm itself.
        v.wait('MENU_RESUMED')
        log = v.log.read_text()
        assert 'TIMEOUT_FIRED' in log and any(f'Load({status})' in log for status in ('SECURITY_VIOLATION', 'ACCESS_DENIED')), log
        assert 'CHILD_STARTED' not in log and 'CHAINLOAD_LOADED' not in log
        time.sleep(2.5)
        assert v.log.read_text().count('CHAINLOAD_REQUEST') == 1
        v.screen('timeout-rejected')
        selected = 1
        def select(index):
            global selected
            while selected != index:
                v.key('up' if selected > index else 'down', f'SELECT {selected-1 if selected > index else selected+1}')
                selected += -1 if selected > index else 1
        def trusted(exit_key='ret'):
            select(0);start = len(v.log.read_text());v.key('ret', 'CHILD_READY')
            log = v.log.read_text()[start:]
            assert 'CHILD_FIRMWARE SecureBoot=1' in log and 'CHILD_FIRMWARE SetupMode=0' in log, log
            v.key(exit_key, 'MENU_RESUMED')
            if exit_key == 'd':assert 'EXIT_DATA_FREED bytes=28' in v.log.read_text()[start:]
        trusted()
        for index, name in enumerate(names[1:5], 1):
            select(index)
            for attempt in range(3):
                start = len(v.log.read_text());v.key('ret', 'MENU_RESUMED')
                log = v.log.read_text()[start:]
                assert any(f'Load({status})' in log for status in ('SECURITY_VIOLATION', 'ACCESS_DENIED')), log
                assert 'CHILD_STARTED' not in log and 'CHAINLOAD_LOADED' not in log
                if 'LOAD_REJECTED_HANDLE' in log:assert 'LOAD_REJECTED_UNLOADED' in log
            v.screen(f'{name}-rejected')
            # The same menu must still run a trusted application after every refusal.
            trusted('d')
            if index == 2:v.key('f2', 'TEXT_READY')
        if a.uki:
            select(5);v.key('ret', 'CHAINLOAD_LOADED')
            serial = v.base/'serial.log';deadline = time.monotonic()+90
            while 'EUTHERBOOT_LINUX_PID1_OK uki' not in serial.read_text(errors='replace'):
                if v.proc.poll() is not None or time.monotonic() > deadline:
                    raise AssertionError('Signed UKI did not reach PID 1: '+serial.read_text(errors='replace')[-4000:])
                time.sleep(.1)
            v.proc.wait(timeout=15)
            text = serial.read_text(errors='replace')
            assert 'EUTHERBOOT_LINUX_PROBE_FAILED' not in text
            assert 'EUTHERBOOT_LINUX_UNAME' in text and 'eutherboot_probe=owner-controlled' in text
        else:v.key('esc', 'EXIT_FIRMWARE')
    assert sha(disk) == before, 'Unexpected virtual ESP mutation'
    for path, digest in inputs.items():assert sha(Path(path)) == digest, 'Source artifact modified'
    log = (out/'boot-1/debug.log').read_text()
    assert log.count('CHAINLOAD_REQUEST') == (19 if a.uki else 18)
    assert log.count('CHILD_STARTED') == 5
    assert log.count('CHAINLOAD_LOADED') == (6 if a.uki else 5)
    evidence['refusals'] = {status: log.count(f'Load({status})') for status in ('ACCESS_DENIED', 'SECURITY_VIOLATION')}
    assert sum(evidence['refusals'].values()) == 13
    evidence['rejected_handle_unloads'] = log.count('LOAD_REJECTED_UNLOADED')
    evidence['whole_disk_sha256'] = before
    evidence['result'] = 'PASS'
    (out/'result.json').write_text(json.dumps(evidence, indent=2)+'\n')
print(f'PASS Secure Boot {a.width}x{a.height}'+(' and signed Linux UKI PID 1' if a.uki else ''))
