# Direktstart av installerat Arch från separat test-USB

Datum: 2026-10-11. Detta är ett fysiskt prov före intern installation.
Euther Rescue 0.1.1 har nu startat på fysisk dator och användaren bekräftar
att Codex-inloggning fungerar. Rescue-stickan behålls som separat räddningsväg.

## Testets upplägg

En separat Kingston DataTraveler 3.0 (cirka 31 GB) används med användarens
uttryckliga godkännande att ersätta dess tidigare Debian-liveinnehåll. GPT har
en 1 GiB FAT32 EFI-partition; resten lämnas opartitionerat. Ingen säker radering
av alla gamla datasektorer utlovas. Intern ESP, GRUB, fstab, pakethooks och
firmwarets bootordning ändras inte vid förberedelsen.

Menyn använder System Regis, svenska och timeout 0:

1. **Arch Linux direkt** – UKI med kopia av aktuell kärna och normal initramfs.
2. **Arch Linux reserv** – samma kärna med kopia av aktuell fallback-initramfs.
3. **Befintlig GRUB** – befintlig EFI-startfil på uttryckligt identifierad intern ESP.

UKI betyder här att kärna, initramfs, os-release och kommandorad samlas i en
EFI-fil med systemd-stub. EutherBoot startar den som en EFI-applikation; den
separata linux-efi-vägens initrd-gräns används därför inte (128 MiB vid detta
prov, höjd till 512 MiB i EutherBoot 0.1.2).
Ingen kärna eller initramfs optimeras eller byggs om för detta test. Det normala
initramfs-arkivet innehåller redan Intel-mikrokod. systemd-ukify installeras inte
på värden; PE-sektionerna byggs med samma objcopy-metod som Linux-fixturerna.

Den inventerade kärnan är 7.2.9-arch1-1 och matchar modulträdets kernelbild.
Btrfs-root och subvolym `@` behålls från den fungerande kommandoraden.
BOOT_IMAGE, quiet och splash utelämnas; seriell konsol plus skärmkonsol och
loglevel 7 läggs till för diagnos. Markören är
`eutherboot_probe=usb-direct-normal-v1` respektive `usb-direct-fallback-v1`.
Maskinspecifika UUID:n och avbilder ligger bara i ignorerade artefakter.

## Fysiskt prov

1. Mata ut teststickan efter leveransen. Låt rescue-stickan vara orörd.
2. Starta datorn och välj **UEFI: Kingston DataTraveler** i den tillfälliga
   bootmenyn. Secure Boot ska vara avstängt för denna osignerade testutgåva.
3. Välj **Arch Linux direkt** och tryck Enter. Ingen automatisk start sker.
4. När Arch är igång, kontrollera:

   ```sh
   grep -o 'eutherboot_probe=[^ ]*' /proc/cmdline
   uname -r
   findmnt -no SOURCE,FSTYPE,FSROOT /
   ```

   Första kommandot ska visa `eutherboot_probe=usb-direct-normal-v1` och
   rotmonteringen ska fortfarande vara Btrfs-subvolymen `/@`.
5. Vid fel: fotografera sista meddelandet. Starta om och välj **Befintlig GRUB**
   eller den tidigare interna startvägen. Reservposten provar fallback-initramfs,
   men är inte en äldre kärna. Rescue-stickan finns för separat felsökning.

Detta är en snapshot, inte en installerad uppdateringskedja. Uppdatera inte
kärnpaket/moduler mellan skapandet och provet utan att återskapa testavbilden.
Avveckla inte GRUB innan direktstart och återställning verifierats fysiskt.

## Byggning och evidens

`scripts/prepare-direct-probe.py` skapar bara en reguljär avbild. Den öppnar
aldrig fysiska blockenheter. Argument anger lokal kommandoradsfil, mål-ESP:s
PARTUUID och stickans kapacitet. Utdata innehåller två UKI:er, release-EFI,
licens och matchande källarkiv. Samtliga tillagda PE-sektioner extraheras och
hashjämförs med indata.

QEMU ansluter endast avbildsfiler. Den verkliga rotpartitionen är avsiktligt
frånvarande: testet kontrollerar markören i kärnans serielogg och initramfs
väntade fel om saknad root via skärmbild/OCR. Det verifierar inte en fullständig
Arch-inloggning eller NVIDIA på fysisk hårdvara. Tredje menyposten provas med
en disponibel EFI-testapplikation på en virtuell ESP med rätt identitet, inte
med den riktiga GRUB-installationen.

Byggtestet behöver befintlig release, TestChild-fixtur, QEMU/KVM, OVMF,
objcopy, mtools, gptfdisk, Pillow och tesseract med engelska språkdata.
Lokal språkdatakatalog kan anges med `--tessdata-dir`. Slutresultat kräver
`artifacts/direct-probe/result.json`; ett påbörjat bygge räcker inte.
Fysisk leverans och bootfilernas hash finns under `artifacts/direct-delivery/`.
`artifacts/direct-host-inventory/boot-before.json` används för att verifiera
att värdens samtliga bootfiler förblev oförändrade under förberedelsen.

## Leveransresultat

Kingston-stickan är skriven och fsync slutförd. Partitionstabellens båda kopior
matchar och alla sex filer på EFI-partitionen hashmatchar byggunderlaget,
inklusive båda UKI:erna, konfiguration och källarkiv. Alla 366 interna bootfiler
är oförändrade mot inventeringen före testbygget. Stickan lämnades skrivskyddat
monterad på `/run/media/nichlas/1DB6-0A6D`. Ingen separat full återläsning av
hela mediet gjordes; opartitionerade sektorer behövde inte skrivas över.

Det första testförsöket väntade felaktigt på initramfs-text på serieporten.
Oraklet ändrades till kärnmarkör plus skärmbild/OCR; engelska OCR-data hämtades
lokalt. Sluttestet passerade normal, fallback och reservpostens EFI-volymval.
Fysisk direktstart är nästa verifieringssteg.
