#!/usr/bin/env python3
"""Read-only snapshot of the user-confirmed boot path; output stays ignored/local."""
from pathlib import Path
import argparse,datetime,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--usb-mount',type=Path,required=True);a=p.parse_args()
out=ROOT/'artifacts/rescue/known-good'
if out.exists():raise SystemExit('Existing known-good snapshot will not be overwritten')
usb=a.usb_mount.resolve()
mount=json.loads(subprocess.check_output(['findmnt','-J','-M',str(usb)],text=True))['filesystems'][0]
assert mount['fstype']=='vfat' and 'ro' in mount['options'].split(',')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
delivery=json.loads((ROOT/'artifacts/host-probe-0.1.1/usb-delivery.json').read_text())
for name,digest in delivery['files'].items():assert sha(usb/name)==digest,f'Delivered file mismatch: {name}'
before=json.loads((ROOT/'artifacts/initramfs-size/before-sha256.json').read_text())
current={str(f):sha(f) for f in Path('/boot').rglob('*') if f.is_file()}
assert current==before,'Internal boot files changed since successful boot inventory; investigate before marking known-good'
out.mkdir(parents=True)
shutil.copytree(usb/'EFI',out/'usb/EFI')
shutil.copytree('/boot',out/'internal-esp')
(out/'host-config').mkdir()
for name in ['/etc/fstab','/etc/default/grub','/etc/mkinitcpio.conf']:
 shutil.copy2(name,out/'host-config'/Path(name).name)
for name in ['/etc/grub.d','/etc/mkinitcpio.d']:
 shutil.copytree(name,out/'host-config'/Path(name).name)
for name,cmd in {
 'block-devices.json':['lsblk','-J','-o','NAME,SIZE,MODEL,FSTYPE,LABEL,UUID,PARTUUID,MOUNTPOINTS'],
 'mounts.json':['findmnt','-J'],
 'firmware-boot.txt':['efibootmgr','-v'],
 'kernel.txt':['uname','-r'],
 'kernel-packages.txt':['pacman','-Q','linux','grub'],
}.items():
 r=subprocess.run(cmd,capture_output=True,text=True)
 (out/name).write_text(r.stdout if r.returncode==0 else f'Unavailable (exit {r.returncode}): {r.stderr}')
files={str(f.relative_to(out)):sha(f) for f in sorted(out.rglob('*')) if f.is_file()}
# Confirm the copied bytes against the sources, not only against their own hashes.
for name,digest in current.items():assert sha(out/'internal-esp'/Path(name).relative_to('/boot'))==digest
for name,digest in delivery['files'].items():assert sha(out/'usb'/name)==digest
metadata={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'evidence':'User confirmed physical EutherBoot 0.1.1 -> GRUB -> Arch; USB hashes match delivered release, all current /boot files match post-boot baseline.','eutherboot_commit':delivery['commit'],'files':files,'private_machine_metadata':True,'physical_restore_tested':False,'root_data_backup':False}
(out/'manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
(out/'SHA256SUMS').write_text(''.join(f'{digest}  {name}\n' for name,digest in files.items()))
print(f'Snapshotted {len(files)} files; verified delivered USB and internal /boot baseline. No source writes.')
