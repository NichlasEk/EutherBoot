#!/usr/bin/env python3
"""Build local-only EFI-stub/unsigned UKI fixtures with a fresh minimal initramfs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import struct
import subprocess

ROOT=Path(__file__).resolve().parent.parent
p=argparse.ArgumentParser()
p.add_argument('--kernel',type=Path,default=Path(os.environ.get('EUTHERBOOT_TEST_KERNEL',f'/usr/lib/modules/{platform.release()}/vmlinuz')))
p.add_argument('--stub',type=Path,default=Path('/usr/lib/systemd/boot/efi/linuxx64.efi.stub'))
a=p.parse_args()
out=ROOT/'artifacts/linux';out.mkdir(parents=True,exist_ok=True)
for path in (a.kernel,a.stub):
    if not path.is_file():p.error(f'Missing {path}; supply --kernel / --stub. No host boot files will be generated.')

def run(*args):return subprocess.run(args,check=True,capture_output=True)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def pe(data):
    offset=struct.unpack_from('<I',data,0x3c)[0]
    assert data[:2]==b'MZ' and data[offset:offset+4]==b'PE\0\0'
    assert struct.unpack_from('<H',data,offset+4)[0]==0x8664
    optional=offset+24
    assert struct.unpack_from('<H',data,optional)[0]==0x20b
    assert struct.unpack_from('<H',data,optional+68)[0]==10
    return offset,optional
kernel=a.kernel.read_bytes();pe(kernel)
assert kernel[0x202:0x206]==b'HdrS','Requires a Linux x86 EFI-stub bzImage'
(out/'kernel.efi').write_bytes(kernel)
run('gcc','-static','-Os','-s','-o',str(out/'init'),str(ROOT/'tests/linux/init.c'))
# Deterministic newc archive; char device metadata needs no privileged mknod.
archive=bytearray()
def add(name,mode,data=b'',major=0,minor=0):
    fields=[1,mode,0,0,1,0,len(data),0,0,major,minor,len(name.encode())+1,0]
    archive.extend(b'070701'+b''.join(f'{x:08x}'.encode() for x in fields))
    archive.extend(name.encode()+b'\0');archive.extend(b'\0'*(-len(archive)%4))
    archive.extend(data);archive.extend(b'\0'*(-len(archive)%4))
for name in ('dev','proc'):add(name,stat.S_IFDIR|0o755)
add('dev/console',stat.S_IFCHR|0o600,major=5,minor=1)
add('init',stat.S_IFREG|0o755,(out/'init').read_bytes())
add('TRAILER!!!',0)
archive.extend(b'\0'*(-len(archive)%512));(out/'initrd.cpio').write_bytes(archive)
common='console=ttyS0,115200 rdinit=/init panic=-1 eutherboot_probe=owner-controlled'
(out/'stub-cmdline.txt').write_text(common+' eutherboot_mode=stub')
(out/'uki-cmdline.txt').write_text(common+' eutherboot_mode=uki')
(out/'os-release').write_text('ID=eutherboot-test\nNAME="EutherBoot disposable Linux probe"\n')
# Follow PE section alignment and actual ImageBase (not hard-coded low addresses).
stub=a.stub.read_bytes();offset,optional=pe(stub)
count=struct.unpack_from('<H',stub,offset+6)[0]
optional_size=struct.unpack_from('<H',stub,offset+20)[0]
base=struct.unpack_from('<Q',stub,optional+24)[0]
alignment=struct.unpack_from('<I',stub,optional+32)[0]
end=struct.unpack_from('<I',stub,optional+56)[0]
for i in range(count):
    section=optional+optional_size+i*40
    virtual_size,rva,raw_size=struct.unpack_from('<III',stub,section+8)
    end=max(end,rva+max(virtual_size,raw_size))
command=['objcopy']
for name,source in [('.linux',out/'kernel.efi'),('.osrel',out/'os-release'),('.cmdline',out/'uki-cmdline.txt'),('.initrd',out/'initrd.cpio')]:
    end=(end+alignment-1)//alignment*alignment
    command+=['--add-section',f'{name}={source}','--change-section-vma',f'{name}={base+end}',
              '--set-section-flags',f'{name}=contents,alloc,load,readonly,data']
    end+=source.stat().st_size
run(*command,str(a.stub),str(out/'test.efi'))
pe((out/'test.efi').read_bytes())
manifest={'kernel_source':str(a.kernel.resolve()),'kernel_sha256':sha(a.kernel),'stub_source':str(a.stub.resolve()),'stub_sha256':sha(a.stub),
          'kernel_description':run('file','-b',str(a.kernel)).stdout.decode().strip(),
          'compiler':run('gcc','--version').stdout.decode().splitlines()[0],
          'objcopy':run('objcopy','--version').stdout.decode().splitlines()[0],
          'artifacts':{name:sha(out/name) for name in ('kernel.efi','initrd.cpio','test.efi','stub-cmdline.txt','uki-cmdline.txt')}}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(f'Built EFI-stub and unsigned UKI fixtures under {out}; no host initramfs or boot files changed.')
