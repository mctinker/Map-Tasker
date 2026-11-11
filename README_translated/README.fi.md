<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../documentation_images/maptasker_logo_dark.png">
    <img src="../documentation_images/maptasker_logo_light.png" alt="MapTasker">
  </picture>
</p>

<div align="center">

![PyPI](https://img.shields.io/pypi/v/maptasker)
![PyPI - Lataukset](https://img.shields.io/pypi/dm/maptasker?color=green&label=downloads)
![Lataukset](https://static.pepy.tech/personalized-badge/maptasker?period=total&units=international_system&left_color=grey&right_color=green&left_text=downloads)
![Python](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Fmctinker%2FMap-Tasker%2Frefs%2Fheads%2FMaster%2Fpyproject.toml)
![PyPI - Lisenssi](https://img.shields.io/pypi/l/maptasker)
![](https://tokei.rs/b1/github/mctinker/Map-Tasker)
[![Sourcery](https://img.shields.io/badge/Sourcery-enabled-brightgreen)](https://sourcery.ai)
[![Koodityyli: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![pytest](https://img.shields.io/badge/tested%20with-pytest-blue?logo=pytest)](https://docs.pytest.org/)
[!["Osta minulle kahvia"](../documentation_images/coffee.png)](https://www.buymeacoffee.com/mctinker)

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

> Tämä käännös on luotu automaattisesti. Mahdollisten ristiriitojen tapauksessa alkuperäinen [englanninkielinen README](../README.md) on määräävä.

## Näytä, muokkaa ja analysoi Tasker-sovelluksen Project-, Profile-, Task- ja Scene-kohteita työpöytäselaimessasi (Mac/Windows 11/Linux) Taskerin varmuuskopio- tai viedyn XML-tiedoston pohjalta

Konfiguraatiokartta (Configuration Map)...
![MapTaskerin konfiguraatiokartta: project, sen profiles ja tasks värikoodattuna sisennettynä kaaviona, jossa jokaisen taskin numeroidut actions ja niiden asetukset on lueteltu alla](../documentation_images/intro.png)

Kaaviokartta (Diagram Map)...
![MapTaskerin kaaviokartta: project ja sen profiles piirretty laatikoina, niiden tasks alapuolella, ja viivat osoittavat, mikä task kutsuu mitä, yksi kutsupolku korostettuna](../documentation_images/Introd.png)

[[Lisää esimerkkejä]](<https://github.com/mctinker/Map-Tasker/wiki#sample-output>)

Tämä on [Tasker](https://tasker.joaoapps.com/)-sovellusta täydentävä ohjelma, joka on tarkoitettu käytettäväksi verkkoselaimessa (katso [huomautus 1](#1)).

Huomasin, että Tasker-projectini/-profileni/-taskini/-scenet olivat muuttuneet hallitsemattomiksi, ja puhelimeni näyttö oli liian pieni niiden selaamiseen. Niin kirjoitin Python-ohjelman, joka luo verkkoselaimeeni täydellisen kartan koko konfiguraatiostani sen Tasker-varmuuskopio-XML-tiedoston pohjalta, jonka olin tallentanut paikalliselle työpöytäasemalleni.

Ajan myötä olen kehittänyt karttaa lisäämällä monia ominaisuuksia, mukaan lukien mahdollisuuden muokata Tasker-objekteja ja saada syvällinen analyysi Tasker-konfiguraatiosta.

Taskerin varmuuskopio tai muu Taskerin viety XML voidaan joko latata manuaalisesti PC-/Mac-/Linux-/pilvilevylle, tai tämä ohjelma voi hakea sen suoraan Android-laitteestasi (katso [huomautus 2](#2)).

## Ominaisuudet

- Valitsemasi tulostuksen yksityiskohtien taso, alkaen yleisestä yleiskatsauksesta erittäin yksityiskohtaiseen asetusten tasoon.
- Näytä vain yksi projekti, profiili tai tehtävä.
- Sisällytä/poista profiilin ja tehtävän ehdot: Tilat, tapahtumat jne.
- Toista kaikki tai muokkaa tulosta niin, että kaikki kentät ovat linjassa.
- Muuta ulkonäköä: valitse 'valo' tai 'tumma' -tila.
- Tulosta käyttämällä suosikkikirjainta, ja korosta "Project", "Profile" ja "Task" -nimien avulla, esimerkiksi lihapainamalla, kursivoimalla, alleviivottamalla tai muulla tavalla.
- Muokkaa eri tulosteen osa-alueisiin liittyviä värejä, jotta ne vastaavat mielentilaasi.
- Sisällytä TaskerNet-kuvaukset ja/tai Taskerin asetukset.
- Monimutkaisille asetuksille voidaan lisätä valinnaisesti sanasto, jossa on lyhenteitä (hotlinks) projekteihisi, profiileihisi, tehtäviisi ja kohtauksiisi.
- Esitä kaavion, joka näyttää koko Tasker-asetuksesi sekä tehtävien kulun.
- Komentoriväline tai graafinen käyttöliittymä.
- Käytä tuotettua XML-tiedostoa tai hanki XML-tiedosto suoraan Android-laitteiltasi konfiguraation kartoittamiseen.
- Lähetä projekteja, profiileja, tehtäviä ja kohtauksia takaisin Tasker-sovellukseen Android-laitteellasi.
- Tallenna ja palauta suoritustilanteen asetukset.
- Tunnista tehtävät, joissa on liian monta "toimintoa", ja jotka voisivat mahdollisesti jaettuna useiksi eri tehtäviksi.
- "Ai-analyysi -ominaisuus mahdollistaa tietyn projektin, profiilin, tehtävän tai kohtauksen analysoinnin käyttämällä joko palvelimella toimivia ChatGPT/Claude/Gemini- tai paikallisesti toimivia Llama-malleja (Ollaman kautta).
- Näytä tulokset suoraan käyttöliittymässä: (Konfiguraatio) Kartanäkymä, puunäkymä ja kaavionäkymä.
- Automaattinen päivitysten havaitseminen ja valinnaisen uusien versioiden asennus.
- Parannettu hakutoiminto ja rakenteellinen "Etsi/Korvaa" -toiminto.
- Lisää ja muokkaa projekteja, profiileja, tehtäviä ja kohtauksia (katso [Huom. 6](#6))
- Luettelon muutokset tietty päivämäärään mennessä.
- Analysoi Tasker-XML:n terveyttä sekä useita muuttujia asetuksissa.
- Vertaa XML-tiedostoa latautuneeseen XML-tiedostoon.
- Tarkista TaskerNet-sivustolta päivitykset projekteille, profiileille ja tehtäville, ja ota ne käyttöön, jos mahdollista.
- Tuo Tasker-objekti toisesta XML-tiedostosta, sekä kaikki sen riippuvuudet.
- Suorita trendianalyysi nähdäksesi, onko koodisi kehittymässä (tai ei).
- Tee inventaario kaikista asioista, joita tehtävä käyttää Android-laitteen ulkopuolella.
- Määritä, mikä "laukeaa" tietyn ehdon (tilanteen tai tapahtuman) perusteella.
- Tutki tehtävän logiikkaa ja vertaile yhtä suoritusta toiseen.
- Käytä Android-laitteessa reaaliaikaista valvontaa nähdäksesi, mitkä profiilit ja tehtävät aktivoituvat.
- Tunnista, mitkä asiat kuluttavat akkusi nopeasti.
- Vie kaikki tekstit, joita henkilö lukee (Flash, Notify, Say, dialogit, kohtausnimet), taulukoiksi, jotka voidaan kääntää tai muokata, ja palauta muokatut tekstit.
- Hallitse globaaleja muuttujia: tarkista, missä ne on määritetty ja luettu, nimeä yksi muuttuja uudelleen kaikissa paikoissa, muuta sen arvoa ja lähetä se puhelimelle.

## Ohjelman riippuvuudet

### - Python-versio 3.11 tai uudempi

### - Täydellinen tai osittainen Tasker-XML-tiedosto: backup.xml tai muu Taskerin viety XML-tiedosto

&nbsp;&nbsp;&nbsp;Sinua pyydetään paikantamaan ja valitsemaan Taskerin viemä XML-tiedosto (esim. backup.xml) työpöydältäsi, Taskerin version 5 tai version 6 luomana. Voit myös valinnaisesti hakea sen suoraan Android-laitteestasi (katso [huomautus 2](#2)).

### - AI-analyysi

&nbsp;&nbsp;&nbsp;Tämä vaatii voimassa olevan API-avaimen, jos käytät palvelinpohjaista analyysiä, ja/tai Ollaman asentamisen paikallista analyysiä varten (katso [huomautus 3](#3)).

## Asennus

Tämä ohjelma ja kaikki sen esivaatimukset vievät noin 230 Mt tilaa. Suositellaan asentamista virtuaaliympäristöön (vaihtoehto 2).

1- Asenna MapTasker syöttämällä jokin seuraavista komennoista terminaaliin/komentoriville:

     ```python -m pip install maptasker -U```
                 ...TAI...
     ```uv add maptasker```

2- Asentaaksesi sen virtuaaliseen ympäristöön, kirjoita seuraava komento terminaaliin/komentoriville:

  pip:n kautta...
  - `cd xxx`, missä 'xxx' on hakemisto, johon haluat asettaa virtuaaliympäristön.
  - `python -m venv venv`
  - Aktivoi virtuaaliympäristö...
    MAC/Linux: `source {directory path to 'xxx'}/venv/bin/activate`
    Windows: `venv\Scripts\activate`
  - `pip install maptasker`

  ...tai...

  uv:n kautta...
  - `cd xxx`, missä 'xxx' on hakemisto, johon haluat asettaa virtuaaliympäristön.
  - `uv venv`
  - Aktivoi virtuaaliympäristö...
    MAC/Linux: `source {directory path to 'xxx'}/venv/bin/activate`
    Windows: `venv\Scripts\activate`
  - `uv pip install maptasker`

- AI-analyysiominaisuudet tarvitsevat ylimääräisiä kirjastoja (OpenAI, Anthropic, Google ja Ollama). MapTasker ei asenna niitä puolestasi; jos haluat ne, asenna MapTasker sen sijaan `ai`-lisäosan kanssa:

     ```python -m pip install "maptasker[ai]" -U```
                 ...TAI...
     ```uv add "maptasker[ai]"```

## Käyttö

- Syötä komento:

     ```maptasker```
     ...tai, jos käytät uv:tä virtuaaliympäristön hallintaan...
     ```uv run maptasker```

### Raportit komentorivilta

Health Check, Compare, Changes Since, Export ja kansion tarkkailu (watch) toimivat ilman ikkunaa, jolloin yöllinen Tasker-varmuuskopio voidaan tarkistaa automaattisesti (`cron`:sta, Tehtävien ajoittajasta, `launchd`:sta tai CI-työstä):

```
maptasker -healthcheck -file backup.xml                 # problems in a backup
maptasker -compare older.xml newer.xml                  # what differs between two backups
maptasker -changes_since week -file backup.xml          # what changed: today, week, month, all, a date, or 3d
maptasker -trend -file backup.xml                       # is the configuration getting healthier or messier
maptasker -export map -format md -file backup.xml       # the Map (or diagram) as md, json or pdf
maptasker -text export -file backup.xml                 # every piece of text a person reads, as a table to translate or edit
maptasker -text apply -table edited.csv -file backup.xml  # put the edited table back
maptasker -watch ~/TaskerBackups                        # record each new backup in the history
```

- **`-file`** hyväksyy varmuuskopion tai kansion (uusinta `.xml`-tiedostoa käytetään). `-outdir` valitsee, minne tiedostot kirjoitetaan, ja `-save` tallentaa raportin myös tiedostona, kuten ikkuna tekee.
- **Vain raportti, ja ainoastaan raportti, menee vakiotulosteeseen (standard output)**; kaikki muu menee vakiovirhetulosteeseen, jolloin `maptasker -healthcheck -file backup.xml > report.txt` tuottaa siistin raportin.
- **Poistumiskoodit (Exit codes)** antavat skriptille mahdollisuuden toimia tuloksen perusteella:

  | Koodi | Merkitys |
  |---|---|
  | 0 | Valmis, ja raportoitavaa ei ollut |
  | 10 | Raportti löysi jotain: Health Check -virheitä (`-fail_on warning` sisällyttääksesi varoitukset, `-fail_on never` jättääksesi ne huomiotta), tai eroja |
  | 11 | `-changes_since`-komennolla ei ollut aiempaa konfiguraatiota vertailtavaksi (ensimmäinen ajo käynnistää historian) |
  | 1 | Ohjelmavirhe |
  | 2 | Tiedostoa ei voitu kirjoittaa (mukaan lukien `-outdir`-kansio, jota ei voida käyttää), tai tulostetta ei voitu luoda |
  | 3 | Tiedosto ei ole kelvollinen Tasker-varmuuskopio |
  | 5 | Pyydettyä yksittäistä Projectia, Profilea tai Taskia (`-project`, `-profile` tai `-task`) ei löytynyt |
  | 6 | Tiedostoa ei annettu, tai tiedostoa/kansiota ei ole olemassa |
  | 7 | Virheellinen valinta, kuten väärä väri, tuntematon `-fail_on`-arvo, tai tiedoston vertaaminen itseensä |
  | 8 | Pyyntö Tasker-palvelinta ajavalle Android-laitteelle epäonnistui |

- **Historia.** Jokainen ladattu varmuuskopio tallennetaan konfiguraatiohistoriaan, jota `-changes_since` lukee. `-watch FOLDER` tallentaa jokaisen uuden, täydellisen varmuuskopion, joka ilmestyy `FOLDER`-kansioon, tiedoston päivämäärän mukaan, jolloin historia täyttyy myös niinä päivinä, kun et koskaan avaa MapTaskeria; `-watch FOLDER -once` tarkistaa vain yhden kerran, ajoitettua työtä varten. Historia säilytetään `MapTasker_Timeline`-kansiossa siinä hakemistossa, josta MapTasker käynnistetään, niin ajoitetun työn tulisi käyttää `-history_dir`-valintaa osoittamaan samaan kansioon, jota ikkuna käyttää.
- **Mikään muu ei muutu.** Nämä ajot eivät koskaan avaa selainta, eivätkä koskaan kirjoita uudelleen asetuksia, joita ikkuna säilyttää.

## Ohjelman tulosteet

MapTasker tuottaa useita tulostetiedostoja, sekä työpöydälle että Android-laitteelle.

Katso [wiki](https://github.com/mctinker/Map-Tasker/wiki/Generated-Output) saadaksesi täydellisen luettelon MapTaskerin tuottamista tulosteista.

## Lisää: [[Ajonaikaiset asetukset]](https://github.com/mctinker/Map-Tasker/wiki/Runtime-Options)&nbsp;&nbsp;&nbsp;[[Esimerkkejä ajonaikaisista asetuksista]](https://github.com/mctinker/Map-Tasker/wiki/Sample-Runtime-Options)&nbsp;&nbsp;&nbsp;[[Esimerkkituloste]](https://github.com/mctinker/Map-Tasker/wiki#sample-output)

## Projektin rakenne

Lyhyt yleiskatsaus päätiedostoista ja niiden tarkoituksesta:

- `maptasker/`: Sisältää sovelluksen perusohjelmakoodin.
  - `maptasker/src/`: Pääasialliset Python-lähtekooditiedostot MapTaskerin logiikalle, jaettuna alipaketteihin kerroksittain.
    (yksi kerros voi tuoda vain alempana olevat; `lint-imports` varmistaa tämän):
    - `gui/`: NiceGUI:n ikkunat, dialogit ja niiden tapahtumankäsittelijät.
    - `device/`: Mitä MapTasker tekee Android-laitteella, käyttäen Taskerin HTTP-palvelua.
    - `mapops/`: massinen korvaaminen, uudelleenjärjestely, korjaaminen, palauttaminen ja suunnittelu; sekä TaskerNet- ja valmiusvälineet.
    - `analysis/`: kysymyksiä, jotka on asetuksen yhteydessä ja joihin vastauksia ei voida muuttaa.
    - `mapgen/` ja `edit/`: varmuuskopion lataaminen ja kartan rakentaminen sen pohjalta, sekä tehtävän, profiilin, projektin ja kohtauksen editointityökalut.
    - `core/`: tilanne, Tasker-toimintojen taulukot ja jaetut työkalut.
    - `mapit.py`, `progargs.py`, `runcli.py`, `rungui.py`, `clireports.py`: pääsykohteet.
  - `maptasker/assets/`: Staattiset resurssit, kuten ikoon, kuvat ja JSON-tiedot, joita sovellus käyttää.
  - `maptasker/locale`: kielilähteet käännösten tekemiseen.
- `documentation_images/`: Kuvia, jo käytetään tässä README-tiedostossa ja muussa dokumentaatiossa.
- `tools/`: kehityksen aikana käytetyt työkalut.
- `tests/`: Sisältää testausohjelmia ja niihin liittyviä tiedostoja, joilla varmistetaan koodin laatu.
- `maptasker/main.py`: Komennon `maptasker` taustalla oleva lähtökohta. Kloonatusta arkistosta käynnistä `python -m maptasker.main`.
- `LICENSE`: Projektille tarkoitettu MIT-lisenssitiedosto.
- `README.md`: Tämä tiedosto.
- `Changelog.md`: Muutosten kirjaus jokaisessa versiossa.
- `pyproject.toml`: Projektin metadatan ja rakennusjärjestelmän asetukset.

## Lisenssi

Tämä projekti on lisensoitu [MIT-lisenssin](../LICENSE) alaisena.

MIT-lisenssi on sallittu vapaan ohjelmiston lisenssi, joka on peräisin Massachusetts Institute of Technologysta (MIT). Sallittuna lisenssinä se asettaa vain hyvin rajoitetut rajoitukset uudelleenkäytölle, ja sillä on siksi korkea lisenssiyhteensopivuus.

Lyhyesti sanottuna tämä tarkoittaa, että saat vapaasti:

- **Käyttää**: Käyttää ohjelmistoa mihin tahansa tarkoitukseen (kommerciaaliseen tai yksityiseen).
- **Muokata**: Muokata ohjelmistoa.
- **Jakaa**: Jakaa alkuperäistä tai muokattua ohjelmistoa.
- **Alilisensoida**: Alilisensoida ohjelmiston.

Sinun täytyy:

- **Sisällyttää tekijänoikeus**: Sisällyttää alkuperäinen tekijänoikeusilmoitus ja itse lisenssi mihin tahansa olennaiseen osaan ohjelmistosta.

Ohjelmisto toimitetaan "SELLAISENAAN", ilman minkäänlaista takuuta. Täyden lisenssitekstin löydät tiedostosta [LICENSE](../LICENSE).

## Vianmääritys ja usein kysytyt kysymykset

**K: `MapTasker_Map.txt`-kaavio näyttää väärin kohdistetulta Windowsin Muistiossa (Notepad).**

V: Muistio ei välttämättä käsittele tämän tiedoston välejä oikein.

Suositellaan käyttämään toista tekstieditoria, kuten Notepad++:aa, VS Codea tai Typepadia (ja asettamaan se oletukseksi `.txt`-tiedostoille). Varmista, että 'tekstin rivitys' on pois päältä ja että käytössä on tasalevyinen fontti.

**K: Miten hankin Tasker-XML-tiedoston suoraan Android-laitteestani?**

V: Edellytykset:

1- Selaimen ja Android-laitteen on oltava samassa paikallisverkossa.

2- Seuraavat kaksi esimerkkiprojektia Tasker-ohjelmalle, jotka on suunniteltu Android-laitteellesi, ja jotka on asennettava sekä kaikki profiilit käytössä:
  ['Http Server Example' Tasker-projekti](https://shorturl.at/bwCD4)
  ['Tasker HTTP API' Tasker-projekti](https://shorturl.at/hlTj0)

Lisätietoja on saatavilla tämän ohjeen [kohdassa 2](#2).

**K: Kaavion yhdysviivat ovat väärin kohdistettuja kiinan-, korean- tai japaninkielisten nimien kohdalla.**

V: Tämä on tunnettu ongelma, joka liittyy näiden kielten fonttimittoihin kaaviokirjastossa.

**K: Miksi joitakin Task-toimintoja (actions) ja Profile-tiloja/tapahtumia (states/events) ei voi muokata/lisätä?

V: Joissain tapauksissa näiden actions-, events- tai states-toimintojen vaatimat tiedot ovat saatavilla vain Androidilla ja/tai Taskerin sisällä. Näiden muokkaamisen sallimisesta seuraisi puutteellinen Task tai Profile, mikä aiheuttaisi Taskerin virhetoiminnan.

## Huomautukset

Yksityiskohdat joistakin kohdista, jotka mainittiin "Vianmääritys ja usein kysytyt kysymykset" -osiossa, on säilytetty tässä lisäkontekstia varten.

### 1
**Windows 11 -erityispiirteet:**

- Ainoastaan Windows 11 on tuettu. Mitkään aiemmat Windows-versiot eivät ole tuettuja.
- `MapTasker_Map.txt`:n näyttöongelmissa Muistiossa käytä vaihtoehtoista tekstieditoria, kuten Typepadia, ja aseta se oletukseksi `.txt`-tiedostoille.

### 2
**XML:n suora hakeminen Androidista:**

Hakeaksesi Tasker-XML-tiedoston suoraan:

- Varmista, että sekä tietokone- että Android-laitteet ovat samassa paikallisessa verkossa ja että Tasker-sovellus on käynnissä.
- ['Http Server Example' - Tasker-projekti](https://shorturl.at/bwCD4) ja ['Tasker HTTP API' - Tasker-projekti](https://shorturl.at/hlTj0) on asuttava ja aktiivisia Android-laitteella, kun palvelin on käynnissä. Muista suorittaa "Update GD HTTP Info" -tehtävä ja (vain ensimmäisellä kerralla) syöttää Google Drive -tunnuksesi, kun sitä pyydetään.
  - HUOMIO: MapTaskerissä on mahdollisuus asentaa "Http Server Example" -ohjelma automaattisesti. Löydät tämän vaihtoehdon "Hanki XML ANDROID-LAITTEESTA" -kohdasta. Mutta jotta tämä toimii, sinun on *tietty* että "Tasker HTTP API" on jo asennettu.
- Kun tiedosto on ladattu, se tallennetaan työpöydälle, ja sitä ei tarvitse ladata uudelleen, ellei sitä ole muutettu.
- Muut MapTaskerin ominaisuudet pyytävät ensin sinulta Android-laitteellasi käyttöoikeuden kyseiselle ominaisuudelle.

### 3
**AI-tuki**

AI-analyysi on käytettävissä vain graafisen käyttöliittymän kautta. Voit suorittaa analyysin käyttäen vain yhtä Projectia, Profilea, Taskia tai Scenea. Tuki on saatavilla palvelinpohjaisille OpenAi (ChatGPT)-, Gemini- ja Anthropic-malleille, sekä paikallisesti ajettaville Llama-malleille.

Llama-pohjaiset mallit on tuettuja [Ollaman](https://ollama.com/) kautta, joka sinun täytyy manuaalisesti ladata, asentaa ja ajaa kerran palvelimen asettamiseksi työpöydällesi. MapTasker lataa Llama-mallit puolestasi dynaamisesti, jos niitä ei ole vielä ladattu.

AI-tukimoduuleja ei asenneta oletuksena, kun MapTasker asennetaan. Sen sijaan ne asennetaan dynaamisesti, kun tiettyä AI-pyyntöä käytetään ensimmäistä kertaa. Tällä tavalla, jos et aio käyttää AI:ta, sinulle ei koidu tätä ylimääräistä kuormaa.

## Sovelluksen muokkaukseen ja analyysiin liittyvät varoitukset
**MapTaskerin muokkaukseen ja analyysiin liittyvät varoitukset**

Katso [Caveats](https://github.com/mctinker/Map-Tasker/blob/Master/caveats.txt)-dokumentti saadaksesi lisätietoja.

## Tehtävälista (ei erityisessä järjestyksessä)

- [x] Tehtävätestit – Tallenna ja vertaile tehtävien vaiheiden sessioita ennen ja jälkeen muutosten tekemisen

- [x] TaskerNet-kuvaukset: lisää/muokkaa.

- [x] Lisää vaatimukset TaskerNet-kuvaan

- [x] Muuttujien hallinta

- [x] Lisäosien poistoneuvoja

- [x] Muistiinpanot ja tunnisteiden tuki

- [ ] Omat mallikirjastot: Tallenna uudelleenkäytettäviä toimintojaksoja, tehtäviä ja profiilimalleja ja lisää ne parametrien avulla.

- [ ] Selkeät, helpottavat selitykset kartalla: tekoälyn luoma, välimuistiin tallennettu ja muokattava lyhyt yhteenveto jokaisesta profiilista ja tehtävästä

- [ ] Dokumentaation sivuston vienti: linkitetty koko, joka koostuu Markdown- tai HTML-sivuista, yksi jokaiselle Projektille, Profilille, Tehtävälle ja Kohtaukselle, sekä kuvioista

- [ ] Kolmen tietojen yhdistäminen, jotta kaksi erillistä varmuuskopioa voidaan yhdistää

- [ ] Projektin riippuvuussuunnitelma

## Tietosuojaseloste

Mitään tietoja ei kerätä ja lähetetä verkon yli minulle tai millekään kolmannelle osapuolelle, lukuun ottamatta alla lueteltuja (verkkoliikenne).

Kun ilmoitat virheestä, sinua pyydetään todennäköisesti toimittamaan virheen tulosteloki ja XML-tiedostosi, joita molempia käytetään vain ohjelman virheenkorjaukseen ja jotka poistetaan sen jälkeen välittömästi.

Verkkoliikenne on seuraavaa:

- Paikallinen LAN-liikenne, kun XML haetaan suoraan Android-laitteestasi.
- Käynnistyksen yhteydessä kerran päivässä tarkistetaan pypi.com:sta, on uusi versio saatavilla.
- Ohjelma päivitetään pypi.com:sta (via 'pip'), jos "Upgrade" valitaan graafisessa käyttöliittymässä.
- Tiedosto 'Changelog.md' luetaan osoitteesta '<https://github.com/mctinker/Map-Tasker>', jos "What's New" valitaan graafisessa käyttöliittymässä.
- chatgpt.com-palvelua käytetään, kun AI-analyysiä käytetään jonkin OpenAi-mallin kanssa. MapTaskerin tuloste lähetetään palvelimelle vakiomuotoisen API-kutsun kautta analysoitavaksi. Sama pätee Claudeen (Anthropic) ja Geminiin (Google).
- Uusia ja päivitettyjä paikallisia AI-malleja ladataan osoitteesta '<https://ollama.com/library>', kun AI-analyysiominaisuutta käytetään.
- Task-action-tunnisteissa ja TaskerNet-kuvauksissa '<img src=https://...>' HTML-tagilla määritellyt kuva- ja videolähteiden hyperlinkit avataan, kun niitä klikataan. Esimerkkejä: imggur.com, Youtube, Dropbox, Google Drive jne.

## Osallistuminen

Osallistumiset ovat tervetulleita! Tässä muutamia tapoja osallistua MapTaskerin kehitykseen:

**Virheiden ilmoittaminen:**

- Jos löydät virheen, avaa issue [GitHubin Issues-sivulla](https://github.com/mctinker/Map-Tasker/issues).
- Sisällytä mahdollisimman paljon yksityiskohtia:
  - Vaiheet virheen toistamiseksi.
  - Odotettu käytös ja todellinen käytös.
  - Käyttöjärjestelmäsi ja Python-versiosi.
  - MapTasker-versio.
  - Tasker-XML-tiedostosi olennaiset osat (jos sovellettavissa, ja varmista, että mukana ei ole arkaluonteisia tietoja).
  - `maptasker.log`-tiedosto, jos se on luotu `-debug`-valinnalla.

**Parannusehdotukset:**

- Avaa issue GitHubissa ja kuvaile ehdotuksesi.
- Selitä käyttötapaus ja miksi tämä parannus olisi hyödyllinen.

**Pull Requestit:**

- Jos haluat osallistua koodilla:
    1. Forkkaa repositorio.
    2. Luo uusi branch ominaisuudellesi tai virheenkorjaukselle (esim. `feature/new-output-format` tai `fix/xml-parsing-error`).
    3. Tee muutoksesi.
    4. Varmista, että koodisi noudattaa Black-koodityyliä (kuten badge osoittaa).
    5. Lisää testejä muutoksillesi `tests/`-hakemistoon, jos sovellettavissa.
    6. Varmista, että kaikki testit menevät läpi.
    7. Lähetä pull request `Master`-branchiin.

**Koodityyli:**

- Tämä projekti käyttää [Ruffia](https://docs.astral.sh/ruff/formatter/) koodin muotoiluun. Varmista, että osallistumisesi on muotoiltu Ruffilla.

Arvostamme apuasi MapTaskerin kehittämisessä!

## Tunnetut ongelmat

- Kaavion yhdysviivat ovat väärin kohdistettuja, jos nimet ovat kiinaksi, koreaksi tai japaniksi.
- Kaikkia Task-toimintoja ja Profile-tilojen/tapahtumien muokkauksia ei tueta, koska jotkin vaativat tietoja, jotka ovat saatavilla vain Android-laitteella.

## Osallistujat

[Taskometer](https://github.com/Taskomater/Tasker-XML-Info)

[©Connor Talbot 2021, Clippy](https://github.com/con-dog/clippy)

[Ollama](https://ollama.com/), [OpenAi](https://openai.com/), [Claude AI](https://claude.ai), [Gemini AI](https://gemini.google.com/)

[NiceGui](https://nicegui.io/)

[!["Buy Me A Coffee"](../documentation_images/coffee.png)](https://www.buymeacoffee.com/mctinker)
