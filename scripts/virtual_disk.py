"""Create a GPT/FAT disk solely inside a caller-owned temporary directory."""
from pathlib import Path
import os
import shutil
import subprocess


def create(source: Path, temporary: Path) -> Path:
    disk = temporary/'disk.img'
    fat = temporary/'fat.img'
    # Exclusive creation prevents accidentally reusing an existing file/device.
    with disk.open('xb') as f:
        f.truncate(128*1024*1024)
    with fat.open('xb') as f:
        f.truncate(64*1024*1024)
    for cmd in [
        ['sgdisk','-n','1:2048:133119','-t','1:ef00',str(disk)],
        ['mkfs.fat','-F','32',str(fat)],
        ['mcopy','-s','-i',str(fat),str(source/'EFI'),'::/'],
    ]:
        subprocess.run(cmd,check=True,capture_output=True)
    with disk.open('r+b') as d, fat.open('rb') as f:
        d.seek(1048576)
        shutil.copyfileobj(f,d)
        d.flush()
        os.fsync(d.fileno())
    return disk
