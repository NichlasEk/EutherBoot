# Euther Rescue 0.1.2

Denna utgåva innehåller EutherBoot 0.1.2 med 512 MiB initrd-gräns och tydliga
storleksfel, den aktuella källkoden och `INSTALL-DEBIAN.md` för Codex på
Debian-datorn. Kör `rescue-start` och be Codex läsa den medföljande guiden
och installera den nya versionen. Arbetskopian heter `EutherBoot-0.1.2`;
äldre arbetskopior skrivs inte över. Historiska leveranser nedan är separata.

USB-avbildens startpost binds till ISO-partitionens exakta PARTUUID.
Det undviker ett observerat kapplöpningsfel där samma ISO-UUID kunde välja
hela USB-disken och därmed blockera montering av EUTHERDATA. Inga interna
partitioner behöver sökas igenom för att hitta live-systemet.

## Leverans av 0.1.2 · 2026-10-11

General UDisk är uppdaterad, synkad och fullständigt återläst: samtliga
15 728 640 000 byte matchar den testade USB-avbildens SHA-256
`76e54df30b08fc6d701be9e6d057f586f5114b7322b367b478b3049c88ff9b75`.
Verifieringen skedde före återmontering. Därefter verifierades geometri,
sex EFI-partitionsfiler och de medföljande EutherBoot-/källarkivsfilerna mot
releasemanifestet direkt från stickan. Debian-guiden finns med.
Datapartitionen lämnas monterad på `/run/media/nichlas/EUTHERDATA`.

ISO: `artifacts/rescue/euther-rescue-0.1.2-x86_64.iso`, SHA-256
`5a10ca0138d4a35f275e50fa9078af2fb9cdec4c76b38a1ce3e7ae80a7cf05e5`.
Produktions-EFI SHA-256:
`7ecc51be45799dc07ae7dc80032f3898ca5d713673f6172bc487d4b70a57c91f`.
Båda avbildsformaten klarade två QEMU-starter, beständig arbetsdata och nätverk.
Riktig Codex-start nådde inloggningsvyn med ISO:ns egna launchers. Fysisk
0.1.2-start och installation/start på Debian-datorn återstår. Evidens finns
i `artifacts/rescue/usb-delivery.json` och `release-012-validation.json`.

Mata ut före flytt, starta stickan, kör `codex login --device-auth` och
`rescue-start`. Be Codex läsa `/usr/local/share/euther-rescue/INSTALL-DEBIAN.md`
och installera den medföljande versionen på rätt Debian-installation.

Arch live-USB med Codex CLI 0.162.1, reparationsverktyg, EutherBoot-källkod och
valfri privat kopia av en verifierad startkedja. Starten använder systemd-boot
oberoende av den installerade datorns GRUB/EutherBoot. UEFI x86-64; Secure Boot
är inte konfigurerat. Ingen intern disk monteras automatiskt.

## Användning

Välj USB i firmwarets tillfälliga UEFI-bootmeny. Live-systemet loggar in som
`rescue`, med svensk tangentbordslayout och sudo. Ethernet använder DHCP;
Wi-Fi ansluts med `iwctl`. Läs den medföljande guiden:

```
less /usr/local/share/euther-rescue/RESCUE.md
lsblk -o NAME,SIZE,MODEL,FSTYPE,LABEL,UUID,MOUNTPOINTS
rescue-data /dev/disk/by-uuid/USB_DATAPARTITIONENS_UUID
codex login --device-auth
rescue-start
```

Datapartitionen heter EUTHERDATA. Identifiera rätt USB och UUID innan montering.
Arbetsfiler sparas under `/mnt/rescue-data/work`. Inloggning ligger i temporärt
hem och behöver göras om efter omstart. Inga kontouppgifter bakas in i avbilden.
Codex behöver internet; diskverktyg och dokumentation fungerar offline.
Rustup ingår, men Rust-toolchain och UEFI-target behöver hämtas vid första
bygget. Ett källarkiv med Cargo-beroenden ingår också.

En privat `known-good/` innehåller den tidigare fysiskt testade EutherBoot-kedjan,
interna ESP:n med GRUB/kärna/initramfs och konfiguration/partitionsidentifierare.
Verifiera `SHA256SUMS` innan användning. Den är ingen backup av root/personliga
filer. ISO med denna katalog får inte publiceras som generell distribution.

## Bygga utan root på värden

Värden behöver Archiso-profilen, Python, QEMU/KVM, OVMF, mtools, dosfstools,
gptfdisk, util-linux och e2fsprogs. Befintlig verifierad Arch-fixture under
`artifacts/arch/manifest.json` och lokal EutherBoot-release behövs.

1. `python3 scripts/prepare-rescue.py` skapar en ny profil. Lägg till
   `--include-known-good` endast med en redan verifierad privat snapshot.
2. `python3 scripts/build-rescue-vm.py` bygger med mkarchiso som root i en
   disponibel qcow2-overlay. Inga värddiskar ansluts till gästen.
3. `python3 scripts/test-rescue-start-qemu.py --installed-launchers` provar
   riktig Codex-start till inloggningsvyn direkt från ISO:n. Därefter provar
   `python3 scripts/test-rescue-qemu.py` två starter, nätverk, frånvaro av
   auth-token och beständig arbetsdata.
4. `python3 scripts/assemble-rescue-usb.py ISO OUTPUT --bytes KAPACITET`
   skapar en reguljär GPT-avbild med ISO, ESP och ext4 på återstående utrymme.
