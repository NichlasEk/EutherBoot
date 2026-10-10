# SPDX-License-Identifier: GPL-3.0-only
# Sourced by root-owned Arch integration scripts, never by the firmware.
set -euo pipefail
CONFIG=/etc/eutherboot/arch.conf
[[ -f $CONFIG && ! -L $CONFIG && $(stat -c %u "$CONFIG") == 0 ]]
source "$CONFIG"
STATE=/var/lib/eutherboot
fail() { echo "EutherBoot: $*" >&2; exit 1; }
valid_token() { [[ $1 =~ ^[a-zA-Z0-9][a-zA-Z0-9._+-]{0,127}$ ]]; }
check_esp() {
    mountpoint -q "$ESP_MOUNT" || fail 'ESP is not mounted'
    [[ $(findmnt -n -M "$ESP_MOUNT" -o FSTYPE) == vfat ]] || fail 'ESP is not FAT'
    local device; device=$(findmnt -n -M "$ESP_MOUNT" -o SOURCE)
    [[ $(lsblk -ndo PARTUUID "$device") == "$ESP_GUID" ]] || fail 'wrong ESP partition'
    [[ $(lsblk -ndo PARTTYPE "$device") == c12a7328-f81f-11d2-ba4b-00a0c93ec93b ]] || fail 'partition is not an ESP'
    [[ ,$(findmnt -n -M "$ESP_MOUNT" -o OPTIONS), == *,rw,* ]] || fail 'ESP is read-only'
    if [[ ${1:-write} == write ]]; then
        local free; free=$(df -B1 --output=avail "$ESP_MOUNT" | tail -1)
        (( free > 384*1024*1024 )) || fail 'less than 384 MiB free on ESP'
    fi
}
check_generation() {
    local generation=$1
    valid_token "$generation" || fail 'invalid generation'
    [[ -d $STATE/generations/$generation && ! -L $STATE/generations/$generation ]] || fail 'missing generation'
    (cd "$STATE/generations/$generation"; sha256sum --quiet -c SHA256SUMS) || fail 'generation checksum mismatch'
}
publish_file() {
    local source=$1 target=$2 temporary
    [[ $(bootctl kernel-identify "$source") == uki ]] || fail 'not a UKI'
    temporary=$(mktemp "${target}.new.XXXXXXXX")
    if ! cp "$source" "$temporary" || ! cmp "$source" "$temporary" || ! sync -f "$temporary"; then
        rm -f "$temporary"; fail 'staging UKI failed; active target retained'
    fi
    mv -f "$temporary" "$target"
    sync -f "$(dirname "$target")"
}
sign_image() {
    local image=$1
    if [[ -n ${SIGNING_KEY:-} ]]; then
        [[ -f $SIGNING_KEY && -f $SIGNING_CERT ]] || fail 'signing material unavailable'
        sbsign --key "$SIGNING_KEY" --cert "$SIGNING_CERT" --output "$image.signed" "$image"
        sbverify --cert "$SIGNING_CERT" "$image.signed"
        mv -f "$image.signed" "$image"
    fi
}
make_recovery() {
    local generation=$1 package=$2 previous recovery directory
    check_generation "$generation"
    previous="$STATE/generations/$generation"
    [[ $(cat "$previous/package") == "$package" ]] || fail 'recovery package mismatch'
    directory="$ESP_MOUNT/EFI/EutherBoot/kernels"
    mkdir -p "$directory" "$STATE/staging"
    recovery=$(mktemp "$STATE/staging/recovery.XXXXXXXX.efi")
    /usr/lib/systemd/ukify build --linux "$previous/modules/vmlinuz" --initrd "$previous/initrd.img" \
        --cmdline "@$previous/cmdline" --uname "$(cat "$previous/version")" --output "$recovery"
    sign_image "$recovery"
    publish_file "$recovery" "$directory/recovery-$generation.efi"
    # Never rotate the normal recovery entry away from a known-good generation
    # merely because another kernel was installed but has not booted yet.
    local confirmed=0
    if [[ -f $STATE/$package.confirmed && -f $directory/$package.efi ]]; then
        [[ $(cat "$STATE/$package.confirmed") == "$(sha256sum "$directory/$package.efi" | cut -d' ' -f1)" ]] && confirmed=1
    fi
    if [[ ! -f $directory/$package-previous.efi || $confirmed == 1 ]]; then
        publish_file "$recovery" "$directory/$package-previous.efi"
        printf '%s\n' "$generation" > "$STATE/$package-previous.new"
        mv "$STATE/$package-previous.new" "$STATE/$package-previous"
    fi
    rm -f "$recovery" "$recovery.signed"
    sync -f "$STATE"
}
