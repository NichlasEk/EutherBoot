# Installera EutherBoot 0.1.2 på Debian-datorn

Denna guide är för Codex-sessionen som användaren startar från Euther Rescue.
Användaren vill uppdatera EutherBoot på Debian 13-datorn som visar
`Linux EFI setup: BAD_BUFFER_SIZE`. Windows reparation och Pop!_OS har startat
via F4 på samma dator. Maskinens exakta installation är ännu inte inventerad.

## Medföljande rättelse

`/usr/local/share/euther-rescue/EutherBoot.efi` är produktionsversion 0.1.2,
utan QEMU-debug. Direktstart med `type='linux-efi'` accepterar nu initrd på
1–536 870 912 byte (512 MiB), i stället för högst 128 MiB. Tom/större initrd,
för lång kommandorad och initrd som växer under läsning ger särskilda feltexter.
Minnesbrist returnerar fortfarande ett fel till menyn.

Samma katalog innehåller `manifest.json`, `SHA256SUMS` och matchande
`eutherboot-source.tar.gz` med offlineberoenden. `manifest.json` identifierar
den exakta EFI-filen och källarkivet. `SHA256SUMS` beskriver hela releasepaketet;
ISO:n innehåller dess EFI/källarkiv/manifest, inte nödvändigtvis alla andra filer.
Verifiera de medföljande filerna specifikt:

```sh
cd /usr/local/share/euther-rescue
python - <<'PY'
import hashlib,json
from pathlib import Path
m=json.loads(Path('manifest.json').read_text())
for name in ('EutherBoot.efi','eutherboot-source.tar.gz'):
    with open(name,'rb') as f: actual=hashlib.file_digest(f,'sha256').hexdigest()
    assert actual == m['files'][name], name
    print(name,actual)
assert m['qemu_debug'] is False
PY
```

## Inventera och välj rätt installation

1. Läs `lsblk -o NAME,PATH,TRAN,MODEL,SERIAL,SIZE,FSTYPE,LABEL,UUID,PARTUUID,MOUNTPOINTS`
   och `efibootmgr -v`. Identifiera räddnings-USB separat från interna diskar.
2. Montera relevanta Debian-root/boot/ESP läsande, med rätt filsystem och
   subvolym. Läs Debians `/etc/os-release` och `/etc/fstab` samt EFI-filer och
   EutherBoot-konfiguration. Ingen värddators Arch-UUID från repo-HANDOFF ska
   återanvändas: den avser en annan maskin.
3. Identifiera den EutherBoot-EFI som verkligen startas. Kontrollera eventuell
   fallback `EFI/BOOT/BOOTX64.EFI`, firmwarepostens sökväg och placeringen av
   tillhörande `EFI/EutherBoot/eutherboot.toml`. Ersätt aldrig en okänd
   Microsoft-, shim-, GRUB- eller systemd-boot-fil för att den heter BOOTX64.EFI.
4. Läs Debian-postens `type`, `path`, `initrd`, `cmdline` och `partition_guid`.
   Mät just den valda initrd-filens byteantal och läs kernelns cmdline-gräns
   om storleken inte förklarar felet. Kontrollera att filerna är rätt Debian-
   version och att `root=` pekar på Debian. 128 MiB-felet är reproducerat i
   QEMU; fysisk orsak är ännu inte bekräftad.

## Utför den beställda uppdateringen

När rätt EutherBoot-installation är identifierad och användaren ber om
installationen: säkerhetskopiera dess EFI, källarkiv och konfiguration med
SHA-256 till beständig data eller den installerade rotpartitionen. Lämna en
återställningsinstruktion med exakta, verifierade sökvägar.

Montera rätt ESP skrivbart. Kopiera den medföljande 0.1.2-EFI:n till en
temporär fil i samma katalog som den identifierade aktiva EutherBoot-filen.
Synka och kontrollera full SHA-256 före namnbyte. Uppdatera också installationens
matchande `source.tar.gz` från det medföljande källarkivet. Synka och läs tillbaka
båda slutliga filerna; jämför mot releasemanifestet. Behåll befintlig meny,
kernel, initrd och cmdline om inventeringen inte visar ett konkret fel i dem.

Uppdateringen kräver inte att GRUB tas bort, att firmwareordningen ändras eller
att någon partition formateras. Om EutherBoot inte finns på intern disk ska
en ny installation behandlas som ett eget steg med verifierad startväg och
bevarad befintlig Debian-bootloader; gissa inte ett ersättningsmål.

Spara resultat, filhashar och återgång i arbetskatalogen och på beständig data.
Avmontera/synka inför användarens omstart. Fysisk Debian-start och skrivbord
är godkända först efter faktisk omstart och användarens bekräftelse.

`known-good/` är en äldre privat kopia från Arch-datorn. Den får inte återställas
över Debian-datorn. Den nya 0.1.2-releasen ovan är uppdateringskällan.
