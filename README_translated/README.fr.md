<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../documentation_images/maptasker_logo_dark.png">
    <img src="../documentation_images/maptasker_logo_light.png" alt="MapTasker">
  </picture>
</p>

<div align="center">

![PyPI](https://img.shields.io/pypi/v/maptasker)
![PyPI - Téléchargements](https://img.shields.io/pypi/dm/maptasker?color=green&label=downloads)
![Téléchargements](https://static.pepy.tech/personalized-badge/maptasker?period=total&units=international_system&left_color=grey&right_color=green&left_text=downloads)
![Python](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Fmctinker%2FMap-Tasker%2Frefs%2Fheads%2FMaster%2Fpyproject.toml)
![PyPI - Licence](https://img.shields.io/pypi/l/maptasker)
![](https://tokei.rs/b1/github/mctinker/Map-Tasker)
[![Sourcery](https://img.shields.io/badge/Sourcery-enabled-brightgreen)](https://sourcery.ai)
[![Style de code : ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![pytest](https://img.shields.io/badge/tested%20with-pytest-blue?logo=pytest)](https://docs.pytest.org/)
[!["Achetez-moi une tasse de café"](../documentation_images/coffee.png)](https://www.buymeacoffee.com/mctinker)

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

> Cette traduction a été générée automatiquement. En cas de divergence, le [README original en anglais](../README.md) prévaut.

## Affichez, modifiez et analysez les Projects, Profiles, Tasks et Scenes de Tasker dans le navigateur de votre ordinateur (Mac/Windows 11/Linux), à partir du fichier de sauvegarde ou du XML exporté par Tasker

Carte de configuration (Configuration Map)...
![Carte de configuration MapTasker : un projet, ses profils et ses tâches sous la forme d'un plan indenté codé par couleur, avec les actions numérotées de chaque tâche et leurs paramètres listés en dessous](../documentation_images/intro.png)

Carte en diagramme (Diagram Map)...
![Carte en diagramme MapTasker : un projet et ses profils représentés par des boîtes avec leurs tâches en dessous, et des lignes traçant quelle tâche appelle quelle autre, avec un chemin d'appel mis en évidence](../documentation_images/Introd.png)

[[Plus d'exemples]](<https://github.com/mctinker/Map-Tasker/wiki#sample-output>)

Il s'agit d'une application développée en complément de [Tasker](https://tasker.joaoapps.com/), conçue pour fonctionner dans un navigateur web (voir la [Note 1](#1)).

J'ai constaté que mes Projects/Profiles/Tasks/Scenes Tasker devenaient ingérables, et que l'écran de mon téléphone était trop petit pour naviguer dans mes Projects, Profiles, Tasks et Scenes. J'ai donc écrit un programme Python permettant d'obtenir, dans mon navigateur web, une carte complète de toute ma configuration, à partir du fichier XML de sauvegarde Tasker que j'avais enregistré sur le disque de mon ordinateur.

Au fil du temps, j'ai amélioré cette carte en y ajoutant de nombreuses options supplémentaires, notamment la possibilité de modifier les objets Tasker et d'obtenir une analyse approfondie de la configuration Tasker.

Le fichier de sauvegarde Tasker, ou tout autre XML exporté par Tasker, peut être téléchargé manuellement sur votre PC/Mac/Linux ou un espace de stockage cloud, ou bien ce programme peut le récupérer directement depuis votre appareil Android (voir la [Note 2](#2)).

## Fonctionnalités

- Le niveau de détail de la sortie que vous choisissez, allant d'un aperçu général à un niveau de détail très précis de votre configuration.
- Affichez uniquement un seul projet, profil ou tâche.
- Inclure/Exclure les conditions de profil et de tâche : États, événements, etc.
- Soit, vous pouvez simplement diffuser tout, soit, vous pouvez rendre la sortie plus esthétique en alignant tous les champs.
- Modifier l'apparence : sélectionnez les modes "clair" ou "sombre".
- Affichez les résultats en utilisant la police à chasse fixe de votre choix, et mettez en évidence les noms de Projet, Profil et Tâche en les mettant en italique, en gras, en couleur ou en soulignant.
- Ajustez les couleurs associées à différents aspects de la sortie pour qu'elles correspondent à votre humeur.
- Inclure les descriptions de TaskerNet et/ou les préférences de l'utilisateur.
- Pour les configurations complexes, vous pouvez également inclure un dictionnaire de liens rapides vers vos projets, profils, tâches et scènes.
- Présentez un schéma de votre configuration complète de Tasker, ainsi qu'un diagramme de flux de tâches.
- Interface en ligne de commande ou graphique.
- Utilisez le fichier XML exporté ou récupérez directement le fichier XML depuis votre appareil Android pour la configuration.
- Envoyez les projets, les profils, les tâches et les scènes à Tasker sur votre appareil Android.
- Enregistrer et restaurer les paramètres de fonctionnement.
- Identifier les tâches qui comportent trop d'« actions » et qui pourraient potentiellement être divisées en plusieurs tâches.
- L'option "Analyse" permet d'analyser un projet, un profil, une tâche ou une scène spécifiques en utilisant les modèles ChatGPT/Claude/Gemini ou Llama (via Ollama) qui fonctionnent sur un serveur ou localement.
- Afficher les résultats directement dans l'interface graphique : (Configuration) Vue de la carte, Vue arborescente et Vue de diagramme.
- Détection automatique des mises à jour et possibilité d'installer manuellement de nouvelles versions.
- Recherche améliorée et fonction "Rechercher/Remplacer" structurée.
- Ajoutez et modifiez des projets, des profils, des tâches et des scènes (voir [Note 6](#6))
- Liste des modifications depuis une date spécifique.
- Analysez la santé du fichier XML de Tasker, ainsi que les nombreuses variables présentes dans la configuration.
- Comparez un fichier XML avec le fichier XML chargé.
- Consultez TaskerNet pour obtenir les dernières mises à jour des projets, des profils et des tâches, et appliquez-les si elles sont disponibles.
- Importer un objet Tasker à partir d'un autre fichier XML, ainsi que toutes ses dépendances.
- Réalisez une analyse des tendances pour déterminer si votre code s'améliore (ou non).
- Faites l'inventaire de tous les éléments qu'une tâche utilise en dehors de l'appareil Android.
- Déterminer « ce qui s'active », en fonction d'une condition spécifique (état ou événement).
- Analysez la logique d'une tâche et comparez un résultat avec un autre.
- Utilisez un moniteur en direct sur l'appareil Android pour voir quels profils et tâches sont actifs.
- Déterminez ce qui consomme le plus d'énergie de votre batterie.

## Dépendances du programme

### - Python version 3.11 ou supérieure

### - Fichier XML Tasker complet ou partiel : backup.xml ou tout autre fichier XML exporté par Tasker

&nbsp;&nbsp;&nbsp;Il vous sera demandé de localiser et d'identifier votre fichier XML exporté par Tasker (par exemple, backup.xml) sur votre ordinateur, créé par Tasker version 5 ou 6. Vous pouvez aussi, facultativement, le récupérer directement depuis votre appareil Android (voir la [Note 2](#2)).

### - Analyse par IA

&nbsp;&nbsp;&nbsp;Cela nécessite une clé API valide si vous utilisez l'analyse basée sur serveur, et/ou l'installation d'Ollama pour l'analyse locale (voir la [Note 3](#3)).

## Installation

Ce programme et l'ensemble de ses prérequis occuperont environ 230 Mo d'espace. Il est recommandé de l'installer dans un environnement virtuel (option 2).

1- Installez MapTasker en entrant l'une des commandes suivantes dans le Terminal/Invite de commandes :

     ```python -m pip install maptasker -U```
                 ...OU...
     ```uv add maptasker```

2- Pour l'installer dans un environnement virtuel, entrez la commande suivante dans le Terminal/invite de commandes :

  via pip...
  - `cd xxx`, où « xxx » est le répertoire dans lequel vous souhaitez configurer l'environnement virtuel.
  - `python -m venv venv`
  - Activez l'environnement virtuel...
    MAC/Linux : `source {directory path to 'xxx'}/venv/bin/activate`
    Windows : `venv\Scripts\activate`
  - `pip install maptasker`

  ...ou...

  via uv...
  - `cd xxx`, où « xxx » est le répertoire dans lequel vous souhaitez configurer l'environnement virtuel.
  - `uv venv`
  - Activez l'environnement virtuel...
    MAC/Linux : `source {directory path to 'xxx'}/venv/bin/activate`
    Windows : `venv\Scripts\activate`
  - `uv pip install maptasker`

- Les fonctionnalités d'analyse par IA nécessitent des bibliothèques supplémentaires (OpenAI, Anthropic, Google et Ollama). MapTasker ne les installe pas automatiquement ; si vous en avez besoin, installez plutôt MapTasker avec l'extra `ai` :

     ```python -m pip install "maptasker[ai]" -U```
                 ...OU...
     ```uv add "maptasker[ai]"```

## Utilisation

- Entrez la commande :

     ```maptasker```
     ...ou, si vous utilisez uv pour gérer l'environnement virtuel...
     ```uv run maptasker```

### Rapports depuis la ligne de commande

Health Check, Compare, Changes Since, Export et la surveillance de dossier (watch) s'exécutent sans fenêtre, ce qui permet de vérifier automatiquement une sauvegarde Tasker nocturne (depuis `cron`, le Planificateur de tâches, `launchd` ou une tâche CI) :

```
maptasker -healthcheck -file backup.xml                 # problèmes détectés dans une sauvegarde
maptasker -compare older.xml newer.xml                  # différences entre deux sauvegardes
maptasker -changes_since week -file backup.xml          # ce qui a changé : today (aujourd'hui), week (semaine), month (mois), all (tout), une date, ou 3d (3 jours)
maptasker -export map -format md -file backup.xml       # la Map (ou le diagramme) au format md, json ou pdf
maptasker -watch ~/TaskerBackups                        # enregistre chaque nouvelle sauvegarde dans l'historique
```

- **`-file`** accepte une sauvegarde, ou un dossier (le fichier `.xml` le plus récent y est utilisé). `-outdir` permet de choisir où les fichiers sont écrits, et `-save` enregistre aussi le rapport dans un fichier, comme le fait la fenêtre.
- **Seul le rapport, et uniquement le rapport, est envoyé sur la sortie standard** ; tout le reste est envoyé sur la sortie d'erreur standard, de sorte que `maptasker -healthcheck -file backup.xml > report.txt` produit un rapport propre.
- **Les codes de sortie (Exit codes)** permettent à un script d'agir selon le résultat :

  | Code | Signification |
  |---|---|
  | 0 | Terminé, et rien à signaler |
  | 10 | Le rapport a détecté quelque chose : erreurs Health Check (`-fail_on warning` pour inclure les avertissements, `-fail_on never` pour les ignorer), ou des différences |
  | 11 | `-changes_since` n'avait aucune configuration antérieure à comparer (la première exécution démarre l'historique) |
  | 1 | Erreur du programme |
  | 2 | Un fichier n'a pas pu être écrit (y compris un dossier `-outdir` inutilisable), ou la sortie n'a pas pu être générée |
  | 3 | Le fichier n'est pas une sauvegarde Tasker valide |
  | 5 | Le Project, Profile ou Task unique demandé (`-project`, `-profile` ou `-task`) n'a pas été trouvé |
  | 6 | Aucun fichier n'a été fourni, ou le fichier/dossier n'existe pas |
  | 7 | Option invalide, par exemple une couleur incorrecte, une valeur `-fail_on` inconnue, ou la comparaison d'un fichier avec lui-même |
  | 8 | La requête vers l'appareil Android exécutant le serveur Tasker a échoué |

- **L'historique.** Toute sauvegarde chargée est enregistrée dans l'historique de configuration, que lit `-changes_since`. `-watch FOLDER` enregistre chaque nouvelle sauvegarde complète apparaissant dans `FOLDER`, datée selon le fichier, de sorte que l'historique se remplit même les jours où vous n'ouvrez jamais MapTasker ; `-watch FOLDER -once` effectue une seule vérification, pour une tâche planifiée. L'historique est conservé dans un dossier `MapTasker_Timeline`, dans le répertoire depuis lequel MapTasker est exécuté ; une tâche planifiée doit donc utiliser `-history_dir` pour pointer vers le même dossier que celui utilisé par la fenêtre.
- **Rien d'autre ne change.** Ces exécutions n'ouvrent jamais de navigateur et ne réécrivent jamais les paramètres conservés par la fenêtre.

## Sortie du programme

MapTasker génère plusieurs fichiers de sortie, à la fois sur l'ordinateur et sur l'appareil Android.

Consultez le [wiki](https://github.com/mctinker/Map-Tasker/wiki/Generated-Output) pour une liste complète des sorties générées par MapTasker.

## Plus d'informations : [[Options d'exécution]](https://github.com/mctinker/Map-Tasker/wiki/Runtime-Options)&nbsp;&nbsp;&nbsp;[[Exemples d'options d'exécution]](https://github.com/mctinker/Map-Tasker/wiki/Sample-Runtime-Options)&nbsp;&nbsp;&nbsp;[[Exemple de sortie]](https://github.com/mctinker/Map-Tasker/wiki#sample-output)

## Structure du projet

Un bref aperçu des principaux fichiers et de leur objectif :

- `maptasker/` : Contient le code de l'application principale.
  - `maptasker/src/` : Les principaux fichiers sources Python pour la logique de MapTasker, organisés en sous-packages par couches.
    (une couche peut importer uniquement celles situées en dessous ; `lint-imports` garantit cela)
    - `gui/` : les fenêtres, les boîtes de dialogue et leurs gestionnaires d'événements de NiceGUI.
    - `device/` : ce que fait l'application MapTasker sur l'appareil Android, grâce au serveur HTTP de Tasker.
    - `mapops/` : remplacement en masse, refonte, réparation, restauration et rédaction ; ainsi que les outils TaskerNet et de préparation.
    - `analysis/` : questions de lecture seule posées lors de la configuration.
    - `mapgen/` et `edit/` : chargement d'une sauvegarde et création de la carte à partir de celle-ci, ainsi que des éditeurs de tâches, de profils, de projets et de scènes.
    - `core/` : état d'exécution, les tables d'actions de Tasker et les utilitaires partagés.
    - `mapit.py`, `progargs.py`, `runcli.py`, `rungui.py`, `clireports.py` : les points d'entrée.
  - `maptasker/assets/` : Les actifs statiques tels que les icônes, les images et les données JSON utilisés par l'application.
  - `maptasker/locale` : fichiers de langue pour les traductions.
- `documentation_images/` : Images utilisées dans ce fichier README et dans d'autres documents.
- `tools/` : outils utilisés pendant le développement.
- `tests/` : Contient des scripts de test et des fichiers associés, destinés à garantir la qualité du code.
- `maptasker/main.py` : Le point d'entrée après la commande `maptasker`. À partir d'un dépôt cloné, exécutez `python -m maptasker.main`.
- `LICENSE` : Le fichier de licence MIT pour le projet.
- `README.md` : Ce fichier.
- `Changelog.md` : Un journal des modifications apportées à chaque version.
- `pyproject.toml` : Métadonnées du projet et configuration du système de construction.

## Licence

Ce projet est sous licence [MIT](../LICENSE).

La licence MIT est une licence de logiciel libre permissive, originaire du Massachusetts Institute of Technology (MIT). Étant une licence permissive, elle n'impose que des restrictions très limitées à la réutilisation et bénéficie donc d'une grande compatibilité entre licences.

En résumé, cela signifie que vous êtes libre de :

- **Utiliser** : utiliser le logiciel pour n'importe quel usage (commercial ou privé).
- **Modifier** : modifier le logiciel.
- **Distribuer** : distribuer le logiciel original ou modifié.
- **Sous-licencier** : accorder une sous-licence du logiciel.

Vous devez :

- **Inclure le copyright** : inclure l'avis de copyright original ainsi que la licence elle-même dans toute partie substantielle du logiciel.

Le logiciel est fourni « EN L'ÉTAT », sans garantie d'aucune sorte. Pour le texte intégral de la licence, veuillez consulter le fichier [LICENSE](../LICENSE).

## Dépannage et FAQ

**Q : Le diagramme `MapTasker_Map.txt` semble mal aligné dans le Bloc-notes de Windows.**

R : Le Bloc-notes peut ne pas gérer correctement l'espacement de ce fichier.

Il est recommandé d'utiliser un autre éditeur de texte tel que Notepad++, VS Code ou Typepad (et de le définir comme application par défaut pour les fichiers `.txt`). Assurez-vous que le « retour à la ligne automatique » est désactivé et qu'une police à espacement fixe est utilisée.

**Q : Comment récupérer le fichier XML Tasker directement depuis mon appareil Android ?**

R : Prérequis :

1- Le navigateur et l'appareil Android doivent être sur le même réseau local.

2- Les deux projets Tasker suivants, que vous devez installer sur votre appareil Android cible, et qui doivent tous deux avoir tous les profils activés :
  ['Exemple de serveur HTTP' (projet Tasker)](https://shorturl.at/bwCD4)
  ['API HTTP de Tasker' (projet Tasker)](https://shorturl.at/hlTj0)

Des informations complémentaires sont disponibles dans la section [Note 2](#2) de ce fichier README.

**Q : Les connecteurs du diagramme sont mal alignés pour les noms en chinois, coréen ou japonais.**

R : Il s'agit d'un problème connu lié aux métriques de police pour ces langues dans la bibliothèque de diagrammes.

**Q : Pourquoi certaines actions de Task et certains states/events de Profile ne sont-ils pas disponibles pour l'édition/l'ajout ?

R : Dans certains cas, ces actions, events ou states nécessitent des informations disponibles uniquement sur Android et/ou dans Tasker lui-même. Autoriser leur modification entraînerait une Task ou un Profile incomplet, provoquant une défaillance de Tasker.

## Notes

Les détails de certains points mentionnés dans la section « Dépannage et FAQ » sont conservés ici pour un contexte supplémentaire.

### 1
**Particularités sous Windows 11 :**

- Seul Windows 11 est pris en charge. Aucune version antérieure de Windows n'est prise en charge.
- Pour les problèmes d'affichage de `MapTasker_Map.txt` dans le Bloc-notes, utilisez un éditeur de texte alternatif tel que Typepad et définissez-le comme application par défaut pour les fichiers `.txt`.

### 2
**Récupération directe du XML depuis Android :**

Pour récupérer directement le fichier XML Tasker :

- Assurez-vous que les appareils de bureau et Android sont connectés au même réseau local et que Tasker est en cours d'exécution.
- The ['Http Server Example' Tasker Project](https://shorturl.at/bwCD4) and ['Tasker HTTP API' Tasker Project](https://shorturl.at/hlTj0) must both be installed and active on the Android device, with the server running. Remember to run the "Update GD HTTP Info" Task and (first time only) enter your Google Drive ID when prompted.
  - AVIS : MapTasker vous offre la possibilité d'installer « Http Server Example » pour vous. Vous trouverez cette option dans le panneau « Obtenir les données XML à partir de l'appareil Android ». Cependant, vous *devez* avoir « Tasker HTTP API » préinstallé pour que cela fonctionne.
- Une fois récupéré, le fichier XML est enregistré sur votre bureau et n'a pas besoin d'être récupéré à nouveau, sauf s'il est modifié.
- D'autres fonctionnalités de MapTasker vous demanderont initialement, sur votre appareil Android, l'autorisation d'utiliser la fonctionnalité spécifique.

### 3
**Prise en charge de l'IA**

L'analyse par IA n'est disponible que via l'interface graphique. Vous ne pouvez exécuter une analyse qu'avec un seul Project, Profile, Task ou Scene à la fois. La prise en charge est disponible pour les modèles basés sur serveur OpenAi (ChatGPT), Gemini et Anthropic, ainsi que pour les modèles Llama basés localement.

Les modèles basés sur Llama sont pris en charge via [Ollama](https://ollama.com/), que vous devez télécharger, installer et exécuter manuellement une fois, afin de configurer le serveur sur votre ordinateur. MapTasker chargera dynamiquement les modèles Llama pour vous s'ils ne sont pas déjà chargés.

Les modules d'IA ne sont pas installés par défaut lors de l'installation de MapTasker. Ils sont plutôt installés dynamiquement lors de la première utilisation de la requête IA spécifique. Ainsi, si vous ne prévoyez pas d'utiliser l'IA, vous n'encourez pas cette surcharge.

## Mises en garde relatives à l'édition et à l'analyse de l'application
**Mises en garde relatives à l'édition et à l'analyse de MapTasker**

Reportez-vous au document [Caveats](https://github.com/mctinker/Map-Tasker/blob/Master/caveats.txt) pour plus de détails.

## Liste de tâches à faire (sans ordre particulier)

- [x] Readiness Check (vérification de l'état de préparation)

- [x] Prise en charge de plugins supplémentaires

- [x] Importation avec dépendances (Import with Dependencies)

- [x] Tests de tâches - Sauvegarder et comparer les sessions de tâches avant et après les modifications apportées à la tâche.

- [x] Task Stepper : exécuter une Task action par action en « mode simulation », en montrant quelles branches If, For et Goto s'exécutent et ce que contient chaque variable

- [x] Live Run Monitor : diffuser en direct les Profiles et Tasks déclenchés sur le téléphone et les mettre en évidence dans la vue Diagram

- [ ] Fusion à trois voies (three-way merge) de deux sauvegardes par rapport à un ancêtre commun, résolue conflit par conflit et annulable en une seule étape

- [x] TaskerNet update tracker : vous avertir lorsque l'auteur d'un partage que vous utilisez publie une nouvelle version, avec un diff des modifications

- [ ] Bibliothèque personnelle de snippets : enregistrer des séquences d'actions, des Tasks et des modèles de Profile réutilisables, et les insérer avec des paramètres

- [ ] Explications en langage simple dans la Map : un résumé en une ligne de chaque Profile et Task, rédigé par IA, mis en cache et modifiable

- [x] Possibilité d'ajouter/modifier les descriptions des tâches dans TaskerNet.

- [x] Vérificateur de ressources manquantes : vérifier que les fichiers, dossiers, images, sons, Scenes et applications référencés par vos actions existent toujours

- [ ] Sauvegarder les préférences de Tasker

- [x] Tableau de bord de complexité et de tendances : suivre dans le temps la longueur des Tasks, l'imbrication, la profondeur des chaînes d'appel et les constats

- [ ] Export vers un site de documentation : un ensemble de pages Markdown ou HTML reliées entre elles, une par Project, Profile, Task et Scene, avec des diagrammes d'appel

- [x] Assistant de renommage et de portée des variables : renommer une variable, ou transformer une variable globale en locale, partout où elle est utilisée, en un seul Undo

## Déclaration de confidentialité

Aucune information n'est capturée et envoyée via le réseau, à moi ou à un tiers quelconque, à l'exception de ce qui est listé ci-dessous (Trafic réseau).

Lorsque vous signalez une erreur, il vous sera très probablement demandé de fournir le fichier journal de sortie de l'erreur ainsi que votre fichier XML, tous deux utilisés uniquement pour déboguer le programme, puis immédiatement supprimés.

Le trafic réseau est le suivant :

- Trafic LAN local lors de la récupération du XML directement depuis votre appareil Android.
- Au démarrage, une fois par jour, vérification auprès de pypi.com pour déterminer si une nouvelle version est disponible.
- Mise à jour du programme depuis pypi.com (via 'pip') si « Upgrade » est sélectionné dans l'interface graphique.
- Lecture du fichier 'Changelog.md' depuis '<https://github.com/mctinker/Map-Tasker>' si « What's New » est sélectionné dans l'interface graphique.
- Utilisation de chatgpt.com lors de l'utilisation de l'analyse par IA avec l'un des modèles OpenAi. La sortie de MapTasker est envoyée au serveur via l'appel API standard pour analyse. Il en va de même pour Claude (Anthropic) et Gemini (Google).
- Des modèles d'IA locaux nouveaux et mis à jour seront chargés depuis '<https://ollama.com/library>' lors de l'exécution de la fonctionnalité d'analyse par IA.
- Les hyperliens source d'images et de vidéos définis via la balise HTML '<img src=https://...>' dans les libellés d'actions de Task et les descriptions TaskerNet seront consultés lorsqu'ils seront cliqués. Exemples : imggur.com, Youtube, Dropbox, Google Drive, etc.

## Contribuer

Les contributions sont les bienvenues ! Voici quelques façons de contribuer à MapTasker :

**Signaler des bugs :**

- Si vous trouvez un bug, veuillez ouvrir une issue sur la [page GitHub Issues](https://github.com/mctinker/Map-Tasker/issues).
- Incluez autant de détails que possible :
  - Les étapes pour reproduire le bug.
  - Le comportement attendu et le comportement observé.
  - Votre système d'exploitation et votre version de Python.
  - La version de MapTasker.
  - Les parties pertinentes de votre fichier XML Tasker (si applicable, et en veillant à ce qu'aucune information sensible ne soit incluse).
  - Le fichier `maptasker.log`, s'il a été généré avec l'option `-debug`.

**Suggérer des améliorations :**

- Ouvrez une issue sur GitHub décrivant votre suggestion.
- Expliquez le cas d'usage et en quoi cette amélioration serait bénéfique.

**Pull Requests :**

- Si vous souhaitez contribuer au code :
    1. Forkez le dépôt.
    2. Créez une nouvelle branche pour votre fonctionnalité ou votre correction de bug (par exemple, `feature/new-output-format` ou `fix/xml-parsing-error`).
    3. Effectuez vos modifications.
    4. Assurez-vous que votre code respecte le style de code Black (comme indiqué par le badge).
    5. Ajoutez des tests pour vos modifications dans le répertoire `tests/`, si applicable.
    6. Assurez-vous que tous les tests passent.
    7. Soumettez une pull request vers la branche `Master`.

**Style de code :**

- Ce projet utilise [Ruff](https://docs.astral.sh/ruff/formatter/) pour le formatage du code. Veuillez vous assurer que vos contributions sont formatées avec Ruff.

Nous vous remercions de votre aide pour améliorer MapTasker !

## Problèmes connus

- Les connecteurs du diagramme sont mal alignés si les noms sont en chinois, coréen ou japonais.
- Toutes les actions de Task et toutes les éditions de states/events de Profile ne sont pas prises en charge, car certaines nécessitent des informations disponibles uniquement sur un appareil Android.

## Contributions

[Taskometer](https://github.com/Taskomater/Tasker-XML-Info)

[©Connor Talbot 2021 pour Clippy](https://github.com/con-dog/clippy)

[Ollama](https://ollama.com/), [OpenAi](https://openai.com/), [Claude AI](https://claude.ai), [Gemini AI](https://gemini.google.com/)

[NiceGui](https://nicegui.io/)

[!["Buy Me A Coffee"](../documentation_images/coffee.png)](https://www.buymeacoffee.com/mctinker)
