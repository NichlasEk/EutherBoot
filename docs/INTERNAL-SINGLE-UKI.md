# Intern EutherBoot utan GRUB

## Utökning med LTS · 2026-10-11

Användaren har bekräftat fysisk intern normalstart utan GRUB. Livekontrollen
visade `eutherboot.internal=single-v1`, kernel `7.2.9-arch1-1`, Btrfs `/@`
och firmwareposten `UEFI OS` på interna ESP:n. Ingen USB var ansluten.
Användaren har därefter beställt ett separat LTS-reservval utan GRUB.

Profilen stöder nu `linux` och valfritt `linux-lts`, med egna UKI-filer:
`arch-normal.efi` och `arch-lts.efi`. Arch är standard, LTS heter
**Arch Linux LTS (reserv)**. LTS använder samma installerade rotfilsystem;
rescue-stickan behövs fortfarande vid skadat root, större paketfel eller diskfel.
LTS är inte en fristående rescue eller en fryst tidigare systemgeneration.

`add-lts --hooks packaging/arch-single PAKETFILER...` utökar en befintlig
single-installation, säkerhetskopierar integrationen under
`/var/lib/eutherboot-single/before-lts`, installerar en staging-preset och
installerar paketen med pacman. På värdar med DKMS ska även
`linux-lts-headers` ingå, så att installerade extramoduler kan byggas.
NVIDIA-paketet måste matcha LTS-kärnan och installerad `nvidia-utils`.
LTS byggs och verifieras före menyposten.
Existerande anpassad LTS-preset eller meny avvisas. Ett avbrutet tillägg ska
inspekteras och återställas från denna kopia före nytt försök; kommandot är
avsiktligt inte en blind, upprepningsbar återställningsoperation.

Båda presets bygger på root. Wrappern inväntar lyckat byggkommando, verifierar
båda färdiga avbilderna mot respektive installerad kärna och kommandorad,
och räknar utrymme inklusive eventuell tillväxt innan första publiceringen.
Filerna kopieras en i taget till ESP, synkas och hashkontrolleras före namnbyte.
Uppdateringar behöver plats för den största tillfälliga avbilden plus 64 MiB;
tillägget kontrollerar också att denna marginal finns efter installationen.
Pakethookarna inkluderar linux-lts och nvidia-open-lts/nvidia-lts.
Borttagning av hanterade kärnpaket stoppas före transaktionen.

`rebuild` bygger och publicerar båda kärnorna när `single.json` har `lts: true`.
Enbart `mkinitcpio -P` publicerar fortfarande inget. Kernelpaketens modulträd
hanteras av pacman. Ett fel efter paketinstallationen rullar inte tillbaka
paket eller moduler. Ett I/O-fel under den andra publiceringen kan lämna
första bilden uppdaterad och andra oförändrad; två filbyten är inte en atomisk
transaktion tillsammans. Använd rescue om paket/moduler och UKI inte stämmer.

Vid önskad återgång till endast normalstart: verifiera normalstarten först,
ta bort LTS-posten, återställ integrationens sparade konfiguration/verktyg/hooks,
och avinstallera därefter LTS-paketen och ta bort dess separata UKI.
Återställ inte den äldre GRUB-kopian för denna återgång.

Fysisk LTS-start och grafik måste provas på datorn efter installation.
Se `HANDOFF.md` för aktuell leveransstatus och `artifacts/lts-qemu/result.json`
för den disponibla virtuella provningen.

## Ursprunglig single-installation (historik)

Plan och läsande kapacitetskontroll 2026-10-11. Användaren vill ta bort GRUB
helt och använda den fysiskt provade Euther Rescue-stickan som återväg.
Normal direktstart via EutherBoot från test-USB och fungerande grafik är
bekräftade. Intern installation är nu utförd och verifierad på fil-/uppdateringsnivå.
Fysisk intern start efter omstart återstår.

## Slutlayout och utrymme

Behåll en normal UKI under `/boot/EFI/Linux/arch-normal.efi`, EutherBoot som
`/boot/EFI/BOOT/BOOTX64.EFI` och dess konfiguration, licens och källarkiv under
`/boot/EFI/EutherBoot/`. Menyn har endast Arch, ingen GRUB- eller reservpost.
Rescue-stickan innehåller det fristående räddningssystemet.

Ta bort GRUB-paketet och dess identifierade genererade bootfiler vid den
senare migrationen. De separata normala och fallback-initramfs-filerna ersätts
av UKI:n, som innehåller normal initramfs. Behåll `/boot/vmlinuz-linux` som
inmatning för standardkedjan i mkinitcpio och behåll paketägda
`intel-ucode.img`. Ingen generell rensning av EFI- eller loader-kataloger.

| Kapacitet | MiB |
| --- | ---: |
| ESP:s användbara kapacitet | 1022,0 |
| Ledigt nu | 418,4 |
| Normal UKI från fysiskt provad USB | 272,9 |
| Beräknat använt efter migration | 308,6 |
| Beräknat ledigt efter migration | 713,4 |
| Ledigt med lika stor ny UKI bredvid den aktiva | 440,5 |

Beräkningen använder aktuell FAT-allokering och verkliga levererade filstorlekar.
Den omfattar EutherBoot, källarkiv och licens. Små katalog-/konfigurationsskillnader
och framtida avbildstillväxt kan ändra slutvärdet. Ingen initramfs-optimering eller
partitionsändring behövs för den uppmätta layouten. Maskinlokala exakta värden:
`artifacts/internal-layout/capacity.json`.

## Implementerad uppdateringsväg

