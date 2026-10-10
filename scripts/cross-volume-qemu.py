#!/usr/bin/env python3
"""Persist/import explicit GPT targets without changing any physical disk or firmware."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import tomllib
from qemu_test import VM
import virtual_disk

ROOT=Path(__file__).resolve().parent.parent
CASES=('save','discard','missing','duplicate','non-esp','alias','self','self-copy','same-path-self','missing-file')
p=argparse.ArgumentParser()
p.add_argument('--case',choices=CASES,default='save')
p.add_argument('--width',type=int,default=1024)
p.add_argument('--height',type=int,default=768)
a=p.parse_args()
out=ROOT/'artifacts'/f'cross-volume-{a.case}-{a.width}x{a.height}'
out.mkdir(parents=True,exist_ok=True)
IDS=['11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222','33333333-3333-4333-8333-333333333333']
SHARED=r'\EFI\Tools\shared.efi'
OWN_PATH=r'\EFI\BOOT\BOOTX64.EFI'

def digest(path,offset=0,size=None):
    h=hashlib.sha256()
    with path.open('rb') as f:
        f.seek(offset)
        while size is None or size>0:
            block=f.read(min(size,1024*1024) if size is not None else 1024*1024)
            if not block:break
            h.update(block)
            if size is not None:size-=len(block)
    return h.hexdigest()

def entry(id,name,path,guid=None):
    value=f"\n[[entry]]\nid='{id}'\nname='{name}'\ntype='efi'\npath='{path}'\n"
    if guid is not None:value+=f"partition_guid='{guid}'\n"
    return value

with tempfile.TemporaryDirectory(prefix='eutherboot-cross-volume-') as tmp:
    tmp=Path(tmp)
    sources=[tmp/f'esp-{i}' for i in range(3)]
    for source in sources:
        (source/'EFI/Tools').mkdir(parents=True)
        shutil.copy2(ROOT/'artifacts/TestChild.efi',source/'EFI/Tools/shared.efi')
    (sources[0]/'EFI/BOOT').mkdir()
    (sources[0]/'EFI/EutherBoot').mkdir()
    shutil.copy2(ROOT/'artifacts/EutherBoot.efi',sources[0]/'EFI/BOOT/BOOTX64.EFI')
    original="[boot]\ndefault='own'\ntimeout=0\ntheme='system-regis'\n"+entry('own','Own volume',SHARED)
    if a.case not in ('save','discard'):
        original=original.replace("default='own'","default='remote'").replace('timeout=0','timeout=2')
        guid=IDS[1];path=SHARED
        if a.case=='missing':guid='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
        elif a.case=='alias':guid=IDS[0]
        elif a.case=='self':guid=IDS[0];path=OWN_PATH
        elif a.case=='same-path-self':
            path=OWN_PATH
            (sources[1]/'EFI/BOOT').mkdir()
            shutil.copy2(ROOT/'artifacts/TestChild.efi',sources[1]/'EFI/BOOT/BOOTX64.EFI')
        elif a.case=='self-copy':
            shutil.copy2(ROOT/'artifacts/EutherBoot.efi',sources[1]/'EFI/Tools/shared.efi')
        elif a.case=='missing-file':(sources[1]/'EFI/Tools/shared.efi').unlink()
        original+=entry('remote','Remote volume',path,guid.upper())
    original=original.encode()
    (sources[0]/'EFI/EutherBoot/eutherboot.toml').write_bytes(original)
    ids=IDS.copy()
    if a.case=='duplicate':ids[2]=ids[1]
    kinds=['ef00','0700' if a.case=='non-esp' else 'ef00','ef00' if a.case=='duplicate' else '0700']
    disk=virtual_disk.create_layout(list(zip(sources,kinds,ids)),tmp)
    before=digest(disk)
    # Both other partitions, including data and all FAT metadata, must remain identical even after Save.
    other_before=digest(disk,1048576+64*1024*1024,128*1024*1024)
    def vm(disk,iteration=1):return VM(tmp,disk,out,iteration,a.width,a.height)
    def read_file(name):
        r=subprocess.run(['mtype','-i',f'{disk}@@1048576','::/EFI/EutherBoot/'+name],capture_output=True)
        return r.stdout if r.returncode==0 else None
    with vm(disk) as v:
        if a.case in ('save','discard'):
            if a.case=='save':
                v.key('f4','DISCOVERY_READY');v.key('down','selected=1')
                v.key('a','DISCOVERY_IMPORT_CONFIRM');v.screen('import-confirmation')
                v.key('n','DISCOVERY_READY');assert 'EDITOR_OPEN' not in v.log.read_text()
                v.key('a','DISCOVERY_IMPORT_CONFIRM');v.key('y','EDITOR_IMPORTED');v.wait('EDITOR_READY')
            else:
                v.open_editor();v.draft();v.key('i','DISCOVERY_READY');v.key('down','selected=1')
                v.key('ret','DISCOVERY_IMPORT_CONFIRM');v.key('y','EDITOR_IMPORTED');v.wait('EDITOR_READY')
            v.screen('imported-draft')
            serial=(v.base/'serial.log').read_text()
            assert 'Default: own  Timeout: 0s' in serial
            assert IDS[1] in serial
            assert 'CHILD_STARTED' not in v.log.read_text() and 'EDITOR_SAVED' not in v.log.read_text()
            v.key('v','EDITOR_VALID')
            if a.case=='discard':
                # Duplicate import leaves the draft unchanged, and selecting a target in the picker never boots it.
                v.key('i','DISCOVERY_READY');v.key('down','selected=1')
                v.key('ret','DISCOVERY_IMPORT_CONFIRM');v.key('y','EDITOR_READY')
                assert 'already present in the draft' in (v.base/'serial.log').read_text()
                v.field('u','partition_guid','bad');v.key('v','EDITOR_INVALID')
                v.field('u','partition_guid','');v.key('v','EDITOR_INVALID') # collides with own-volume path
                v.field('u','partition_guid',IDS[1]);v.key('v','EDITOR_VALID')
                v.key('f5','EDITOR_PREVIEW');v.screen('preview');v.key('spc','EDITOR_READY')
                v.key('s','EDITOR_CONFIRM');v.key('n','EDITOR_SAVE_CANCELLED')
                v.key('esc','EDITOR_CONFIRM');v.key('y','EDITOR_DISCARD')
                assert 'CHILD_STARTED' not in v.log.read_text()
            else:
                v.key('d','EDITOR_UPDATED');v.field('t','timeout','2')
                v.key('s','EDITOR_CONFIRM');v.screen('save-confirmation');v.key('y','EDITOR_SAVED')
                v.wait('CONFIG_OK entries=2 default=1 timeout=2')
                time.sleep(2.3)
                assert 'TIMEOUT_ARMED' not in v.log.read_text() and 'CHILD_STARTED' not in v.log.read_text()
                # Persisted entry launches from remote even before reboot.
                offset=len(v.log.read_text());v.key('ret','CHILD_READY')
                assert f'CHILD_VOLUME {IDS[1]}' in v.log.read_text()[offset:]
                v.key('ret','MENU_RESUMED')
        elif a.case in ('alias','self'):
            assert 'CONFIG_ERROR' in v.log.read_text() and 'TIMEOUT_ARMED' not in v.log.read_text()
            assert ('Duplicate EFI target' if a.case=='alias' else 'EutherBoot itself') in v.log.read_text()
            v.screen('rejected-config');time.sleep(2.3)
            assert 'CHILD_STARTED' not in v.log.read_text()
        elif a.case in ('missing','duplicate','non-esp'):
            assert 'DEFAULT_UNAVAILABLE' in v.log.read_text() and 'TIMEOUT_ARMED' not in v.log.read_text()
            time.sleep(2.3);assert 'CHILD_STARTED' not in v.log.read_text()
            v.key('ret','MENU_RESUMED');v.screen('unavailable')
            assert ('Ambiguous ESP GUID' if a.case=='duplicate' else 'Missing ESP GUID') in v.log.read_text()
            assert 'CHILD_STARTED' not in v.log.read_text()
            v.key('up','SELECT 0');offset=len(v.log.read_text());v.key('ret','CHILD_READY')
            assert f'CHILD_VOLUME {IDS[0]}' in v.log.read_text()[offset:]
            v.key('ret','MENU_RESUMED')
        elif a.case in ('self-copy','missing-file'):
            v.wait('MENU_RESUMED');v.screen('rejected-target')
            assert 'TIMEOUT_FIRED' in v.log.read_text()
            assert 'CHILD_STARTED' not in v.log.read_text() and 'CHAINLOAD_LOADED' not in v.log.read_text()
            assert ('UNSUPPORTED' if a.case=='self-copy' else 'NOT_FOUND') in v.log.read_text()
            time.sleep(2.3);assert v.log.read_text().count('CHAINLOAD_REQUEST')==1
            v.key('up','SELECT 0');v.key('ret','CHILD_READY');v.key('ret','MENU_RESUMED')
        else:
            v.wait('CHILD_READY');assert 'TIMEOUT_FIRED' in v.log.read_text()
            assert f'CHILD_VOLUME {IDS[1]}' in v.log.read_text()
            v.key('ret','MENU_RESUMED')
        v.key('esc','EXIT_FIRMWARE')
    assert digest(disk,1048576+64*1024*1024,128*1024*1024)==other_before
    if a.case=='save':
        saved=read_file('eutherboot.toml');parsed=tomllib.loads(saved.decode())
        assert parsed['boot']['default']=='efi-1' and parsed['boot']['timeout']==2
        assert len(parsed['entry'])==2
        assert parsed['entry'][1]['partition_guid']==IDS[1] and parsed['entry'][1]['path']==SHARED
        assert 'partition_guid' not in parsed['entry'][0]
        assert read_file('eutherboot.toml.bak')==original
        assert read_file('eutherboot.toml.txn') is None and read_file('eutherboot.toml.new') is None
        (out/'saved.toml').write_bytes(saved);(out/'backup.toml').write_bytes(read_file('eutherboot.toml.bak'))
        # Rebuild with the exact saved bytes but reverse ESP partition positions.
        # GUID resolution must survive a changed partition number/device path.
        (sources[0]/'EFI/EutherBoot/eutherboot.toml').write_bytes(saved)
        moved=tmp/'reordered';moved.mkdir()
        second=virtual_disk.create_layout([(sources[1],'ef00',IDS[1]),(sources[0],'ef00',IDS[0]),(sources[2],'0700',IDS[2])],moved)
        second_before=digest(second)
        with vm(second,2) as v:
            assert 'CONFIG_OK entries=2 default=1 timeout=2' in v.log.read_text()
            v.wait('CHILD_READY');assert 'TIMEOUT_FIRED' in v.log.read_text()
            assert f'CHILD_VOLUME {IDS[1]}' in v.log.read_text()
            v.key('ret','MENU_RESUMED');v.screen('reordered-return')
            time.sleep(2.3);assert v.log.read_text().count('CHAINLOAD_REQUEST')==1
            v.key('esc','EXIT_FIRMWARE')
        assert digest(second)==second_before
    else:
        assert digest(disk)==before,'Unexpected disk write'
        assert read_file('eutherboot.toml')==original
    (out/'result.txt').write_text(f'PASS {a.case}\nOther partitions SHA256 unchanged: {other_before}\n'+('Saved configuration and exact backup verified; reordered-ESP reboot passed.\n' if a.case=='save' else f'Whole disk SHA256 unchanged: {before}\n'))
    print(f'PASS cross-volume: {a.case} ({a.width}x{a.height})')
