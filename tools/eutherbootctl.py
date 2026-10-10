#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Explicit, side-by-side installation. Planning is read-only; never edits NVRAM."""
import argparse
import base64
import hashlib
import json
import os
import re
from pathlib import Path
import shlex
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import uuid

STATE=Path('/var/lib/eutherboot')
MANIFEST=STATE/'installation.json'
ESP_TYPE='c12a7328-f81f-11d2-ba4b-00a0c93ec93b'

def run(*args):
    result=subprocess.run([str(a) for a in args],capture_output=True,text=True)
    if result.returncode:raise RuntimeError(f'{args[0]}: {result.stderr.strip() or result.stdout.strip()}')
    return result.stdout.strip()
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def atomic(path,data,mode=0o644):
    if path.is_symlink():raise RuntimeError(f'Refusing symlink: {path}')
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.eutherboot-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),mode)
        os.replace(name,path)
        fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:
        Path(name).unlink(missing_ok=True)
def image_check(path):
    data=path.read_bytes()
    if len(data)<128 or data[:2]!=b'MZ':raise RuntimeError('Not a PE image')
    pe=struct.unpack_from('<I',data,60)[0]
    if pe+94>len(data) or data[pe:pe+4]!=b'PE\0\0':raise RuntimeError('Truncated PE image')
    if struct.unpack_from('<H',data,pe+4)[0]!=0x8664 or struct.unpack_from('<H',data,pe+24)[0]!=0x20b or struct.unpack_from('<H',data,pe+92)[0]!=10:
        raise RuntimeError('Expected an x86_64 PE32+ EFI application')
def esp_check(path,guid,require_space=True,minimum_free=8*1024**2):
    if str(uuid.UUID(guid))!=guid or uuid.UUID(guid).int==0:raise RuntimeError('Expected a canonical nonzero ESP PARTUUID')
    if path.is_symlink() or path.resolve()!=path:raise RuntimeError('ESP must be an absolute canonical mount path')
    mount=json.loads(run('findmnt','-J','-M',path,'-o','TARGET,SOURCE,FSTYPE,OPTIONS'))['filesystems'][0]
    if mount['target']!=str(path) or mount['fstype']!='vfat':raise RuntimeError('Expected an exact FAT mount point')
    if 'rw' not in mount['options'].split(','):raise RuntimeError('ESP is read-only')
    if run('lsblk','-ndo','PARTUUID',mount['source'])!=guid:raise RuntimeError('ESP PARTUUID does not match')
    if run('lsblk','-ndo','PARTTYPE',mount['source'])!=ESP_TYPE:raise RuntimeError('Partition is not GPT ESP type')
    if require_space and shutil.disk_usage(path).free<minimum_free:raise RuntimeError(f'ESP needs at least {minimum_free//1024**2} MiB free')
    if (path/'EFI').is_symlink():raise RuntimeError('EFI directory must not be a symlink')
    return mount

def arch_capacity(boot=Path('/boot')):
    """Budget current + immutable recovery + stable recovery, staging and headroom.

    Existing boot files are retained. This estimate cannot predict future kernel
    growth; publication also checks the actual completed UKI before copying it.
    """
    sizes=[]
    for package in ('linux','linux-lts'):
        kernel=boot/f'vmlinuz-{package}';initrd=boot/f'initramfs-{package}.img'
        if not kernel.is_file() or not initrd.is_file():
            raise RuntimeError(f'Missing {package} kernel/initramfs; build both before installation')
        sizes.append(kernel.stat().st_size+initrd.stat().st_size+8*1024**2)
    return 3*sum(sizes)+max(sizes)+384*1024**2

