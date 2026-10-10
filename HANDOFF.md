# EutherBoot – handoff inför första fysiska USB-testet

Uppdaterad 2026-10-10. **Fysisk EutherBoot-meny demonstrerad; GRUB-start blockerad av partitionsidentifieringen.**

## Aktuell överlämning

Första fysiska försöket har rapporterats med foto: System Regis-menyn visas,
men valet av befintlig startladdare ger `Missing ESP GUID … Menu retained.`
Linux-inventering bekräftar att konfigurerad PARTUUID och ESP-typ stämmer;
UDisks rapporterar GPT-flaggor 0. GRUB via EutherBoot är inte demonstrerad.

QEMU har reproducerat samma feltext när PartitionInfo-protokollet simuleras
saknat på andra volymer. Tidigare behandlades firmware-status UNSUPPORTED som
om volymen bevisligen inte var en ESP. Koden skiljer nu protokollbrist från
verifierat olämpliga partitioner och rapporterar `Firmware lacks PartitionInfo`.
Detta är en diagnostisk korrigering, ingen verifierad lösning på fysisk uppstart.
Firmware som inte exponerar den interna disken alls är fortfarande en annan
möjlig orsak. F4-resultat eller en ny fysisk diagnostikkörning behövs.
USB är inte omskriven; dess tidigare verifierade innehåll gäller fortfarande.

Lokal reproduktion före korrigeringen:
`artifacts/physical-probe-missing-partition-info-before/`.
Efter korrigeringen:
`artifacts/cross-volume-missing-partition-info-1024x768/`.
Testet använder en separat test-faults-binär och disponibla virtuella diskar.
Verifiering: 25 kärntester, release-bygge utan testfunktioner och fem QEMU-fall
(same-path-self, missing, duplicate, non-esp, missing-partition-info).
Protokollbrist ger också `partial=true` i F4. Testerna jämför hela virtuella
diskens SHA-256 före/efter och provar återgång samt ett fungerande lokalt mål.

Snabbvägen för användaren: spara arbetet → tillfällig UEFI-bootmeny →
**General UDisk** → **Existing boot loader** → vanlig GRUB → Arch.
Vid problem: fotografera sista bilden, stäng av, ta ur USB och använd vanlig
intern uppstart. Den mer kontrollerade testordningen med en vanlig GRUB-start
som jämförelse finns längre ned.

### Fyll i efter försöket

| Kontrollpunkt | Utfall just nu |
| --- | --- |
| USB syns som UEFI-val i firmware | Ej rapporterat |
| EutherBoot-titel och meny visas | Bekräftat på foto |
| Menyn är läsbar och tangentbordet svarar | Ej rapporterat |
| Enter på Existing boot loader visar vanlig GRUB | Ej rapporterat |
| Arch når inloggning/skrivbord | Ej rapporterat |
| Körande kernel efter försöket (`uname -r`) | Ej rapporterat |
| Feltext/foto och sista fungerande steg | Missing ESP GUID; menyn kvar |
| Vanlig intern GRUB-start fungerar utan USB | Ej rapporterat |

Tidigare förslag på första fråga efter återkomst: **”Kom du till EutherBoot, sedan GRUB
och till sist Arch? Om inte, vad var den sista bild eller feltext du såg?”**

## Läs detta först efter omstart

Arbeta i `/run/media/nichlas/Kingston1TB/EutherBoot`. Läs denna fil och
`docs/HOST-COMPATIBILITY.md`, kontrollera Git och de lokala resultatfilerna innan
något byggs om eller skrivs. Fråga efter vad användaren faktiskt såg under testet.
En lyckad Linux-start ensam bevisar inte att vägen gick genom EutherBoot.

Kod och USB-källarkiv bygger på commit `74da2c3`. Efterföljande handoff-commits
ändrar endast dokumentation. Användaren har godkänt återkommande commit/push.
Licens: GPL-3.0-only.

## Vad som nu finns på USB

- General UDisk, 15 728 640 000 byte (cirka 15,7 GB / 14,6 GiB).
- Vid leveransen: `/dev/sdf`, stabil länk `/dev/disk/by-id/usb-General_UDisk-0:0`.
  **Identifiera på nytt efter omstart; enhetsbokstaven får inte återanvändas blint.**
- En 64 MiB FAT32 EFI System Partition, resten oanvänt. Det är avsiktligt.
- Monterad skrivskyddat vid `/run/media/nichlas/F911-7E73` efter leveransen.
- `EFI/BOOT/BOOTX64.EFI`: riktig release av EutherBoot, utan testinstrumentering.
- `EFI/EutherBoot/eutherboot.toml`: ett manuellt val, **Existing boot loader**,
  timeout 0 (ingen automatisk start).
- Målet är den befintliga datorns ESP via explicit PARTUUID och
  `\EFI\BOOT\BOOTX64.EFI`, alltså dess befintliga GRUB. Samma filnamn på USB
  och intern ESP betyder inte samma mål: partitionens identitet styr valet.
- USB innehåller GPL-licensen och matchande källarkiv. Avbilden är osignerad;
  Secure Boot var avstängt vid inventeringen. Ändra inte nycklar eller
  säkerhetsinställningar för att få testet att fungera.

Personliga partitionsidentifierare ligger i ignorerade lokala artefakter,
inte i denna versionshanterade handoff.

## Testordning och återgång

1. Spara pågående arbete. För en tydlig jämförelse: starta först via den vanliga,
   oförändrade GRUB-vägen och kontrollera att Arch fungerar. Inventeringen visade
   körande 7.2.6-arch2-1 men installerad 7.2.9.arch1-1; nästa vanliga start provar
   alltså även en redan väntande kerneluppdatering.
