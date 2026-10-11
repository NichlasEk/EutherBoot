#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Create and test a regular-file direct-Arch USB probe. Never opens host disks."""
import argparse,hashlib,json,os,shutil,struct,subprocess,tempfile,time,uuid
from pathlib import Path
from PIL import Image
from qemu_test import VM
import virtual_disk
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--tessdata-dir',type=Path,help='Optional local English Tesseract data')
p.add_argument('--cmdline-file',type=Path,required=True)
p.add_argument('--target-guid',required=True,help='Existing GRUB ESP PARTUUID')
p.add_argument('--device-bytes',type=int,required=True)
p.add_argument('--kernel',type=Path,default=Path('/boot/vmlinuz-linux'))
p.add_argument('--initrd',type=Path,default=Path('/boot/initramfs-linux.img'))
p.add_argument('--fallback-initrd',type=Path,default=Path('/boot/initramfs-linux-fallback.img'))
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
ocr_options=['--tessdata-dir',str(a.tessdata_dir)] if a.tessdata_dir else []
assert 'eng' in subprocess.check_output(['tesseract',*ocr_options,'--list-langs'],text=True).splitlines(), 'English Tesseract data required'
assert str(uuid.UUID(a.target_guid))==a.target_guid and uuid.UUID(a.target_guid).int
assert a.device_bytes>1100*1024**2 and a.device_bytes%512==0
stub=Path('/usr/lib/systemd/boot/efi/linuxx64.efi.stub')
for f in [a.kernel,a.initrd,a.fallback_initrd,stub,a.cmdline_file]:assert f.is_file()
cmdline=a.cmdline_file.read_text().strip()
assert '\n' not in cmdline and '\0' not in cmdline and 'root=' in cmdline
assert 'eutherboot_probe=' not in cmdline

def run(*args):return subprocess.run([str(x) for x in args],check=True,capture_output=True)
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def build_uki(initrd,destination,variant):
    work=out/variant;work.mkdir()
    command_line=cmdline+' loglevel=7 eutherboot_probe=usb-direct-'+variant+'-v1'
    (work/'cmdline').write_text(command_line+'\0')
    shutil.copy2('/etc/os-release',work/'os-release')
    data=stub.read_bytes();off=struct.unpack_from('<I',data,0x3c)[0];opt=off+24
    assert data[:2]==b'MZ' and data[off:off+4]==b'PE\0\0'
    assert struct.unpack_from('<H',data,off+4)[0]==0x8664
    assert struct.unpack_from('<H',data,opt)[0]==0x20b
    assert struct.unpack_from('<H',data,opt+68)[0]==10
    count=struct.unpack_from('<H',data,off+6)[0];optsize=struct.unpack_from('<H',data,off+20)[0]
    base=struct.unpack_from('<Q',data,opt+24)[0];alignment=struct.unpack_from('<I',data,opt+32)[0]
    end=struct.unpack_from('<I',data,opt+56)[0]
    for i in range(count):
        size,rva,raw=struct.unpack_from('<III',data,opt+optsize+i*40+8);end=max(end,rva+max(size,raw))
    sections=[('.linux',a.kernel),('.osrel',work/'os-release'),('.cmdline',work/'cmdline'),('.initrd',initrd)]
    command=['objcopy']
    for name,source in sections:
        end=(end+alignment-1)//alignment*alignment
        command+=['--add-section',f'{name}={source}','--change-section-vma',f'{name}={base+end}','--set-section-flags',f'{name}=contents,alloc,load,readonly,data']
        end+=source.stat().st_size
    run(*command,stub,destination)
    # Verify embedded bytes, not merely the existence of PE section headers.
    for name,source in sections:
        extracted=work/(name[1:]+'.extracted')
        run('objcopy','--dump-section',f'{name}={extracted}',destination,work/'inspect.efi')
        assert sha(extracted)==sha(source),name
        extracted.unlink();(work/'inspect.efi').unlink()
    return {'sha256':sha(destination),'initrd_sha256':sha(initrd),'cmdline':command_line}

def menu(v,name):
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        v.screen(name)
        with Image.open(v.base/(name+'.ppm')) as im:
            colors={rgb:n for n,rgb in im.getcolors(im.width*im.height)}
            if colors.get((9,15,24),0)>im.width*im.height//2 and colors.get((208,184,125),0)>500:
                im.save(v.base/(name+'.png'));return
        assert v.proc.poll() is None
        time.sleep(.2)
    raise AssertionError('Release menu not observed')

source=out/'files';(source/'EFI/BOOT').mkdir(parents=True);(source/'EFI/EutherBoot').mkdir();(source/'EFI/Linux').mkdir()
release=ROOT/'artifacts/release';manifest=json.loads((release/'manifest.json').read_text());assert not manifest['qemu_debug']
for name in ['EutherBoot.efi','eutherboot-source.tar.gz']:assert sha(release/name)==manifest['files'][name]
shutil.copy2(release/'EutherBoot.efi',source/'EFI/BOOT/BOOTX64.EFI')
shutil.copy2(release/'eutherboot-source.tar.gz',source/'EFI/EutherBoot/source.tar.gz')
shutil.copy2(ROOT/'LICENSE',source/'EFI/EutherBoot/LICENSE')
ukis={}
for name,initrd in [('normal',a.initrd),('fallback',a.fallback_initrd)]:
    ukis[name]=build_uki(initrd,source/f'EFI/Linux/arch-{name}.efi',name)
