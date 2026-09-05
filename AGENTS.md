# AGENTS.md

Este repositorio genera el sitio web de la Constitución Política de los
Estados Unidos Mexicanos (CPEUM), que se publica en
<https://cpeum.mx/>.

A diferencia de cómo se organizaba antes, aquí **no** se mantienen los
artículos ni los decretos de la Constitución. Los datos en formato
`restructuredText` y su historial de reformas (cada cambio constitucional,
desde 1917, como un `commit` en `git`) viven en el repositorio
[`cpeum-decretos`](https://github.com/ceyusa/cpeum-decretos), que se
incorpora como un *submódulo* de git en el directorio `cpeum-decretos/`.

En este repositorio únicamente hay *scripts*, *css* y algunas páginas de
soporte necesarios para compilar esos datos y generar el sitio HTML.

## Estructura del proyecto

- `cpeum-decretos/`: submódulo con los artículos y los decretos de la
  CPEUM en formato `rst` (más su historial de reformas como *commits*).
  Es la fuente de datos para el sitio.
- `CPEUM/`: páginas de soporte del sitio, escritas en `rst`: `acercade.rst`
  y `estadisticas.rst`. No contiene los artículos de la Constitución.
- `css/`: las hojas de estilo usadas por el HTML generado.
- `scripts/`: scripts en bash o Python para automatizar diferentes tareas
  identificadas en este proyecto.
- `html/`: donde se genera, en formato HTML, la Constitución y los
  documentos derivados (artefactos de build, no versionados).

Para clonar este repositorio junto con su submódulo de datos:

```bash
git clone --recurse-submodules https://github.com/ceyusa/cpeum
```

## Flujo de generación del sitio

El flujo completo de compilación está documentado y ejecutable localmente
en `run.sh` (compila el `cpeum.rst` del submódulo en `html/index.html`,
junto con las páginas de soporte, los diffs de reformas y las gráficas
estadísticas). El CI en `.github/workflows/main.yml` replica esos pasos
sin el servidor HTTP.

## Scripts

- `scripts/rst2html5.py`: es un script en Python que, utilizado como
  dependencia [`docutils`](https://www.docutils.org/) convierte los
  archivos en `restructuredText` en un sitio en HTML.

  Para compilar la Constitución (tomada del submódulo) se ejecuta:

  ```bash
  mkdir -p html
  uv run scripts/rst2html5.py cpeum-decretos/CPEUM/cpeum.rst html/index.html
  ```

  Las páginas de soporte se compilan de igual forma, por ejemplo:

  ```bash
  uv run scripts/rst2html5.py CPEUM/acercade.rst html/acercade.html
  uv run scripts/rst2html5.py CPEUM/estadisticas.rst html/estadisticas.html
  ```

- `scripts/generar_reformas.js`: es un script en JavaScript que, usando
  el paquete [`diff2html`](https://www.npmjs.com/package/diff2html),
  genera una página HTML con el diff de cada reforma constitucional
  (con una apariencia similar a la de GitHub) y un índice de todas las
  reformas en `html/decretos/`. Cada reforma se corresponde con un
  `commit` de reforma dentro del submódulo `cpeum-decretos`.

  Para ejecutar el script:

  ```bash
  node scripts/generar_reformas.js
  ```

- `scripts/generar_graficos.py`: genera las gráficas (SVG) de estadísticas
  de las reformas en `html/graficos/` a partir del historial de commits de
  reforma.

- `scripts/sitemap.py`: genera el `html/sitemap.xml` del sitio.

- `scripts/bluesky.py`: utilidad Python para publicar reformas en BlueSky.
  La publicación también está implementada de forma directa (inline) en el
  workflow `.github/workflows/bluesky.yaml`, que es el que se usa
  actualmente.

### Uso de Python

Python se usa a través de un entorno virtual controlado con `uv`. El
archivo `pyproject.toml` describe las dependencias actuales.

Todos los scripts en Python no deben tener ningún problema detectado por
`ruff` y `pylint`.

- **Linting:** `ruff check scripts/*.py*`
- **Formateo:** `ruff format scripts/*.py*`
- **Pylint:** `uv run pylint scripts/*.py*`

### Bash

Usar `shellcheck` para validar los scripts en bash.

### CSS

Usar `biome` para validar y corregir formato de archivos CSS.

```bash
npx @biomejs/biome lint --write css/
```

### JavaScript

Usar `biome` para validar y corregir formato de los scripts en
JavaScript.

```bash
npx @biomejs/biome check scripts/*.js
npx @biomejs/biome lint --write scripts/*.js
npx @biomejs/biome format --write scripts/*.js
```

Las dependencias de los scripts en JavaScript se gestionan con `npm` y
se describen en `package.json`. Para instalar las dependencias y
generar los diffs de reformas se ejecuta:

```bash
npm install
node scripts/generar_reformas.js
```

## pre-commit

El proyecto utiliza `pre-commit` para realizar revisiones automáticas a
cada commit. Aquí únicamente se validan los archivos de este repositorio:
scripts en Python y JavaScript (`ruff`/`pylint`/`biome`), css (`biome`) y
cuestiones genéricas de git/yaml. La validación de los artículos,
vocabulario, ortografía y reflow de los `.rst` de la Constitución se hace
en el repositorio de datos [`cpeum-decretos`](https://github.com/ceyusa/cpeum-decretos),
que tiene su propio pre-commit y CI.

## Ortografía

Sólo las páginas de soporte (`CPEUM/acercade.rst` y
`CPEUM/estadisticas.rst`) usan `es-local.dic` para su revisión ortográfica
con `pyspelling`. La ortografía del cuerpo de la Constitución la revisa el
repositorio `cpeum-decretos`.

```bash
uv run pyspelling -n ortografia
```

Las palabras no reconocidas se añaden al final de archivo `es-local.dic`.
Las palabras que se añaden pueden ser nombres propios o *palabras
correctas* pero no registradas.

## Validación del formato `restructuredText`

La validación con `rstcheck` de los archivos de la Constitución se hace en
el repositorio `cpeum-decretos`. En este repositorio, al compilar las
páginas de soporte (`CPEUM/*.rst`) con `rst2html5.py` (que usa
`strict_visitor: yes` en `docutils.conf`), se detectan también errores de
formato de esos archivos.

## Formato del mensajes de `commit`

*No* utilizar la especificación de `conventional commits`. En cambio, si
cambia algo en los `css`, el prefijo es `css`. Si cambia algo en los
`scripts`, el prefijo es `scripts`.

En este repositorio no se registran decretos constitucionales; los commits
con el formato de los cambios y Decretos Constitucionales (asunto
`Artículo[s] …`, presidente, fecha de publicación en el DOF, etc.) se
realizan en el repositorio `cpeum-decretos`, según su propio `AGENTS.md`.
