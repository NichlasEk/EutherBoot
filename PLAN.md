# EutherBoot – visuellt lyft, räddnings-USB och ersättning av GRUB

Datum: 2026-10-11. Status: grafisk meny/editor implementerade; rescue-USB skrivet, fysiskt test återstår.

## Mål och ordning

EutherBoot ska bli datorns ordinarie bootmeny och starta Arch direkt, utan GRUB.
Ett separat Arch live-USB med Codex CLI ska göra det möjligt att felsöka och
reparera installationen även när den interna bootloadern inte fungerar.

Arbetsordning:

1. Förbättra EutherBoot visuellt och verifiera den befintliga startvägen.
2. Bygg och testa ett självständigt räddnings-USB med Codex.
3. Verifiera direktstart av befintligt Arch genom EutherBoot från USB.
4. Installera EutherBoot internt och verifiera uppdateringar.
5. Avveckla GRUB när både direktstart och räddningsväg är fysiskt testade.

Planen kräver inte flera permanenta kärn-/UKI-generationer på intern ESP.
Den befintliga hanterade installationslösningens generationskrav behöver därför
anpassas separat; dess nuvarande utrymmeskontroller ska inte bara kringgås.

## Verifierat utgångsläge

- EutherBoot 0.1.1 har startat på fysisk hårdvara.
- Foto visar F4 med två verifierade ESP:er och en hittad EFI-applikation.
- Användaren har verifierat F4 → Esc → huvudmeny → befintlig GRUB → Arch.
- Körande kärna och installerat linux-paket motsvarar 7.2.9-arch1-1.
- Intern ESP är cirka 1 GiB, med cirka 418 MiB ledigt vid inventeringen.
- Inga gamla kärnavbilder hittades på ESP:n. Gamla modulrester ligger på root.
- Separat provbyggd initramfs minskade från 256 till 101 MiB med explicit NVIDIA
  och utan bred KMS-insamling. Den är inte installerad eller starttestad.
- Installerade startfiler är oförändrade. Inga partitioner behöver ändras för
  första etappen.

Detaljer och begränsningar finns i [handoff](HANDOFF.md),
[kompatibilitetsrapport](docs/HOST-COMPATIBILITY.md) och
[validering](docs/VALIDATION.md).

## Etapp 1 – visuellt lyft först

### Föreslagen riktning

