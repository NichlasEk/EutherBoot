#!/usr/bin/env bash
set -euo pipefail
[[ $(findmnt -n --nofsroot -o SOURCE /) == /dev/vdb3 ]]
systemd-detect-virt --quiet --vm
mkdir -p /etc/pacman.d/hooks /root/hook-fixture/usr/lib/modules/0.0-test/extramodules
# Isolate trigger semantics from upstream initramfs generation in this guest.
ln -s /dev/null /etc/pacman.d/hooks/90-mkinitcpio-install.hook
for phase in pre post; do
    name=05-eutherboot.hook; [[ $phase == pre ]] || name=99-eutherboot.hook
    sed "s|^Exec = .*|Exec = /root/hook-oracle $phase|" "/hook-esp/EFI/Hooks/$name" > "/etc/pacman.d/hooks/$name"
done
cat > /root/hook-oracle <<'ORACLE'
#!/usr/bin/env bash
set -eu
printf '%s\n' "$1" >> /root/hook-events
if [[ $1 == pre ]]; then
    [[ ! -e /root/refuse-transaction ]]
    [[ ! -e /usr/lib/modules/0.0-test/extramodules/fixture.ko ]]
else
    [[ $(cat /usr/lib/modules/0.0-test/extramodules/fixture.ko) == original ]]
fi
ORACLE
chmod 755 /root/hook-oracle
cd /root/hook-fixture
printf 'original\n' > usr/lib/modules/0.0-test/extramodules/fixture.ko
cat > .PKGINFO <<'INFO'
pkgname = eutherboot-hook-fixture
pkgver = 1-1
pkgdesc = Disposable path-trigger oracle
url = https://example.invalid/
builddate = 1700000000
packager = EutherBoot test
size = 9
arch = any
INFO
tar -cf /root/fixture.tar .PKGINFO usr
pacman -U --noconfirm /root/fixture.tar
printf 'pre\npost\n' > /root/expected-events
cmp /root/expected-events /root/hook-events
# A second transaction must be aborted before changing any package payload.
touch /root/refuse-transaction
sed -i 's/pkgver = 1-1/pkgver = 2-1/' .PKGINFO
printf 'changed\n' > usr/lib/modules/0.0-test/extramodules/fixture.ko
tar -cf /root/fixture2.tar .PKGINFO usr
if pacman -U --noconfirm /root/fixture2.tar; then exit 1; fi
[[ $(pacman -Q eutherboot-hook-fixture) == 'eutherboot-hook-fixture 1-1' ]]
[[ $(cat /usr/lib/modules/0.0-test/extramodules/fixture.ko) == original ]]
printf 'pre\npost\npre\n' > /root/expected-events
cmp /root/expected-events /root/hook-events
echo PATH_HOOKS_AND_ABORT_VERIFIED