2. Med USB anslutet: starta om och öppna moderkortets **tillfälliga bootmeny**.
   Välj USB-enhetens UEFI-alternativ, exempelvis `UEFI: General UDisk`.
   Ändra inte permanent bootordning. Exakt tangent/etikett är ännu inte verifierad.
3. Kontrollera att EutherBoot/System Regis syns och att menyn är läsbar.
   Notera upplösning, eventuell svart bild och om tangentbordet svarar.
4. Välj **Existing boot loader** och tryck Enter. Bekräfta att den vanliga
   GRUB-menyn verkligen visas, välj sedan normal Arch-start.
5. Efter inloggning: notera `uname -r` och om grafik/inloggning fungerar.
   Rapportera kedjan **firmware → EutherBoot → GRUB → Arch**, steg för steg.

Om USB saknas i bootmenyn, skärmen blir svart eller start misslyckas: fotografera
sista synliga bild/feltext och notera exakt senaste fungerande steg. Stäng av vid
behov, ta ur USB och välj den vanliga interna startvägen. Ingen avinstallation
behövs eftersom ingen EutherBoot-installation gjorts på intern disk.

Om Arch misslyckas även via vanlig GRUB ska det undersökas separat från USB-menyn;
den väntande kerneluppdateringen är en möjlig skillnad, inte en fastställd orsak.
Radera inte befintliga fallback-filer som felsökningsåtgärd.

## Bevis och avgränsningar

Leveransen verifierade:

- Hela 128 MiB råavbilden efter skrivning: SHA-256 stämde exakt.
- GPT-reservtabellen flyttades till USB-enhetens verkliga slut. De skrivna
  GPT-sektorerna återlästes och jämfördes med den validerade GPT-tabellen.
- Hela 64 MiB EFI-partitionen återlästes och jämfördes efter GPT-ändringen.
- Monterad EFI-fil och TOML-konfiguration jämfördes med originalen.
- Den befintliga GRUB-filen på `/boot` hade oförändrad kontrollsumma.

Avbildens SHA-256:
`7cbde55b16dfbfff08072b5af0882511691a39cb7c3e7e7385b262cc91b9295b`

EFI-filens SHA-256:
`c674a24b4b5fc15793fd6775bd0a725599a4cbde753708b66e9c76cd18e6d823`

**Hela USB-enheten ska inte jämföras med råavbildens hash efter GPT-flytten.**
Den är större och GPT-headern är avsiktligt ändrad. EFI-partitionens verifierade hash:
`da10f86d47370b24b11e4830be1c44c96218d5250831d0b7f17fdf3a0b6e8978`

Lokal evidens, avsiktligt Git-ignorerad:

- `artifacts/host-probe/usb-delivery.json`: fysisk skrivning, GPT, återläsning
  och monterad filverifiering. `physical_boot_tested` är fortfarande false.
- `artifacts/host-probe/usb-result.json`: avbildsbyggets QEMU-resultat. Dess
  `physical_media_written: false` beskriver byggsteget före leveransen;
  leveransfilen ovan dokumenterar den senare fysiska skrivningen.
- `artifacts/host-probe/usb-eutherboot.toml`: exakt personlig målkonfiguration.
- `artifacts/host-probe/existing-loader.sha256`: kontrollsumma för intern GRUB.
- `artifacts/host-probe/boot-1/`: bilder från det virtuella avbildstestet.
- `artifacts/host-compatibility.json`: tidigare skrivskyddad värdinventering.
- `artifacts/arch-host-layout/result.json`: godkänd virtuell Arch-matris.

Skrivningen gjordes via UDisks efter användarens systemautentisering. Direkt
`sgdisk` mot den överlämnade filbeskrivaren nekades åtkomst efter lyckad rååterläsning.
GPT justerades därför i en lokal gles fil, validerades, skrevs sektorsvis till
USB och återlästes. En USB-reset noterades i kärnloggen under skrivningen;
slutlig återläsning och monterad kontroll lyckades. Det bevisar inte långvarig
medietillförlitlighet. De lokala flash-skripten är engångsverktyg med låst
sessionsidentitet och ska **inte** köras blint efter omstart.

## Vad detta inte installerar eller bevisar

Ingen ändring av hostens BootOrder, Secure Boot-nycklar, interna partitioner,
bootloaderfiler eller Arch-hooks har gjorts. USB-testet demonstrerar ännu inte
fysisk firmware-, tangentbords-, grafik- eller GRUB-kompatibilitet.

Virtuell testning har demonstrerat Btrfs `@`, ESP vid `/boot`, udev-initramfs,
normal/LTS/recovery, uppgradering och återgång med en **2 GiB virtuell ESP**.
Den installerar inte motsvarande hantering på denna dator. Nuvarande 1 GiB ESP
hade cirka 419 MiB ledigt och normal initramfs cirka 257 MiB. Kapacitetskontrollen
kräver betydligt mer utrymme för UKI-generationer och staging; LTS/ukify och
matchande NVIDIA-stöd saknades också. Full hanterad installation är därför inte
redo här. Extern linux-efi-initrd har dessutom en nuvarande gräns på 128 MiB.

## Nästa utvecklaråtgärd

Samla först det fysiska utfallet. Uppdatera handoff och evidens med observerade
steg, inte antaganden. Vid fel: skilj USB-upptäckt, EFI-start, rendering/input,
partitionsval, GRUB-chainload och Linux-start åt. Gör ett smalt reproducerbart
test för det felande steget innan större kodändringar. Bygg inte om eller flasha
om en redan verifierad sticka enbart för att en ny session har börjat.

En lyckad USB-kedja avslutar första fysiska kompatibilitetsprovet. Full installation
med automatiska Arch-uppdateringar kräver fortfarande separat lagringsplan,
förutsättningar och uttryckligt godkänd installation på den riktiga datorn.
