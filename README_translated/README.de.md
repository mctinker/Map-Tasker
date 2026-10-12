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

> Diese Übersetzung wurde automatisch erstellt. Bei Abweichungen gilt die [ursprüngliche englische README](../README.md).

## Zeigen, bearbeiten und analysieren Sie Ihre Tasker-Projects, -Profiles, -Tasks und -Scenes im Desktop-Browser (Mac/Windows 11/Linux) anhand der Tasker-Backup- oder exportierten XML-Datei

Konfigurationskarte (Configuration Map)...
![MapTasker-Konfigurationskarte: ein Project, seine Profiles und seine Tasks als farblich codierte, eingerückte Gliederung, mit den nummerierten Actions jeder Task und ihren Einstellungen darunter](../documentation_images/intro.png)

Diagrammkarte (Diagram Map)...
![MapTasker-Diagrammkarte: ein Project und seine Profiles als Kästen gezeichnet mit ihren Tasks darunter, und Linien, die zeigen, welche Task welche andere Task aufruft, mit einem hervorgehobenen Aufrufpfad](../documentation_images/Introd.png)

[[Weitere Beispiele]](<https://github.com/mctinker/Map-Tasker/wiki#sample-output>)

Dies ist eine Anwendung, die [Tasker](https://tasker.joaoapps.com/) ergänzt und für die Ausführung in einem Webbrowser gedacht ist (siehe [Hinweis 1](#1)).

Ich stellte fest, dass meine Tasker-Projects/-Profiles/-Tasks/-Scenes immer unübersichtlicher wurden und mein Telefon zu klein war, um bequem durch sie zu navigieren. Deshalb habe ich ein Python-Programm geschrieben, das anhand der Tasker-Backup-XML-Datei, die ich auf meinem Desktop-Laufwerk gespeichert hatte, eine vollständige Karte meiner gesamten Konfiguration in meinem Webbrowser erstellt.

Mit der Zeit habe ich die Karte um viele zusätzliche Optionen erweitert, darunter die Möglichkeit, Tasker-Objekte zu bearbeiten und eine eingehende Analyse der Tasker-Konfiguration zu erhalten.

Das Tasker-Backup oder eine andere von Tasker exportierte XML-Datei kann entweder manuell auf Ihr PC-/Mac-/Linux-/Cloud-Laufwerk hochgeladen werden, oder dieses Programm kann sie direkt von Ihrem Android-Gerät abrufen (siehe [Hinweis 2](#2)).

## Funktionen

- Wählen Sie den Detailgrad der Ausgabe, von einer zusammenfassenden Übersicht bis zu einer sehr detaillierten Ansicht Ihrer Konfiguration.
- Zeigen Sie nur ein einzelnes Project, Profile oder eine Task an.
- Ein- oder Ausschließen von Profile- und Task-Bedingungen: States, Events usw.
- Geben Sie einfach alles als Stream aus, oder machen Sie die Ausgabe durch Ausrichten aller Felder "ordentlich".
- Ändern Sie das Erscheinungsbild: wählen Sie den 'hellen' oder 'dunklen' Modus.
- Geben Sie die Ausgabe in Ihrer bevorzugten Monospace-Schrift aus, und heben Sie die Namen von Projects, Profiles und Tasks durch Kursivschrift, Fettdruck, Hervorhebung und/oder Unterstreichung hervor.
- Ändern Sie die Farben, die mit verschiedenen Aspekten der Ausgabe verbunden sind, je nach Stimmung.
- Fügen Sie TaskerNet-Beschreibungen und/oder Tasker-Einstellungen (Preferences) hinzu.
- Für komplexe Konfigurationen können Sie optional ein Verzeichnis mit Hyperlinks zu Ihren Projects, Profiles, Tasks und Scenes einbinden.
- Zeigen Sie ein Diagramm Ihrer gesamten Tasker-Konfiguration sowie einen Task Flow an.
- Kommandozeilen- oder grafische Benutzeroberfläche.
- Verwenden Sie exportiertes XML, oder rufen Sie das XML direkt von Ihrem Android-Gerät für die Konfigurationskarte ab.
- Senden Sie Projects, Profiles, Tasks und Scenes zurück an Tasker auf Ihrem Android-Gerät.
- Speichern und wiederherstellen Sie Laufzeiteinstellungen.
- Identifizieren Sie Tasks mit zu vielen "Actions", die möglicherweise in mehrere Tasks aufgeteilt werden sollten.
- KI-Analyseoption zur Analyse eines bestimmten Projects, Profiles, Task oder Scene, entweder mit serverbasierten Modellen wie ChatGPT/Claude/Gemini oder lokal unterstützten Modellen wie Llama (über Ollama).
- Zeigen Sie Ergebnisse direkt in der grafischen Oberfläche an: (Konfigurations-)Map-Ansicht, Tree-Ansicht und Diagram-Ansicht.
- Automatische Erkennung von Updates und optionale Installation neuer Versionen.
- Erweiterte Suche und strukturiertes 'Suchen/Ersetzen'.
- Hinzufügen und Bearbeiten von Projects, Profiles, Tasks und Scenes (siehe [Hinweis 6](#6)).
- Zeigen Sie eine Liste der Änderungen seit einem bestimmten Datum an.
- Verknüpfen Sie ein Project, Profile, Task oder Scene mit dem TaskerNet-Share, aus dem es stammt, werden Sie benachrichtigt, wenn der Autor eine neuere Version veröffentlicht, und übernehmen Sie dessen Änderungen einzeln.
- Analysieren Sie den Gesundheitszustand des Tasker-XML sowie der zahlreichen Variablen in der gesamten Konfiguration.
- Vergleichen Sie eine XML-Datei mit dem geladenen XML.

## Programmabhängigkeiten

### - Python Version 3.11 oder höher

### - Vollständige oder teilweise Tasker-XML-Datei: backup.xml oder eine andere von Tasker exportierte XML-Datei

&nbsp;&nbsp;&nbsp;Sie werden aufgefordert, Ihre von Tasker exportierte XML-Datei (z. B. backup.xml) auf Ihrem Desktop zu suchen und auszuwählen, erstellt von Tasker Version 5 oder Version 6. Optional können Sie sie auch direkt von Ihrem Android-Gerät abrufen (siehe [Hinweis 2](#2)).

### - KI-Analyse

&nbsp;&nbsp;&nbsp;Dies erfordert einen gültigen API-Schlüssel bei Verwendung der serverbasierten Analyse und/oder die Installation von Ollama für die lokale Analyse (siehe [Hinweis 3](#3)).


## Installation

Dieses Programm und alle seine Voraussetzungen benötigen etwa 230 MB Speicherplatz. Es wird empfohlen, es in einer virtuellen Umgebung zu installieren (Option 2).

- Installieren Sie MapTasker, indem Sie einen der folgenden Befehle in das Terminal/die Eingabeaufforderung eingeben:

     ```python -m pip install maptasker -U```
                 ...ODER...
     ```uv add maptasker```

- Um es in einer virtuellen Umgebung zu installieren, geben Sie den folgenden Befehl in das Terminal/die Eingabeaufforderung ein:

  über pip...
  - `cd xxx`, wobei 'xxx' das Verzeichnis ist, in dem Sie die virtuelle Umgebung einrichten möchten.
  - `python -m venv venv`
  - Aktivieren Sie die virtuelle Umgebung...
    MAC/Linux: `source {directory path to 'xxx'}/venv/bin/activate`
    Windows: `venv\Scripts\activate`
  - `pip install maptasker`

  ...oder...
  
  über uv...
  - `cd xxx`, wobei 'xxx' das Verzeichnis ist, in dem Sie die virtuelle Umgebung einrichten möchten.
  - `uv venv`
  - Aktivieren Sie die virtuelle Umgebung...
    MAC/Linux: `source {directory path to 'xxx'}/venv/bin/activate`
    Windows: `venv\Scripts\activate`
  - `uv pip install maptasker`

- Die KI-Analysefunktionen benötigen zusätzliche Bibliotheken (OpenAI, Anthropic, Google und Ollama). MapTasker installiert diese nicht automatisch; wenn Sie sie möchten, installieren Sie MapTasker stattdessen mit dem `ai`-Extra:

     ```python -m pip install "maptasker[ai]" -U```
                 ...ODER...
     ```uv add "maptasker[ai]"```
  
## Verwendung

- Geben Sie den Befehl ein:

     ```maptasker```
     ...oder, wenn Sie uv zur Verwaltung der virtuellen Umgebung verwenden...
     ```uv run maptasker```

### Berichte über die Kommandozeile

Health Check, Compare, Changes Since, Export und eine Ordnerüberwachung (watch) laufen ohne Fenster, sodass ein nächtliches Tasker-Backup automatisch überprüft werden kann (über `cron`, die Aufgabenplanung, `launchd` oder einen CI-Job):

```
maptasker -healthcheck -file backup.xml                 # Probleme in einem Backup
maptasker -compare older.xml newer.xml                  # Unterschiede zwischen zwei Backups
maptasker -changes_since week -file backup.xml          # was sich geändert hat: today (heute), week (Woche), month (Monat), all (alles), ein Datum, oder 3d (3 Tage)
maptasker -export map -format md -file backup.xml       # die Map (oder das Diagramm) als md, json oder pdf
maptasker -watch ~/TaskerBackups                        # erfasst jedes neue Backup im Verlauf
```

- **`-file`** akzeptiert ein Backup oder einen Ordner (die neueste `.xml`-Datei darin wird verwendet). `-outdir` legt fest, wohin Dateien geschrieben werden, und `-save` speichert den Bericht ebenfalls als Datei, genau wie das Fenster.
- **Nur der Bericht, und ausschließlich der Bericht, geht an die Standardausgabe**; alles andere geht an die Standardfehlerausgabe, sodass `maptasker -healthcheck -file backup.xml > report.txt` einen sauberen Bericht ergibt.
- **Exit-Codes** ermöglichen es einem Skript, basierend auf dem Ergebnis zu handeln:

  | Code | Bedeutung |
  |---|---|
  | 0 | Fertig, und es gab nichts zu melden |
  | 10 | Der Bericht hat etwas gefunden: Health-Check-Fehler (`-fail_on warning`, um Warnungen einzuschließen, `-fail_on never`, um sie zu ignorieren), oder Unterschiede |
  | 11 | `-changes_since` hatte keine frühere Konfiguration zum Vergleich (der erste Lauf beginnt den Verlauf) |
  | 1 | Programmfehler |
  | 2 | Eine Datei konnte nicht geschrieben werden (einschließlich eines `-outdir`-Ordners, der nicht verwendet werden kann), oder die Ausgabe konnte nicht erstellt werden |
  | 3 | Die Datei ist kein gültiges Tasker-Backup |
  | 5 | Das angeforderte einzelne Project, Profile oder Task (`-project`, `-profile` oder `-task`) wurde nicht gefunden |
  | 6 | Es wurde keine Datei angegeben, oder die Datei bzw. der Ordner existiert nicht |
  | 7 | Ungültige Option, z. B. eine falsche Farbe, ein unbekannter `-fail_on`-Wert, oder der Vergleich einer Datei mit sich selbst |
  | 8 | Die Anfrage an das Android-Gerät, auf dem der Tasker-Server läuft, ist fehlgeschlagen |

- **Der Verlauf (History).** Jedes geladene Backup wird im Konfigurationsverlauf erfasst, den `-changes_since` liest. `-watch FOLDER` erfasst jedes neue, vollständige Backup, das in `FOLDER` erscheint, datiert nach der Datei, sodass der Verlauf auch an Tagen weiter gefüllt wird, an denen Sie MapTasker nie öffnen; `-watch FOLDER -once` prüft nur einmal, für einen geplanten Job. Der Verlauf wird in einem Ordner namens `MapTasker_Timeline` in dem Verzeichnis gespeichert, aus dem MapTasker ausgeführt wird; ein geplanter Job sollte daher `-history_dir` verwenden, um auf denselben Ordner zu verweisen, den das Fenster verwendet.
- **Sonst ändert sich nichts.** Diese Läufe öffnen niemals einen Browser und überschreiben niemals die Einstellungen, die das Fenster speichert.

## Programmausgabe

MapTasker erzeugt mehrere Ausgabedateien, sowohl auf dem Desktop als auch auf dem Android-Gerät.

Eine vollständige Liste der von MapTasker erzeugten Ausgabe finden Sie im [Wiki](https://github.com/mctinker/Map-Tasker/wiki/Generated-Output).


## Mehr: [[Laufzeitoptionen]](https://github.com/mctinker/Map-Tasker/wiki/Runtime-Options)&nbsp;&nbsp;&nbsp;[[Beispiele für Laufzeitoptionen]](https://github.com/mctinker/Map-Tasker/wiki/Sample-Runtime-Options)&nbsp;&nbsp;&nbsp;[[Beispielausgabe]](https://github.com/mctinker/Map-Tasker/wiki#sample-output)

## Projektstruktur

Ein kurzer Überblick über die wichtigsten Dateien und ihren Zweck:

- `maptasker/`: Enthält den Kerncode der Anwendung.
  - `maptasker/src/`: Die wichtigsten Python-Quelldateien für die Logik von MapTasker.
  - `maptasker/assets/`: Statische Ressourcen wie Symbole, Bilder und JSON-Daten, die von der Anwendung verwendet werden.
  - `maptasker/locale`: Sprachdateien für Übersetzungen.
- `documentation_images/`: In dieser README und anderer Dokumentation verwendete Bilder.
- `tools/`: während der Entwicklung verwendete Hilfsprogramme.
- `tests/`: Enthält Testskripte und zugehörige Dateien zur Sicherstellung der Codequalität.
- `maptasker/main.py`: Der Einstiegspunkt hinter dem Befehl `maptasker`. Führen Sie aus einem geklonten Repository `python -m maptasker.main` aus.
- `LICENSE`: Die MIT-Lizenzdatei des Projekts.
- `README.md`: Diese Datei (das englische Original).
- `Changelog.md`: Ein Protokoll der in jeder Version vorgenommenen Änderungen.
- `pyproject.toml`: Projektmetadaten und Build-System-Konfiguration.

## Lizenz

Dieses Projekt ist unter der [MIT-Lizenz](../LICENSE) lizenziert.

Die MIT-Lizenz ist eine freizügige Open-Source-Lizenz, die am Massachusetts Institute of Technology (MIT) entstanden ist. Als freizügige Lizenz schränkt sie die Weiterverwendung nur sehr begrenzt ein und weist daher eine hohe Lizenzkompatibilität auf.

Kurz gesagt bedeutet dies, dass Sie Folgendes frei tun dürfen:

- **Verwenden**: Die Software für jeden Zweck (kommerziell oder privat) verwenden.
- **Ändern**: Die Software modifizieren.
- **Verteilen**: Die Original- oder modifizierte Software verteilen.
- **Unterlizenzieren**: Die Software unterlizenzieren.

Sie müssen:

- **Copyright einbeziehen**: Den ursprünglichen Copyright-Hinweis und die Lizenz selbst in jedem wesentlichen Teil der Software einbeziehen.

Die Software wird "WIE SIE IST" ohne jegliche Garantie bereitgestellt. Den vollständigen Lizenztext finden Sie in der Datei [LICENSE](../LICENSE).

## Fehlerbehebung und FAQ

**F: Das `MapTasker_Map.txt`-Diagramm sieht im Windows-Editor (Notepad) falsch ausgerichtet aus.**

A: Der Editor verarbeitet möglicherweise die Abstände dieser Datei nicht korrekt.

Es wird empfohlen, einen anderen Texteditor wie Notepad++, VS Code oder Typepad zu verwenden (und ihn als Standard für `.txt`-Dateien festzulegen). Stellen Sie sicher, dass der 'Zeilenumbruch' deaktiviert ist und eine Monospace-Schrift verwendet wird.

**F: Wie rufe ich die Tasker-XML-Datei direkt von meinem Android-Gerät ab?**

A: Voraussetzungen:

1- Browser und Android-Gerät müssen sich im gleichen lokalen Netzwerk befinden.

2- Das ['Http Server Example'-Tasker-Project](https://shorturl.at/bwCD4) muss auf dem Android-Gerät installiert und aktiv sein, mit laufendem Server.

Weitere Details finden Sie im Abschnitt "Hinweise" dieser README.

**F: Diagramm-Verbindungen sind bei Namen in Chinesisch, Koreanisch oder Japanisch falsch ausgerichtet.**

A: Dies ist ein bekanntes Problem im Zusammenhang mit den Schrift-Metriken dieser Sprachen in der Diagramm-Bibliothek.

**F: Warum sind manche Task-Actions und Profile-States/Events nicht zum Bearbeiten/Hinzufügen verfügbar?

A: In manchen Fällen erfordern diese Actions, Events oder States Informationen, die nur auf Android und/oder innerhalb von Tasker selbst verfügbar sind. Das Zulassen einer Bearbeitung würde zu einer unvollständigen Task oder einem unvollständigen Profile führen, was einen Tasker-Fehler verursachen würde.

## Hinweise

Details zu einigen der im Abschnitt "Fehlerbehebung und FAQ" erwähnten Punkte sind hier für zusätzlichen Kontext aufgeführt.

### 1
**Besonderheiten unter Windows 11:**

- Nur Windows 11 wird unterstützt. Keine früheren Windows-Versionen werden unterstützt.
- Bei Anzeigeproblemen von `MapTasker_Map.txt` im Editor verwenden Sie einen alternativen Texteditor wie Typepad und legen Sie ihn als Standard für `.txt`-Dateien fest.

### 2
**Direktes Abrufen von XML von Android:**

Um die Tasker-XML-Datei direkt abzurufen:

- Stellen Sie sicher, dass sich Desktop und Android-Gerät im gleichen lokalen Netzwerk befinden und Tasker läuft.
- Das ['Http Server Example'-Tasker-Project](https://shorturl.at/bwCD4) muss auf dem Android-Gerät installiert und aktiv sein, mit laufendem Server. Denken Sie daran, die Task "Update GD HTTP Info" auszuführen und (nur beim ersten Mal) Ihre Google-Drive-ID bei Aufforderung einzugeben.
- Nach dem Abrufen wird das XML auf Ihrem Desktop gespeichert und muss nicht ständig neu abgerufen werden, sofern es sich nicht ändert.

### 3
**KI-Unterstützung**

Die KI-Analyse ist nur über die grafische Oberfläche verfügbar. Sie können eine Analyse nur mit einem einzelnen Project, Profile, Task oder Scene durchführen. Unterstützt werden serverbasiertes OpenAi (ChatGPT), Gemini und Anthropic sowie lokal basierte Llama-Modelle.

Llama-basierte Modelle werden über [Ollama](https://ollama.com/) unterstützt, das Sie manuell herunterladen, installieren und einmal ausführen müssen, um den Server auf Ihrem Desktop einzurichten. MapTasker lädt die Llama-Modelle für Sie dynamisch, falls sie noch nicht geladen sind.

Die unterstützenden KI-Module werden bei der Installation von MapTasker nicht standardmäßig installiert. Stattdessen werden sie dynamisch bei der ersten Verwendung der jeweiligen KI-Anfrage installiert. Auf diese Weise entsteht Ihnen kein zusätzlicher Aufwand, wenn Sie nicht planen, KI zu verwenden.


## Hinweise zur Bearbeitung und Analyse der Anwendung
**MapTasker-Hinweise zur Bearbeitung und Analyse**

Einzelheiten finden Sie im Dokument [Caveats](https://github.com/mctinker/Map-Tasker/blob/Master/caveats.txt).


## To-Do-Liste (in keiner bestimmten Reihenfolge)

- [ ] Readiness Check (Bereitschaftsprüfung)

- [x] Unterstützung zusätzlicher Plugins

- [ ] Verbleibende Tasker-Einstellungen abbilden

- [ ] Task Stepper: eine Task Action für Action als "Trockenlauf" simulieren und zeigen, welche If-, For- und Goto-Zweige ausgeführt werden und was jede Variable enthält

- [ ] Live Run Monitor: live streamen, welche Profiles und Tasks auf dem Telefon ausgelöst werden, und sie in der Diagram-Ansicht hervorheben

- [ ] Drei-Wege-Zusammenführung (Three-way merge) zweier Backups gegenüber einem gemeinsamen Vorfahren, Konflikt für Konflikt gelöst und in einem Schritt rückgängig gemacht

- [x] TaskerNet-Update-Tracker: benachrichtigt Sie, wenn der Autor eines von Ihnen verwendeten Shares eine neuere Version veröffentlicht, mit einem Diff der Änderungen

- [ ] Persönliche Snippet-Bibliothek: wiederverwendbare Action-Sequenzen, Tasks und Profile-Vorlagen speichern und mit Parametern einfügen

- [ ] Erklärungen in einfacher Sprache in der Map: eine von KI geschriebene, zwischengespeicherte und bearbeitbare Ein-Zeilen-Zusammenfassung jedes Profile und jeder Task

- [ ] Fehlende-Ressourcen-Prüfer: überprüfen, ob die Dateien, Ordner, Bilder, Töne, Scenes und Apps, auf die Ihre Actions verweisen, noch existieren

- [ ] Komplexitäts- und Trend-Dashboard: Verfolgen von Task-Länge, Verschachtelung, Aufruf-Kettentiefe und Befunden im Zeitverlauf

- [ ] Export einer Dokumentationswebsite: ein verlinkter Satz von Markdown- oder HTML-Seiten, eine pro Project, Profile, Task und Scene, mit Aufrufdiagrammen

- [ ] Assistent zum Umbenennen und für den Geltungsbereich von Variablen: eine Variable umbenennen oder eine globale in eine lokale umwandeln, überall dort, wo sie verwendet wird, als ein einziges Undo

## Datenschutzerklärung

Es werden keinerlei Informationen über das Netzwerk erfasst und an mich oder Dritte gesendet, außer den unten aufgeführten (Netzwerkverkehr).

Wenn Sie einen Fehler melden, werden Sie höchstwahrscheinlich gebeten, die Ausgabeprotokolldatei des Fehlers und Ihre XML-Datei bereitzustellen, beide werden ausschließlich zur Fehlerbehebung des Programms verwendet und danach sofort gelöscht.

Der Netzwerkverkehr ist wie folgt:

- Lokaler LAN-Verkehr beim direkten Abrufen des XML von Ihrem Android-Gerät.
- Beim Start, einmal täglich, wird bei pypi.com geprüft, ob eine neue Version verfügbar ist.
- Aktualisierung des Programms von pypi.com (über 'pip'), wenn 'Upgrade' in der grafischen Oberfläche ausgewählt wird.
- Lesen der Datei 'Changelog.md' von '<https://github.com/mctinker/Map-Tasker>', wenn "What's New" in der grafischen Oberfläche ausgewählt wird.
- Verwendung von chatgpt.com bei der Verwendung der KI-Analyse mit einem der OpenAi-Modelle. Die Ausgabe von MapTasker wird über den Standard-API-Aufruf zur Analyse an den Server gesendet. Dasselbe gilt für Claude (Anthropic) und Gemini (Google).
- Neue und aktualisierte lokale KI-Modelle werden von '<https://ollama.com/library>' geladen, wenn die KI-Analysefunktion ausgeführt wird.
- Bild- und Video-Quell-Hyperlinks, die über das HTML-Tag '<img src=https://...>' in Task-Action-Labels und TaskerNet-Beschreibungen definiert sind, werden beim Anklicken aufgerufen. Beispiele: imggur.com, Youtube, Dropbox, Google Drive usw.

## Mitwirken

Beiträge sind willkommen! Hier sind einige Möglichkeiten, wie Sie zu MapTasker beitragen können:

**Fehler melden:**

- Wenn Sie einen Fehler finden, öffnen Sie bitte ein Issue auf der [GitHub-Issues-Seite](https://github.com/mctinker/Map-Tasker/issues).
- Fügen Sie so viele Details wie möglich hinzu:
  - Schritte zur Reproduktion des Fehlers.
  - Erwartetes und tatsächliches Verhalten.
  - Ihr Betriebssystem und Ihre Python-Version.
  - MapTasker-Version.
  - Relevante Teile Ihrer Tasker-XML-Datei (falls zutreffend, und stellen Sie sicher, dass keine sensiblen Informationen enthalten sind).
  - Die Datei `maptasker.log`, falls sie mit der Option `-debug` erstellt wurde.

**Verbesserungen vorschlagen:**

- Öffnen Sie ein Issue auf GitHub und beschreiben Sie Ihren Vorschlag.
- Erklären Sie den Anwendungsfall und warum diese Verbesserung von Vorteil wäre.

**Pull Requests:**

- Wenn Sie Code beitragen möchten:
    1. Forken Sie das Repository.
    2. Erstellen Sie einen neuen Branch für Ihr Feature oder Ihre Fehlerkorrektur (z. B. `feature/new-output-format` oder `fix/xml-parsing-error`).
    3. Nehmen Sie Ihre Änderungen vor.
    4. Stellen Sie sicher, dass Ihr Code dem Black-Code-Stil entspricht (wie im Badge angezeigt).
    5. Fügen Sie Tests für Ihre Änderungen im Verzeichnis `tests/` hinzu, falls zutreffend.
    6. Stellen Sie sicher, dass alle Tests bestehen.
    7. Reichen Sie einen Pull Request für den `Master`-Branch ein.

**Code-Stil:**

- Dieses Projekt verwendet [Ruff](https://docs.astral.sh/ruff/formatter/) zur Code-Formatierung. Bitte stellen Sie sicher, dass Ihre Beiträge mit Ruff formatiert sind.

Wir danken Ihnen für Ihre Hilfe bei der Verbesserung von MapTasker!

## Bekannte Probleme

- Diagramm-Verbindungen sind falsch ausgerichtet, wenn Namen in Chinesisch, Koreanisch oder Japanisch vorliegen.
- Nicht alle Task-Actions und Profile-State/Event-Bearbeitungen werden unterstützt, da einige Informationen erfordern, die nur auf einem Android-Gerät verfügbar sind.

## Mitwirkende

[Taskometer](https://github.com/Taskomater/Tasker-XML-Info)

[©Connor Talbot 2021 für Clippy](https://github.com/con-dog/clippy)

[Ollama](https://ollama.com/), [OpenAi](https://openai.com/), [Claude AI](https://claude.ai), [Gemini AI](https://gemini.google.com/)

[NiceGui](https://nicegui.io/)

[!["Buy Me A Coffee"](../documentation_images/coffee.png)](https://www.buymeacoffee.com/mctinker)
