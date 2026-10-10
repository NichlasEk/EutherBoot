#!/usr/bin/env python3
"""LoadFile2 callback/lifetime tests with a returning synthetic EFI consumer."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import tempfile
from qemu_test import VM
import virtual_disk

ROOT = Path(__file__).resolve().parent.parent
p = argparse.ArgumentParser()
p.add_argument('--case', choices=('return', 'install', 'cleanup', 'old-stub', 'empty', 'none'), default='return')
p.add_argument('--width', type=int, default=1024)
p.add_argument('--height', type=int, default=768)
a = p.parse_args()
out = ROOT/'artifacts'/f'initrd-{a.case}-{a.width}x{a.height}'
out.mkdir(parents=True, exist_ok=True);(out/'result.json').unlink(missing_ok=True)

def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f, 'sha256').hexdigest()

def synthetic_kernel(child):
    # This remains TestChild's executable code, NOT a Linux kernel. Move its PE
    # headers/file offsets to make space for synthetic Linux-identification fields.
    # The test exercises a returning application through the production Linux path.
    source = child.read_bytes();data = bytearray(source[:64] + bytes(1024) + source[64:])
    pe = struct.unpack_from('<I', source, 60)[0]+1024
    struct.pack_into('<I', data, 60, pe)
    optional = pe+24
    struct.pack_into('<I', data, optional+60, struct.unpack_from('<I', data, optional+60)[0]+1024)
    struct.pack_into('<I', data, optional+64, 0) # old optional checksum no longer applies
    sections = struct.unpack_from('<H', data, pe+6)[0]
    table = optional+struct.unpack_from('<H', data, pe+20)[0]
    assert struct.unpack_from('<II', data, optional+112+4*8)==(0,0), 'Unsigned fixture required'
    for i in range(sections):
        field = table+i*40+20
        offset = struct.unpack_from('<I', data, field)[0]
        if offset:struct.pack_into('<I', data, field, offset+1024)
    data[0x1fe:0x200] = b'\x55\xaa';data[0x202:0x206] = b'HdrS'
    struct.pack_into('<H', data, 0x206, 0x20b)
    struct.pack_into('<I', data, 0x238, 4096)
    struct.pack_into('<HH', data, optional+44, 0 if a.case=='old-stub' else 1, 0)
    return data

with tempfile.TemporaryDirectory(prefix='eutherboot-initrd-') as directory:
    tmp = Path(directory);esp = tmp/'esp';(esp/'EFI/BOOT').mkdir(parents=True)
    files = esp/'EFI/EutherBoot';files.mkdir()
    firmware = ROOT/'artifacts'/('EutherBoot-faults.efi' if a.case in ('install','cleanup') else 'EutherBoot.efi')
    shutil.copy2(firmware, esp/'EFI/BOOT/BOOTX64.EFI')
    child = ROOT/'artifacts/TestChild.efi'
    shutil.copy2(child, files/'child.efi')
    (files/'probe.efi').write_bytes(synthetic_kernel(child))
    payload = bytes((i*29+7)%256 for i in range(4097))
    (files/'probe.img').write_bytes(b'' if a.case=='empty' else payload)
    fnv = 0xcbf29ce484222325
    for b in payload:fnv=((fnv^b)*0x100000001b3)&0xffffffffffffffff
    config=r"""[boot]
default='probe'
timeout=0
[[entry]]
id='probe'
name='Returning LoadFile2 consumer'
type='linux-efi'
path='\EFI\EutherBoot\probe.efi'
"""
    if a.case!='none':config+="initrd='\\EFI\\EutherBoot\\probe.img'\n"
    config+=r"""[[entry]]
id='plain'
name='Plain EFI isolation check'
type='efi'
path='\EFI\EutherBoot\child.efi'
"""
    (files/'eutherboot.toml').write_text(config)
    if a.case in ('install','cleanup'):(files/'initrd-fault').write_text(a.case)
    disk=virtual_disk.create(esp,tmp);before=digest(disk)
    with VM(tmp,disk,out,width=a.width,height=a.height) as v:
        for attempt in range(3):
            start=len(v.log.read_text())
            if a.case in ('install','old-stub','empty'):
                v.key('ret','MENU_RESUMED');text=v.log.read_text()[start:]
                expected={'install':'DEVICE_ERROR','old-stub':'UNSUPPORTED','empty':'BAD_BUFFER_SIZE'}[a.case]
                assert expected in text and 'CHILD_STARTED' not in text and 'CHAINLOAD_LOADED' not in text
                if a.case=='install':assert 'INITRD_REMOVED' in text
                else:assert 'INITRD_INSTALLED' not in text
            else:
                v.key('ret','CHILD_READY');text=v.log.read_text()[start:]
                if a.case=='none':assert 'CHILD_INITRD_ABSENT' in text and 'INITRD_INSTALLED' not in text
                else:
                    assert 'CHILD_INITRD_CONTRACT_OK' in text and 'CHILD_INITRD_ERROR' not in text
                    assert text.count(f'CHILD_INITRD_BYTES size={len(payload)} fnv={fnv:016x}')==2
                v.key('d' if attempt==2 else 'ret', 'INITRD_CLEANUP_BLOCKED' if a.case=='cleanup' else 'MENU_RESUMED')
                if a.case=='cleanup':
                    # Neither Esc nor Enter may escape while callback code is live.
                    v.key('esc');v.key('ret')
                    assert 'MENU_RESUMED' not in v.log.read_text()[start:]
                    v.screen('cleanup-blocked');v.key('r','MENU_RESUMED')
                text=v.log.read_text()[start:]
                if a.case!='none':assert text.index('INITRD_REMOVED') < text.index('MENU_RESUMED')
            v.screen(f'menu-{attempt}')
            # A separate, ordinary child independently verifies no provider survived.
            v.key('down','SELECT 1');start=len(v.log.read_text());v.key('ret','CHILD_READY')
            assert 'CHILD_INITRD_ABSENT' in v.log.read_text()[start:]
            v.key('ret','MENU_RESUMED');v.key('up','SELECT 0')
        v.key('esc','EXIT_FIRMWARE')
    assert digest(disk)==before
    (out/'result.json').write_text(json.dumps({'result':'PASS','case':a.case,'disk_sha256':before,
        'firmware_sha256':digest(firmware),'child_sha256':digest(child),'synthetic_probe_sha256':digest(files/'probe.efi'),
        'payload_sha256':hashlib.sha256(payload).hexdigest()},indent=2)+'\n')
print(f'PASS LoadFile2 {a.case} ({a.width}x{a.height})')
