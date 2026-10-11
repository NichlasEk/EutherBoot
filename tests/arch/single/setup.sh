#!/bin/bash
set -euo pipefail
systemd-detect-virt --quiet --vm
[[ $(findmnt -n --nofsroot -o SOURCE /) == /dev/vdb3 ]]
cp -a /boot/EFI/TestPayload /root/single-payload
rm -rf /boot/EFI/TestPayload
p=/root/single-payload
systemctl start pacman-init.service
pacman -U --noconfirm --needed "$p"/deps/*.pkg.tar.zst
cp "$p/kernel" /boot/vmlinuz-linux
cp "$p/initrd" /boot/initramfs-linux.img
# Exercise the same udev/Btrfs arrangement as the host, with virtual drivers.
cat > /etc/mkinitcpio.conf <<'CONF'
MODULES=(virtio_pci virtio_blk btrfs)
BINARIES=(/usr/bin/btrfs)
FILES=()
HOOKS=(base udev autodetect microcode modconf keyboard keymap block filesystems fsck)
CONF
printf '\nPARTUUID=%s /boot vfat defaults 0 2\n' "$(lsblk -ndo PARTUUID /dev/vdc1)" >> /etc/fstab
python /root/single-payload/eutherboot-single.py install --esp /boot --esp-guid eeeeeeee-1111-4111-8111-eeeeeeeeeeee --cmdline "$p/cmdline" --image "$p/EutherBoot.efi" --source "$p/source.tar.gz" --license "$p/LICENSE" --hooks "$p/hooks" --apply
# Driver package trigger with no kernel/firmware paths: must rebuild and publish.
mkdir -p /root/driver-fixture/usr/share
printf fixture > /root/driver-fixture/usr/share/eutherboot-driver-fixture
cat > /root/driver-fixture/.PKGINFO <<'INFO'
pkgname = nvidia-open
pkgver = 0.0-1
pkgdesc = Disposable package-trigger test only
builddate = 1700000000
size = 7
arch = any
INFO
(cd /root/driver-fixture; tar -cf /root/driver-fixture.tar .PKGINFO usr)
rm /var/lib/eutherboot-single/staging/linux.efi
pacman -U --noconfirm /root/driver-fixture.tar > /root/driver-trigger.log 2>&1
cat /root/driver-trigger.log
grep -F EUTHERBOOT_SINGLE_PUBLISHED /root/driver-trigger.log
pacman -R --noconfirm nvidia-open
# Pad real UKI to host size: still a valid PE, challenge actual copy capacity.
cp /var/lib/eutherboot-single/staging/linux.efi /root/unpadded.efi
truncate -s 286150656 /var/lib/eutherboot-single/staging/linux.efi
python /usr/local/lib/eutherboot-single/eutherboot-single.py publish
sha256sum /boot/EFI/Linux/arch-normal.efi > /root/good.sha
# Invalid input must not replace the active target.
printf broken > /var/lib/eutherboot-single/staging/linux.efi
if python /usr/local/lib/eutherboot-single/eutherboot-single.py publish; then exit 1; fi
sha256sum -c /root/good.sha
cp /root/unpadded.efi /var/lib/eutherboot-single/staging/linux.efi
# Real FAT capacity refusal through the pacman pre-transaction hook.
free=$(df -B1 --output=avail /boot | tail -1)
dd if=/dev/zero of=/boot/filler bs=1M count=$((free/1048576-32)) status=none
if pacman -U --noconfirm "$p/linux.pkg.tar.zst"; then exit 1; fi
[[ $(uname -r) == $(basename "$(dirname "$(pacman -Qql linux | grep '/vmlinuz$')")") ]]
sha256sum -c /root/good.sha
rm /boot/filler
# Fail an actual mkinitcpio build; publication must not run with stale output.
cp /etc/mkinitcpio.conf /root/mkinitcpio.good
printf '\nHOOKS=(nonexistent_eutherboot_test_hook)\n' >> /etc/mkinitcpio.conf
if python /usr/local/lib/eutherboot-single/eutherboot-single.py rebuild; then exit 1; fi
sha256sum -c /root/good.sha
cp /root/mkinitcpio.good /etc/mkinitcpio.conf
python /usr/local/lib/eutherboot-single/eutherboot-single.py rebuild
[[ ! -f /boot/initramfs-linux.img && ! -f /boot/initramfs-linux-fallback.img ]]
if pacman -Q grub; then exit 1; fi
python - <<'PY'
from pathlib import Path
p=Path('/etc/fstab');lines=[]
for line in p.read_text().splitlines():
    f=line.split()
    if len(f)>=4 and f[1]=='/':
        f[3]=','.join([x for x in f[3].split(',') if not x.startswith(('subvol=','subvolid='))]+['subvol=@'])
        line='\t'.join(f)
    lines.append(line)
if not any(len(x.split())>1 and x.split()[1]=='/swap' for x in lines):
    lines.append('PARTUUID=985d9e6f-ac49-4187-86d5-dd967894cf3a /swap btrfs subvol=swap 0 0')
p.write_text('\n'.join(lines)+'\n')
PY
btrfs subvolume snapshot / /@
sync
echo SINGLE_SETUP_AND_FAILURES_PASS
