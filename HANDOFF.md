# EutherBoot – handoff inför omstart och fysiskt test av 0.1.1

Uppdaterad 2026-10-11. **USB 0.1.1 är levererad och återläst. Nästa steg är
användarens fysiska F4-test, inte ett nytt bygge eller en ny skrivning.**

## Börja här efter omstart

1. Arbeta i `/run/media/nichlas/Kingston1TB/EutherBoot` och läs denna fil.
2. Samla användarens foto/resultat: syntes **0.1.1**, vad visade **F4**, kom
   **Existing boot loader** vidare till GRUB och sedan Arch?
3. Läs `artifacts/host-probe-0.1.1/usb-delivery.json` och `usb-result.json`.
   Kontrollera `git status --short --branch` och `git log -3 --oneline`.
4. Om stickan behöver läsas: identifiera enhet, PARTUUID, storlek och mount på
   nytt. Återanvänd aldrig `/dev/sdf` eller diskseq från förra sessionen blint.
5. Undersök det observerade felsteget innan någon kod eller USB ändras.
   En vanlig Linux-start bevisar inte att vägen gick genom EutherBoot.

Användaren har godkänt återkommande commit/push och bad uttryckligen om
kompatibilitetsfixen och USB-uppdateringen. Ingen full installation på intern
disk är beställd. Licens: GPL-3.0-only.

## Aktuell leverans

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
QEMU-testprogrammet är inte GRUB; fysisk GRUB-/Arch-kompatibilitet återstår.

## Användarens nästa test

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
| Fysisk meny visar 0.1.1 | Väntar på användarens test |
| F4: antal filsystem/ESP och identifieringsfel | Väntar på foto |
| F4: intern GRUB-fil syns | Ej verifierat |
| Existing boot loader → vanlig GRUB | Ej verifierat |
| GRUB → Arch/skrivbord | Ej verifierat |
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
