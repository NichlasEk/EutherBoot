#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Unsigned Arch UKIs with optional LTS, external rescue. Explicit install; no NVRAM writes."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from eutherbootctl import atomic, digest, esp_check, image_check, run

CONFIG = Path('/etc/eutherboot/single.json')
STATE = Path('/var/lib/eutherboot-single')
PROGRAM = Path('/usr/local/lib/eutherboot-single')
MARGIN = 64 * 1024**2
DRIVER_TRIGGERS = '''[Trigger]
Type = Package
Operation = Install
Operation = Upgrade
Operation = Remove
Target = nvidia
Target = nvidia-open
Target = nvidia-lts
Target = nvidia-open-lts
Target = nvidia-dkms
Target = nvidia-open-dkms

'''

def kernel(package="linux"):
    paths = [Path(p) for p in run('pacman', '-Qql', package).splitlines()
             if p.startswith('/usr/lib/modules/') and p.endswith('/vmlinuz')]
    if len(paths) != 1 or not paths[0].is_file():
        raise RuntimeError('Cannot identify unique package-owned kernel')
    return paths[0]

def check(c, required=0):
    esp_check(Path(c['esp']), c['guid'], minimum_free=required + MARGIN)
    if shutil.disk_usage(STATE).free < max(required * 3, 512 * 1024**2):
        raise RuntimeError('Insufficient root staging space')

def validate(image, c, package="linux"):
    image_check(image)
    if run('bootctl', 'kernel-identify', image) != 'uki':
        raise RuntimeError('Not a UKI')
    k = kernel(package)
    with tempfile.TemporaryDirectory(dir=STATE) as tmp:
        tmp = Path(tmp)
        for section in ('linux', 'cmdline', 'uname', 'initrd'):
            run('objcopy', '--dump-section', f'.{section}={tmp / section}', image, tmp/'inspect.efi')
        if digest(tmp/'linux') != digest(k):
            raise RuntimeError('UKI kernel does not match installed linux package')
        if (tmp/'uname').read_bytes().rstrip(b'\0\n').decode() != k.parent.name:
            raise RuntimeError('UKI kernel version mismatch')
        # mkinitcpio joins input lines with a trailing space before newline/NUL.
        if (tmp/'cmdline').read_bytes().rstrip(b'\0\n ').decode() != c['cmdline']:
            raise RuntimeError('UKI command line mismatch')
        if (tmp/'initrd').stat().st_size < 1024:
            raise RuntimeError('Missing initramfs')

def publish(image, c, package="linux"):
    if image.is_symlink() or not image.is_file():
        raise RuntimeError('Missing regular staged UKI')
    check(c, image.stat().st_size)
    validate(image, c, package)
    target = target_path(c, package)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix='.eutherboot-', dir=target.parent, delete=False) as f:
        temporary = Path(f.name)
        try:
            with image.open('rb') as source:
                shutil.copyfileobj(source, f)
            f.flush(); os.fsync(f.fileno())
            if digest(temporary) != digest(image):
                raise RuntimeError('ESP copy hash mismatch')
            os.replace(temporary, target)
            fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(fd)
            finally: os.close(fd)
        finally:
            temporary.unlink(missing_ok=True)
    if digest(target) != digest(image):
        raise RuntimeError('Published UKI hash mismatch')
    atomic(STATE/('last-publish.json' if package == 'linux' else 'last-publish-lts.json'), (json.dumps({'kernel': kernel(package).parent.name,
        'sha256': digest(target), 'time': time.time()}, indent=2)+'\n').encode())
    print('EUTHERBOOT_SINGLE_PUBLISHED', kernel(package).parent.name, flush=True)

def packages(c):
    return ('linux', 'linux-lts') if c.get('lts') else ('linux',)

def target_path(c, package):
    name = 'arch-normal.efi' if package == 'linux' else 'arch-lts.efi'
    return Path(c['esp'])/'EFI/Linux'/name

def preset(package='linux'):
    return (f"ALL_kver='/boot/vmlinuz-{package}'\nPRESETS=('default')\n"
            f"default_uki='/var/lib/eutherboot-single/staging/{package}.efi'\n"
            "default_cmdline='/etc/eutherboot/single.cmdline'\n"
            "default_options='--no-ukify'\n")