Användarens referenser är rEFInd/rEFIt för grafisk kvalitet och tydliga
startikoner, samt [EutherFPScan](https://github.com/NichlasEk/EutherFPScan) för
System Regis-identiteten. Referenskoden granskades vid commit
`1599ed4aa679cbfaa51fbafbeafcc1354007c7b6`, särskilt `regis/style.css`,
`sddm/regis/LoginView.qml` och `regis/assets/regis.svg`.

Uttrycket ska vara mörkblått och varmt guld med diskreta turkosa detaljer.
Detta ersätter det tidigare preliminära förslaget med blå/cyan som huvudaccent.

| Del | Riktning från EutherFPScan |
| --- | --- |
| Bakgrund | Nästan svart marinblå, `#090f18` |
| Paneler | Djup blå, `#101b29`, med försiktig toning |
| Primär accent | Varmt guld, `#d0b87d` |
| Rubriker | Ljust elfenben, `#eee5cd`, serifkaraktär |
| Brödtext | Klar sans-serif; sekundär text `#a5b1c0` |
| Fokusdetaljer | Turkos `#72d7d5`, tydlig form utöver färgen |
| Dekoration | Tunna geometriska ledningslinjer och Regis-emblem med tre kronor |

- Placera stora, konsekvent ritade startikoner i en centrerad rad eller ett
  anpassningsbart rutnät med gott om luft. Visa bara verkligt konfigurerade val.
- Ge valt alternativ en mjukt tonad panel, guldram och en tydlig textetikett.
- Visa valt systems namn och kort beskrivning under ikonerna. Tekniska sökvägar
  och GUID hör hemma i detaljvyn.
- Placera mindre verktygsikoner separat nedanför startvalen. Visa endast
  funktioner som faktiskt finns; exempelvis omstart kräver implementation först.
- Håll logotyp och System Regis-identitet diskreta ovanför huvudvalen.
- Använd en lugn bakgrund med geometriska detaljer, egna ikoner och ett enhetligt
  materialuttryck. Referensbildernas galaxbakgrund och ikonuppsättning kopieras inte.
- Samla tangentförklaringar i nederkanten. Fastställ vänster/höger-navigation
  för ikonraden och behåll befintlig tangentbordsfunktion under övergången.
- Skala om och paginera vid liten upplösning eller många startalternativ.

Grafisk kvalitet kräver också bättre text och kantutjämning. Undersök en
licenskompatibel font som rasteriseras vid bygge till en inbäddad glyphatlas,
samt skalbara kodritade ikoner eller förberedda ikonstorlekar. UEFI behöver inte
Qt, GTK eller en webbläsare för detta. Bevara GOP- och textreservvägarna.
Animation är fortsatt valfri; första bilden ska vara snabb och färdig.

### Genomförande

1. Ta referensbilder av nuvarande huvudmeny i QEMU.
2. Implementera ett första sammanhängande utseende för huvudmenyn i befintlig
   GOP-renderare; använd paletten ovan och förbättra text/ikoner så att kvaliteten inte begränsas
   till större versioner av nuvarande bitmaptext.
3. Visa faktiska QEMU-bilder för visuell granskning och justera layouten.
4. Kontrollera lång text, flera sidor, vald rad, fel och tangentförklaringar.
5. Ge F4 och editor samma formspråk i en efterföljande del av etappen. Behåll
   fullständig information och fungerande textläge under övergången.
6. Leverera en identifierad testversion på avsett testmedium efter att den
   befintliga startvägen klarat regressionskontroll.

### Klart när

- Huvudmenyn är läsbar vid 640×480 och 1024×768 samt en högre upplösning.
- Alla tillåtna menyval går att nå, även med sidindelning och långa namn.
- F2/textreservvägen fungerar; F4 och Esc beter sig som tidigare.
- Val, start, felretur och eventuell timeout behåller sina befintliga regler.
- Den nya versionen har fysiskt visat korrekt meny och startat GRUB → Arch.

Etappen omfattar utseende och presentation. Direktstart och intern installation
hör till senare etapper, så ett visuellt test kan jämföras med den kända vägen.

## Etapp 2 – självständigt Arch live-USB med Codex

### Innehåll

- Egen Archiso-profil med terminalmiljö, svenskt tangentbord och nätverksstöd.
- Förinstallerad, versionsbestämd Codex CLI med kontrollerat ursprung.
- Git, editor, tmux, curl, arkivverktyg och relevanta byggverktyg för EutherBoot.
- arch-chroot, pacman, mkinitcpio, Btrfs-/FAT-verktyg och EFI-/GPT-inspektion.
- EutherBoot-källkod, matchande fungerande EFI-fil, bygginstruktioner och handoff.
- Offlineinstruktioner för att montera root/ESP och reparera startkedjan manuellt.
- Beständig datayta för arbetsfiler, loggar och sessionsunderlag.

Välj exakt USB-layout och kapacitet efter att avbilden har byggts och mätts.
Räddningsmediet ska ha egen kärna och eget rotfilsystem och inte behöva läsa
startfiler från intern ESP. Ge det en oberoende, etablerad UEFI-startväg så att
en regression i EutherBoot inte samtidigt slår ut räddningsmiljön.

### Codex och arbetsflöde

1. Starta USB via firmwarets tillfälliga bootmeny.
2. Anslut nätverket och logga in i Codex, exempelvis med enhetskod via mobilen.
3. Läs medföljande handoff; den nya sessionen får inte denna chatt automatiskt.
4. Identifiera diskar och börja med skrivskyddad inspektion av installationen.
5. Montera skrivbart och använd chroot när en konkret reparation ska utföras.
6. Spara resultat och uppdaterad handoff på USB:s beständiga datayta.

AI-hjälpen behöver nätverk och giltig inloggning. Diskverktyg och manuella
instruktioner ska fungera offline. Byggavbilden innehåller inga kontotoken;
eventuell beständig inloggning hanteras separat från den distribuerbara avbilden.

### Verifiering och leverans

- Bygg avbilden och dokumentera paketversioner och kontrollsummor.
- Testa i QEMU utan intern startdisk: terminal, nätverk, verktyg och datalagring.
- Öva återställning på en virtuell Arch-disk med saknade bootfiler.
- Identifiera fysisk USB och dess innehåll innan någon avbild skrivs. En
  omskrivning av befintlig teststicka måste vara ett medvetet destinationsval.
- Återläs och kontrollera leveransen samt testa fysisk start, nätverk, Codex-
  inloggning och åtkomst till intern installation.
- Bekräfta beständighet genom en omstart av USB-miljön.

Klart när användaren kan starta räddningsmiljön oberoende av intern bootloader
och arbeta med Codex där. Interna bootfiler behöver inte förstöras för detta test.

## Etapp 3 – direkt Arch-start från EutherBoot på USB

1. Bevara nuvarande fungerande bootfiler på räddningsmediets datayta.
2. Bygg och mät en komplett direktstartskandidat med den mindre initramfsen.
3. Välj mellan EFI-stub med extern initramfs och en självständig UKI. En UKI
   förenklar sammanhållningen av kärna, initramfs och kommandorad; den externa
   vägen har för närvarande en 128 MiB-gräns i EutherBoot.
4. Utgå från datorns riktiga root-/Btrfs-inställningar och aktuell kärna.
5. Lägg kandidaten på testmediet och starta befintligt internt Arch utan GRUB.
6. Verifiera root, rätt kärna, NVIDIA/grafik, tangentbord, nätverk och omstart.

En lyckad provbyggnad är inte ett godkänt fysiskt starttest. Om den mindre
initramfsen inte fungerar justeras den före intern installation.

## Etapp 4 – liten intern installation och uppdateringsflöde

Mål: EutherBoot, konfiguration och en aktuell direktstartskandidat på ESP:n.
Räddnings-USB ersätter behovet av flera permanenta interna generationer.

- Mät faktiska filer, ledigt utrymme och nödvändigt arbetsutrymme innan layouten
  bestäms. Förstora inte ESP:n enbart utifrån det gamla generationsbudgeten.
- Anpassa installations-/uppdateringsverktygen till en uttrycklig enkel profil
  utan obligatorisk LTS eller permanent flergenerationslagring.
- Bygg och verifiera en ny kandidat innan den aktiva ersätts. Räkna med
  tillfälligt utrymme för gammal och ny fil och definiera återhämtning vid avbrott.
- Testa uppdatering, full ESP och avbruten publicering i QEMU.
- Installera internt först när räddningsmediet och direktstarten fungerar.
- Verifiera fysisk start utan USB samt start efter en verklig kärnuppdatering.

USB-räddning innebär manuell återhämtning vid fel; den ger inte automatisk rollback
och ersätter inte backup av personliga data.

## Etapp 5 – avveckla GRUB

- Kontrollera att ordinarie intern start går direkt genom EutherBoot.
- Kontrollera att uppdateringsflödet inte är beroende av GRUB.
- Spara identifierade GRUB-filer och relevant konfiguration på räddningsmediet.
- Ta bort endast bekräftat överflödiga filer/paket och justera firmwareposter
  utifrån den då aktuella disk- och bootinventeringen.
- Kontrollera kallstart utan USB och en separat start av räddnings-USB.
- Uppdatera README, installation, validering och handoff till slutligt upplägg.

## Nästa konkreta arbete

**Börja med etapp 1: huvudmenyns visuella utformning.** Räddnings-USB och
ersättningen av GRUB är planerade efterföljande arbeten. Den här planfilen
installerar inget, skriver inget USB och ändrar ingen bootordning.

## Nästa prioriteringar efter USB-leveransen

Se [rEFInd-genomgång och Secure Boot-spår](docs/REFIND-REVIEW.md).

Rescue 0.1.1 har byggts, QEMU-testats och levererats till General UDisk med
korrigerad Codex-start och grafisk editor inkluderad. Nästa steg är fysisk
Codex-inloggning/arbetsdata, sedan direktstart av installerat Arch. Värddatorn
har inte startats om under bygget eller USB-leveransen.

## Direktstartstest förberett

Rescue-stickans fysiska start och Codex-inloggning är bekräftade av användaren.
En separat Kingston DataTraveler har fått EutherBoot med normal/fallback-UKI
för befintligt Arch samt GRUB som reservval. Avbilden är QEMU-testad och USB-
leveransen verifierad; fysisk direktstart återstår. Se
[DIRECT-ARCH-USB.md](docs/DIRECT-ARCH-USB.md). Ingen intern installation ännu.
