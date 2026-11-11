<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../documentation_images/maptasker_logo_dark.png">
    <img src="../documentation_images/maptasker_logo_light.png" alt="MapTasker">
  </picture>
</p>

<div align="center">

![PyPI](https://img.shields.io/pypi/v/maptasker)
![PyPI - Descargas](https://img.shields.io/pypi/dm/maptasker?color=green&label=downloads)
![Descargas](https://static.pepy.tech/personalized-badge/maptasker?period=total&units=international_system&left_color=grey&right_color=green&left_text=downloads)
![Python](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Fmctinker%2FMap-Tasker%2Frefs%2Fheads%2FMaster%2Fpyproject.toml)
![PyPI - Licencia](https://img.shields.io/pypi/l/maptasker)
![](https://tokei.rs/b1/github/mctinker/Map-Tasker)
[![Sourcery](https://img.shields.io/badge/Sourcery-enabled-brightgreen)](https://sourcery.ai)
[![Estilo de código: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![pytest](https://img.shields.io/badge/tested%20with-pytest-blue?logo=pytest)](https://docs.pytest.org/)
[!["Comprar una taza de café"](../documentation_images/coffee.png)](https://www.buymeacoffee.com/mctinker)

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

> Esta traducción se generó automáticamente. Si hay alguna discrepancia, el [README original en inglés](../README.md) prevalece.

## Visualice, edite y analice los Proyectos, Perfiles, Tareas y Escenas de Tasker en el navegador de su escritorio (Mac/Windows 11/Linux) a partir del archivo de copia de seguridad o del XML exportado por Tasker

Mapa de configuración...
![Mapa de configuración de MapTasker: un proyecto, sus perfiles y sus tareas como un esquema sangrado y codificado por colores, con las acciones numeradas de cada tarea y su configuración debajo](../documentation_images/intro.png)

Mapa de diagrama...
![Mapa de diagrama de MapTasker: un proyecto y sus perfiles dibujados como cuadros con sus tareas debajo, y líneas que trazan qué tarea llama a cuál, con una ruta de llamada resaltada](../documentation_images/Introd.png)

[[Más ejemplos]](<https://github.com/mctinker/Map-Tasker/wiki#sample-output>)

Esta es una aplicación complementaria de [Tasker](https://tasker.joaoapps.com/) diseñada para ejecutarse en un navegador web (vea la [Nota 1](#1)).

Descubrí que mis Proyectos, Perfiles, Tareas y Escenas de Tasker se estaban volviendo inmanejables, y que la pantalla de mi teléfono era demasiado pequeña para navegar por ellos. Así que escribí un programa en Python para generar un mapa completo de toda mi configuración en el navegador web, a partir del archivo XML de copia de seguridad de Tasker que guardé en el disco de mi escritorio local.

Con el tiempo, perfeccioné el mapa añadiendo muchas opciones adicionales, incluida la posibilidad de editar objetos de Tasker y de obtener un análisis en profundidad de la configuración.

El archivo XML de copia de seguridad de Tasker, u otro XML exportado por Tasker, se puede subir manualmente a su PC/Mac/Linux o a una unidad en la nube, o este programa puede obtenerlo directamente desde su dispositivo Android (vea la [Nota 2](#2)).

## Características

- El nivel de detalle de la salida que elija, desde una visión general hasta un nivel de detalle muy específico de su configuración.
- Mostrar solo un único proyecto, perfil o tarea.
- Incluir/excluir condiciones para perfiles y tareas: estados, eventos, etc.
- Simplemente transmita todo o, en cambio, formatee la salida para que todos los campos estén alineados.
- Cambia la apariencia: elige los modos 'claro' o 'oscuro'.
- Genera la salida utilizando la fuente monoespaciada que prefieras, y destaca los nombres de "Proyecto", "Perfil" y "Tarea" utilizando negritas, cursivas, resaltes y/o subrayados.
- Modifique los colores asociados a los diferentes aspectos de la salida para que se adapten a su estado de ánimo.
- Incluya descripciones y/o preferencias de Tasker.
- Para configuraciones complejas, opcionalmente incluya un diccionario de enlaces rápidos a sus proyectos, perfiles, tareas y escenas.
- Muestra un diagrama de toda tu configuración de Tasker, así como un diagrama de flujo de tareas.
- Interfaz de línea de comandos o interfaz gráfica de usuario.
- Utilice el archivo XML exportado o obtenga el archivo XML directamente desde su dispositivo Android para la configuración.
- Envía los proyectos, perfiles, tareas y escenas de nuevo a Tasker en tu dispositivo Android.
- Guarda y restaura la configuración durante la ejecución.
- Identifique las tareas que tienen demasiadas "acciones" y que podrían dividirse en varias tareas.
- Opción de Análisis AI para analizar un proyecto, perfil, tarea o escena específicos utilizando los modelos compatibles, ya sean ChatGPT/Claude/Gemini basados en servidor o los modelos Llama basados localmente (a través de Ollama).
- Mostrar los resultados directamente dentro de la interfaz gráfica de usuario: (Configuración) Vista de mapa, vista de árbol y vista de diagrama.
- Detección automática de actualizaciones y, opcionalmente, instalación de nuevas versiones.
- Búsqueda mejorada y función de "Buscar y Reemplazar" estructurada.
- Añadir y editar proyectos, perfiles, tareas y escenas (ver [Nota 6](#6))
- Lista de cambios desde una fecha específica.
- Analice la salud del archivo XML de Tasker, así como las numerosas variables presentes en la configuración.
- Compara un archivo XML con el XML cargado.
- Verifique TaskerNet para obtener las últimas actualizaciones de los proyectos, perfiles y tareas, y aplíquelas si están disponibles.
- Importe un objeto de Tasker de otro archivo XML, junto con todas sus dependencias.
- Realice un análisis de tendencias para determinar si su código está mejorando (o no).
- Realice un inventario de todo lo que una Tarea utiliza fuera del dispositivo Android.
- Determinar "qué se activa" en función de una condición específica (estado o evento).
- Analice la lógica de una tarea y compare un resultado con otro.
- Ejecute una monitorización en tiempo real en el dispositivo Android para ver qué perfiles y tareas están activas.
- Identifique qué está consumiendo más batería.
- Extrae cada fragmento de texto que una persona lee (Flash, Notify, Say, diálogos, etiquetas de escena) y organízalos en una tabla para traducirlos o editarlos, y luego vuelve a insertar el texto editado.
- Gestionar las variables globales: identificar dónde se establecen y se leen, renombrar una en todas las partes, modificar su valor y enviarla al teléfono.

## Dependencias del programa

### - Python versión 3.11 o superior

### - Archivo XML completo o parcial de Tasker: backup.xml u otro archivo XML exportado por Tasker

&nbsp;&nbsp;&nbsp;Se le pedirá que localice e identifique su archivo XML exportado por Tasker (por ejemplo, backup.xml) en su escritorio, creado por Tasker versión 5 o versión 6. Opcionalmente, puede obtenerlo directamente desde su dispositivo Android (vea la [Nota 2](#2)).

### - Análisis con IA

&nbsp;&nbsp;&nbsp;Esto requiere una clave API válida si se usa el análisis basado en servidor, y/o tener Ollama instalado para el análisis local (vea la [Nota 3](#3)).

## Instalación

Este programa y todos sus requisitos previos ocuparán alrededor de 230 MB de espacio. Se recomienda instalarlo en un entorno virtual (opción 2).

1- Instale MapTasker introduciendo uno de los siguientes comandos en la Terminal/Símbolo del sistema:

     ```python -m pip install maptasker -U```
                 ...O BIEN...
     ```uv add maptasker```

2- Para instalarlo en un entorno virtual, introduzca el siguiente comando en la terminal/línea de comandos:

  mediante pip...
  - `cd xxx`, donde 'xxx' es el directorio en el que desea configurar el entorno virtual.
  - `python -m venv venv`
  - Active el entorno virtual...
    MAC/Linux: `source {directory path to 'xxx'}/venv/bin/activate`
    Windows: `venv\Scripts\activate`
  - `pip install maptasker`

  ...o bien...

  mediante uv...
  - `cd xxx`, donde 'xxx' es el directorio en el que desea configurar el entorno virtual.
  - `uv venv`
  - Active el entorno virtual...
    MAC/Linux: `source {directory path to 'xxx'}/venv/bin/activate`
    Windows: `venv\Scripts\activate`
  - `uv pip install maptasker`

- Las funciones de análisis con IA necesitan bibliotecas adicionales (OpenAI, Anthropic, Google y Ollama). MapTasker no las instala automáticamente; si las desea, instale MapTasker con el extra `ai`:

     ```python -m pip install "maptasker[ai]" -U```
                 ...O BIEN...
     ```uv add "maptasker[ai]"```

## Uso

- Introduzca el comando:

     ```maptasker```
     ...o, si usa uv para gestionar el entorno virtual...
     ```uv run maptasker```

### Informes desde la línea de comandos

Health Check (chequeo de salud), Compare (comparar), Changes Since (cambios desde), Export (exportar) y la vigilancia de carpetas se ejecutan sin ventana, de modo que una copia de seguridad nocturna de Tasker puede comprobarse automáticamente (desde `cron`, el Programador de tareas, `launchd` o un trabajo de CI):

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

- **`-file`** acepta una copia de seguridad, o una carpeta (se usa el `.xml` más reciente que contenga). `-outdir` elige dónde se escriben los archivos, y `-save` también guarda el informe como archivo, igual que hace la ventana.
- **El informe, y solo el informe, se envía a la salida estándar**; todo lo demás se envía a la salida de error estándar, de modo que `maptasker -healthcheck -file backup.xml > report.txt` produce un informe limpio.
- **Los códigos de salida** permiten que un script actúe según el resultado:

  | Código | Significado |
  |---|---|
  | 0 | Finalizado, y no había nada que informar |
  | 10 | El informe encontró algo: errores de Health Check (use `-fail_on warning` para incluir advertencias, `-fail_on never` para ignorarlas), o diferencias |
  | 11 | `-changes_since` no tenía ninguna configuración anterior con la que comparar (la primera ejecución inicia el historial) |
  | 1 | Error del programa |
  | 2 | No se pudo escribir un archivo (incluida una carpeta `-outdir` que no se puede usar), o no se pudo generar la salida |
  | 3 | El archivo no es una copia de seguridad válida de Tasker |
  | 5 | No se encontró el Proyecto, Perfil o Tarea individual solicitado (`-project`, `-profile` o `-task`) |
  | 6 | No se proporcionó ningún archivo, o el archivo o carpeta no existe |
  | 7 | Opción no válida, como un color incorrecto, un valor de `-fail_on` desconocido, o comparar un archivo consigo mismo |
  | 8 | Falló la solicitud al dispositivo Android que ejecuta el servidor de Tasker |

- **El historial.** Toda copia de seguridad que se carga queda registrada en el historial de configuración, que es lo que lee `-changes_since`. `-watch FOLDER` registra cada copia de seguridad nueva y completa que aparece en `FOLDER`, con la fecha del archivo, de modo que el historial se completa incluso en los días en que nunca abre MapTasker; `-watch FOLDER -once` revisa una sola vez, útil para un trabajo programado. El historial se guarda en una carpeta `MapTasker_Timeline` dentro del directorio desde el que se ejecuta MapTasker, por lo que un trabajo programado debería usar `-history_dir` para apuntar a la misma carpeta que usa la ventana.
- **Nada más cambia.** Estas ejecuciones nunca abren un navegador ni reescriben la configuración que conserva la ventana.

## Salida del programa

MapTasker genera varios archivos de salida, tanto en el escritorio como en el dispositivo Android.

Consulte la [wiki](https://github.com/mctinker/Map-Tasker/wiki/Generated-Output) para ver una lista completa de la salida generada por MapTasker.

## Más información: [[Opciones de ejecución]](https://github.com/mctinker/Map-Tasker/wiki/Runtime-Options)&nbsp;&nbsp;&nbsp;[[Ejemplos de opciones de ejecución]](https://github.com/mctinker/Map-Tasker/wiki/Sample-Runtime-Options)&nbsp;&nbsp;&nbsp;[[Ejemplo de salida]](https://github.com/mctinker/Map-Tasker/wiki#sample-output)

## Estructura del proyecto

Una breve descripción de los principales archivos y su propósito:

- `maptasker/`: Contiene el código de la aplicación principal.
  - `maptasker/src/`: Los principales archivos fuente de Python para la lógica de MapTasker, organizados en subpaquetes por capa.
    (una capa puede importar solo las que están debajo; `lint-imports` lo hace posible):
    - `gui/`: las ventanas, los cuadros de diálogo y sus manejadores de eventos de NiceGUI.
    - `device/`: lo que hace la aplicación MapTasker en el dispositivo Android, a través del servidor HTTP de Tasker.
    - `mapops/`: reemplazo masivo, refactorización, reparación, restauración y elaboración de borradores; así como las herramientas de TaskerNet y de preparación.
    - `analysis/`: Preguntas de solo lectura que se hacen a una configuración.
    - `mapgen/` y `edit/`: carga de una copia de seguridad y creación del mapa a partir de ella, así como de los editores de Tarea, Perfil, Proyecto y Escena.
    - `core/`: estado de ejecución, las tablas de acciones de Tasker y las utilidades compartidas.
    - `mapit.py`, `progargs.py`, `runcli.py`, `rungui.py`, `clireports.py`: los puntos de entrada.
  - `maptasker/assets/`: Activos estáticos como iconos, imágenes y datos JSON utilizados por la aplicación.
  - `maptasker/locale`: archivos de idioma para traducciones.
- `documentation_images/`: Imágenes utilizadas en este archivo README y en otra documentación.
- `tools/`: herramientas utilizadas durante el desarrollo.
- `tests/`: Contiene scripts de prueba y archivos relacionados para garantizar la calidad del código.
- `maptasker/main.py`: El punto de entrada que sigue al comando `maptasker`. Desde un repositorio clonado, ejecute `python -m maptasker.main`.
- `LICENSE`: Archivo de la licencia MIT para el proyecto.
- `README.md`: Este archivo.
- `Changelog.md`: Un registro de los cambios realizados en cada versión.
- `pyproject.toml`: Metadatos del proyecto y configuración del sistema de construcción.

## Licencia

Este proyecto está licenciado bajo la [Licencia MIT](../LICENSE).

La Licencia MIT es una licencia de software libre permisiva originada en el Instituto Tecnológico de Massachusetts (MIT). Al ser una licencia permisiva, impone restricciones muy limitadas a la reutilización y, por lo tanto, tiene una alta compatibilidad con otras licencias.

En resumen, esto significa que usted es libre de:

- **Usar**: Usar el software para cualquier propósito (comercial o privado).
- **Modificar**: Modificar el software.
- **Distribuir**: Distribuir el software original o modificado.
- **Sublicenciar**: Sublicenciar el software.

Usted debe:

- **Incluir el copyright**: Incluir el aviso de copyright original y la propia licencia en cualquier parte sustancial del software.

El software se proporciona "TAL CUAL", sin garantía de ningún tipo. Para el texto completo de la licencia, consulte el archivo [LICENSE](../LICENSE).

## Solución de problemas y preguntas frecuentes

**P: El diagrama `MapTasker_Map.txt` se ve desalineado en el Bloc de notas de Windows.**

R: El Bloc de notas puede no manejar correctamente el espaciado de este archivo.

Se recomienda usar un editor de texto diferente, como Notepad++, VS Code o Typepad (y establecerlo como predeterminado para archivos `.txt`). Asegúrese de que el "ajuste de texto" esté desactivado y de usar una fuente monoespaciada.

**P: ¿Cómo obtengo el archivo XML de Tasker directamente desde mi dispositivo Android?**

R: Requisitos previos:

1- El navegador y el dispositivo Android deben estar en la misma red local.

2- Los siguientes dos proyectos de ejemplo de Tasker en su dispositivo Android, ambos de los cuales deben instalarse con todos los perfiles habilitados:
  ['Ejemplo de servidor HTTP' Proyecto de Tasker](https://shorturl.at/bwCD4)
  ['API HTTP de Tasker' Proyecto de Tasker](https://shorturl.at/hlTj0)

Se pueden encontrar más detalles en la sección [Nota 2](#2) de este archivo README.

**P: Los conectores del diagrama quedan desalineados con nombres en chino, coreano o japonés.**

R: Este es un problema conocido relacionado con las métricas de las fuentes para estos idiomas en la biblioteca de diagramación.

**P: ¿Por qué algunas acciones de Tareas y estados/eventos de Perfiles no están disponibles para editar/añadir?

R: En algunos casos, estas acciones, eventos o estados requieren información que solo está disponible en Android y/o dentro de Tasker. Permitir una edición para estos daría como resultado una Tarea o Perfil incompleto, lo que provocaría un fallo en Tasker.

## Notas

Los detalles de algunos de los puntos mencionados en la sección "Solución de problemas y preguntas frecuentes" se conservan aquí para contexto adicional.

### 1
**Particularidades de Windows 11:**

- Solo se admite Windows 11. No se admite ninguna versión anterior de Windows.
- Para problemas de visualización de `MapTasker_Map.txt` en el Bloc de notas, use un editor de texto alternativo como Typepad y establézcalo como predeterminado para archivos `.txt`.

### 2
**Obtención directa del XML desde Android:**

Para obtener el archivo XML de Tasker directamente:

- Asegúrese de que tanto los dispositivos de escritorio como los de Android estén conectados a la misma red local y de que Tasker esté en funcionamiento.
- Los proyectos de Tasker ['Http Server Example'](https://shorturl.at/bwCD4) y ['Tasker HTTP API'](https://shorturl.at/hlTj0) deben estar instalados y activos en el dispositivo Android, con el servidor en funcionamiento. Recuerde ejecutar la tarea "Update GD HTTP Info" y, solo la primera vez, introducir su ID de Google Drive cuando se le solicite.
  - NOTA: MapTasker ofrece la opción de instalar "Ejemplo de Servidor HTTP" por usted. Puede encontrar esta opción en el panel "OBTENER XML DEL DISPOSITIVO ANDROID". Sin embargo, *es necesario* que "Tasker HTTP API" ya esté instalado para que funcione.
- Una vez descargado, el archivo XML se guarda en el escritorio y no necesita ser descargado de nuevo con frecuencia, a menos que se haya modificado.
- Otras características de MapTasker solicitarán primero permiso en su dispositivo Android para que la función específica pueda funcionar.

### 3
**Compatibilidad con IA**

El análisis con IA solo está disponible a través de la interfaz gráfica. Solo puede ejecutar un análisis usando un único Proyecto, Perfil, Tarea o Escena. Es compatible con OpenAi (ChatGPT), Gemini y Anthropic basados en servidor, así como con modelos Llama basados localmente.

Los modelos basados en Llama son compatibles a través de [Ollama](https://ollama.com/), que debe descargar, instalar y ejecutar manualmente una vez para configurar el servidor en su escritorio. MapTasker cargará dinámicamente los modelos Llama por usted si aún no están cargados.

Los módulos de soporte de IA no se instalan de forma predeterminada al instalar MapTasker. En su lugar, se instalan dinámicamente la primera vez que se usa la solicitud de IA específica. De esta forma, si no planea usar la IA, no incurrirá en esa sobrecarga.

## Advertencias de edición y análisis de la aplicación
**Advertencias de edición y análisis de MapTasker**

Consulte el documento de [Advertencias (Caveats)](https://github.com/mctinker/Map-Tasker/blob/Master/caveats.txt) para más detalles.

## Lista de tareas pendientes (sin un orden particular)

- [x] Comprobación de preparación (Readiness Check)

- [x] Soporte para complementos adicionales

- [x] Importación con dependencias (Import with Dependencies)

- [x] Pruebas de tareas: Almacenar y comparar sesiones de "paso" de tareas antes y después de realizar cambios en la tarea.

- [ ] Mapear las preferencias restantes de Tasker

- [x] Live Run Monitor: transmitir en vivo qué Perfiles y Tareas se activan en el teléfono y resaltarlos en la vista de Diagrama

- [ ] Explicaciones en lenguaje sencillo dentro del Mapa: un resumen de una línea, escrito por IA, en caché y editable, de cada Perfil y Tarea

- [ ] Exportación a sitio de documentación: un conjunto enlazado de páginas Markdown o HTML, una por cada Proyecto, Perfil, Tarea y Escena, con diagramas de llamadas

- [ ] Fusión de tres fuentes para combinar dos copias de seguridad divergentes.

- [ ] Gráfico de dependencias del proyecto

## Declaración de privacidad

No se captura ni se envía por la red ninguna información a mí ni a ningún otro tercero, salvo lo indicado a continuación (Tráfico de red).

Al reportar un error, es muy probable que se le pida que proporcione el archivo de registro de salida del error y su archivo XML, ambos usados únicamente para depurar el programa y luego eliminados de inmediato.

El tráfico de red es el siguiente:

- Tráfico de red local (LAN) al obtener el XML directamente desde su dispositivo Android.
- Al inicio, una vez al día, se comprueba en pypi.com si hay una nueva versión disponible.
- Se actualiza el programa desde pypi.com (mediante 'pip') si se selecciona 'Upgrade' (Actualizar) en la interfaz gráfica.
- Se lee el archivo 'Changelog.md' desde '<https://github.com/mctinker/Map-Tasker>' si se selecciona "What's New" (Novedades) en la interfaz gráfica.
- Se usa chatgpt.com cuando se utiliza el análisis con IA con cualquiera de los modelos de OpenAi. La salida de MapTasker se envía al servidor mediante la llamada API estándar para su análisis. Lo mismo ocurre con Claude (Anthropic) y Gemini (Google).
- Se cargarán modelos de IA locales nuevos y actualizados desde '<https://ollama.com/library>' al ejecutar la función de Análisis con IA.
- Se accederá a los hiperenlaces de origen de imágenes y videos definidos mediante la etiqueta HTML '<img src=https://...>' en las etiquetas de acción de Tareas y en las descripciones de TaskerNet, cuando se haga clic en ellos. Ejemplos: imggur.com, Youtube, Dropbox, Google Drive, etc.

## Cómo contribuir

¡Las contribuciones son bienvenidas! Estas son algunas formas en las que puede contribuir a MapTasker:

**Reportar errores:**

- Si encuentra un error, por favor abra un issue en la [página de GitHub Issues](https://github.com/mctinker/Map-Tasker/issues).
- Incluya tantos detalles como sea posible:
  - Pasos para reproducir el error.
  - Comportamiento esperado y comportamiento real.
  - Su sistema operativo y versión de Python.
  - Versión de MapTasker.
  - Partes relevantes de su archivo XML de Tasker (si corresponde, y asegurándose de no incluir información sensible).
  - El archivo `maptasker.log`, si se generó con la opción `-debug`.

**Sugerir mejoras:**

- Abra un issue en GitHub describiendo su sugerencia.
- Explique el caso de uso y por qué esta mejora sería beneficiosa.

**Pull Requests:**

- Si desea contribuir con código:
    1. Haga un fork del repositorio.
    2. Cree una nueva rama para su función o corrección de error (por ejemplo, `feature/new-output-format` o `fix/xml-parsing-error`).
    3. Realice sus cambios.
    4. Asegúrese de que su código cumpla con el estilo de código Black (como indica la insignia).
    5. Añada pruebas para sus cambios en el directorio `tests/` si corresponde.
    6. Asegúrese de que todas las pruebas pasen.
    7. Envíe una pull request a la rama `Master`.

**Estilo de código:**

- Este proyecto utiliza [Ruff](https://docs.astral.sh/ruff/formatter/) para el formateo de código. Asegúrese de que sus contribuciones estén formateadas con Ruff.

¡Agradecemos su ayuda para mejorar MapTasker!

## Problemas conocidos

- Los conectores del diagrama quedan desalineados si los nombres están en chino, coreano o japonés.
- No se admite la edición de todas las acciones de Tareas y estados/eventos de Perfiles, ya que algunos requieren información que solo está disponible en un dispositivo Android.

## Contribuciones

[Taskometer](https://github.com/Taskomater/Tasker-XML-Info)

[©Connor Talbot 2021, para Clippy](https://github.com/con-dog/clippy)

[Ollama](https://ollama.com/), [OpenAi](https://openai.com/), [Claude AI](https://claude.ai), [Gemini AI](https://gemini.google.com/)

[NiceGui](https://nicegui.io/)

[!["Buy Me A Coffee"](../documentation_images/coffee.png)](https://www.buymeacoffee.com/mctinker)
