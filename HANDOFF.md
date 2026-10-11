# EutherBoot – System Regis och rescue-USB

Uppdaterad 2026-10-11. **Fysiskt test godkänt enligt foto och användarens rapport:
F4 → Esc → huvudmeny → befintlig bootloader → GRUB → Arch.**

Ny inventering: körande och installerad kärna är 7.2.9-arch1-1. På `/boot`
finns en aktuell kärna, normal- och fallback-initramfs; inga gamla kärnavbilder
hittades. Ledigt: 438 767 616 byte (418,4 MiB). Gamla modulrester om cirka
166,1 MiB finns på rotpartitionen, inte ESP:n. Inget har raderats.
Se `docs/HOST-COMPATIBILITY.md` för utrymmesstatus.


## Rescue-arbetet 2026-10-11

Grafiska System Regis-menyn med godkänt stål-/guldemblem och inställbar
nedräkning är pushad i `17e20d9`. Den nya grafiken är QEMU-testad; det
fysiskt bekräftade startförloppet ovan avser fortfarande äldre 0.1.1.

Användaren beställde Arch rescue-USB med förinstallerad Codex och godkände
uttryckligen att skriva över den anslutna General UDisk-stickan. Rescue har
egen systemd-boot-start, svensk konsol, Codex CLI 0.162.1 och manuellt ansluten
ext4-arbetsdata. Intern boot, GRUB och NVRAM ska inte ändras av leveransen.

390 filer från den senast fungerande EFI-kedjan har kopierats och verifierats:
den tidigare levererade USB-kedjan, interna ESP:n, konfiguration och UUID-data.
Kopian och ISO:n är privata ignorerade artefakter under `artifacts/rescue/`.
Läs [rescue/README.md](rescue/README.md) för byggning och användning.

Resultatfiler: `build-result.json`, `test-result.json`, `usb-test-result.json`
och efter lyckad fysisk skrivning `usb-delivery.json`. Läs dessa före nya
åtgärder; återskapa eller skriv inte om en redan verifierad sticka utan skäl.
Den medföljande källkopian i ISO:n är en snapshot av `17e20d9`; dess HANDOFF
beskriver det äldre fysiska testet, inte den nya rescue-leveransen.

## Aktuell leverans och editor

Rescue-stickan är färdigskriven och fsync slutförd. Full återläsning hoppades
över på användarens uttryckliga begäran. GPT i båda ändar matchade avbilden,
EFI-filer kontrollerades och EFI-/datapartitionerna monterades. Se lokal
`artifacts/rescue/usb-delivery.json`. Fysisk start och autentiserad Codex återstår.
Stickan är osignerad; första testet kräver UEFI med Secure Boot avstängt.
Interna `/boot` har verifierats oförändrat mot tidigare 366 filhashar.

Grafisk editor, svenska namn/texter och tre grafiska paletter plus textläge
är implementerade. G byter tema, L språk; F2 ger tillfällig textreserv.
Se [editorbeskrivningen](docs/design/EDITOR.md). Rescue-avbildens källsnapshot
är fortfarande `17e20d9` och innehåller inte dessa senare editorändringar.
Användaren testar stickan på en annan dator medan en modell laddas ned här:
starta inte om värddatorn. Nästa prioriteringar finns i
[rEFInd-genomgången](docs/REFIND-REVIEW.md).

## Börja här efter omstart

1. Läs aktuell rescue-status nedan. Den gamla 0.1.1-leveransen är historik. Arbeta i `/run/media/nichlas/Kingston1TB/EutherBoot`.
2. Foto och rapport finns sammanfattade nedan; evidens finns i
   `artifacts/physical-0.1.1/`. Vanlig intern start utan USB är ännu inte separat rapporterad.
3. Läs `artifacts/host-probe-0.1.1/usb-delivery.json` och `usb-result.json`.
   Kontrollera `git status --short --branch` och `git log -3 --oneline`.
4. Om stickan behöver läsas: identifiera enhet, PARTUUID, storlek och mount på
   nytt. Återanvänd aldrig `/dev/sdf` eller diskseq från förra sessionen blint.
5. Undersök det observerade felsteget innan någon kod eller USB ändras.
   En vanlig Linux-start bevisar inte att vägen gick genom EutherBoot.

Användaren har godkänt återkommande commit/push och bad uttryckligen om
kompatibilitetsfixen och USB-uppdateringen. Ingen full installation på intern
disk är beställd. Licens: GPL-3.0-only.

