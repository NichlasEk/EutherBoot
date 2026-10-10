#!/usr/bin/env bash
set -euo pipefail
[[ $(findmnt -n -o SOURCE /) == /dev/vdb3 ]]
[[ $(lsblk -ndo PARTUUID /dev/vdb3) == 985d9e6f-ac49-4187-86d5-dd967894cf3a ]]
systemd-detect-virt --quiet --vm
payload=/eutherboot/EFI/TestPayload
layout=$(cat "$payload/layout")
if [[ $layout == btrfs-at-udev ]]; then
    cat > /etc/mkinitcpio.conf <<'CONF'
MODULES=(virtio_pci virtio_blk btrfs)
BINARIES=(/usr/bin/btrfs)
FILES=()
HOOKS=(base udev kms autodetect microcode modconf keyboard keymap block filesystems fsck)
CONF
fi
mkdir -p /root/eutherboot-original
version=$(uname -r)
cp -a --reflink=auto "/usr/lib/modules/$version" /root/eutherboot-original/modules
cp /boot/initramfs-linux.img /root/eutherboot-original/initrd.img
printf '%s\n' "$version" > /root/eutherboot-original/version
printf 'linux\n' > /root/eutherboot-original/package
printf '%s eutherboot.managed=1 eutherboot.recovery=linux-original\n' "$(cat "$payload/cmdline")" > /root/eutherboot-original/cmdline
(cd /root/eutherboot-original; find . -type f ! -name SHA256SUMS -print0 | LC_ALL=C sort -z | xargs -0 sha256sum) > /root/eutherboot-original/SHA256SUMS
mkdir -p /etc/systemd/network
printf '[Match]\nName=en* eth*\n[Network]\nDHCP=yes\n' > /etc/systemd/network/20-eutherboot-test.network
systemctl enable --now systemd-networkd systemd-resolved
networkctl reload; systemctl start pacman-init.service
for attempt in $(seq 1 90); do curl -fsI --max-time 5 https://geo.mirror.pkgbuild.com/core/os/x86_64/core.db >/dev/null && break; sleep 1; done
pacman -Syu --noprogressbar --noconfirm --needed systemd-ukify binutils linux-lts sbsigntools
if [[ $layout == btrfs-at-udev ]]; then
    for package in linux linux-lts; do
        printf "\nPRESETS=('default' 'fallback')\nfallback_image='/boot/initramfs-%s-fallback.img'\nfallback_options='-S autodetect'\n" "$package" >> "/etc/mkinitcpio.d/$package.preset"
    done
    mkinitcpio -P
fi
mkdir -p /usr/lib/modules/0.0-eutherboot-stale
printf 'linux\n' > /usr/lib/modules/0.0-eutherboot-stale/pkgbase
printf '\nPARTUUID=%s /eutherboot vfat defaults 0 2\n' "$(lsblk -ndo PARTUUID /dev/vdc1)" >> /etc/fstab
mkdir -p /etc/eutherboot-test
install -m600 "$payload/owner.key" /etc/eutherboot-test/owner.key
install -m644 "$payload/owner.crt" /etc/eutherboot-test/owner.crt
rm "$payload/owner.key"
# Planning must leave the ESP and root integration unchanged.
[[ ! -e /etc/eutherboot/arch.conf && ! -e /eutherboot/EFI/EutherBoot ]]
args=(install --esp /eutherboot --esp-guid eeeeeeee-1111-4111-8111-eeeeeeeeeeee
      --image "$payload/EutherBoot.efi" --config "$payload/installed.toml"
      --validator "$payload/config-check" --arch --cmdline "$payload/cmdline"
      --arch-files "$payload/arch" --signing-key /etc/eutherboot-test/owner.key
      --signing-cert /etc/eutherboot-test/owner.crt)
# Reproduce the inventoried free-space range on the disposable FAT ESP.
# The fixed 384 MiB guard would pass; the payload-based budget must refuse.
free=$(df -B1 --output=avail /eutherboot | tail -1)
fill=$(( (free - 419*1024*1024) / (1024*1024) ))
(( fill > 0 ))
dd if=/dev/zero of="$payload/capacity-filler" bs=1M count="$fill" status=none
sync -f "$payload"
if python "$payload/eutherbootctl.py" "${args[@]}" --apply >/tmp/capacity-refusal.log 2>&1; then exit 1; fi
grep -F 'ESP needs at least' /tmp/capacity-refusal.log
[[ ! -e /etc/eutherboot/arch.conf && ! -e /eutherboot/EFI/EutherBoot && ! -e /var/lib/eutherboot/installation.json ]]
rm "$payload/capacity-filler"
sync -f "$payload"
python "$payload/eutherbootctl.py" "${args[@]}"
[[ ! -e /etc/eutherboot/arch.conf && ! -e /eutherboot/EFI/EutherBoot ]]
if python "$payload/eutherbootctl.py" "${args[@]}" --esp-guid aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa >/tmp/wrong-esp.log 2>&1; then exit 1; fi
grep -F 'ESP PARTUUID does not match' /tmp/wrong-esp.log
[[ ! -e /etc/eutherboot/arch.conf && ! -e /eutherboot/EFI/EutherBoot ]]
python "$payload/eutherbootctl.py" "${args[@]}" --apply
if python "$payload/eutherbootctl.py" "${args[@]}" --apply >/tmp/duplicate.log 2>&1; then exit 1; fi
grep -F 'Existing EutherBoot installation/path' /tmp/duplicate.log
# Independently import the pristine image's pre-bootstrap-upgrade generation.
# Production prepare() created the current normal/LTS recoveries automatically.
mv /root/eutherboot-original /var/lib/eutherboot/generations/linux-original
bash -c 'source /usr/local/lib/eutherboot/common.sh; make_recovery linux-original linux'
for package in linux linux-lts; do
    for directory in /usr/lib/modules/*; do
        [[ -f $directory/pkgbase && $(cat "$directory/pkgbase") == "$package" ]] || continue
        basename "$directory" > "/var/lib/eutherboot/test-$package-version"
    done
done
sha256sum /eutherboot/EFI/BOOT/BOOTX64.EFI
python "$payload/eutherbootctl.py" status

if [[ $layout == btrfs-at-udev ]]; then
    python - <<'PYCODE'
from pathlib import Path
p=Path('/etc/fstab');lines=[];root_source=None;has_swap_mount=False
for line in p.read_text().splitlines():
    fields=line.split()
    if len(fields)>=2 and fields[1]=='/swap':has_swap_mount=True
    if len(fields)>=4 and fields[1]=='/':
        root_source=fields[0]
        fields[3]=','.join([x for x in fields[3].split(',') if not x.startswith(('subvol=','subvolid='))]+['subvol=@'])
        line='\t'.join(fields)
    lines.append(line)
if not has_swap_mount:
    if root_source is None:
        root_source='PARTUUID=985d9e6f-ac49-4187-86d5-dd967894cf3a'
        lines.append(f'{root_source} / btrfs defaults,subvol=@,compress=zstd:3 0 0')
    lines.append(f'{root_source} /swap btrfs subvol=swap 0 0')
p.write_text('\n'.join(lines)+'\n')
PYCODE
    btrfs subvolume show /swap
    btrfs subvolume snapshot / /@
    sync
fi
