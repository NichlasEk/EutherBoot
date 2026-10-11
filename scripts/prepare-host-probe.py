#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Build and test a USB-image FILE; never flash media or attach host disks."""
import argparse,hashlib,json,os,shutil,subprocess,tempfile,time,uuid
from pathlib import Path
from PIL import Image
from qemu_test import VM
import virtual_disk
ROOT=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=ROOT/'artifacts/host-probe')
parser.add_argument('--target-guid',required=True,help='Existing loader ESP PARTUUID; embedded in local image only')
parser.add_argument('--target-path',default=r'\EFI\BOOT\BOOTX64.EFI')
args=parser.parse_args()
assert str(uuid.UUID(args.target_guid))==args.target_guid and uuid.UUID(args.target_guid).int
OUT=args.output.resolve();OUT.mkdir(parents=True,exist_ok=True)
(OUT/'usb-result.json').unlink(missing_ok=True)
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(*args):subprocess.run([str(a) for a in args],check=True,capture_output=True)
def menu(v,name):
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        v.screen(name)
        with Image.open(v.base/f'{name}.ppm') as frame:
            colors={rgb:n for n,rgb in frame.getcolors(frame.width*frame.height)}
            if colors.get((8,21,35),0)>frame.width*frame.height//2 and colors.get((184,161,105),0)>1500 and colors.get((218,225,229),0)>1000:
                frame.save(v.base/f'{name}.png');return
        if v.proc.poll() is not None:raise RuntimeError('VM exited before menu')
        time.sleep(.2)
    raise AssertionError('System Regis framebuffer not observed')
with tempfile.TemporaryDirectory(prefix='eutherboot-probe-') as directory:
    tmp=Path(directory);source=tmp/'source'
    (source/'EFI/BOOT').mkdir(parents=True);(source/'EFI/EutherBoot').mkdir()
    shutil.copy2(ROOT/'artifacts/release/EutherBoot.efi',source/'EFI/BOOT/BOOTX64.EFI')
    config=source/'EFI/EutherBoot/eutherboot.toml'
    config.write_text("[boot]\ndefault='existing'\ntimeout=0\ntheme='system-regis'\n\n[[entry]]\nid='existing'\nname='Existing boot loader'\ntype='efi'\npath='"+args.target_path+"'\npartition_guid='"+args.target_guid+"'\n")
    run(ROOT/'artifacts/release/config-check',config)
    shutil.copy2(ROOT/'LICENSE',source/'EFI/EutherBoot/LICENSE')
    shutil.copy2(ROOT/'artifacts/release/eutherboot-source.tar.gz',source/'EFI/EutherBoot/source.tar.gz')
    (tmp/'usb').mkdir();disk=virtual_disk.create(source,tmp/'usb',esp_mib=64)
    # A disposable EFI child stands in for the real GRUB target. No host disk is attached.
    target=tmp/'target';target_file=target/args.target_path.lstrip('\\').replace('\\','/')
    target_file.parent.mkdir(parents=True);shutil.copy2(ROOT/'artifacts/TestChild.efi',target_file)
    (tmp/'target-disk').mkdir();target_disk=virtual_disk.create(target,tmp/'target-disk',esp_mib=64)
    run('sgdisk','-u',f'1:{args.target_guid}',target_disk)
    usb_hash=sha(disk);target_hash=sha(target_disk)
    with VM(tmp,disk,OUT,memory=512,readonly=True,extra_disks=((target_disk,'raw'),),ready_marker=None) as v:
        menu(v,'usb-menu')
        assert not v.log.read_text(), 'Release manager must have no debug-port trace'
        v.key('ret','CHILD_READY');v.screen('selected-target')
        v.key('ret','CHILD_RETURN');menu(v,'returned-menu')
    assert sha(disk)==usb_hash and sha(target_disk)==target_hash
    staging=OUT/'usb.img.new'
    with staging.open('xb') as dest,disk.open('rb') as src:
        shutil.copyfileobj(src,dest);dest.flush();os.fsync(dest.fileno())
    os.replace(staging,OUT/'usb.img')
    shutil.copy2(config,OUT/'usb-eutherboot.toml')
(OUT/'usb-result.json').write_text(json.dumps({'image':'usb.img','sha256':usb_hash,'efi_sha256':sha(ROOT/'artifacts/release/EutherBoot.efi'),
    'source_archive_sha256':sha(ROOT/'artifacts/release/eutherboot-source.tar.gz'),'target_guid':args.target_guid,
    'target_path':args.target_path,'automatic_boot':False,'release_framebuffer':True,'explicit_target_chainload_and_return':True,
    'target_in_test':'disposable EFI child, not physical GRUB','host_disks_attached':False,'physical_media_written':False},indent=2)+'\n')
print('PASS: release USB image, graphical menu, explicit cross-ESP target and return; no physical writes')
