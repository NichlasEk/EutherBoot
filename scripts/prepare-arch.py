#!/usr/bin/env python3
"""Verify official Arch basic image and extract its own kernel/initramfs read-only."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import uuid

ROOT=Path(__file__).resolve().parent.parent
VERSION='20261001.604814'
NAME=f'Arch-Linux-x86_64-basic-{VERSION}.qcow2'
URL=f'https://geo.mirror.pkgbuild.com/images/v{VERSION}/{NAME}'
FINGERPRINT='1B9A16984A4E8CB448712D2AE0B78BF4326C6F8F'
out=ROOT/'artifacts/arch';out.mkdir(parents=True,exist_ok=True)
cache=ROOT/'artifacts/arch-download';cache.mkdir(exist_ok=True)

def run(*args):
    result=subprocess.run([str(x) for x in args],capture_output=True,timeout=180)
    if result.returncode:
        raise RuntimeError(f'{args[0]} failed: {result.stderr.decode(errors="replace")}')
    return result
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def download(url,dest):
    if dest.is_file():return
    partial=dest.with_suffix(dest.suffix+'.part')
    subprocess.run(['curl','-fL','--retry','3',url,'-o',str(partial)],check=True)
    partial.replace(dest)

image=cache/NAME
download(URL,image);download(URL+'.sig',cache/'image.sig');download(URL+'.SHA256',cache/'image.SHA256')
expected=(cache/'image.SHA256').read_text().split()[0]
assert sha(image)==expected,'Arch image checksum mismatch (remove incomplete cache file to retry)'
with tempfile.TemporaryDirectory(prefix='eutherboot-arch-key-') as directory:
    run('gpg','--homedir',directory,'--batch','--import',ROOT/'tests/arch/arch-boxes.asc')
    verification=run('gpg','--homedir',directory,'--batch','--status-fd','1','--verify',cache/'image.sig',image)
    valid=[line.split() for line in verification.stdout.decode().splitlines() if line.startswith('[GNUPG:] VALIDSIG ')]
    assert len(valid)==1 and (valid[0][2]==FINGERPRINT or valid[0][-1]==FINGERPRINT),'Unexpected Arch signing key'
    (out/'signature.txt').write_bytes(verification.stdout+verification.stderr)
info=json.loads(run('qemu-img','info','--output=json',image).stdout)
assert info['format']=='qcow2' and not info.get('backing-filename') and info['virtual-size']<=64*1024**3
# Reuse only a fully provenance-checked preparation; source changes force a new directory.
manifest=out/'manifest.json'
if manifest.exists():
    previous=json.loads(manifest.read_text())
    assert previous['image_sha256']==expected
    for name,digest in previous['artifacts'].items():assert sha(out/name)==digest,f'Stale {name}'
    previous['image']=str(image)
    manifest.write_text(json.dumps(previous,indent=2)+'\n')
    print('Verified cached Arch fixtures and signature');raise SystemExit
with tempfile.TemporaryDirectory(prefix='extract-',dir=out) as directory:
    work=Path(directory)
    raw=work/'source.raw'
    run('qemu-img','convert','-f','qcow2','-O','raw',image,raw)
    with raw.open('rb') as f:
        f.seek(512);header=f.read(512);assert header[:8]==b'EFI PART'
        location,count,size=struct.unpack_from('<QII',header,72)
        assert count<=128 and 128<=size<=512
        f.seek(location*512);entries=f.read(count*size)
    parts=[]
    for i in range(count):
        e=entries[i*size:(i+1)*size]
        if e[:16]==bytes(16):continue
        first,last=struct.unpack_from('<QQ',e,32)
        assert 0<first<=last and (last+1)*512<=raw.stat().st_size
        parts.append({'number':i+1,'type':str(uuid.UUID(bytes_le=e[:16])),'guid':str(uuid.UUID(bytes_le=e[16:32])),
                      'offset':first*512,'size':(last-first+1)*512})
    root=next(p for p in parts if p['type']=='4f68bce3-e8cd-4db1-96e7-fbcaf984b709')
    esp=next(p for p in parts if p['type']=='c12a7328-f81f-11d2-ba4b-00a0c93ec93b')
    # Sparse copy of the root partition into a regular file, no loop/NBD mounts or sudo.
    partition=work/'root.btrfs'
    with raw.open('rb') as source,partition.open('xb') as target:
        start=root['offset'];end=start+root['size'];target.truncate(root['size']);position=start
        while position<end:
            try:data=os.lseek(source.fileno(),position,os.SEEK_DATA)
            except OSError as e:
                if e.errno==6:break
                raise
            if data>=end:break
            hole=min(os.lseek(source.fileno(),data,os.SEEK_HOLE),end)
            source.seek(data);target.seek(data-start)
            while data<hole:
                n=os.copy_file_range(source.fileno(),target.fileno(),min(8*1024*1024,hole-data))
                assert n>0;data+=n
            position=hole
    extracted=work/'extracted';extracted.mkdir(exist_ok=True)
    run('btrfs','restore','--path-regex',r'^/(|boot(|/vmlinuz-linux|/initramfs-linux.img))$',partition,extracted)
    assert (extracted/'boot/vmlinuz-linux').is_file() and (extracted/'boot/initramfs-linux.img').is_file()
    # Keep only required guest boot payloads and provenance; discard bulky extraction inputs.
    for source,name in [('boot/vmlinuz-linux','kernel.efi'),('boot/initramfs-linux.img','initrd.img')]:
        (out/name).write_bytes((extracted/source).read_bytes())
    manifest.write_text(json.dumps({'version':VERSION,'url':URL,'image':str(image),'image_sha256':expected,
        'signer':FINGERPRINT,'partitions':parts,'root':root,'esp':esp,
        'artifacts':{name:sha(out/name) for name in ('kernel.efi','initrd.img')}},indent=2)+'\n')
print(f'Verified/extracted Arch {VERSION}; original QCOW2 unchanged, no host mounts or boot writes')
