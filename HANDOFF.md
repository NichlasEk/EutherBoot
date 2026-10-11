# EutherBoot – System Regis och rescue-USB

## Ny räddningsutgåva 0.1.2 för Debian · 2026-10-11

EutherBoot 0.1.2 höjer direktstartens initrd-gräns till **512 MiB** och skiljer
storleksfel, för lång cmdline och växande initrd i feltexten. Debian 13 har i
QEMU startat med 128 MiB + 1 byte och exakt 512 MiB; 512 MiB + 1 byte, tom
initrd och för liten kernel-cmdlinekapacitet avvisas med fungerande reservval.

Euther Rescue 0.1.2 är levererad på General UDisk med denna produktions-EFI, matchande källarkiv,
ny källsnapshot och `/usr/local/share/euther-rescue/INSTALL-DEBIAN.md`.
**På Debian-datorn ska Codex börja med den guiden.** Arch-identiteterna längre
ned gäller en annan dator och ska inte användas som installationsmål där.
`rescue-start` använder `EutherBoot-0.1.2` så att en gammal arbetskopia inte
skymmer rättelsen.

Hela stickans **15 728 640 000 byte** har lästs tillbaka efter skrivning och
fsync; SHA-256 matchar den QEMU-testade USB-avbilden:
`76e54df30b08fc6d701be9e6d057f586f5114b7322b367b478b3049c88ff9b75`.
Kontrollen gjordes före återmontering. Partitionsgeometri, sex ESP-filer och
den inbyggda 0.1.2-EFI:n, källarkivet och Debian-guiden verifierades också.
Datapartitionen är monterad på `/run/media/nichlas/EUTHERDATA`.
Mata ut stickan före fysisk flytt. Ingen intern EFI/NVRAM har ändrats här.

ISO: `artifacts/rescue/euther-rescue-0.1.2-x86_64.iso`.
ISO SHA-256: `5a10ca0138d4a35f275e50fa9078af2fb9cdec4c76b38a1ce3e7ae80a7cf05e5`.
Medföljande EutherBoot-EFI SHA-256:
`7ecc51be45799dc07ae7dc80032f3898ca5d713673f6172bc487d4b70a57c91f`.
ISO/USB har vardera klarat två QEMU-starter, nätverk och beständig arbetsdata.
Codex når inloggningsvyn med ISO:ns egna startskript. Evidens:
`artifacts/rescue/usb-delivery.json` och `release-012-validation.json`.
Privata ISO-/backup-/loggartefakter är fortsatt Git-ignorerade.

Nästa steg på Debian-datorn: starta General UDisk, kör
`codex login --device-auth`, sedan `rescue-start`. Be Codex läsa
`/usr/local/share/euther-rescue/INSTALL-DEBIAN.md` och installera den medföljande
0.1.2-versionen på den identifierade Debian-installationen. **Fysisk start av
nya räddningsutgåvan och faktisk Debian-start efter installation återstår.**

USB-provet hittade också att Archiso:s UUID-sökning ibland monterade hela
USB-disken som ISO och blockerade EUTHERDATA. USB-avbildens startpost binds nu
till ISO-partitionens exakta PARTUUID; testet kontrollerar att den emulerade
USB-starten faktiskt monterar en partition. Interna partitioner behöver inte
sökas igenom för att hitta live-systemet.

## Historik: första Debian 13-undersökningen · 2026-10-11

Användarens andra dator visar `Linux EFI setup: BAD_BUFFER_SIZE`; Windows
reparation och Pop!_OS startade via F4 enligt användaren. Fler fysiska prov
väntar. Debian 13:s officiella cloudbild har nu provats i QEMU: originalets
initrd på 36 847 801 byte startar till inloggning, samma fil nollutfylld till
134 217 729 byte ger exakt feltexten. Ett separat experimentbygge med enbart
128 → 256 MiB initrd-gräns startar också den stora filen till inloggning.

Det bekräftar felmekanismen i emulatorn, **inte orsaken på den fysiska datorn**.
Nästa kontroll där är den valda Debian-postens konfiguration och initrd-storlek.
Vid den första undersökningen ändrades inte produktionsgränsen, installerad
EFI eller USB. Den efterföljande 0.1.2-leveransen beskrivs ovan. Se
`docs/DEBIAN-QEMU.md` för reproduktion, avgränsningar och evidens under
`artifacts/debian/`. Arch/LTS-status nedan gäller fortsatt separat.

