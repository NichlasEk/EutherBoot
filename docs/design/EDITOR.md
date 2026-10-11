# Grafisk editor, svenska och teman

Designförslag 2026-10-11, framtaget medan rescue-USB skrevs. SVG-filerna är
skisser; de visar inte funktioner som redan är implementerade i EFI-programmet.

- [Regis: marinblått, stål och guld](editor-regis.svg)
- [Ljust tema](editor-ljus.svg)
- [Hög kontrast](editor-kontrast.svg)

## Ursprungligt nuläge före implementation

F3-editorn ritas med firmwarets textkonsol. Den grafiska menyn används bara
vid förhandsvisning. G växlar mellan `system-regis` och `text`; några andra
teman godtas inte av parsern. Alla UI-texter är engelska.

`editor.rs::prompt` tar bara emot ASCII. `config.rs` avvisar svenska tecken i
postnamn. `graphics.rs` och fontatlasserna omfattar endast ASCII. Dessutom
räknar vissa fält byte och detaljvyn delar text i byteblock. Därför räcker det
inte att översätta strängarna eller bara lägga till å/ä/ö i typsnittet.

Rescue-Linux har separat svensk konsollayout. UEFI-editorn tar emot tecken
från firmware; dess layout och svenska inmatning måste provas på fysisk dator.
Inga påståenden om generell svensk UEFI-tangentbordslayout är ännu verifierade.

## Föreslagen editor

Behåll det godkända emblemet: stålsvärd och guldkronor. Marinblå ytor, tunna
linjer, läsbara antialiaserade typsnitt och en sparsam guldmarkering för fokus.

På 1024×768 visas startposter till vänster och den valda postens fält till
höger. Fält för typ, partition, initrd och kommandorad ligger på en separat
Detaljer-sida. Globala val (förvald post, timeout, tema och språk) ska tydligt
skiljas från postens egna fält i implementationen. Skissen visar dessa ihop
för att pröva formspråket, inte en fastställd slutlig fältordning.

På 640×480 används en kolumn och separata sidor för poster, detaljer och
globala inställningar. Text får inte krympas tills den blir oläslig. Tangentbord
är förstahandsstyrning; knappliknande element innebär inte utlovat musstöd.

Inspektion, utkast och osparade ändringar ska vara lätta att skilja åt.
Spara öppnar fortsatt en bekräftelse med en sammanfattning av ändringarna.
Förhandsvisning startar ingenting och skriver ingenting. Avbryt ska behålla
originalet. Befintlig transaktion, backup och återställning ska återanvändas.

## Svenska i tre separata steg

1. Gemensamma språktexter för `en` och `sv`, inklusive fel, hjälp, bekräftelser,
   upptäckt och förhandsvisning. Saknad språknyckel får en läsbar reservtext.
2. Definierad uppsättning visningstecken med minst ÅÄÖåäö. Samma teckenregler
   används för inmatning, validering och fontatlas. Gränser för visningsnamn
   räknas i tecken; klippning/radbrytning får inte dela UTF-8. Kontrolltecken
   och osynliga styrtecken ska fortsatt avvisas. Tekniska ID:n och GUID-format
   förblir oförändrade; svenska postnamn innebär inte automatiskt Unicode-stöd
   för alla sökvägar och Linux-kommandorader.
3. Fysiskt tangentbordstest för å/ä/ö och viktiga sökvägstecken. Om firmware
   inte levererar tecknen korrekt behövs ett uttryckligt separat beslut om
   layoutstöd; undvik att gissa genom att byta plats på mottagna tecken.

## Teman

Börja med tre inbyggda paletter: `system-regis` (standard),
`system-regis-light` och `high-contrast`. Behåll `text` som reservläge.
Språk väljs separat från tema. Ett tema styr färger och eventuellt bakgrund,
inte startlogik, timeout eller lagring. Samma tema används i huvudmeny,
editor, upptäckt, dialoger och förhandsvisning.

Centralisera färgroller för bakgrund, yta, text, dämpad text, fokus och fel.
Markera fokus och status med både form/text och färg. Börja med inbyggda teman;
externa godtyckliga typsnitt, skript eller temapaket behövs inte i första steget.

## Genomförande och verifiering

1. Separera text-/fältritning från editorns tillstånd och lagring.
2. Inför teckenregler, svenska glypher och UTF-8-säker klippning med enhetstester.
3. Inför språktexter och central palett; bevara befintliga konfigurationer.
4. Implementera grafisk inspektion, utkast, fält, detaljer och bekräftelse,
   inklusive lågupplöst layout och textreserv.
5. Prova hela flödet i QEMU: redigera `Räddningsmiljö`, byt tema/språk,
   förhandsvisa, avbryt, spara och starta om. Kontrollera exakt backup och
   att avbrutna ändringar inte skrivits. Kör befintliga fel-/återställningstest.
6. Prova fysisk tangentbordsinmatning och båda grafik-/textlägena.

## Implementation i denna etapp

Grafiska vyer för inspektion, utkast, fält, detaljer och bekräftelse är nu
implementerade med samma GOP-renderare som huvudmenyn. G växlar de fyra temana
(inklusive text); L växlar svenska/engelska. Namn stöder ASCII och ÅÄÖåäöÉé,
med teckenbaserade gränser och UTF-8-säker klippning. Inställningarna ligger i
utkastet tills användaren sparar. Vid avbrutet utkast återställs menyns tema/språk.

Implementationens navigering använder de befintliga bokstavskommandona; skissens
Tab-flöde är inte implementerat. På 640×480 används en kompakt lista med tre
poster per sida och detaljer bakom F6. F4-upptäckt har fortfarande textgränssnitt,
och tekniska parser-/lagringsfel har kvar engelska diagnostiktexter. Svenska
firmwaretangenter och fysisk grafik måste fortfarande provas på datorn.

Rescue 0.1.1 innehåller nu både den nya editorns källkod och projektets
EFI-release. Rescue-systemets egen start använder fortfarande systemd-boot.