config="[boot]\ndefault='arch'\ntimeout=0\ntheme='system-regis'\nlanguage='sv'\n\n"
for ident,label,path,guid in [('arch','Arch Linux direkt',r'\EFI\Linux\arch-normal.efi',None),('fallback','Arch Linux reserv',r'\EFI\Linux\arch-fallback.efi',None),('grub','Befintlig GRUB',r'\EFI\BOOT\BOOTX64.EFI',a.target_guid)]:
    config+=f"[[entry]]\nid='{ident}'\nname='{label}'\ntype='efi'\npath='{path}'\n"
    if guid:config+=f"partition_guid='{guid}'\n"
    config+='\n'
(source/'EFI/EutherBoot/eutherboot.toml').write_text(config)
run(release/'config-check',source/'EFI/EutherBoot/eutherboot.toml')
(out/'layout').mkdir();disk=virtual_disk.create(source,out/'layout',esp_mib=1024)
prefix_bytes=disk.stat().st_size
with disk.open('r+b') as f:f.truncate(a.device_bytes)
run('sgdisk','-e',disk);run('sgdisk','-v',disk)
image=out/'usb.img';disk.rename(image)
# Only the partitioned prefix and relocated backup GPT need writing to physical media.
ranges=[{'offset':0,'bytes':prefix_bytes},{'offset':a.device_bytes-32768,'bytes':32768}]
with image.open('rb') as f:
    for r in ranges:
        f.seek(r['offset']);h=hashlib.sha256();left=r['bytes']
        while left:
            b=f.read(min(left,4*1024**2));assert b;h.update(b);left-=len(b)
        r['sha256']=h.hexdigest()
with tempfile.TemporaryDirectory(prefix='direct-probe-test-') as d:
    tmp=Path(d)
    for index,variant in enumerate(['normal','fallback'],1):
        with VM(tmp,image,out,iteration=index,memory=4096,cpu='host',accel='kvm',readonly=True,ready_marker=None) as v:
            menu(v,'menu')
            if variant=='fallback':v.key('down')
            v.key('ret');deadline=time.monotonic()+120
            while time.monotonic()<deadline:
                log=(v.base/'serial.log').read_text(errors='replace')
                if f'eutherboot_probe=usb-direct-{variant}-v1' in log:
                    v.screen('actual-initramfs')
                    with Image.open(v.base/'actual-initramfs.ppm') as frame:frame.save(v.base/'actual-initramfs.png')
                    text=run('tesseract',v.base/'actual-initramfs.png','stdout','--psm','6',*ocr_options).stdout.decode(errors='replace')
                    (v.base/'initramfs-ocr.txt').write_text(text)
                    if 'emergency shell' in text.lower() and ('not found' in text.lower() or 'failed to mount' in text.lower()):break
                assert v.proc.poll() is None,'Kernel exited before initramfs'
                time.sleep(2)
            else:raise AssertionError('Actual UKI did not reach initramfs: '+log[-2000:])
            v.screen('actual-initramfs')
            assert not v.log.read_text(),'Manager must be a release build'
        print(f'PASS actual {variant} UKI reaches initramfs; host root deliberately absent',flush=True)
    target=tmp/'target';(target/'EFI/BOOT').mkdir(parents=True)
    shutil.copy2(ROOT/'artifacts/TestChild.efi',target/'EFI/BOOT/BOOTX64.EFI')
    (tmp/'target-disk').mkdir();td=virtual_disk.create(target,tmp/'target-disk')
    run('sgdisk','-u',f'1:{a.target_guid}',td);before=sha(td)
    with VM(tmp,image,out,iteration=3,memory=512,readonly=True,ready_marker=None,extra_disks=((td,'raw'),)) as v:
        menu(v,'menu');v.key('down');v.key('down');v.key('ret','CHILD_READY');v.key('ret','CHILD_RETURN');menu(v,'returned-menu')
    assert sha(td)==before
result={'image':str(image),'device_bytes':a.device_bytes,'write_ranges':ranges,'efi_sha256':sha(source/'EFI/BOOT/BOOTX64.EFI'),'source_commit':manifest['git_commit'],'source_dirty':manifest['dirty'],'source_archive_sha256':sha(source/'EFI/EutherBoot/source.tar.gz'),'kernel_sha256':sha(a.kernel),'stub_sha256':sha(stub),'ukis':ukis,'config_sha256':sha(source/'EFI/EutherBoot/eutherboot.toml'),'actual_normal_and_fallback_initramfs_reached':True,'grub_entry_test':'Disposable EFI child reached and returned, not actual GRUB','host_disks_attached':False,'physical_boot_verified':False,'autoboot_seconds':0}
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS direct probe image and three boot-menu routes; physical host root boot remains untested',flush=True)
