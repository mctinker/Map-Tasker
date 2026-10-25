<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../documentation_images/maptasker_logo_dark.png">
    <img src="../documentation_images/maptasker_logo_light.png" alt="MapTasker">
  </picture>
</p>

<div align="center">

![PyPI](https://img.shields.io/pypi/v/maptasker)
![PyPI - Downloads](https://img.shields.io/pypi/dm/maptasker?color=green&label=downloads)
![Downloads](https://static.pepy.tech/personalized-badge/maptasker?period=total&units=international_system&left_color=grey&right_color=green&left_text=downloads)
![Python](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Fmctinker%2FMap-Tasker%2Frefs%2Fheads%2FMaster%2Fpyproject.toml)
![PyPI - License](https://img.shields.io/pypi/l/maptasker)
![](https://tokei.rs/b1/github/mctinker/Map-Tasker)
[![Sourcery](https://img.shields.io/badge/Sourcery-enabled-brightgreen)](https://sourcery.ai)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[!["Buy Me A Coffee"](../documentation_images/coffee.png)](https://www.buymeacoffee.com/mctinker)

</div>

<p align="center">
  <b>Read this in:</b>
  <a href="../README.md">English</a> •
  <a href="README.zh-CN.md">简体中文</a> •
  <a href="README.es.md">Español</a> •
  <a href="README.hi.md">हिन्दी</a> •
  <a href="README.fr.md">Français</a> •
  <a href="README.ar.md">العربية</a> •
  <a href="README.de.md">Deutsch</a> •
  <a href="README.da.md">Dansk</a> •
  <a href="README.fi.md">Suomi</a> •
  <a href="README.ru.md">Русский</a> •
  <a href="README.ko.md">한국어</a> •
  <a href="README.ja.md">日本語</a>
</p>

---

# MapTasker

> Denne oversættelse er genereret automatisk. Ved eventuelle afvigelser er den [originale engelske README](../README.md) gældende.

## Vis/rediger/analyser Tasker-Projects, -Profiles, -Tasks og -Scenes i din skrivebordsbrowser (Mac/Windows 11/Linux) baseret på Taskers backup- eller eksporterede XML-fil

Konfigurationskort (Configuration Map)...
![MapTasker-konfigurationskort: et project, dets profiles og dets tasks som et farvekodet, indrykket skitse, med hver tasks nummererede actions og deres indstillinger angivet nedenunder](../documentation_images/intro.png)

Diagramkort (Diagram Map)...
![MapTasker-diagramkort: et project og dets profiles tegnet som kasser med deres tasks nedenunder, og linjer, der viser, hvilken task der kalder hvilken, med én kaldesti fremhævet](../documentation_images/Introd.png)

[[Flere eksempler]](<https://github.com/mctinker/Map-Tasker/wiki#sample-output>)

Dette er et program, der understøtter [Tasker](https://tasker.joaoapps.com/), og som er tiltænkt at køre i en webbrowser (se [Note 1](#1)).

Jeg fandt ud af, at mine Tasker-Projects/-Profiles/-Tasks/-Scenes blev uoverskuelige, og at min telefon var for lille til at navigere i dem. Derfor skrev jeg et Python-program, der giver et komplet kort over hele min konfiguration i min webbrowser, baseret på den Tasker-backup-XML-fil, jeg havde gemt på mit lokale skrivebords-drev.

Over tid har jeg forbedret kortet med mange yderligere muligheder, herunder muligheden for at redigere Tasker-objekter og få en dybdegående analyse af Tasker-konfigurationen.

Taskers backup-fil eller andet Tasker-eksporteret XML kan enten uploades manuelt til din PC/Mac/Linux/cloud-drev, eller dette program kan hente den direkte fra din Android-enhed (se [Note 2](#2)).

## Funktioner

- Vælg selv detaljeringsgraden for output, fra et kort overblik til et meget detaljeret niveau af din konfiguration.
- Vis kun et enkelt Project, Profile eller Task.
- Inkluder/udelad Profile- og Task-betingelser: States, Events osv.
- Lad output blive strømmet direkte, eller gør det "flot" ved at justere alle felter.
- Skift udseende: vælg 'lys' eller 'mørk' tilstand.
- Output med din foretrukne monospace-skrifttype, og marker Project-, Profile- og Task-navne med kursiv, fed, markering og/eller understregning.
- Ændr farverne, der er knyttet til forskellige aspekter af output, efter dit humør.
- Inkluder TaskerNet-beskrivelser og/eller Tasker-indstillinger (preferences).
- For komplekse konfigurationer kan du valgfrit inkludere en indholdsfortegnelse med hyperlinks til dine Projects, Profiles, Tasks og Scenes.
- Vis et diagram over hele din Tasker-konfiguration samt en Task Flow.
- Kommandolinje- eller grafisk brugergrænseflade.
- Brug eksporteret XML, eller hent XML direkte fra din Android-enhed til konfigurationskortet.
- Send Projects, Profiles, Tasks og Scenes tilbage til Tasker på din Android-enhed.
- Gem og gendan kørselsindstillinger.
- Identificer Tasks med for mange "actions", som potentielt bør opdeles i flere Tasks.
- AI-analysemulighed til at analysere et bestemt Project, Profile, Task eller Scene ved brug af enten de serverbaserede ChatGPT/Claude/Gemini eller de lokalt baserede Llama-modeller (via Ollama).
- Vis resultater direkte i den grafiske brugergrænseflade: (konfigurations-) Map-visning, Tree-visning og Diagram-visning.
- Automatisk opdagelse af opdateringer og valgfri installation af nye versioner.
- Forbedret søgning og struktureret 'Find/Replace'.
- Tilføj og rediger Projects, Profiles, Tasks og Scenes (se [Note 6](#6)).
- Vis en liste over ændringer siden en bestemt dato.
- Knyt et Project, Profile, Task eller Scene til det TaskerNet-share, det kommer fra, bliv underrettet, når forfatteren udgiver en nyere version, og tag dennes ændringer én ad gangen.
- Analyser sundhedstilstanden for Tasker-XML'en samt de mange variabler i hele konfigurationen.
- Sammenlign en XML-fil med den indlæste XML.

## Programafhængigheder

### - Python version 3.11 eller nyere

### - Fuld eller delvis Tasker-XML-fil: backup.xml eller en anden Tasker-eksporteret XML-fil

&nbsp;&nbsp;&nbsp;Du vil blive bedt om at finde og angive din Tasker-eksporterede XML-fil (f.eks. backup.xml) på dit skrivebord, oprettet af Tasker version 5 eller version 6. Du kan også valgfrit hente den direkte fra din Android-enhed (se [Note 2](#2)).

### - AI-analyse

&nbsp;&nbsp;&nbsp;Dette kræver en gyldig API-nøgle, hvis du bruger den serverbaserede analyse, og/eller at Ollama er installeret til lokal analyse (se [Note 3](#3)).


## Installation

Dette program og alle dets forudsætninger vil kræve omkring 230 MB plads. Det anbefales at installere det i et virtuelt miljø (valgmulighed 2).

- Installer MapTasker ved at indtaste en af følgende kommandoer i Terminal/Kommandoprompt:

     ```python -m pip install maptasker -U```
                 ...ELLER...
     ```uv add maptasker```

- For at installere det i et virtuelt miljø, indtast følgende kommando i Terminal/kommandoprompt:

  via pip...
  - `cd xxx`, hvor 'xxx' er den mappe, du vil opsætte det virtuelle miljø i.
  - `python -m venv venv`
  - Aktiver det virtuelle miljø...
    MAC/Linux: `source {directory path to 'xxx'}/venv/bin/activate`
    Windows: `venv\Scripts\activate`
  - `pip install maptasker`

  ...eller...
  
  via uv...
  - `cd xxx`, hvor 'xxx' er den mappe, du vil opsætte det virtuelle miljø i.
  - `uv venv`
  - Aktiver det virtuelle miljø...
    MAC/Linux: `source {directory path to 'xxx'}/venv/bin/activate`
    Windows: `venv\Scripts\activate`
  - `uv pip install maptasker`

- AI-analysefunktionerne kræver ekstra biblioteker (OpenAI, Anthropic, Google og Ollama). MapTasker installerer ikke disse for dig; hvis du vil have dem, skal du installere MapTasker med `ai`-ekstraen i stedet:

     ```python -m pip install "maptasker[ai]" -U```
                 ...ELLER...
     ```uv add "maptasker[ai]"```
  
## Anvendelse

- Indtast kommandoen:

     ```maptasker```
     ...eller, hvis du bruger uv til at administrere det virtuelle miljø...
     ```uv run maptasker```

### Rapporter fra kommandolinjen

Health Check, Compare, Changes Since, Export og en mappeovervågning (watch) kører uden vindue, så en natlig Tasker-backup kan kontrolleres automatisk (fra `cron`, Jobplanlæggeren, `launchd` eller et CI-job):

```
maptasker -healthcheck -file backup.xml                 # problemer i en backup
maptasker -compare older.xml newer.xml                  # hvad der er forskelligt mellem to backups
maptasker -changes_since week -file backup.xml          # hvad der er ændret: today (i dag), week (uge), month (måned), all (alt), en dato, eller 3d (3 dage)
maptasker -export map -format md -file backup.xml       # Map'en (eller diagrammet) som md, json eller pdf
maptasker -watch ~/TaskerBackups                        # registrerer hver ny backup i historikken
```

- **`-file`** accepterer en backup eller en mappe (den nyeste `.xml`-fil i den bruges). `-outdir` vælger, hvor filer skrives, og `-save` gemmer også rapporten som en fil, ligesom vinduet gør.
- **Kun rapporten, og kun rapporten, sendes til standard output**; alt andet sendes til standard error, så `maptasker -healthcheck -file backup.xml > report.txt` giver en ren rapport.
- **Exit-koder** gør det muligt for et script at handle baseret på resultatet:

  | Kode | Betydning |
  |---|---|
  | 0 | Færdig, og der var intet at rapportere |
  | 10 | Rapporten fandt noget: Health Check-fejl (`-fail_on warning` for at inkludere advarsler, `-fail_on never` for at ignorere dem), eller forskelle |
  | 11 | `-changes_since` havde ingen tidligere konfiguration at sammenligne med (det første kørsel starter historikken) |
  | 1 | Programfejl |
  | 2 | En fil kunne ikke skrives (herunder en `-outdir`-mappe, der ikke kan bruges), eller output kunne ikke oprettes |
  | 3 | Filen er ikke en gyldig Tasker-backup |
  | 5 | Det ønskede enkelte Project, Profile eller Task (`-project`, `-profile` eller `-task`) blev ikke fundet |
  | 6 | Ingen fil blev angivet, eller filen/mappen findes ikke |
  | 7 | Ugyldig indstilling, såsom en forkert farve, en ukendt `-fail_on`-værdi, eller sammenligning af en fil med sig selv |
  | 8 | Anmodningen til Android-enheden, der kører Tasker-serveren, mislykkedes |

- **Historikken.** Hver backup, der indlæses, registreres i konfigurationshistorikken, som er det, `-changes_since` læser. `-watch FOLDER` registrerer hver ny, komplet backup, der dukker op i `FOLDER`, dateret efter filen, så historikken fyldes op, selv på dage hvor du aldrig åbner MapTasker; `-watch FOLDER -once` kontrollerer kun en enkelt gang, til et planlagt job. Historikken opbevares i en mappe kaldet `MapTasker_Timeline` i den mappe, MapTasker køres fra, så et planlagt job bør bruge `-history_dir` til at pege på den samme mappe, vinduet bruger.
- **Intet andet ændres.** Disse kørsler åbner aldrig en browser og overskriver aldrig de indstillinger, vinduet opbevarer.

## Programoutput

MapTasker genererer en række outputfiler, både på skrivebordet og på Android-enheden.

Se [wikien](https://github.com/mctinker/Map-Tasker/wiki/Generated-Output) for en komplet liste over MapTaskers genererede output.


## Mere: [[Kørselsindstillinger]](https://github.com/mctinker/Map-Tasker/wiki/Runtime-Options)&nbsp;&nbsp;&nbsp;[[Eksempler på kørselsindstillinger]](https://github.com/mctinker/Map-Tasker/wiki/Sample-Runtime-Options)&nbsp;&nbsp;&nbsp;[[Eksempel på output]](https://github.com/mctinker/Map-Tasker/wiki#sample-output)

## Projektstruktur

Et kort overblik over de vigtigste filer og deres formål:

- `maptasker/`: Indeholder kerneapplikationskoden.
  - `maptasker/src/`: De vigtigste Python-kildefiler til MapTaskers logik.
  - `maptasker/assets/`: Statiske ressourcer såsom ikoner, billeder og JSON-data, som applikationen bruger.
  - `maptasker/locale`: sprogfiler til oversættelser.
- `documentation_images/`: Billeder brugt i denne README og anden dokumentation.
- `tools/`: hjælpeprogrammer brugt under udvikling.
- `tests/`: Indeholder testscripts og relaterede filer for at sikre kodekvaliteten.
- `maptasker/main.py`: Indgangspunktet bag kommandoen `maptasker`. Fra et klonet repository, kør `python -m maptasker.main`.
- `LICENSE`: Projektets MIT-licensfil.
- `README.md`: Denne fil (den oprindelige engelske udgave).
- `Changelog.md`: En log over ændringer foretaget i hver version.
- `pyproject.toml`: Projektmetadata og build-system-konfiguration.

## Licens

Dette projekt er licenseret under [MIT-licensen](../LICENSE).

MIT-licensen er en tilladende fri software-licens, der stammer fra Massachusetts Institute of Technology (MIT). Som en tilladende licens sætter den kun meget begrænsede restriktioner på genbrug og har derfor høj licenskompatibilitet.

Kort sagt betyder det, at du er fri til at:

- **Bruge**: Bruge softwaren til ethvert formål (kommercielt eller privat).
- **Ændre**: Ændre softwaren.
- **Distribuere**: Distribuere den originale eller ændrede software.
- **Underlicensere**: Underlicensere softwaren.

Du skal:

- **Inkludere copyright**: Inkludere den oprindelige copyright-meddelelse og selve licensen i enhver væsentlig del af softwaren.

Softwaren leveres "SOM DEN ER", uden nogen form for garanti. For den fulde licenstekst, se venligst filen [LICENSE](../LICENSE).

## Fejlfinding og ofte stillede spørgsmål

**S: Diagrammet `MapTasker_Map.txt` ser forkert justeret ud i Notesblok på Windows.**

S: Notesblok håndterer måske ikke mellemrum i denne fil korrekt.

Det anbefales at bruge en anden teksteditor såsom Notepad++, VS Code eller Typepad (og sætte den som standard for `.txt`-filer). Sørg for, at 'tekstombrydning' er slået fra, og at der bruges en monospace-skrifttype.

**S: Hvordan henter jeg Tasker-XML-filen direkte fra min Android-enhed?**

S: Forudsætninger:

1- Browseren og Android-enheden skal være på samme lokale netværk.

2- ['Http Server Example'-Tasker-projektet](https://shorturl.at/bwCD4) skal være installeret og aktivt på Android-enheden, med serveren kørende.

Yderligere detaljer findes i afsnittet "Noter" i denne README.

**S: Diagramforbindelser er forkert justeret for navne på kinesisk, koreansk eller japansk.**

S: Dette er et kendt problem relateret til skrifttypemetrikker for disse sprog i diagram-biblioteket.

**S: Hvorfor er visse Task-actions og Profile-states/events ikke tilgængelige til redigering/tilføjelse?

S: I visse tilfælde kræver disse actions, events eller states oplysninger, der kun er tilgængelige på Android og/eller i Tasker selv. At tillade redigering af disse ville resultere i en ufuldstændig Task eller Profile, hvilket ville forårsage en Tasker-fejl.

## Noter

Detaljer om nogle af de punkter, der er nævnt i afsnittet "Fejlfinding og ofte stillede spørgsmål", er bevaret her for yderligere kontekst.

### 1
**Specifikt for Windows 11:**

- Kun Windows 11 understøttes. Ingen tidligere versioner af Windows understøttes.
- Ved visningsproblemer med `MapTasker_Map.txt` i Notesblok, brug en alternativ teksteditor som Typepad og sæt den som standard for `.txt`-filer.

### 2
**Direkte hentning af XML fra Android:**

For at hente Tasker-XML-filen direkte:

- Sørg for, at både skrivebordet og Android-enheden er på samme lokale netværk, og at Tasker kører.
- ['Http Server Example'-Tasker-projektet](https://shorturl.at/bwCD4) skal være installeret og aktivt på Android-enheden, med serveren kørende. Husk at køre "Update GD HTTP Info"-Tasken og (kun første gang) indtaste dit Google Drive-ID, når du bliver bedt om det.
- Når den er hentet, gemmes XML'en på dit skrivebord og behøver ikke konstant at blive hentet igen, medmindre den ændres.

### 3
**AI-understøttelse**

AI-analyse er kun tilgængelig via den grafiske brugergrænseflade. Du kan kun køre en analyse ved brug af et enkelt Project, Profile, Task eller Scene. Understøttelse er tilgængelig for serverbaseret OpenAi (ChatGPT), Gemini og Anthropic, samt lokalt baserede Llama-modeller.

Llama-baserede modeller understøttes via [Ollama](https://ollama.com/), som du manuelt skal downloade, installere og køre én gang for at opsætte serveren på dit skrivebord. MapTasker vil dynamisk indlæse Llama-modellerne for dig, hvis de ikke allerede er indlæst.

De understøttende AI-moduler installeres ikke som standard, når MapTasker installeres. I stedet installeres de dynamisk ved første brug af den specifikke AI-anmodning. På denne måde pådrager du dig ikke denne overhead, hvis du ikke planlægger at bruge AI.


## Forbehold ved redigering og analyse af applikationen
**MapTasker-forbehold ved redigering og analyse**

Se dokumentet [Caveats](https://github.com/mctinker/Map-Tasker/blob/Master/caveats.txt) for detaljer.


## To-do-liste (i ingen bestemt rækkefølge)

- [x] Readiness Check (beredskabskontrol)

- [x] Understøttelse af yderligere plugins

- [x] Import med afhængigheder (Import with Dependencies)

- [ ] Kortlæg resterende Tasker-indstillinger

- [x] Task Stepper: "dry-run" en Task action for action, og vis hvilke If-, For- og Goto-forgreninger der køres, og hvad hver variabel indeholder

- [x] Live Run Monitor: strøm live, hvilke Profiles og Tasks der udløses på telefonen, og markér dem i Diagram-visningen

- [ ] Tre-vejs-sammenlægning (three-way merge) af to backups i forhold til en fælles forfader, løst konflikt for konflikt og kan fortrydes i ét trin

- [x] TaskerNet-opdateringssporing: giver dig besked, når forfatteren af et share, du bruger, udgiver en ny version, med en diff af ændringerne

- [ ] Personligt snippet-bibliotek: gem genanvendelige action-sekvenser, Tasks og Profile-skabeloner, og indsæt dem med parametre

- [ ] Forklaringer i almindeligt sprog i Map'en: en AI-skrevet, cachelagret og redigerbar en-linjes opsummering af hver Profile og Task

- [x] Kontrol af manglende ressourcer: bekræft, at de filer, mapper, billeder, lyde, Scenes og apps, dine actions refererer til, stadig findes

- [x] Kompleksitets- og trend-dashboard: følg Task-længde, indlejring, kalde-kædedybde og fund over tid

- [ ] Eksport af dokumentationswebsted: et sammenkoblet sæt Markdown- eller HTML-sider, én pr. Project, Profile, Task og Scene, med kaldediagrammer

- [x] Assistent til omdøbning og scope af variabler: omdøb en variabel, eller lav en global til en lokal, alle steder den bruges, som én fortrydelig handling

## Erklæring om privatliv

Der indsamles og sendes ingen oplysninger overhovedet via netværket til mig eller nogen anden tredjepart, bortset fra det, der er anført nedenfor (netværkstrafik).

Når du rapporterer en fejl, vil du højst sandsynligt blive bedt om at angive output-logfilen for fejlen samt din XML-fil, som begge udelukkende bruges til at fejlfinde programmet og derefter slettes med det samme.

Netværkstrafikken er som følger:

- Lokal LAN-trafik, når XML hentes direkte fra din Android-enhed.
- Ved opstart, én gang dagligt, kontrolleres pypi.com for at afgøre, om en ny version er tilgængelig.
- Programmet opdateres fra pypi.com (via 'pip'), hvis 'Upgrade' vælges i den grafiske brugergrænseflade.
- Filen 'Changelog.md' læses fra '<https://github.com/mctinker/Map-Tasker>', hvis "What's New" vælges i den grafiske brugergrænseflade.
- chatgpt.com bruges, når AI-analyse anvendes med en af OpenAi-modellerne. Output fra MapTasker sendes til serveren via det almindelige API-kald til analyse. Det samme gælder for Claude (Anthropic) og Gemini (Google).
- Nye og opdaterede lokale AI-modeller indlæses fra '<https://ollama.com/library>', når AI-analysefunktionen køres.
- Billede- og video-kilde-hyperlinks defineret via HTML-tagget '<img src=https://...>' i Task-action-labels og TaskerNet-beskrivelser vil blive tilgået, når der klikkes på dem. Eksempler: imggur.com, Youtube, Dropbox, Google Drive osv.

## Bidrag

Bidrag er velkomne! Her er nogle måder, du kan bidrage til MapTasker på:

**Rapportering af fejl:**

- Hvis du finder en fejl, åbn venligst et issue på [GitHub Issues-siden](https://github.com/mctinker/Map-Tasker/issues).
- Inkluder så mange detaljer som muligt:
  - Trin til at genskabe fejlen.
  - Forventet adfærd og faktisk adfærd.
  - Dit operativsystem og Python-version.
  - MapTasker-version.
  - Relevante dele af din Tasker-XML-fil (hvis relevant, og sørg for, at ingen følsomme oplysninger er inkluderet).
  - `maptasker.log`-filen, hvis den er genereret med `-debug`-indstillingen.

**Forslag til forbedringer:**

- Åbn et issue på GitHub og beskriv dit forslag.
- Forklar anvendelsesformålet, og hvorfor denne forbedring ville være en fordel.

**Pull Requests:**

- Hvis du vil bidrage med kode:
    1. Fork repositoriet.
    2. Opret en ny branch til din funktion eller fejlrettelse (f.eks. `feature/new-output-format` eller `fix/xml-parsing-error`).
    3. Foretag dine ændringer.
    4. Sørg for, at din kode følger Black-kodestilen (som angivet af badge'et).
    5. Tilføj tests for dine ændringer i mappen `tests/`, hvis relevant.
    6. Sørg for, at alle tests bestås.
    7. Indsend en pull request til `Master`-branchen.

**Kodestil:**

- Dette projekt bruger [Ruff](https://docs.astral.sh/ruff/formatter/) til kodeformatering. Sørg venligst for, at dine bidrag er formateret med Ruff.

Vi værdsætter din hjælp til at gøre MapTasker bedre!

## Kendte problemer

- Diagramforbindelser er forkert justeret, hvis navne er på kinesisk, koreansk eller japansk.
- Ikke alle Task-actions og Profile-state/event-redigeringer understøttes, da nogle kræver oplysninger, der kun er tilgængelige på en Android-enhed.

## Bidragydere

[Taskometer](https://github.com/Taskomater/Tasker-XML-Info)

[©Connor Talbot 2021 for Clippy](https://github.com/con-dog/clippy)

[Ollama](https://ollama.com/), [OpenAi](https://openai.com/), [Claude AI](https://claude.ai), [Gemini AI](https://gemini.google.com/)

[NiceGui](https://nicegui.io/)

[!["Buy Me A Coffee"](../documentation_images/coffee.png)](https://www.buymeacoffee.com/mctinker)