## Nu: nya OS-ikoner installerade · 2026-10-11

EutherBoot på den interna ESP:n är uppdaterad med **32 ikoner**: Windows,
30 Linuxdistributioner/varianter och generell Linux. Ikonen väljs från
menypostens namn, med stöd för reservsuffix och hela ord. Debian får sin
spiral; båda befintliga Arch-posterna får den fyllda Arch-symbolen.
Se `docs/OS-ICONS.md` för namn, källor och licenser.

Den nya produktionens EFI SHA-256:
`aaa86f2710bf2941b5ed71582d465b8c3997fe6f92dafb1cfd4fe22537082a0b`.
Matchande källarkiv är också installerat. Båda filerna är synkade och
hashkontrollerade. Konfigurationen, normal-/LTS-UKI och firmwareposter är
hash-/textmässigt oförändrade. **Ingen omstart har gjorts.**

160 ikonkontroller i QEMU (alla ikoner, tre teman och tre upplösningar),
EFI-barnstart/retur och textläge är godkända. Den exakta produktionsfilen
har också startat och återvänt från båda konfigurerade sökvägarna med
ersättningsprogram på disponibel disk. Fysisk start med nya EFI:n och
fysisk LTS-grafik återstår; följ LTS-provet nedan vid nästa omstart.

Säkerhetskopia före ikonuppdateringen:
`/var/lib/eutherboot-single/before-os-icons/` (tidigare EFI, källarkiv och meny).
Vid behov kan den gamla `BOOTX64.EFI` och dess `source.tar.gz` återläggas från
rescue efter att rätt intern ESP identifierats. Ingen GRUB behövs.
Evidens: `artifacts/icons/installed-result.json`, `install.log`,
`qemu/result.json`, `production-qemu/result.json` och skärmbilder i samma träd.

## Nu: Arch + LTS installerat utan GRUB · 2026-10-11

Användaren bekräftade fysisk intern normalstart utan USB och beställde sedan
ett LTS-reservval. **Tillägget är installerat och slutverifierat.**

- **Arch Linux** är standardval, kernel `7.2.9-arch1-1`, timeout 10 sekunder.
- **Arch Linux LTS (reserv)** är andra valet, kernel `6.18.55-1-lts`.
- `linux-lts`, `linux-lts-headers` och `nvidia-open-lts` är installerade.
  NVIDIA `615.78.08` matchar båda kärnornas modulversion/vermagic; alla fyra
  startmoduler finns i båda initramfs. Btrfs är inbyggt i båda kärnorna.
- DKMS: system76-io, system76, vboxhost och vhba är byggda och installerade
  för båda kärnorna. LTS-headers lades till efter initiala fel om saknade
  headers; de felen är åtgärdade. Ingen fysisk LTS-grafiktest har gjorts.
- ESP ledigt: **449,863,680 byte (429.0 MiB)**.
  Båda aktiva bilderna och en temporär normalstor bild får plats med 64 MiB
  marginal. Storlek/tillväxt kontrolleras också vid framtida publicering.
- Uppdateringsprofilen hanterar båda bilderna. Verklig kärnuppdatering,
  LTS-ominstallation, normal/LTS/normal kallstart och negativa felprov är
  godkända i QEMU på disponibel 1 GiB ESP. Se `docs/VALIDATION.md`.
- Vid LTS-tillägget var EFI-startfil, NVRAM och bootordning oförändrade.
  EFI-filen har därefter uppdaterats med ikoner enligt avsnittet ovan; GRUB saknas.
  Rescue-stickan är fortsatt den fristående återställningsvägen.

### Nästa fysiska prov — användaren gör omstarten

1. Spara arbetet och starta om när det passar.
2. I EutherBoot, välj **Arch Linux LTS (reserv)** med högerpil eller nedåtpil
   och Enter. Tangenttryck avbryter nedräkningen.
3. Kontrollera att skrivbord och grafik fungerar. Öppna detta repo i Codex
   och skriv ”jag är tillbaka”. Vid problem: välj vanliga **Arch Linux**;
   om inte heller den fungerar, använd Euther Rescue-stickan.