## Historisk leverans: EutherBoot 0.1.1

- **EutherBoot 0.1.1**, kod och matchande källarkiv från commit `8e205dd`.
  Senare handoff-commits ändrar bara dokumentation. Kod och leveransnotering
  är pushade till `origin/main` på `https://github.com/NichlasEk/EutherBoot`.
- **General UDisk**, 15 728 640 000 byte, stabil länk
  `/dev/disk/by-id/usb-General_UDisk-0:0`. Vid leverans: `/dev/sdf`.
- 64 MiB FAT32 ESP; resterande utrymme oanvänt. Efter verifiering lämnades
  den skrivskyddat monterad vid `/run/media/nichlas/F911-7E73`.
- `EFI/BOOT/BOOTX64.EFI`: release utan QEMU-/felinjektion.
- `EFI/EutherBoot/source.tar.gz`: matchande källkod och offlineberoenden.
- `EFI/EutherBoot/eutherboot.toml`: **Existing boot loader**, timeout 0,
  explicit intern ESP-PARTUUID och `\EFI\BOOT\BOOTX64.EFI` (befintlig GRUB).
  Personliga identifierare finns i ignorerade artefakter.
- EFI-filen och källarkivet uppdaterades med fsync. Efter av-/återmontering
  stämde SHA-256 för båda samt konfigurationen. Konfiguration och intern GRUB
  är oförändrade. Ingen GPT-/partitionsändring gjordes vid 0.1.1-uppdateringen.

EFI SHA-256:
`82ac7c5f8b117a42812eeec6455be463749f44ddf15468696e5ce88c738c32ab`

Källarkiv SHA-256:
`cbfff7150fb8e3f1fd550dacc27e4a8b8042e6e4983c3ea341856c587484165d`

## Vad som är observerat och vad som återstår

Första fysiska försöket, version 0.1.0: foto visar System Regis-menyn och
`Missing ESP GUID … Menu retained.` GRUB via EutherBoot demonstrerades inte.
Linux-inventering bekräftade rätt mål-PARTUUID, ESP-typ och GPT-flaggor 0.

QEMU reproducerade samma feltext när PartitionInfo simulerades saknat.
Det är ett verifierat kodproblem men **inte bevis för den fysiska orsaken**.
Version 0.1.1 har en reservväg som läser primär GPT via redan exponerade
BlockIO-enheter, verifierar header-/tabell-CRC, gränser, ESP-typ, GUID och exakt
start/storlek mot enhetssökvägen. Den skriver inte till disk, reparerar inte GPT,
ansluter inte kontroller och laddar inga lagringsdrivrutiner.

F4 visar nu antal firmware-filsystem, verifierade ESP:er och första
identifieringsfelet. Om firmware inte exponerar den interna disken alls kan
reservvägen inte hitta den. Det är fortfarande ett separat möjligt felspår.

Verifierat lokalt:

- 29 kärntester inklusive felaktig CRC, längder, GUID/geometri, attribut och 4K-block.
- QEMU-start, återgång och F4 utan PartitionInfo på samtliga volymer.
- Saknade/dubbla GUID och icke-ESP avvisas även med GPT-reservvägen.
- Normal startväg och F4 vid 640×480 fungerar.
- Exakt releaseavbild startar ett testprogram på en separat virtuell ESP och
  återgår till menyn. Hela virtuella diskars kontrollsummor är oförändrade.
- Fysiska USB-filer återlästa enligt leveransen ovan.

Clippy kördes inte: komponenten saknas i den lokala verktygskedjan.
QEMU-testprogrammet är inte GRUB. Användaren har nu separat bekräftat fysisk
GRUB-start och Arch-inloggning via EutherBoot 0.1.1.

## Genomfört fysiskt test (ursprungliga instruktioner)

1. Spara arbetet och öppna firmwarets tillfälliga bootmeny.
2. Välj **General UDisk**, kontrollera **0.1.1** nere till höger.
3. Tryck **F4** och fotografera hela sökresultatet, inklusive antal och feltext.
4. Tryck **Esc**, välj **Existing boot loader** och tryck Enter.
5. Notera om vanlig GRUB visas och om Arch når skrivbordet. Efter inloggning:
   notera `uname -r`. Om fel uppstår, fotografera sista bilden.

