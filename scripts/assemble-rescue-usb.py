#!/usr/bin/env python3
"""Assemble a USB image in a regular file; never opens physical devices."""
import argparse,json,re,subprocess,tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('iso',type=Path);p.add_argument('output',type=Path);p.add_argument('--bytes',type=int,required=True);a=p.parse_args()
assert a.iso.is_file() and not a.output.exists()
assert a.bytes%512==0 and a.bytes>a.iso.stat().st_size+1024**3
subprocess.run(['cp','--reflink=auto',str(a.iso),str(a.output)],check=True)
with a.output.open('r+b') as f:f.truncate(a.bytes)
subprocess.run(['sgdisk','-e',str(a.output)],check=True)
# Archiso uses GPT partitions 1 (ISO) and 2 (ESP). Check before adding 3.
info=subprocess.check_output(['sfdisk','--json',str(a.output)],text=True)
table=json.loads(info)['partitiontable'];assert table['label']=='gpt'
parts=table['partitions'];assert len(parts)==2
# Hybrid ISO UUIDs are shared by the entire USB and partition 1. Selecting the
# whole disk can prevent mounting its ext4 partition. Bind this USB's loader
# entry to its exact ISO PARTUUID; no discovery/mount of internal disks needed.
iso_part,esp=parts
assert iso_part['name']=='ISO9660' and esp['type'].lower()=='c12a7328-f81f-11d2-ba4b-00a0c93ec93b'
fat=str(a.output)+'@@'+str(esp['start']*512)
entry='::/loader/entries/01-archiso-linux.conf'
original=subprocess.check_output(['mtype','-i',fat,entry],text=True)
iso_device='/dev/disk/by-partuuid/'+iso_part['uuid'].lower()
updated,count=re.subn(r'archisosearchuuid=\S+', 'archisodevice='+iso_device, original)
assert count==1 and 'archisosearchfilename=' not in updated
with tempfile.TemporaryDirectory(prefix='euther-usb-entry-') as directory:
    config=Path(directory)/'entry.conf';config.write_text(updated)
    subprocess.run(['mcopy','-o','-i',fat,str(config),entry],check=True)
assert subprocess.check_output(['mtype','-i',fat,entry],text=True)==updated
start=((max(x['start']+x['size'] for x in parts)+2047)//2048)*2048
end=((a.bytes//512-34)//2048)*2048-1
assert end-start>1024*1024*2
subprocess.run(['sgdisk',f'-n3:{start}:{end}','-t3:8300','-c3:Euther Rescue Data',str(a.output)],check=True)
subprocess.run(['mkfs.ext4','-F','-q','-L','EUTHERDATA','-b','4096','-m','0','-E',f'offset={start*512},lazy_itable_init=0,lazy_journal_init=0,nodiscard',str(a.output),str((end-start+1)//8)],check=True)
subprocess.run(['sgdisk','-v',str(a.output)],check=True)
Path(str(a.output)+'.json').write_text(json.dumps({'bytes':a.bytes,'iso_bytes':a.iso.stat().st_size,'iso_device':iso_device,'data_start_sector':start,'data_sectors':end-start+1,'sector_bytes':512},indent=2)+'\n')