Agenten ska då börja läsande: `uname -r`, `/proc/cmdline`, `findmnt /`,
`findmnt /boot`, `nvidia-smi` och relevanta journalfel vid behov.
Förväntad LTS-kärna är `6.18.55-1-lts`; båda valen använder markören
`eutherboot.internal=single-v1` och Btrfs `/@`. Kernelversionen skiljer valen.
Be användaren bekräfta grafikutfallet; paket-/filkontrollen är inte ett
fysiskt grafiktest. **Återbygg eller installera inte om vid återkomsten.**

### Evidens och återgång

- `artifacts/internal-lts/installed-result.json` och `verify.log` är slutresultat.
- `install.log` och `headers.log` visar byggningen samt tidigare kontrollfel;
  verifieraren korrigerades för NVIDIA-filnamn med bindestreck och inbyggd
  Btrfs. Senaste `verify.log` är godkänd för båda färdiga bilderna.
- `artifacts/lts-qemu/result.json` och fyra bootloggar är virtuella resultat.
- Före LTS sparades den då fysiskt fungerande normalbilden i
  `/var/lib/eutherboot-single/pre-lts-normal.efi`, hashverifierad.
- Föregående integration/meny finns under
  `/var/lib/eutherboot-single/before-lts`; äldre komplett ESP-kopia ligger
  fortfarande i `/var/lib/eutherboot-single/backup`.
- Läs `docs/INTERNAL-SINGLE-UKI.md` före en eventuell återgång till bara Arch.
  LTS använder samma rotfilsystem och ersätter inte den fristående rescue-stickan.

Ingen automatisk omstart har gjorts. Fysisk LTS-start återstår.

## Historik: single-installationen före LTS

## Nu: EutherBoot installerat internt, GRUB borttaget — 2026-10-11

Användaren bekräftade fysisk USB-direktstart och fungerande grafik och bad
uttryckligen om bytet: **GRUB bort helt, Euther Rescue som återväg**. Bytet är
nu utfört. Ingen partitionsändring, NVRAM-ändring eller automatisk omstart.

- EutherBoot på intern `/boot/EFI/BOOT/BOOTX64.EFI`, samma hash som den fysiskt
  provade releasefilen: `707ce74a51d1563ca757e0f044e7f6a02eda8804013c848d823a7c83d332eb65`.
- En normal UKI: `/boot/EFI/Linux/arch-normal.efi`, kernel `7.2.9-arch1-1`.
  Menyn visar **Arch Linux**, svenska, System Regis och 10 sekunders timeout.
- GRUB-paket och `/boot/grub` borttagna. Separata normal-/fallback-initramfs
  borttagna; kernelkällan och paketägd Intel-mikrokod är kvar.
- **748 019 712 byte (713,4 MiB) ledigt** på ESP efter verifierad ombyggnad.
- Säkerhetskopia av gamla ESP-filer och preset på rotpartitionen:
  `/var/lib/eutherboot-single/backup`. Den är hashverifierad och är inte en
  aktiv intern reservstart. Rescue-stickan är fortfarande räddningsvägen.
- Enkel uppdateringsprofil installerad. Bygger på root, verifierar kärna och
  cmdline, kopierar/synkar/hashkontrollerar ny UKI före namnbyte på ESP.
  Ingen LTS eller intern generationshantering.
- Värdens nya `rebuild`-kommando kördes och publicerade UKI:n korrekt. EFI- och
  UKI-hashar kontrollerades, firmwareposter/bootordning är oförändrade.

### Nästa session efter omstart

Användaren ska **stänga av, ta ur Kingston DataTraveler-teststickan och starta
från intern disk**. Befintlig firmwarepost heter `UEFI OS`. Ingen GRUB visas;
EutherBoot ska starta Arch efter 10 sekunder eller Enter. Rescue General UDisk
kan användas från tillfällig UEFI-meny vid problem.

När användaren skriver ”jag är tillbaka”, kör agenten läsande kontroller:

```sh
cat /proc/cmdline
uname -r
findmnt -no SOURCE,FSTYPE,FSROOT /
findmnt /boot
lsblk -o NAME,TRAN,MODEL,SIZE,FSTYPE,LABEL,MOUNTPOINTS
efibootmgr -v
```