def publish_all(c):
    # Validate all images before replacing either active image. Copy sequentially
    # to retain space for a full temporary image on a 1 GiB ESP.
    images = [(p, STATE/f'staging/{p}.efi') for p in packages(c)]
    for package, image in images:
        if image.is_symlink() or not image.is_file():
            raise RuntimeError('Missing regular staged UKI')
        validate(image, c, package)
    # Include growth of the first image when budgeting the second copy.
    free = shutil.disk_usage(c['esp']).free
    for package, image in images:
        size = image.stat().st_size
        if free < size + MARGIN:
            raise RuntimeError('Insufficient ESP space for all UKI publications')
        target = target_path(c, package)
        free += (target.stat().st_size if target.exists() else 0) - size
    for package, image in images:
        publish(image, c, package)

def add_lts(a):
    if os.geteuid(): raise RuntimeError('Adding LTS requires root')
    c = json.loads(CONFIG.read_text())
    if c.get('lts'): raise RuntimeError('LTS is already enabled')
    # Do not hide an existing custom preset or menu entry.
    lts_preset = Path('/etc/mkinitcpio.d/linux-lts.preset')
    if lts_preset.exists(): raise RuntimeError('Existing LTS preset requires review')
    menu_path = Path(c['esp'])/'EFI/EutherBoot/eutherboot.toml'
    import tomllib
    menu = menu_path.read_text()
    entries = tomllib.loads(menu).get('entry', [])
    if len(entries) != 1 or entries[0].get('path') != r'\EFI\Linux\arch-normal.efi':
        raise RuntimeError('Expected existing single Arch menu')
    expected = 'Exec = /usr/share/libalpm/scripts/mkinitcpio install'
    upstream = Path('/usr/share/libalpm/hooks/90-mkinitcpio-install.hook').read_text()
    if upstream.count(expected) != 1: raise RuntimeError('Unexpected upstream hook')
    # Allow two host-sized images plus the additional kernel source and margin.
    check(c, 2 * target_path(c, 'linux').stat().st_size + 32*1024**2)
    backup = STATE/'before-lts'
    backup.mkdir()
    for path in [CONFIG, menu_path, PROGRAM/'eutherboot-single.py',
                 *Path('/etc/pacman.d/hooks').glob('*eutherboot-single*'),
                 Path('/etc/pacman.d/hooks/90-mkinitcpio-install.hook')]:
        saved = backup/path.relative_to('/')
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, saved)
        if digest(path) != digest(saved): raise RuntimeError('LTS backup mismatch')
    # Install the new wrapper in single mode first. Package installation then
    # builds the LTS preset on root, with no LTS menu entry until validation.
    atomic(PROGRAM/'eutherboot-single.py', Path(__file__).read_bytes(), 0o755)
    for name in ('04-eutherboot-single-remove.hook','05-eutherboot-single.hook'):
        atomic(Path('/etc/pacman.d/hooks')/name, (a.hooks/name).read_bytes())
    atomic(Path('/etc/pacman.d/hooks/90-mkinitcpio-install.hook'),
           (DRIVER_TRIGGERS + upstream.replace(expected,
            'Exec = /usr/bin/python3 /usr/local/lib/eutherboot-single/eutherboot-single.py transaction')).encode())
    atomic(lts_preset, preset('linux-lts').encode())
    subprocess.run(['pacman','-U','--needed','--noconfirm', *map(str,a.packages)], check=True)
    # Rebuild explicitly: pacman's post-transaction failure does not necessarily
    # cause a failing pacman exit status. Never expose an unverified LTS image.
    subprocess.run(['mkinitcpio','-p','linux-lts'], check=True)
    lts_size = (STATE/'staging/linux-lts.efi').stat().st_size
    check(c, lts_size + max(lts_size, target_path(c, 'linux').stat().st_size))
    publish(STATE/'staging/linux-lts.efi', c, 'linux-lts')
    c['lts'] = True
    atomic(CONFIG, (json.dumps(c,indent=2)+'\n').encode())
    menu += "\n[[entry]]\nid='arch-lts'\nname='Arch Linux LTS (reserv)'\ntype='efi'\npath='\\EFI\\Linux\\arch-lts.efi'\n"
    atomic(menu_path, menu.encode())
    run('sync','-f',c['esp'])
    print('EUTHERBOOT_LTS_ENABLED; backup:', backup, flush=True)