Den befintliga hanterade installeraren ska inte köras med förbigångna spärrar:
den är byggd för LTS och interna återställningsgenerationer. Den här modellen
har en separat enkel profil i `tools/eutherboot-single.py`, utan LTS eller
interna generationskopior. Pakethooks finns i `packaging/arch-single/`.

1. Ändra linux-preset till endast normal UKI, byggd i en staging-katalog på
   rotfilsystemet. Behåll `/boot/vmlinuz-linux` som kernelkälla. Skapa inte
   längre separata normal-/fallback-initramfs-filer på ESP.
2. Låt Archs befintliga mkinitcpio-pakethook utlösa bygget vid kärn-, firmware-
   och relevanta moduluppdateringar. Den lokala mkinitcpio-versionen stöder
   UKI med objcopy utan systemd-ukify; verktygsberoendena ska kontrolleras.
3. En wrapper runt Archs pakethook inväntar lyckad avslutningsstatus från
   byggkommandot och verifierar rätt kernel/kommandorad,
   rätt monterad ESP och plats för faktisk ny fil plus marginal. Kopiera till
   temporärt syskonnamn, synka och hashverifiera innan det aktiva namnet ersätts.
   En misslyckad byggning eller kopiering får inte först radera aktiv UKI.
4. Kontrollera kapacitet även före pakettransaktionen och hantera kvarlämnade
   stagingfiler. Publiceringsfel ska ge tydligt fel genom mkinitcpio/pacman.
   Att en gammal UKI finns kvar garanterar inte start efter moduluppdatering;
   modellen har ingen modulåterställning och använder rescue vid sådana fel.
5. Prova profil och verkliga pakethooks på disponibel 1 GiB FAT-ESP i QEMU:
   första start, kärnuppdatering, nästa start samt bygg-/kopierings-/utrymmesfel.
   FAT och namnbyte ger inte någon garanti mot alla strömavbrott.

## Migration efter godkänd lokal provning

Spara kontrollerad kopia av nuvarande ESP, preset, konfiguration och EFI-poster
utanför ESP. Identifiera räddningsmediet och återställningsinstruktionen.
Bygg och verifiera den interna UKI:n före radering; använd egen intern markör
så att nästa fysiska start går att skilja från USB-testet.

Den uppmätta normala UKI:n får plats även före rensning. Lägg in den först,
installera den provade uppdateringsprofilen, ersätt GRUB med EutherBoot och
ta bort endast de specificerade överflödiga filerna. Verifiera hash och konfig,
och granska firmwareposter mot deras verkliga EFI-sökvägar innan de ändras.
GRUB ska inte behållas som intern reserv. Ingen automatisk omstart.

Nästa fysiska prov ska ske från intern disk utan test-USB. Kontrollera intern
markör, kernel, rot och grafik. Rescue-stickan används vid problem.

Installationsverktyget skriver endast med explicit `install --apply` och ändrar
inte NVRAM. Det sparar och hashverifierar befintligt ESP-innehåll samt preset
under `/var/lib/eutherboot-single/backup` före bytet. Den aktiva installationen
innehåller inte GRUB; säkerhetskopian ligger på rotpartitionen.

### Varför ingen mkinitcpio-efterhook används

Ett riktigt felprov visade att mkinitcpio kan skapa UKI och köra efterhooks
även när en initramfs-hook saknas och hela kommandot sedan returnerar fel.
Därför publicerar vår wrapper först efter att byggprocessen har returnerat 0.
Den kopierar distributionens `90-mkinitcpio-install.hook` till `/etc/pacman.d/hooks`
och ersätter dess Exec med wrappern. Befintliga path-triggers behålls och
NVIDIA-pakettriggers läggs till. Följ ändringar i distributionens hook vid
framtida mkinitcpio-uppgraderingar.

Manuell ombyggnad och publicering körs med:

```sh
sudo python3 /usr/local/lib/eutherboot-single/eutherboot-single.py rebuild
```

Enbart `mkinitcpio -P` bygger stagingfilen och publicerar den inte. Fel i
paketuppdateringens efterfas rullar inte tillbaka redan installerade paket;
reparera före omstart eller använd rescue-stickan.

### Återställning från rescue

Starta Euther Rescue och identifiera intern Btrfs-root och ESP på nytt. Montera
root med subvolym `@` under `/mnt` och rätt ESP under `/mnt/boot`. Ingen
formatering behövs. Den installerade profilen och dess säkerhetskopia finns på
root, inte på teststickan. Förstahandsvägen är att reparera paket/moduler och
köra ovanstående `rebuild` via `arch-chroot /mnt`.

Om den gamla bootkedjan måste återställas: spara felresultatet, inaktivera de
nya hookfilerna `04-eutherboot-single-remove.hook`, `05-eutherboot-single.hook`
och `90-mkinitcpio-install.hook` under den monterade rotens `/etc/pacman.d/hooks`.
Återställ `linux.preset` från säkerhetskopian till `/etc/mkinitcpio.d/` och
återlägg `backup/boot/` på ESP. Kopian innehåller den tidigare GRUB-EFI-filen;
GRUB-paketet behöver installeras igen för framtida underhåll. Återställda gamla
startfiler kräver matchande moduler; efter senare paketuppdateringar behövs
ombyggnad. Låt agenten kontrollera aktuella enheter och paket innan återställning.

Verifieringsartefakt: `artifacts/single-qemu/result.json`. Den måste finnas för
en godkänd slutkörning; påbörjade loggar räcker inte. Värdinstallationens separata
resultat sparas i `artifacts/internal-layout/installed-result.json`. Fysisk
intern start verifieras först efter användarens omstart.