Förväntad markör är **`eutherboot.internal=single-v1`**, Btrfs FSROOT `/@`
och kernel `7.2.9-arch1-1` om inget paketbyte skett. Kontrollera menyväg och
fungerande grafik med användaren. Saknad markör bevisar inte intern start.
Fysisk intern normalstart **bekräftades 2026-10-11** av användaren och
livekontroll: intern markör, kernel 7.2.9-arch1-1, Btrfs `/@`, BootCurrent
0001 (`UEFI OS` på intern ESP) och inga anslutna USB-diskar.
Användaren har därefter beställt ett separat LTS-reservval utan GRUB.
Återbygg eller skriv inte om något bara för att användaren återkommer.

### Verifiering och återställning

`artifacts/single-qemu/result.json`: disponibel 1 GiB ESP, Btrfs `/@`,
installation utan GRUB, fysisk release-EFI i QEMU, två godkända Arch-starter
med riktig kärnuppdatering 7.2.7 → 7.2.9. Inga felande systemd-enheter.
Felaktig UKI, misslyckad mkinitcpio-hook, full ESP och verklig pacman-avvisning
bevarade aktiv fil. Syntetisk NVIDIA-pakettrigger gav ombyggnad/publicering;
verklig NVIDIA-uppdatering är inte separat provad. Kopierings-/namnbytesfel
provades separat med injicerade fel.

Värdresultat: `artifacts/internal-layout/installed-result.json`, `install.log`,
`rebuild.log`, `boot-before.json` och `firmware-before.txt`. Läs
`docs/INTERNAL-SINGLE-UKI.md` för profil och rescue-återställning.
Manuell publicerande ombyggnad:

```sh
sudo python3 /usr/local/lib/eutherboot-single/eutherboot-single.py rebuild
```

Enbart `mkinitcpio -P` bygger staging, inte publicering. Pacman-integrationen
inväntar lyckat byggkommando innan publicering; mkinitcpio-efterhooks används
inte, eftersom ett felprov visade att de kan köras trots byggfel.

## Historik före interninstallationen

Följande äldre instruktioner om kvarvarande GRUB och förbud mot intern
installation beskriver tidigare läge och ersätts av avsnittet ovan.

Uppdaterad 2026-10-11. **Fysiskt test godkänt enligt foto och användarens rapport:
F4 → Esc → huvudmeny → befintlig bootloader → GRUB → Arch.**

Ny inventering: körande och installerad kärna är 7.2.9-arch1-1. På `/boot`
finns en aktuell kärna, normal- och fallback-initramfs; inga gamla kärnavbilder
hittades. Ledigt: 438 767 616 byte (418,4 MiB). Gamla modulrester om cirka
166,1 MiB finns på rotpartitionen, inte ESP:n. Inget har raderats.
Se `docs/HOST-COMPATIBILITY.md` för utrymmesstatus.


## Nu: separat USB för direktstart av installerat Arch

### Återkomstkontroll 2026-10-11

Efter användarens ”jag är tillbaka” verifierades live att `/proc/cmdline`
innehåller `eutherboot_probe=usb-direct-normal-v1`, att `uname -r` är
`7.2.9-arch1-1` och att `/` är `/dev/nvme0n1p2[/@]`, Btrfs med FSROOT `/@`.
Kingston DataTraveler 3.0 är ansluten (28,9 GiB, en 1 GiB FAT-partition,
omonterad vid kontrollen). Detta bekräftar normaltestets startkommandorad på
den körande värden. Användaren svarade därefter ”allt funkar fint” på frågan
om direktval och fungerande skrivbord/grafik. Fysisk normal direktstart är
därmed bekräftad; reservstart är inte testad i denna kontroll. Git var rent.
Kontrollen var enbart läsande; ingen bootkonfiguration eller USB ändrades.
Leveransstatus och instruktioner nedan beskriver läget före återkomsten.

