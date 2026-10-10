#!/usr/bin/env bash
set -euo pipefail
source /etc/eutherboot-update.conf
publish=/usr/local/lib/eutherboot/publish
expect_refusal() {
    local reason=$1; shift
    if "$@" > /run/eutherboot-refusal.log 2>&1; then
        echo "Unexpected success: $*" >&2; exit 1
    fi
    cat /run/eutherboot-refusal.log
    grep -Fq "$reason" /run/eutherboot-refusal.log
}
sha256sum -c /var/lib/eutherboot/uki-after.sha256
package=$(find /var/cache/pacman/pkg -maxdepth 1 -name 'linux-[0-9]*-x86_64.pkg.tar.zst' | head -1)
[[ -n "$package" ]]
pacman -Q linux > /run/eutherboot-package-before
umount "$ESP_MOUNT"
expect_refusal 'ESP is not mounted' pacman -U --noconfirm "$package"
pacman -Q linux | cmp /run/eutherboot-package-before -
mount "$ESP_MOUNT"
sha256sum -c /var/lib/eutherboot/uki-after.sha256
echo 'FAILURE_CHECK_MISSING_ESP_PASS'
mount -o remount,ro "$ESP_MOUNT"
expect_refusal 'ESP is read-only' "$publish" --check
mount -o remount,rw "$ESP_MOUNT"
echo 'FAILURE_CHECK_READONLY_ESP_PASS'
umount "$ESP_MOUNT"
mount -o ro /dev/vdb2 "$ESP_MOUNT"
expect_refusal 'wrong ESP partition' "$publish" --check
umount "$ESP_MOUNT"; mount "$ESP_MOUNT"
echo 'FAILURE_CHECK_WRONG_ESP_PASS'
mv /var/lib/eutherboot/arch-linux.efi /var/lib/eutherboot/arch-linux.valid
printf 'incomplete UKI' > /var/lib/eutherboot/arch-linux.efi
expect_refusal 'not a UKI' "$publish" /var/lib/eutherboot/arch-linux.efi
mv /var/lib/eutherboot/arch-linux.valid /var/lib/eutherboot/arch-linux.efi
sha256sum -c /var/lib/eutherboot/uki-after.sha256
echo 'FAILURE_CHECK_INVALID_UKI_PASS'
# A normal cached-package reinstall must replace an existing UKI through the hook.
old_hash=$(sha256sum "$ESP_MOUNT/EFI/Linux/arch-linux.efi" | cut -d' ' -f1)
pacman -U --noconfirm "$package"
[[ $(sha256sum "$ESP_MOUNT/EFI/Linux/arch-linux.previous.efi" | cut -d' ' -f1) == "$old_hash" ]]
cmp /var/lib/eutherboot/arch-linux.efi "$ESP_MOUNT/EFI/Linux/arch-linux.efi"
sha256sum "$ESP_MOUNT/EFI/Linux/arch-linux.efi" > /var/lib/eutherboot/uki-after.sha256
echo 'SUCCESSFUL_REPLACEMENT_PASS'
# An abandoned partial staging file must not replace or become the default target.
head -c 1048576 /var/lib/eutherboot/arch-linux.efi > "$ESP_MOUNT/EFI/Linux/.arch-linux.interrupted"
sync
sha256sum -c /var/lib/eutherboot/uki-after.sha256
echo 'FAILURE_CHECK_ABANDONED_STAGE_PASS'