def arch_files(args):
    root=args.arch_files.resolve()
    if not args.cmdline:raise RuntimeError('--cmdline is required for Arch integration')
    cmdline=args.cmdline.read_text().strip()
    if not cmdline.isascii() or not cmdline or len(cmdline)>950 or any(c in cmdline for c in '\n\r\0') or 'eutherboot.' in cmdline:
        raise RuntimeError('Command line must be one explicit ASCII line without eutherboot options')
    # Early recovery must reach its archive without waiting for a separate /var or /usr.
    root_device=run('findmnt','-n','-T','/','-o','MAJ:MIN')
    for path in ('/usr/lib/modules','/var/lib'):
        if run('findmnt','-n','-T',path,'-o','MAJ:MIN')!=root_device or run('findmnt','-n','-T',path,'-o','TARGET')!='/':
            raise RuntimeError('Separate /usr or /var subvolumes/filesystems are not supported by this recovery service')
    for command in ('mkinitcpio','bootctl','sha256sum','flock','mount','modprobe'):
        if not shutil.which(command):raise RuntimeError(f'Missing prerequisite: {command}')
    if not Path('/usr/lib/systemd/ukify').is_file():raise RuntimeError('Install systemd-ukify before enabling Arch integration')
    conf=f'ESP_MOUNT={shlex.quote(str(args.esp))}\nESP_GUID={shlex.quote(args.esp_guid)}\n'
    if bool(args.signing_key)!=bool(args.signing_cert):raise RuntimeError('Both signing key and certificate are required')
    if args.signing_key:
        key=args.signing_key.resolve();cert=args.signing_cert.resolve()
        if not cert.is_file() or not key.is_file() or key.stat().st_uid!=0 or key.stat().st_mode & 0o077:
            raise RuntimeError('Signing key must be root-owned, mode 0600 or stricter, and certificate must exist')
        if key.is_relative_to(args.esp):raise RuntimeError('Never store a signing private key on the ESP')
        for command in ('sbsign','sbverify'):
            if not shutil.which(command):raise RuntimeError(f'Missing prerequisite: {command}')
        conf+=f'SIGNING_KEY={shlex.quote(str(key))}\nSIGNING_CERT={shlex.quote(str(cert))}\n'
    files={Path('/etc/eutherboot/arch.conf'):(conf.encode(),0o600),
           Path('/etc/eutherboot/cmdline'):((cmdline+' eutherboot.managed=1\n').encode(),0o644)}
    for name in ('common.sh','prepare','publish','restore-modules','finalize','mark-good'):
        files[Path('/usr/local/lib/eutherboot')/name]=((root/name).read_bytes(),0o755)
    files[Path('/etc/initcpio/post/95-eutherboot')]=((root/'publish').read_bytes(),0o755)
    for name in ('05-eutherboot.hook','99-eutherboot.hook'):
        files[Path('/etc/pacman.d/hooks')/name]=((root/name).read_bytes(),0o644)
    for name in ('eutherboot-recovery.service','eutherboot-success.service'):
        files[Path('/etc/systemd/system')/name]=((root/name).read_bytes(),0o644)
    for package in ('linux','linux-lts'):
        run('pacman','-Q',package)
        preset=Path(f'/etc/mkinitcpio.d/{package}.preset')
        if preset.is_symlink():raise RuntimeError(f'Preset is a symlink: {preset}')
        original=preset.read_text()
        if 'eutherboot' in original.lower():raise RuntimeError(f'Preset already mentions EutherBoot: {preset}')
        # Keep the normal /boot initramfs for the existing boot manager.
        output=run('bash','-c','source "$1"; printf "%s" "${default_image:-}"','bash',preset)
        if output!=f'/boot/initramfs-{package}.img':raise RuntimeError(f'Nonstandard {package} preset; refusing to alter it automatically')
        extra=f"\n# EutherBoot managed integration\ndefault_uki='{STATE}/staging/{package}.efi'\ndefault_cmdline='/etc/eutherboot/cmdline'\n"
        files[preset]=((original+extra).encode(),0o644)
    return files

