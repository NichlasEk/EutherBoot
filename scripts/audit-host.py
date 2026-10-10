#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Read-only Arch compatibility inventory. Does not source presets or mount disks."""
import json
from pathlib import Path
import re
import shutil
import subprocess

def read(path):
    try:return Path(path).read_text().strip()
    except OSError:return None

def output(*args):
    p=subprocess.run(args,capture_output=True,text=True)
    return p.stdout.strip() if p.returncode==0 else None

def mount(path):
    value=output('findmnt','-J','-T',path,'-o','TARGET,FSTYPE,FSROOT')
    return json.loads(value)['filesystems'][0] if value else None

root_device=output('findmnt','-n','--nofsroot','-o','SOURCE','/')
root_types=output('lsblk','-sn','-o','TYPE',root_device) if root_device else None
packages={p:output('pacman','-Q',p) for p in ('linux','linux-lts','mkinitcpio','systemd','systemd-ukify','grub','nvidia-open','nvidia-open-lts','nvidia-dkms','nvidia-open-dkms')}
mounts={p:mount(p) for p in ('/','/boot','/usr/lib/modules','/var/lib')}
payloads={str(p):p.stat().st_size for pattern in ('vmlinuz-*','initramfs-*.img') for p in Path('/boot').glob(pattern) if p.is_file()}
secure=Path('/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c')
try:secure_boot=bool(secure.read_bytes()[4])
except (OSError,IndexError):secure_boot=None
config=read('/etc/mkinitcpio.conf') or ''
settings={m.group(1):m.group(2) for m in re.finditer(r'^(HOOKS|MODULES|BINARIES)=(.*)$',config,re.M)}
free=shutil.disk_usage('/boot').free
sizes=[payloads[f'/boot/vmlinuz-{p}']+payloads[f'/boot/initramfs-{p}.img']+8*1024**2 for p in ('linux','linux-lts') if f'/boot/vmlinuz-{p}' in payloads and f'/boot/initramfs-{p}.img' in payloads]
minimum=3*sum(sizes)+max(sizes,default=0)+384*1024**2
blockers=[]
if root_types and 'crypt' in root_types.split():blockers.append('Encrypted root requires a separately validated initramfs configuration')
for p in ('linux','linux-lts','systemd-ukify'):
    if packages[p] is None:blockers.append(f'Missing prerequisite: {p}')
missing_payloads=[p for p in ('linux','linux-lts') if f'/boot/vmlinuz-{p}' not in payloads or f'/boot/initramfs-{p}.img' not in payloads]
for p in missing_payloads:blockers.append(f'Missing boot payload: {p}')
if free<minimum:blockers.append('ESP free space below initial retained-generation budget (even before missing kernel payloads)')
for p in ('/usr/lib/modules','/var/lib'):
    if not mounts[p] or mounts[p]['target']!='/':blockers.append(f'{p} is not on the root mount')
if not mounts['/boot'] or mounts['/boot']['target']!='/boot' or mounts['/boot']['fstype']!='vfat':
    blockers.append('This inventory did not identify an exact FAT ESP mount at /boot')
loader_status=output('bootctl','status','--no-pager') or ''
loader_match=re.search(r'Product:\s+([^\r\n]+)',loader_status)
report={'read_only':True,'scope':'compatibility inventory, not installation approval',
        'firmware':{p:read('/sys/class/dmi/id/'+p) for p in ('board_vendor','board_name','bios_version')},
        'uefi':Path('/sys/firmware/efi').exists(),'secure_boot':secure_boot,
        'bootloader_product':loader_match.group(1).strip() if loader_match else None,
        'nvidia_lts_modules_need_validation':'nvidia' in settings.get('MODULES',''),
        'root_block_types':root_types.split() if root_types else None,
        'running_kernel':output('uname','-r'),'packages':packages,'mounts':mounts,
        'mkinitcpio':settings,'boot_payload_bytes':payloads,'boot_free_bytes':free,
        'minimum_initial_esp_bytes_for_present_payloads':minimum,'missing_payloads_make_estimate_incomplete':bool(missing_payloads),
        'external_initrd_over_128_mib':[name for name,size in payloads.items() if name.endswith('.img') and size>128*1024**2],
        'blockers':blockers,'unverified':['Physical firmware and keyboard/graphics','NVIDIA modules and physical GPU','Real Secure Boot enrollment/trust']}
print(json.dumps(report,indent=2))