Vid problem: stäng av vid behov, ta ur USB och använd den vanliga interna
startvägen. Ingen avinstallation behövs. Ändra inte permanent bootordning eller
Secure Boot-nycklar. Om Arch även misslyckas via vanlig GRUB, undersök det separat.
Äldre kernelinventering är historisk; kontrollera aktuella versioner vid behov.

| Kontrollpunkt för 0.1.1 | Status |
| --- | --- |
| Fysisk meny visar 0.1.1 | Foto visar 0.1.1 i F4 |
| F4: antal filsystem/ESP och identifieringsfel | Foto: 2 filsystem, 2 verifierade ESP, 1 app, 1 överhoppad; inget identifieringsfel visas |
| F4: intern GRUB-fil syns | Foto visar ESP och `\EFI\BOOT\BOOTX64.EFI`; direktstart från F4 ej testad |
| Existing boot loader → vanlig GRUB | Bekräftat av användaren efter Esc från F4 |
| GRUB → Arch/skrivbord | Bekräftat av användaren; aktuell uname: 7.2.9-arch1-1 |
| Vanlig intern start utan USB | Inget separat kontrollresultat rapporterat |

## Evidens och återgångsfiler

Alla nedanstående artefakter är avsiktligt Git-ignorerade:

- `artifacts/host-probe-0.1.1/usb-delivery.json`: aktuell fysisk leverans/återläsning.
- `artifacts/host-probe-0.1.1/usb-result.json`, `boot-1/`, `usb.img`: release-QEMU.
  `physical_media_written: false` i byggresultatet gäller avbildssteget;
  den efterföljande filuppdateringen dokumenteras i leveransfilen.
- `artifacts/host-probe/pre-gpt-update/`: tidigare EFI, konfiguration och källarkiv.
- `artifacts/physical-first-attempt/menu-missing-esp.png`: första fysiska fotot.
- `artifacts/physical-probe-missing-partition-info-before/`: ursprunglig reproduktion.
- `artifacts/cross-volume-missing-partition-info-1024x768/`: senaste lyckade reservvägstest.
- `artifacts/cross-volume-*-gpt/`: negativa/positiva fall med reservvägen.
- `artifacts/host-probe/usb-delivery.json`: historisk 0.1.0-leverans.
  Dess EFI-/hel-ESP-hash gäller **inte** den uppdaterade stickan.

Lokala flash-/update-skript är engångsverktyg låsta till sessionsidentitet.
Kör dem inte blint efter omstart. Ingen omskrivning behövs för att samla F4-resultatet.

## Avgränsning mot full installation

BootOrder, Secure Boot-nycklar, interna partitioner, bootloaderfiler och Arch-hooks
har inte ändrats. Läs `docs/HOST-COMPATIBILITY.md` före eventuell installationsplan.
Tidigare inventering visade otillräckligt ESP-utrymme för hanterade UKI-generationer
samt saknade LTS/ukify-förutsättningar. Den virtuella Arch-matrisen använde en
2 GiB ESP och verifierar inte värdens NVIDIA-drivrutin eller fysiska firmware.
Full installation kräver separat lagringsplan och uttrycklig beställning.

## Pågående visuellt arbete efter det fysiska testet

Den lokala huvudmenyn har nu mörkblå/guld-palett, tre kronor, inbäddade
kantutjämnade typsnitt, ikonkort, rundade ramar och vänster/höger-navigation.
Se `PLAN.md` för riktningen från EutherFPScan. F4/editor använder fortsatt
textvyer. UI-bygget har fortfarande versionsnummer 0.1.1 och är ett lokalt
utvecklingsbygge: det är inte den hashidentifierade USB-leveransen ovan.
Ingen ny USB-skrivning, intern installation eller fysisk UI-verifiering har gjorts.
Artefakter: `artifacts/regis-ui-result.json` och `artifacts/qemu-*/`.

### Godkänt emblem och autoboot

Det godkända stålsvärdet med tre guldkronor är nu inbäddat som RGBA-bild i
UI-bygget. Den grafiska menyn visar en sekundnedräkning vid positiv timeout.
Arch-installationens mall använder 10 sekunder; testkonfigurationen och den
redan levererade USB-konfigurationen har fortsatt explicit 0. Befintliga
konfigurationer skrivs inte om. F3/E/T/S/Y ändrar och sparar timeout.
Den separata starttimern förblir styrande; en tangent avbryter båda timers.
Ingen ny fysisk leverans eller fysisk test av dessa ändringar har gjorts.
Se `artifacts/regis-emblem-countdown-result.json` för aktuell QEMU-status.