def install(args):
    esp_check(args.esp,args.esp_guid,minimum_free=(384 if args.arch else 8)*1024**2)
    target=args.esp/'EFI/EutherBoot'
    if target.exists() or MANIFEST.exists():raise RuntimeError('Existing EutherBoot installation/path; refusing to overwrite')
    image_check(args.image)
    if bool(args.signing_key)!=bool(args.signing_cert):raise RuntimeError('Both signing key and certificate are required')
    if args.signing_key and not args.arch:raise RuntimeError('This installer currently accepts signing material only with --arch')
    run(args.validator,args.config)
    configuration=args.config.read_text()
    if '\\EFI\\EutherBoot\\EutherBoot.efi'.lower() in configuration.lower():raise RuntimeError('Configuration points to EutherBoot itself')
    files=arch_files(args) if args.arch else {}
    if args.arch:
        esp_check(args.esp,args.esp_guid,minimum_free=arch_capacity())
    for path in files:
        if path.is_symlink():raise RuntimeError(f'Refusing symlink: {path}')
        if path.exists() and not str(path).startswith('/etc/mkinitcpio.d/'):
            raise RuntimeError(f'Existing integration file: {path}')
    plan={'action':'install','esp':str(args.esp),'esp_partuuid':args.esp_guid,
          'efi':str(target/'EutherBoot.efi'),'image_sha256':digest(args.image),
          'root_files':[str(p) for p in files],'state_journal':str(MANIFEST),'arch_integration':args.arch,
          'firmware_variables':'unchanged','existing_loaders':'unchanged'}
    print(json.dumps(plan,indent=2),flush=True)
    if not args.apply:return
    if os.geteuid()!=0:raise RuntimeError('--apply requires root')
    if Path('/var/lib/pacman/db.lck').exists():raise RuntimeError('A pacman transaction is running')
    records=[];installation_id=str(uuid.uuid4())
    manifest={'id':installation_id,'esp':str(args.esp),'guid':args.esp_guid,'status':'installing','files':records,'arch':args.arch,'signed':bool(args.signing_key)}
    STATE.mkdir(parents=True,exist_ok=True)
    atomic(MANIFEST,(json.dumps(manifest,indent=2)+'\n').encode(),0o600)
    try:
        for path,(data,mode) in files.items():
            previous=base64.b64encode(path.read_bytes()).decode() if path.exists() else None
            record={'path':str(path),'before':previous,'mode':stat.S_IMODE(path.stat().st_mode) if path.exists() else mode,'sha256':hashlib.sha256(data).hexdigest()}
            records.append(record)
            atomic(MANIFEST,(json.dumps(manifest,indent=2)+'\n').encode(),0o600)
            atomic(path,data,mode)
        stage=args.esp/'EFI'/f'.EutherBoot-install-{installation_id}'
        stage.mkdir()
        atomic(stage/'.installation-id',(installation_id+'\n').encode())
        atomic(stage/'EutherBoot.efi',args.image.read_bytes())
        if args.signing_key:
            run('sbsign','--key',args.signing_key,'--cert',args.signing_cert,'--output',stage/'signed.efi',stage/'EutherBoot.efi')
            run('sbverify','--cert',args.signing_cert,stage/'signed.efi')
            os.replace(stage/'signed.efi',stage/'EutherBoot.efi')
        atomic(stage/'eutherboot.toml',configuration.encode())
        os.rename(stage,target)
        manifest['image_sha256']=digest(target/'EutherBoot.efi')
        manifest['config_sha256']=digest(target/'eutherboot.toml')
        if args.arch:
            (STATE/'staging').mkdir(exist_ok=True)
            run('systemctl','daemon-reload')
            run('systemctl','enable','eutherboot-recovery.service','eutherboot-success.service')
            # Capture an initial recovery generation before touching any generated payload.
            run('/usr/local/lib/eutherboot/prepare')
            print(run('mkinitcpio','-p','linux','-p','linux-lts'),flush=True)
            if any((STATE/'pending').iterdir()):raise RuntimeError('Boot publication incomplete')
        manifest['status']='installed'
        atomic(MANIFEST,(json.dumps(manifest,indent=2)+'\n').encode(),0o600)
        print('Installed alongside existing loaders. Select \\EFI\\EutherBoot\\EutherBoot.efi through firmware Boot From File for the first test.')
    except BaseException:
        manifest['status']='incomplete'
        atomic(MANIFEST,(json.dumps(manifest,indent=2)+'\n').encode(),0o600)
        print('Installation incomplete; existing loaders remain intact. Inspect status and use remove --apply to undo the recorded integration.',file=sys.stderr)
        raise

