"""Create a GPT/FAT disk solely inside a caller-owned temporary directory."""
from pathlib import Path
import os
import shutil
import subprocess


def create(source: Path, temporary: Path, esp_mib: int = 64) -> Path:
    if not 64 <= esp_mib <= 1024: raise ValueError('ESP size outside fixture bounds')
    disk = temporary/'disk.img'
    fat = temporary/'fat.img'
    # Exclusive creation prevents accidentally reusing an existing file/device.
    with disk.open('xb') as f:
        f.truncate((esp_mib+64)*1024*1024)
    with fat.open('xb') as f:
        f.truncate(esp_mib*1024*1024)
    for cmd in [
        ['sgdisk','-n',f'1:2048:{2048+esp_mib*2048-1}','-t','1:ef00',str(disk)],
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


def create_layout(partitions, temporary: Path) -> Path:
    """Several (source directory, GPT type, unique GUID) FAT partitions.

    Like create(), every output is exclusively created under a temporary directory.
    There is deliberately no physical-device output argument.
    """
    disk = temporary/'disk.img'
    with disk.open('xb') as f:
        f.truncate(128*1024*1024*len(partitions))
    command = ['sgdisk']
    for i, (_, kind, guid) in enumerate(partitions, 1):
        start = 2048 + (i-1)*131072
        command += ['-n', f'{i}:{start}:{start+131071}', '-t', f'{i}:{kind}', '-u', f'{i}:{guid}']
    subprocess.run([*command, str(disk)], check=True, capture_output=True)
    for i, (source, _, _) in enumerate(partitions):
        fat = temporary/f'fat-{i}.img'
        with fat.open('xb') as f:
            f.truncate(64*1024*1024)
        subprocess.run(['mkfs.fat','-F','32',str(fat)], check=True, capture_output=True)
        subprocess.run(['mcopy','-s','-i',str(fat),str(source/'EFI'),'::/'], check=True, capture_output=True)
        with disk.open('r+b') as d, fat.open('rb') as f:
            d.seek(1048576 + i*64*1024*1024)
            shutil.copyfileobj(f, d)
            d.flush()
            os.fsync(d.fileno())
    return disk