Ny läsande installationskontroll samma dag: cirka 418,4 MiB ledigt på ESP,
men installerarens budget för befintliga payloads är cirka 1,47 GiB ledigt,
redan före LTS. `linux-lts` och `systemd-ukify` saknas fortfarande.
Direktstartstestet är godkänt. Användaren förtydligade att GRUB ska tas bort
helt och rescue-stickan ska vara återväg; flera interna reservgenerationer är
inte målbilden. Den gamla installerarens budget är därför inte krav för den
valda layouten. Se `docs/INTERNAL-SINGLE-UKI.md`: en normal UKI ger cirka
713,4 MiB ledigt och 440,5 MiB under byte med lika stor ny UKI. En enkel
uppdateringsprofil behöver implementeras och provas före migration.
Ingen intern installation eller radering har gjorts.

Användaren bekräftar att Euther Rescue 0.1.1 startar fysiskt och att Codex-
inloggning fungerar från stickan. Rescue-stickan behålls intakt. En annan
Kingston DataTraveler 3.0, cirka 31 GB, godkändes uttryckligen för överskrivning.
Den nya teststickan är nu färdigskriven, synkad och verifierad; inte omstartad
på den fysiska datorn ännu.

### Nästa session: agenten kör kontrollen

Användaren vill slippa terminalkommandon. Be honom bara starta via den
tillfälliga UEFI-bootmenyn → **Kingston DataTraveler** → **Arch Linux direkt**
och öppna Codex i detta repo när Arch har startat. Ingen automatisk start.
Användaren kan skriva ”jag är tillbaka”; agenten gör då nedanstående kontroll.

**Börja med läsning, inte ett nytt bygge eller en ny USB-skrivning.**
Leveransen är redan klar och pushad i `7240835`. Kontrollera aktuell gitstatus
och kör följande själv på den startade värden:

```sh
cat /proc/cmdline
uname -r
findmnt -no SOURCE,FSTYPE,FSROOT /
lsblk -o NAME,TRAN,MODEL,SERIAL,SIZE,FSTYPE,LABEL,MOUNTPOINTS
```

- Markören `eutherboot_probe=usb-direct-normal-v1` bekräftar den normala
 testpostens kommandorad. Tillsammans med användarens rapport om menyval och
 fungerande Arch-session ger detta evidens för fysisk direktstart.
- `usb-direct-fallback-v1` betyder att reservposten användes.
- Saknad markör betyder att direktstart ännu inte är bekräftad. Fråga vilken
 menyväg som användes; anta inte att USB-start lyckades bara för att Arch kör.
- Förväntad kärna är `7.2.9-arch1-1`, rotfilsystem Btrfs med subvolym `/@`.
 Kontrollera också användarens rapport om fungerande grafik. Vid grafikfel:
 läs relevanta journal-/drivrutinsuppgifter innan ändringar föreslås.

Spara verifierat utfall i denna handoff och `docs/VALIDATION.md`, med tydlig
skillnad mellan normalstart, reservstart och eventuell GRUB-start. Intern
installation är ett senare steg: skriv inte intern ESP, NVRAM eller pakethooks
och ta inte bort GRUB som en del av denna kontroll. Vid startfel använder
användaren **Befintlig GRUB** eller den tidigare interna startvägen; separat
rescue-USB finns kvar. Agenten ska inte starta om datorn automatiskt.

Ingen kontrollscriptinstallation behövs; användaren valde denna handoff i
stället. USB:s startinnehåll ändrades inte under handoff-arbetet.

Förväntad markör: `eutherboot_probe=usb-direct-normal-v1`. Root ska fortfarande
vara Btrfs `/@`. **Arch Linux reserv** använder aktuell fallback-initramfs;
**Befintlig GRUB** går till den oförändrade interna EFI-startfilen.
Secure Boot ska vara avstängt för denna osignerade testversion.

Se [hela instruktionen](docs/DIRECT-ARCH-USB.md). Kärna 7.2.9-arch1-1 och
normal/fallback-initramfs är kopierade från aktuella `/boot`, inte ombyggda.
UKI-filerna ligger på USB; ingen intern installation eller pakethook har gjorts.
Teststickan är en snapshot: återskapa den om kärna/moduler uppdateras före provet.

QEMU verifierade båda verkliga UKI:erna till initramfs och det väntade stoppet
för saknad root (inga interna diskar anslöts). GRUB-menypostens volymval och
retur provades med en disponibel EFI-applikation. Fysisk Arch-inloggning via
direktvalet återstår. Båda GPT-kopiorna och sex levererade filhashar verifierades;
366 interna bootfilers hash är oförändrade. Ingen separat full återläsning.

