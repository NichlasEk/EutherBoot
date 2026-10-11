#!/usr/bin/env python3
"""Assemble a USB image in a regular file; never opens physical devices."""
import argparse,json,subprocess
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
start=((max(x['start']+x['size'] for x in parts)+2047)//2048)*2048
end=((a.bytes//512-34)//2048)*2048-1
assert end-start>1024*1024*2
subprocess.run(['sgdisk',f'-n3:{start}:{end}','-t3:8300','-c3:Euther Rescue Data',str(a.output)],check=True)
subprocess.run(['mkfs.ext4','-F','-q','-L','EUTHERDATA','-b','4096','-m','0','-E',f'offset={start*512},lazy_itable_init=0,lazy_journal_init=0,nodiscard',str(a.output),str((end-start+1)//8)],check=True)
subprocess.run(['sgdisk','-v',str(a.output)],check=True)
Path(str(a.output)+'.json').write_text(json.dumps({'bytes':a.bytes,'iso_bytes':a.iso.stat().st_size,'data_start_sector':start,'data_sectors':end-start+1,'sector_bytes':512},indent=2)+'\n')
