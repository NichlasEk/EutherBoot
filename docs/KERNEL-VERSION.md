# Kärnversion i startmenyn

Menyn läser versionen ur respektive startfil på den konfigurerade volymen.
UKI använder `.uname`, annars läses x86-bootheadern i `.linux`. Direkta
x86-kärnfiler använder samma bootheader. Versionen visas under OS-namnet
med 13-punkters text, i textläget och i den grafiska menyförhandsvisningen.
Långa versioner förkortas med `...` i ikonrutorna.

Informationen är endast visningsmetadata: läsfel påverkar inte startpolicyn.
Filer öppnas läsande och hela kärnan eller initrd läses aldrig in för detta.
Högst 96 PE-sektioner granskas; versionstext begränsas till 128 ASCII-tecken.
UKI med `.profile` visas utan version eftersom profilen kan välja annan kärna.
Kedjestart via GRUB/annan bootloader visar ingen version för den senare kärnan.

Formatreferenser:

- [Unified Kernel Image](https://uapi-group.org/specifications/specs/unified_kernel_image/)
- [Linux x86 boot protocol](https://www.kernel.org/doc/html/latest/arch/x86/boot.html)

Verifiering: `bash scripts/build.sh` och
`python3 scripts/test-kernel-version-qemu.py`. QEMU-provet använder kopior av
`/boot/EFI/Linux/arch-normal.efi` och `arch-lts.efi` på disponibla diskar,
en syntetisk direktkärna samt ett startbart EFI-testprogram utan version.
Värdens diskar ansluts aldrig till gästen. Resultat och bilder hamnar i
`artifacts/kernel-version/`.