Artefakter: `artifacts/direct-probe/result.json`, `artifacts/direct-delivery/result.json`
och `artifacts/direct-host-inventory/`. USB lämnades skrivskyddat monterat på
`/run/media/nichlas/1DB6-0A6D`; mata ut via filhanteraren före omstart/flytt.
Identifiera alltid stickan på nytt; det är inte rescue-stickans General UDisk.
Den aktuella modellnedladdningen rapporterades klar, men ingen omstart av
värddatorn har utförts av agenten.

## Rescue-leverans: Euther Rescue 0.1.1

ISO: `artifacts/rescue/euther-rescue-0.1.1-x86_64.iso`.
SHA-256: `958f0a2614c80c6da17124743a4a613e9519e6c8aeaaa11038ed174c6c18e44b`.
Källsnapshot `e89ed0b` inkluderar grafisk editor och korrigerad Codex-start.
Den inbyggda launchern nådde inloggningsvyn i QEMU utan injicerad rättelse;
komplett USB-layout klarade två starter, nätverk, återställning och persistens.
Se `artifacts/rescue/{build-result,codex-start-fixed-result,usb-test-result}.json`.

General UDisk (15 728 640 000 byte) är uppdaterad till rescue 0.1.1 och
synkad. Första autentiseringsförsöket hann löpa ut; efter användarens återkomst
lyckades Polkit och skrivningen slutfördes. Alla block jämfördes mot den
QEMU-testade avbilden, bara avvikande block skrevs om. Separat full återläsning
hoppades över enligt användarens tidigare önskemål; båda GPT-kopiorna stämde.
Sex EFI-partitionsfiler, inklusive kärna och initramfs, hashjämfördes mot
avbilden. EFI-/datapartitionerna monterades. Datapartitionen
lämnades vid `/run/media/nichlas/EUTHERDATA`. Mata ut före fysisk flytt.

Leveransresultat: `artifacts/rescue/usb-delivery.json`. Användaren har efter
leveransen bekräftat fysisk start och lyckad Codex-inloggning. Beständig
arbetsdata efter fysisk omstart är inte separat rapporterad. Förra utgåvan nådde fysiskt rescue-
autologin men misslyckades i Codex-starten; detta är den korrigerade avbilden.
Autentiserad AI-session är inte verifierad av QEMU-testet.

Tidigare avbild/resultat/profil finns bevarade i
`artifacts/rescue/previous-1791713511/`; äldre ISO ligger kvar separat.
Ingen intern boot eller firmware har ändrats och värden har inte startats om.

## Historik: rescue-arbetet 2026-10-11

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

## Historik: första rescue-avbilden och editorarbetet

Rescue-stickan är färdigskriven och fsync slutförd. Full återläsning hoppades
över på användarens uttryckliga begäran. GPT i båda ändar matchade avbilden,
EFI-filer kontrollerades och EFI-/datapartitionerna monterades. Se lokal
`artifacts/rescue/usb-delivery.json`. Fysisk start till rescue-autologin är nu bekräftad med användarens foto.
Codex-start misslyckades: saknad state-katalog, sedan ENOSPC. Autentiserad
Codex återstår. Felet har reproducerats i samma ISO i QEMU. Skapad state-katalog och
`codex --no-daemon` når inloggningsvyn. Version/help-testet täckte inte detta.
Aktuell launcher rättar katalogen och använder foreground-läge; ISO/sticka
är ännu inte uppdaterade. Se rescue/README.md för workaround och test.
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

1. Läs avsnittet om aktuellt direktstartstest överst. Den gamla 0.1.1-leveransen är historik. Arbeta i `/run/media/nichlas/Kingston1TB/EutherBoot`.
2. Foto och rapport finns sammanfattade nedan; evidens finns i
   `artifacts/physical-0.1.1/`. Vanlig intern start utan USB är ännu inte separat rapporterad.
3. Läs `artifacts/rescue/usb-delivery.json` och `usb-test-result.json` för aktuell rescue.
   Historisk EutherBoot-leverans finns under `artifacts/host-probe-0.1.1/`.
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
