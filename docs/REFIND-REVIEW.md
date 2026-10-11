# rEFInd: lärdomar och nästa steg

Genomgång 2026-10-11. Förslag för EutherBoot, inte implementerade funktioner.
Ingen omstart eller ändring av värdens firmware behövs för detta arbete.

## Prioritet

1. Prova rescue-stickan på den andra datorn: UEFI-start, tangentbord, nätverk,
   Codex-inloggning och arbetsfil som finns kvar efter omstart. Nuvarande
   rescue-startfil är osignerad och kräver Secure Boot avstängt.
2. Lägg till en läsande diagnostikvy: SecureBoot/SetupMode, firmwarearkitektur,
   grafikläge och startvolym. Skilj okänd status från avstängt och avvisad signatur.
3. Förbättra upptäckt: visa ursprungsvolym och filtrera hjälpprogram/dubbletter.
   Behåll uttryckligt val och import till utkast. rEFInd har separata filter för
   volymer, kataloger och filer: [konfiguration](https://www.rodsbooks.com/refind/configfile.html).
4. Fortsätt System Regis-temat med gemensamma färgroller och tydliga ikoner.
   Separata visuella resurser är användbara; kopiera inte rEFInds utseende.
   [Temadokumentationen](https://www.rodsbooks.com/refind/themes.html) beskriver
   bakgrund, ikoner och markeringar som separata resurser.
5. Verifiera direkt Arch-start och återställning fysiskt innan GRUB avvecklas.

## Secure Boot: två skilda spår

**Egna firmwarebetrodda nycklar:** projektets hanterade Arch-installation kan
redan signera EutherBoot och UKI:er. Befintliga isolerade OVMF-tester provar
accepterade och avvisade avbilder. Nyckelregistrering sker inte automatiskt;
fysisk verifiering återstår. Läs INSTALLATION.md och VALIDATION.md.

**Shim/MOK:** möjligt framtida kompatibilitetsspår, inte en menyinställning.
rEFInd dokumenterar MOK-registrering och SBAT. Vi behöver separat design,
autentisering av efterföljande program, uppdaterings-/återkallningshantering
samt tester med betrodda, okända och återkallade avbilder. Ingen garanti om
start på godtycklig dator med Secure Boot på kan ges.
Källor: [rEFInd Secure Boot](https://www.rodsbooks.com/refind/secureboot.html),
[shim SBAT](https://github.com/rhboot/shim/blob/main/SBAT.md).

Rescue behöver ett eget verifierat Secure Boot-flöde. Att bara signera dess
första EFI-fil räcker inte som bevis för hela räddningsmiljöns integritet.
Även live-systemets innehåll och uppdateringar måste ingå i designen.
Extern TOML och separat initrd ska inte beskrivas som autentiserade bara för
att EutherBoot är signerad; den testade självständiga UKI-vägen är tydligare.

## Avgränsning

Inga firmwarevariabler, nycklar eller interna bootfiler ändras i denna etapp.
Fler filsystemsdrivrutiner, legacy BIOS och musanimationer prioriteras efter
fungerande direktstart och räddning. Verktyg för omstart/firmwareinställningar
kan tillkomma senare; återgång till firmware är inte samma sak som att öppna
firmwareinställningarna.