5. `python3 scripts/test-rescue-qemu.py --usb-image OUTPUT` provar den faktiska
   USB-layouten via emulerad USB, med en skrivbar temporär overlay.

`--resume --reuse-transfer` återanvänder en inspekterad bygg-overlay och samma
profilarkiv. Vid ny profil: använd `--resume --fresh-work` utan
`--reuse-transfer`, så att mkarchiso inte återanvänder gamla byggsteg. Efter kerneluppdatering krävs matchande `builder/bootstrap-kernel.efi`
och `builder/bootstrap.img`; starta inte en uppdaterad gästs rot med en gammal
kärna vars moduler saknas. Dessa är lokala byggartefakter, inte värdens bootfiler.
Byggloggar och JSON-resultat sparas under `artifacts/rescue/`.

## Leverans och verifieringsgränser

Fysisk skrivning sker separat efter identifiering och uttryckligt godkännande
av målenheten. Läs tillbaka alla skrivna byte och jämför SHA-256, synka och
montera datapartitionen. QEMU-start bevisar inte fysisk firmwarekompatibilitet.
Codex `--version`/`--help` bevisar inte en autentiserad AI-session. Återställning
av datorns bootkedja ska inte räknas som verifierad före ett separat fysiskt test.

## Validering av första privata avbilden

2026-10-11: ISO och komplett USB-layout klarade vardera två UEFI-starter i
QEMU. Kontrollerna omfattade Codex-version/help, nätverk, frånvaro av inbakad
inloggning, SHA-256 för bootkopian, återkopiering av EFI-filer till en tom
FAT-avbild samt arbetsfil som överlevde omstart. Testerna använde inga interna
diskar. Den autentiserade Codex-sessionen och fysisk USB-start återstår.

ISO SHA-256:
`a5aa2d5f4f4b1ec63ae72a16e0bd52f9645f37327543c6c304328ba2a75c3890`.

## Fysisk skrivning 2026-10-11

General UDisk har skrivits och synkats. Full återläsning hoppades över efter
uttrycklig begäran; partitionstabellens båda kopior jämfördes mot avbilden och
EFI-/datapartitionerna monterades. Detta ersätter inte en full bytejämförelse.
Leveransresultat finns privat i `artifacts/rescue/usb-delivery.json`.
Startfilen är osignerad: använd UEFI med Secure Boot avstängt för denna utgåva.
Fysiskt starttest och autentiserad Codex-session återstår. Källsnapshoten är
`17e20d9`; senare editorändringar finns ännu inte på stickan.

## Codex-start på första rescue-utgåvan

Fysisk start till rescue-autologin är bekräftad 2026-10-11. Första Codex-starten
visade saknad state-katalog, följt av `No space left on device`. Samma ENOSPC
reproducerades i den levererade ISO:n i QEMU: Arch live-root har 256 MiB
skrivbar RAM-overlay. Codex bakgrundsserver misslyckas under starten;
`--no-daemon` når inloggningsvyn med cirka 5 MiB använt på root.
Efter det misslyckade försöket är root inte längre fullt, så `df` i efterhand
kan visa gott om ledigt utrymme. USB-datapartitionen är en separat lagringsyta.

På den redan levererade stickan, utan omstart eller omskrivning:

```bash
mkdir -p ~/.codex
cd ~/work/EutherBoot
codex --no-daemon
```

Den nya launchern skapar state-katalogen med privata rättigheter och använder
`--no-daemon` för rescue. `rescue-start` vidarebefordrar nu argument.
State/inloggning ligger fortsatt i det temporära hemmet; ingen token kopieras
automatiskt till USB-data. En uttryckligen vald `CODEX_HOME` respekteras.
En satt CODEX_HOME måste finnas enligt
[OpenAI-dokumentationen](https://learn.chatgpt.com/docs/config-file/environment-variables).

`python3 scripts/test-rescue-start-qemu.py` injicerar aktuella launchers i en
disponibel gästs RAM och provar verklig terminalstart till inloggningsvyn,
privata katalogrättigheter, argument och frånvaro av auth/daemoninstallation.
Det testet ändrar inte befintlig ISO eller fysisk sticka. Med
`--installed-launchers` verifieras i stället launcherna som redan finns i ISO:n;
ingen launcher injiceras. Nybyggd ISO ska också
provas med de vanliga rescue-testerna före ny USB-leverans. Autentiserad session
på testdatorn återstår.

## Leverans av 0.1.1

2026-10-11: ombyggd ISO och USB-avbild verifierade i QEMU, inklusive riktig
Codex-start från ISO:ns egna launchers och arbetsdata efter omstart. Källsnapshot
`e89ed0b` innehåller även den grafiska editorn. General UDisk är uppdaterad och
fsync slutförd. Befintliga block jämfördes mot avbilden och avvikande block
skrevs om; ingen separat full återläsning gjordes enligt användarens önskemål.
GPT och sex startfilers hash (inklusive kärna/initramfs) kontrollerades;
datapartitionen lämnades monterad på EUTHERDATA.
Fysiskt test av 0.1.1 och autentiserad Codex-session återstår.

ISO: `artifacts/rescue/euther-rescue-0.1.1-x86_64.iso`.
SHA-256: `958f0a2614c80c6da17124743a4a613e9519e6c8aeaaa11038ed174c6c18e44b`.
Privat leveransevidens: `artifacts/rescue/usb-delivery.json`.