def install(a):
    c = {'esp': str(a.esp), 'guid': a.esp_guid, 'cmdline': a.cmdline.read_text().strip()}
    if not c['cmdline'].isascii() or any(x in c['cmdline'] for x in ('\n','\r','\0','eutherboot_probe=')):
        raise RuntimeError('Invalid/internal probe command line')
    if 'root=' not in c['cmdline'] or 'eutherboot.internal=single-v1' not in c['cmdline']:
        raise RuntimeError('Expected root and internal boot marker')
    for p in (CONFIG, STATE, PROGRAM, Path('/etc/eutherboot/arch.conf')):
        if p.exists(): raise RuntimeError(f'Existing integration: {p}')
    if Path('/etc/pacman.d/hooks/90-mkinitcpio-install.hook').exists():
        raise RuntimeError('Existing custom mkinitcpio hook must be reviewed')
    if Path('/usr/share/libalpm/hooks/90-mkinitcpio-install.hook').read_text().count('Exec = /usr/share/libalpm/scripts/mkinitcpio install') != 1:
        raise RuntimeError('Unexpected upstream mkinitcpio hook')
    for name in ('objcopy','bootctl','mkinitcpio','pacman'):
        if not shutil.which(name): raise RuntimeError(f'Missing {name}')
    for var in Path('/sys/firmware/efi/efivars').glob('SecureBoot-*'):
        if var.read_bytes()[4:] != b'\0': raise RuntimeError('Unsigned profile needs Secure Boot off')
    esp_check(a.esp, a.esp_guid)
    image_check(a.image)
    k = kernel()
    if digest(k) != digest(Path('/boot/vmlinuz-linux')):
        raise RuntimeError('Boot kernel differs from package kernel')
    estimate = k.stat().st_size + Path('/boot/initramfs-linux.img').stat().st_size + 8*1024**2
    if shutil.disk_usage(a.esp).free < estimate + MARGIN:
        raise RuntimeError('Initial UKI must fit before deleting any boot files')
    backup_size = sum(p.stat().st_size for p in a.esp.rglob('*') if p.is_file())
    if shutil.disk_usage('/var/lib').free < backup_size + 4 * estimate + MARGIN:
        raise RuntimeError('Insufficient root space for verified backup and build')
    print(json.dumps({'profile':'single-uki-external-rescue','esp':c['esp'],
        'estimated_initial_uki':estimate,'remove_grub':True,'nvram_changes':False,
        'apply':a.apply}, indent=2), flush=True)
    if not a.apply: return
    if os.geteuid(): raise RuntimeError('Apply requires root')
    STATE.mkdir(mode=0o700)
    backup = STATE/'backup'; backup.mkdir()
    shutil.copytree(a.esp, backup/'boot')
    shutil.copy2('/etc/mkinitcpio.d/linux.preset', backup/'linux.preset')
    (backup/'fstab').write_bytes(Path('/etc/fstab').read_bytes())
    if shutil.which('efibootmgr'):
        (backup/'efibootmgr.txt').write_text(run('efibootmgr','-v'))
    hashes = {str(p.relative_to(backup/'boot')):digest(p) for p in (backup/'boot').rglob('*') if p.is_file()}
    for name, sha in hashes.items():
        if digest(a.esp/name) != sha: raise RuntimeError('Backup verification failed')
    atomic(backup/'boot-hashes.json', (json.dumps(hashes,indent=2)+'\n').encode())
    (STATE/'staging').mkdir()
    # Build in isolation before installing hooks or replacing the bootloader.
    temporary_cmdline = STATE/'initial.cmdline'; temporary_cmdline.write_text(c['cmdline']+'\n')
    run('mkinitcpio','-k',k,'-U',STATE/'staging/linux.efi','--cmdline',temporary_cmdline,'--no-ukify','--nopost')
    publish(STATE/'staging/linux.efi',c)
    PROGRAM.mkdir(parents=True)
    for name in ('eutherboot-single.py','eutherbootctl.py'):
        atomic(PROGRAM/name, (Path(__file__).parent/name).read_bytes(), 0o755)
    atomic(CONFIG, (json.dumps(c,indent=2)+'\n').encode())
    atomic(CONFIG.with_name('single.cmdline'), (c['cmdline']+'\n').encode())
    atomic(Path('/etc/mkinitcpio.d/linux.preset'), preset().encode())
    upstream = Path('/usr/share/libalpm/hooks/90-mkinitcpio-install.hook').read_text()
    expected = 'Exec = /usr/share/libalpm/scripts/mkinitcpio install'
    if upstream.count(expected) != 1: raise RuntimeError('Unexpected upstream mkinitcpio hook')
    atomic(Path('/etc/pacman.d/hooks/90-mkinitcpio-install.hook'), (DRIVER_TRIGGERS + upstream.replace(expected, 'Exec = /usr/bin/python3 /usr/local/lib/eutherboot-single/eutherboot-single.py transaction')).encode())
    trigger = (a.hooks/'05-eutherboot-single.hook').read_bytes()
    atomic(Path('/etc/pacman.d/hooks/05-eutherboot-single.hook'),trigger)
    atomic(Path('/etc/pacman.d/hooks/04-eutherboot-single-remove.hook'),(a.hooks/'04-eutherboot-single-remove.hook').read_bytes())
    menu = "[boot]\ndefault='arch'\ntimeout=10\ntheme='system-regis'\nlanguage='sv'\n\n[[entry]]\nid='arch'\nname='Arch Linux'\ntype='efi'\npath='\\EFI\\Linux\\arch-normal.efi'\n"
    atomic(a.esp/'EFI/EutherBoot/eutherboot.toml',menu.encode())
    for name, source in [('LICENSE',a.license),('source.tar.gz',a.source)]:
        atomic(a.esp/'EFI/EutherBoot'/name,source.read_bytes())
    # Last boot-critical replacement. Existing firmware path remains valid.
    atomic(a.esp/'EFI/BOOT/BOOTX64.EFI',a.image.read_bytes())
    if subprocess.run(['pacman','-Qq','grub'],capture_output=True).returncode == 0:
        run('pacman','-R','--noconfirm','grub')
    for name in ('initramfs-linux.img','initramfs-linux-fallback.img'):
        (a.esp/name).unlink(missing_ok=True)
    if (a.esp/'grub').exists(): shutil.rmtree(a.esp/'grub')
    run('sync','-f',a.esp)
    atomic(STATE/'installed.json',(json.dumps(c,indent=2)+'\n').encode())
    print('EUTHERBOOT_SINGLE_INSTALLED; backup:',backup,flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='action',required=True)
    ins=sub.add_parser('install')
    for flag in ('esp','cmdline','image','source','license','hooks'):
        ins.add_argument('--'+flag,type=Path,required=True)
    ins.add_argument('--esp-guid',required=True); ins.add_argument('--apply',action='store_true')
    lts=sub.add_parser('add-lts')
    lts.add_argument('--hooks',type=Path,required=True)
    lts.add_argument('packages',type=Path,nargs='+')
    sub.add_parser('preflight'); sub.add_parser('deny-remove')
    sub.add_parser('publish'); sub.add_parser('rebuild'); sub.add_parser('transaction')
    a=p.parse_args()
    if a.action=='install': return install(a)
    if a.action=='add-lts': return add_lts(a)
    if a.action=='deny-remove': raise RuntimeError('Remove single-UKI integration before removing a managed kernel or mkinitcpio')
    c=json.loads(CONFIG.read_text())
    with (STATE/'publish.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        check(c, max(target_path(c,p).stat().st_size for p in packages(c)))
        if a.action=='transaction':
            # On a kernel upgrade, the upstream remove hook saves our preset
            # as .pacsave. Its install hook restores it before building.
            subprocess.run(['/usr/share/libalpm/scripts/mkinitcpio','install'],check=True)
        for package in packages(c):
            if Path(f'/etc/mkinitcpio.d/{package}.preset').read_text()!=preset(package):
                raise RuntimeError('UKI preset changed; review before updating')
        if CONFIG.with_name('single.cmdline').read_text().strip()!=c['cmdline']:
            raise RuntimeError('UKI command line changed; review before updating')
        if a.action!='preflight':
            if a.action=='rebuild':
                subprocess.run(['mkinitcpio', *[x for p in packages(c) for x in ('-p',p)]],check=True)
            publish_all(c)

if __name__=='__main__':
    try: main()
    except (RuntimeError,OSError,ValueError,KeyError,subprocess.CalledProcessError) as e:
        sys.exit('EutherBoot single: '+str(e))
