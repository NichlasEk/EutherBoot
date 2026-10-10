#!/usr/bin/env bash
set -euo pipefail
# Refuse accidental execution anywhere except the disposable fixture root.
[[ $(lsblk -ndo PARTUUID /dev/vdb3) == 985d9e6f-ac49-4187-86d5-dd967894cf3a ]]
[[ $(findmnt -n -o SOURCE /) == /dev/vdb3 ]]
systemd-detect-virt --quiet --vm
payload=/eutherboot/EFI/EutherBoot/TestPayload
[[ -d "$payload" ]]
install -Dm755 "$payload/publish.sh" /usr/local/lib/eutherboot/publish
install -Dm755 "$payload/95-eutherboot" /etc/initcpio/post/95-eutherboot
install -Dm644 "$payload/05-eutherboot-esp.hook" /etc/pacman.d/hooks/05-eutherboot-esp.hook
install -Dm644 "$payload/update.conf" /etc/eutherboot-update.conf
install -Dm644 "$payload/cmdline" /etc/kernel/cmdline
mkdir -p /var/lib/eutherboot
cp /etc/mkinitcpio.d/linux.preset /var/lib/eutherboot/original-linux.preset
cat >> /etc/mkinitcpio.d/linux.preset <<'PRESET'

# EutherBoot QEMU fixture: build on root, publish only after successful generation.
default_uki='/var/lib/eutherboot/arch-linux.efi'
default_cmdline='/etc/kernel/cmdline'
PRESET
printf '\nPARTUUID=%s /eutherboot vfat defaults 0 2\n' "$(lsblk -ndo PARTUUID /dev/vda1)" >> /etc/fstab
# The supplied image has networkd but no usable wired DHCP profile for this NIC.
mkdir -p /etc/systemd/network
printf '[Match]\nName=en* eth*\n[Network]\nDHCP=yes\n' > /etc/systemd/network/20-eutherboot-test.network
systemctl enable --now systemd-networkd systemd-resolved
networkctl reload
systemctl start pacman-init.service
/usr/local/lib/eutherboot/publish --check
uname -r > /var/lib/eutherboot/kernel-before
pacman -Q linux > /var/lib/eutherboot/package-before
for attempt in $(seq 1 90); do curl -fsI --max-time 5 https://geo.mirror.pkgbuild.com/core/os/x86_64/core.db >/dev/null && break; sleep 1; done
# This is a full guest upgrade. Dependencies are installed in the same transaction.
pacman -Syu --noconfirm --needed binutils systemd-ukify
[[ -s /eutherboot/EFI/Linux/arch-linux.efi ]]
[[ $(bootctl kernel-identify /eutherboot/EFI/Linux/arch-linux.efi) == uki ]]
pacman -Q linux > /var/lib/eutherboot/package-after
! cmp -s /var/lib/eutherboot/package-before /var/lib/eutherboot/package-after
for directory in /usr/lib/modules/*; do
    if [[ $(cat "$directory/pkgbase" 2>/dev/null) == linux ]]; then
        basename "$directory" > /var/lib/eutherboot/kernel-expected
    fi
done
[[ -s /var/lib/eutherboot/kernel-expected ]]
! cmp -s /var/lib/eutherboot/kernel-before /var/lib/eutherboot/kernel-expected
sha256sum /eutherboot/EFI/Linux/arch-linux.efi > /var/lib/eutherboot/uki-after.sha256
printf 'BEFORE_KERNEL=%s\nEXPECTED_KERNEL=%s\n' "$(cat /var/lib/eutherboot/kernel-before)" "$(cat /var/lib/eutherboot/kernel-expected)"
cat /var/lib/eutherboot/package-before /var/lib/eutherboot/package-after
