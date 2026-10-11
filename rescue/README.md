# Euther Rescue 0.1.0

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
3. `python3 scripts/test-rescue-qemu.py` verifierar två starter, Codex-binär,
   nätverk, avsaknad av auth-token och beständig arbetsdata.
4. `python3 scripts/assemble-rescue-usb.py ISO OUTPUT --bytes KAPACITET`
   skapar en reguljär GPT-avbild med ISO, ESP och ext4 på återstående utrymme.
5. `python3 scripts/test-rescue-qemu.py --usb-image OUTPUT` provar den faktiska
   USB-layouten via emulerad USB, med en skrivbar temporär overlay.

`--resume --reuse-transfer` återanvänder en inspekterad bygg-overlay och samma
profilarkiv. Efter kerneluppdatering krävs matchande `builder/bootstrap-kernel.efi`
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
