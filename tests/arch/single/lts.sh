#!/bin/bash
set -euo pipefail
p=/root/single-payload
python "$p/eutherboot-single.py" add-lts --hooks "$p/hooks" "$p/linux-lts.pkg.tar.zst"
cp /var/lib/eutherboot-single/staging/linux.efi /root/linux-unpadded.efi
cp /var/lib/eutherboot-single/staging/linux-lts.efi /root/lts-unpadded.efi
# Two host-sized UKIs coexist and can be replaced on a 1 GiB ESP.
truncate -s 286150656 /var/lib/eutherboot-single/staging/linux.efi
truncate -s 286150656 /var/lib/eutherboot-single/staging/linux-lts.efi
python /usr/local/lib/eutherboot-single/eutherboot-single.py publish
sha256sum /boot/EFI/Linux/arch-{normal,lts}.efi > /root/both-good.sha
printf broken > /var/lib/eutherboot-single/staging/linux-lts.efi
if python /usr/local/lib/eutherboot-single/eutherboot-single.py publish; then exit 1; fi
sha256sum -c /root/both-good.sha
cp /root/lts-unpadded.efi /var/lib/eutherboot-single/staging/linux-lts.efi
cp /etc/mkinitcpio.conf /root/lts-mkinitcpio.good
printf '\nHOOKS=(nonexistent_eutherboot_test_hook)\n' >> /etc/mkinitcpio.conf
if python /usr/local/lib/eutherboot-single/eutherboot-single.py rebuild; then exit 1; fi
sha256sum -c /root/both-good.sha
cp /root/lts-mkinitcpio.good /etc/mkinitcpio.conf
# Actual LTS transaction must abort before removing modules on a full ESP.
free=$(df -B1 --output=avail /boot | tail -1)
dd if=/dev/zero of=/boot/filler bs=1M count=$((free/1048576-32)) status=none
if pacman -U --noconfirm "$p/linux-lts.pkg.tar.zst"; then exit 1; fi
sha256sum -c /root/both-good.sha
rm /boot/filler
python /usr/local/lib/eutherboot-single/eutherboot-single.py rebuild
if pacman -R --noconfirm linux-lts; then exit 1; fi
pacman -Q linux-lts
sed -i "s/default='arch'/default='arch-lts'/;s/timeout=10/timeout=1/" /boot/EFI/EutherBoot/eutherboot.toml
sync
echo LTS_INSTALL_AND_FAILURES_PASS
