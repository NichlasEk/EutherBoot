#!/usr/bin/env bash
# QEMU prototype; installed in the guest only by the integration runner.
set -euo pipefail
source /etc/eutherboot-update.conf
fail() { echo "EutherBoot update refused: $*" >&2; exit 1; }
[[ "$ESP_GUID" =~ ^[0-9a-f-]{36}$ ]] || fail 'invalid ESP identity'
mountpoint -q "$ESP_MOUNT" || fail 'ESP is not mounted'
[[ $(findmnt -n -M "$ESP_MOUNT" -o FSTYPE) == vfat ]] || fail 'ESP is not FAT'
device=$(findmnt -n -M "$ESP_MOUNT" -o SOURCE)
[[ $(lsblk -ndo PARTUUID "$device") == "$ESP_GUID" ]] || fail 'wrong ESP partition'
[[ ,$(findmnt -n -M "$ESP_MOUNT" -o OPTIONS), == *,rw,* ]] || fail 'ESP is read-only'
free=$(df -B1 --output=avail "$ESP_MOUNT" | tail -1)
((free > 256*1024*1024)) || fail 'less than 256 MiB free on ESP'
[[ ${1:-} == --check ]] && exit 0
[[ $# == 1 && $1 == /var/lib/eutherboot/arch-linux.efi ]] || fail 'unexpected staging path'
source_image=$1
[[ -f "$source_image" && ! -L "$source_image" ]] || fail 'missing UKI'
[[ $(bootctl kernel-identify "$source_image") == uki ]] || fail 'not a UKI'
exec 9>/run/eutherboot-publish.lock
flock -n 9 || fail 'another publication is running'
directory="$ESP_MOUNT/EFI/Linux"
mkdir -p "$directory"
temporary=$(mktemp "$directory/.arch-linux.XXXXXXXX")
trap 'rm -f "$temporary"' EXIT
cp "$source_image" "$temporary"
cmp "$source_image" "$temporary"
sync -f "$temporary"
# Retain the old image for diagnosis, not as a complete kernel/module rollback.
if [[ -f "$directory/arch-linux.efi" ]]; then
    cp "$directory/arch-linux.efi" "$directory/.arch-linux.previous.new"
    sync -f "$directory/.arch-linux.previous.new"
    mv -f "$directory/.arch-linux.previous.new" "$directory/arch-linux.previous.efi"
fi
mv -f "$temporary" "$directory/arch-linux.efi"
sync -f "$directory"
echo "EUTHERBOOT_UKI_PUBLISHED kernel=${KERNELVERSION:-manual}"
sha256sum "$directory/arch-linux.efi"