def upgrade(args):
    esp_check(args.esp,args.esp_guid)
    manifest=json.loads(MANIFEST.read_text())
    if manifest['status']!='installed' or manifest['esp']!=str(args.esp) or manifest['guid']!=args.esp_guid:
        raise RuntimeError('Expected a complete installation on the specified ESP')
    target=args.esp/'EFI/EutherBoot'
    if (target/'.installation-id').read_text().strip()!=manifest['id']:
        raise RuntimeError('ESP installation identity mismatch')
    current=target/'EutherBoot.efi'
    if digest(current)!=manifest['image_sha256']:
        raise RuntimeError('Installed EFI image changed outside this installer')
    image_check(args.image)
    if bool(args.signing_key)!=bool(args.signing_cert):
        raise RuntimeError('Both signing key and certificate are required')
    print(json.dumps({'action':'upgrade','efi':str(current),'image_sha256':digest(args.image),
        'backup':str(target/'EutherBoot.previous.efi'),'configuration':'unchanged',
        'firmware_variables':'unchanged'},indent=2),flush=True)
    if not args.apply:return
    if Path('/var/lib/pacman/db.lck').exists():raise RuntimeError('A pacman transaction is running')
    # A signed installation must not silently become unsigned during an upgrade.
    if manifest.get('signed') and not args.signing_key:
        raise RuntimeError('This installation requires signing key and certificate for upgrades')
    with tempfile.TemporaryDirectory(prefix='upgrade-',dir=STATE) as directory:
        candidate=Path(directory)/'EutherBoot.efi'
        candidate.write_bytes(args.image.read_bytes())
        if args.signing_key:
            run('sbsign','--key',args.signing_key,'--cert',args.signing_cert,'--output',candidate.with_suffix('.signed'),candidate)
            run('sbverify','--cert',args.signing_cert,candidate.with_suffix('.signed'))
            candidate=candidate.with_suffix('.signed')
        image_check(candidate)
        atomic(target/'EutherBoot.previous.efi',current.read_bytes())
        manifest['previous_image_sha256']=digest(current)
        # Journal the candidate before replacement so an interrupted upgrade is diagnosable.
        manifest['pending_image_sha256']=digest(candidate)
        atomic(MANIFEST,(json.dumps(manifest,indent=2)+'\n').encode(),0o600)
        atomic(current,candidate.read_bytes())
        manifest['image_sha256']=manifest.pop('pending_image_sha256')
        manifest['signed']=bool(args.signing_key)
        atomic(MANIFEST,(json.dumps(manifest,indent=2)+'\n').encode(),0o600)
    print('EFI image upgraded; previous EFI image retained alongside it.')

