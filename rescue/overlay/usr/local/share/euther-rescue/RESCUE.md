# Euther Rescue

Detta är en självständig Arch live-miljö. Interna diskar monteras inte automatiskt.
Användaren rescue har sudo för manuella reparationer. Ingen SSH-server startas.

## Börja här

1. Kör `lsblk -o NAME,SIZE,MODEL,FSTYPE,LABEL,UUID,PARTUUID,MOUNTPOINTS`.
2. Ethernet använder DHCP. För Wi-Fi: `iwctl`, sedan `station DEVICE connect SSID`.
3. Kontrollera nätverk och klocka: `networkctl`, `timedatectl`, `curl -I https://chatgpt.com`.
4. För beständig arbetsdata: kör `rescue-data /dev/disk/by-uuid/UUID` med en
   avsedd, befintlig ext4-partition. Verktyget formaterar aldrig en partition.
5. Kör `codex login --device-auth` och därefter `rescue-start`.

Codex-inloggning sker i live-miljön och ligger i temporärt hem. Kopiera inte
kontotoken till källkod eller offentliga loggar. Arbetsfiler på datapartitionen
överlever omstart, men inloggningen behöver normalt göras om. Utan datapartition
försvinner arbetet vid omstart. Den nya Codex-sessionen behöver läsa HANDOFF.md.

## Inspektion av den installerade datorn

Identifiera rätt enheter ovan. Exemplen nedan är platshållare, inte kommandon
med verifierade diskvägar. Använd PARTUUID/UUID efter egen inventering.

- Skapa `/mnt/arch` och `/mnt/esp` med sudo.
- Btrfs-inspektion: `sudo mount -o ro,nologreplay,subvol=@ ROOT_DEVICE /mnt/arch`.
- ESP-inspektion: `sudo mount -o ro ESP_DEVICE /mnt/esp`.
- Läs installationens `/etc/fstab`, bootfiler och EutherBoot-konfiguration.
- Jämför hash och innehåll före en reparation. USB-start är inte bevis för varför
  den interna starten slutade fungera.

## Reparation

När rätt partitioner och åtgärd är fastställda: avmontera inspektionsmounts,
montera root skrivbart med rätt subvolym och ESP på installationens verkliga
mountpoint, montera eventuella separata underpartitioner och använd
`sudo arch-chroot /mnt/arch`. Där kan kärna/initramfs byggas om eller startfiler
återställas. Använd installationens konfiguration, inte live-miljöns initramfs.
Ändra inte partitionstabell eller firmwareposter som en automatisk första åtgärd.

En medföljande release och källarkiv finns under `/usr/local/share/euther-rescue/`.
Ersätt bara filer på den identifierade ESP:n efter kontroll av avsedd startväg.
Efter skrivningar: sync, lämna chroot och avmontera innan omstart.

## Offline

Diskverktyg, editor och dokumentation fungerar utan nätverk. Codex-modellen och
nya paketnedladdningar kräver nätverk. Ingen lokal AI-modell ingår. Detta USB
ersätter inte backup av personliga data.

## Senast fungerande startkedja

Den personliga avbilden kan innehålla `known-good/` i samma katalog som denna
fil. Den innehåller den hashidentifierade EutherBoot 0.1.1 från den fysiskt
testade stickan, dess konfiguration/källarkiv, hela interna ESP:n inklusive
GRUB och kärna/initramfs samt fstab, mkinitcpio-/GRUB-konfiguration och
partitionsinventering. `manifest.json` beskriver exakt verifieringsnivå.
Den nya utvecklingsversionen av EutherBoot ligger separat och ska inte
förväxlas med denna kopia.

Kontrollera först kopian med `cd known-good && sha256sum -c SHA256SUMS`.
Jämför sedan live-inventeringen med `block-devices.json` och `host-config/fstab`.
Återanvänd inte gamla /dev/sdX-namn: identifiera rätt ESP genom PARTUUID och
filesystem-UUID. Undersök om kernelpaket/moduler på root har ändrats sedan
kopian togs; en gammal kärna med nya eller saknade moduler är inte en komplett
återställning. Ingen backup av root eller personliga filer ingår.

Återställ enbart de skadade/saknade startfiler som felet kräver, till rätt
monterad ESP. En återställning av USB-kedjan använder `usb/EFI/`; den interna
kedjan använder `internal-esp/`. Återskapa inte partitions-UUID eller NVRAM
automatiskt. Synka, avmontera och prova firmwarets tillfälliga bootmeny efter
åtgärden. Spara loggen och den före reparationen befintliga konfigurationen.

Kopian innehåller maskinspecifika identifierare och är privat. Publicera inte
ISO:n eller dess known-good-katalog som en generell räddningsdistribution.
