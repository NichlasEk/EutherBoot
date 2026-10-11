#!/usr/bin/env python3
"""Stage a self-contained Archiso profile; no root, host mounts or USB writes."""
from pathlib import Path
import argparse,base64,hashlib,json,shutil,subprocess,tarfile,urllib.request
parser=argparse.ArgumentParser();parser.add_argument('--include-known-good',action='store_true');args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'artifacts/rescue';out.mkdir(parents=True,exist_ok=True)
profile=out/'profile'
if profile.exists():raise SystemExit('Profile already exists; archive it before preparing another snapshot')
releng=Path('/usr/share/archiso/configs/releng')
shutil.copytree(releng,profile,symlinks=True)
(profile/'packages.x86_64').write_text((ROOT/'rescue/packages.x86_64').read_text())
ai=profile/'airootfs'
# Use only network/keyring infrastructure from upstream; remove unattended scripts,
# audio, cloud provisioning and upstream auto-login state.
shutil.rmtree(ai/'root')
for path in list((ai/'etc/systemd/system').rglob('*')):
    if path.is_symlink() and not any(x in path.name for x in ['network','resolve','timesync','iwd','pacman-init']):path.unlink()
for name in ['livecd-talk.service','livecd-alsa-unmuter.service','choose-mirror.service']:
    (ai/'etc/systemd/system'/name).unlink(missing_ok=True)
shutil.rmtree(ai/'etc/ssh',ignore_errors=True)
shutil.rmtree(ai/'usr/local',ignore_errors=True)
shutil.copytree(ROOT/'rescue/overlay',ai,dirs_exist_ok=True)
(ai/'etc/passwd').write_text('root:x:0:0:root:/root:/usr/bin/bash\nrescue:x:1000:1000:Rescue:/home/rescue:/usr/bin/bash\n')
(ai/'etc/group').write_text('root:x:0:root\nrescue:x:1000:\nwheel:x:998:rescue\n')
(ai/'etc/shadow').write_text('root:!:14871::::::\nrescue::14871::::::\n')
(ai/'etc/hostname').write_text('euther-rescue\n')
(ai/'etc/vconsole.conf').write_text('KEYMAP=sv-latin1\n')
(ai/'etc/locale.conf').write_text('LANG=en_US.UTF-8\n')
(ai/'home/rescue').mkdir(parents=True)
(ai/'root').mkdir()
(ai/'etc/sudoers.d').mkdir(exist_ok=True)
(ai/'etc/sudoers.d/rescue').write_text('rescue ALL=(ALL:ALL) NOPASSWD: ALL\n')
for tty in ['getty@tty1','serial-getty@ttyS0']:
    d=ai/f'etc/systemd/system/{tty}.service.d';d.mkdir(parents=True,exist_ok=True)
    (d/'autologin.conf').write_text('[Service]\nExecStart=\nExecStart=-/usr/bin/agetty --autologin rescue --noclear %I $TERM\n')
(ai/'etc/mkinitcpio.conf.d/archiso.conf').write_text('HOOKS=(base udev microcode modconf kms memdisk archiso archiso_loop_mnt block filesystems keyboard)\nCOMPRESSION="zstd"\n')
(ai/'etc/pacman.d/mirrorlist').write_text('Server = https://geo.mirror.pkgbuild.com/$repo/os/$arch\n')
for p in (profile/'efiboot/loader/entries').glob('*.conf'):
    if p.name!='01-archiso-linux.conf':p.unlink()
p=profile/'efiboot/loader/entries/01-archiso-linux.conf'
s=p.read_text().replace('Arch Linux install medium','Euther Rescue').replace('%KERNEL_PARAMS%','%KERNEL_PARAMS% console=tty0 console=ttyS0,115200')
p.write_text(s)
(profile/'efiboot/loader/loader.conf').write_text('timeout 5\ndefault 01-archiso-linux.conf\n')
(profile/'profiledef.sh').write_text('''iso_name="euther-rescue"
iso_label="EUTHER_RESCUE"
iso_publisher="EutherBoot"
iso_application="System Regis Arch Rescue"
iso_version="0.1.2"
install_dir="arch"
bootmodes=('uefi.systemd-boot')
pacman_conf="pacman.conf"
airootfs_image_type="squashfs"
airootfs_image_tool_options=('-comp' 'zstd' '-Xcompression-level' '15' '-b' '1M' '-processors' '2')
file_permissions=(
 ["/etc/shadow"]="0:0:400"
 ["/etc/sudoers.d/rescue"]="0:0:440"
 ["/root"]="0:0:750"
 ["/home/rescue"]="1000:1000:750"
 ["/usr/local/bin/codex"]="0:0:755"
 ["/usr/local/bin/rescue-start"]="0:0:755"
 ["/usr/local/bin/rescue-data"]="0:0:755"
)
''')
# Verify the platform package against npm's published SHA-512 integrity before use.
version='0.162.1-linux-x64'
url=f'https://registry.npmjs.org/@openai%2Fcodex/{version}'
meta=json.load(urllib.request.urlopen(url))
archive=out/'codex.tgz'
if not archive.exists():urllib.request.urlretrieve(meta['dist']['tarball'],archive)
algorithm,expected=meta['dist']['integrity'].split('-',1)
assert algorithm=='sha512'
assert base64.b64encode(hashlib.sha512(archive.read_bytes()).digest()).decode()==expected
executables=[]
with tarfile.open(archive) as tar:
    prefix='package/vendor/x86_64-unknown-linux-musl/'
    for member in tar.getmembers():
        if not member.name.startswith(prefix) or not member.isfile():continue
        relative=Path(member.name[len(prefix):])
        assert not relative.is_absolute() and '..' not in relative.parts
        target=ai/'opt/codex'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(tar.extractfile(member).read())
        if member.mode & 0o111:executables.append('/opt/codex/'+str(relative))
# The checked-in launcher initializes the live user's Codex state directory.
with (profile/'profiledef.sh').open('a') as f:
    for executable in executables:f.write(f'file_permissions["{executable}"]="0:0:755"\n')
license_url='https://raw.githubusercontent.com/openai/codex/rust-v0.162.1/LICENSE'
license_data=urllib.request.urlopen(license_url).read()
assert b'Apache License' in license_data
(ai/'opt/codex/LICENSE').write_bytes(license_data)
share=ai/'usr/local/share/euther-rescue'
release=ROOT/'artifacts/release'
for name in ['EutherBoot.efi','eutherboot-source.tar.gz','manifest.json','SHA256SUMS']:
    shutil.copy2(release/name,share/name)
# Reviewed repository files, including new source/docs; ignored artifacts and host home are excluded.
repo=share/'EutherBoot';repo.mkdir()
files=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT).decode().split('\0')
for name in filter(None,files):
    source=ROOT/name
    if source.is_file():
        dest=repo/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
if args.include_known_good:
    known=out/'known-good'
    manifest=json.loads((known/'manifest.json').read_text())
    for name,digest in manifest['files'].items():
        assert hashlib.sha256((known/name).read_bytes()).hexdigest()==digest
    shutil.copytree(known,share/'known-good')
metadata={'rescue_version':'0.1.2','private_known_good_included':args.include_known_good,'codex_version':version,'registry_url':url,'tarball':meta['dist']['tarball'],'integrity':meta['dist']['integrity'],'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),'archiso':subprocess.check_output(['pacman','-Q','archiso'],text=True).strip(),'credentials_included':False,'codex_license_url':license_url,'codex_license_sha256':hashlib.sha256(license_data).hexdigest()}
(out/'profile-manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
(share/'profile-manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
print(profile)