def prune(args):
    esp_check(args.esp,args.esp_guid,require_space=False)
    manifest=json.loads(MANIFEST.read_text())
    if manifest['esp']!=str(args.esp) or manifest['guid']!=args.esp_guid:
        raise RuntimeError('Installation identity mismatch')
    generation=args.generation
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._+-]{0,127}',generation):
        raise RuntimeError('Invalid generation identifier')
    target=args.esp/'EFI/EutherBoot'
    if (target/'.installation-id').read_text().strip()!=manifest['id']:
        raise RuntimeError('ESP installation identity mismatch')
    references=[STATE/'linux-previous',STATE/'linux-lts-previous',
                STATE/'pending/linux',STATE/'pending/linux-lts']
    if any(p.is_file() and p.read_text().strip()==generation for p in references):
        raise RuntimeError('Generation is a selected recovery or pending transaction')
    if f'eutherboot.recovery={generation}' in Path('/proc/cmdline').read_text().split():
        raise RuntimeError('Generation belongs to the running recovery kernel')
    # Also protect explicit menu entries and the editor backup/staged configuration.
    for config in target.glob('eutherboot.toml*'):
        if config.is_file() and generation.lower() in config.read_text(errors='replace').lower():
            raise RuntimeError(f'Generation is referenced by configuration: {config.name}')
    archive=STATE/'generations'/generation
    if archive.is_symlink() or not archive.is_dir():raise RuntimeError('Missing or symbolic-link generation')
    image=target/'kernels'/f'recovery-{generation}.efi'
    print(json.dumps({'action':'prune','generation':generation,'archive':str(archive),
        'immutable_uki':str(image),'selected_recoveries':'retained'},indent=2),flush=True)
    if not args.apply:return
    if Path('/var/lib/pacman/db.lck').exists():raise RuntimeError('A pacman transaction is running')
    import fcntl
    with open('/run/eutherboot-generation.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        image.unlink(missing_ok=True)
        run('sync','-f',target)
        shutil.rmtree(archive)
        run('sync','-f',STATE)
    print('Unreferenced generation removed.')

def remove(args):
    esp_check(args.esp,args.esp_guid,require_space=False)
    manifest=json.loads(MANIFEST.read_text())
    if manifest['esp']!=str(args.esp) or manifest['guid']!=args.esp_guid:raise RuntimeError('Installation identity mismatch')
    if 'eutherboot.recovery=' in Path('/proc/cmdline').read_text():raise RuntimeError('Boot a normal or LTS kernel before uninstalling recovery support')
    target=args.esp/'EFI/EutherBoot'
    if target.exists() and (target/'.installation-id').read_text().strip()!=manifest['id']:raise RuntimeError('ESP installation identity mismatch')
    for record in manifest['files']:
        path=Path(record['path'])
        if path.exists() and (path.is_symlink() or digest(path)!=record['sha256']):
            # A journaled write may not have happened during an interrupted install.
            before=record['before']
            if before is None or path.read_bytes()!=base64.b64decode(before):raise RuntimeError(f'Locally modified file retained; resolve before removal: {path}')
    print(json.dumps({'action':'remove','owned_efi_directory':str(target),'restore_files':[r['path'] for r in manifest['files']],
                      'generations':'retained under /var/lib/eutherboot','firmware_variables':'unchanged'},indent=2),flush=True)
    if not args.apply:return
    if os.geteuid()!=0:raise RuntimeError('--apply requires root')
    if Path('/var/lib/pacman/db.lck').exists():raise RuntimeError('A pacman transaction is running')
    backup=STATE/f'removed-{manifest["id"]}'
    stage=args.esp/'EFI'/f'.EutherBoot-install-{manifest["id"]}'
    if stage.exists():shutil.rmtree(stage)
    if target.exists():
        shutil.copytree(target,backup)
        shutil.rmtree(target)
    if manifest['arch']:
        run('systemctl','disable','eutherboot-recovery.service','eutherboot-success.service')
    for record in reversed(manifest['files']):
        path=Path(record['path'])
        if record['before'] is None:path.unlink(missing_ok=True)
        else:atomic(path,base64.b64decode(record['before']),record['mode'])
    if manifest['arch']:run('systemctl','daemon-reload')
    atomic(STATE/f'removed-{manifest["id"]}.json',MANIFEST.read_bytes(),0o600)
    MANIFEST.unlink()
    print('Removed only the owned installation; configuration, UKIs and recovery generations retained in the removal archive.')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    subs=parser.add_subparsers(dest='action',required=True)
    for action in ('install','upgrade','remove','prune','status'):
        p=subs.add_parser(action)
        if action=='status':continue
        p.add_argument('--esp',type=Path,required=True);p.add_argument('--esp-guid',required=True)
        p.add_argument('--apply',action='store_true',help='Perform the printed plan; otherwise read-only')
        if action=='prune':p.add_argument('--generation',required=True)
        if action in ('install','upgrade'):
            p.add_argument('--image',type=Path,required=True)
            p.add_argument('--signing-key',type=Path);p.add_argument('--signing-cert',type=Path)
        if action=='install':
            p.add_argument('--config',type=Path,required=True)
            p.add_argument('--validator',type=Path,required=True)
            p.add_argument('--arch',action='store_true');p.add_argument('--cmdline',type=Path)
            p.add_argument('--arch-files',type=Path,default=Path(__file__).resolve().parent.parent/'packaging/arch')
    args=parser.parse_args()
    if args.action=='status':
        if not MANIFEST.exists():print('No managed installation');return
        manifest=json.loads(MANIFEST.read_text())
        summary={key:manifest[key] for key in ('id','status','esp','guid','arch','image_sha256','pending_image_sha256') if key in manifest}
        summary['generations']=[p.name for p in sorted((STATE/'generations').glob('*')) if p.is_dir() and not p.name.startswith('.')]
        summary['selected_recovery']={p.name:p.read_text().strip() for p in (STATE/'linux-previous',STATE/'linux-lts-previous') if p.is_file()}
        print(json.dumps(summary,indent=2));return
    try:
        if args.apply:
            import fcntl
            if os.geteuid()!=0:raise RuntimeError('--apply requires root')
            with open('/run/eutherboot-install.lock','w') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                {'install':install,'upgrade':upgrade,'remove':remove,'prune':prune}[args.action](args)
        else:
            {'install':install,'upgrade':upgrade,'remove':remove,'prune':prune}[args.action](args)
    except (RuntimeError,OSError,ValueError,KeyError,struct.error) as error:
        print(f'EutherBoot: {error}',file=sys.stderr);sys.exit(1)
if __name__=='__main__':main()
