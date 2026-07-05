# AGENTS.md

Este proyecto mantiene la Constitución Política de los Estados Unidos
Mexicanos (CPEUM) en formato `restructuredText`.

Cada cambio Constitucional, desde 1917, está representado como un
`commit` en `git`.

## Fuente de información

La Constitución en formato `restructuredText` se ha reconstruido a
partir de los decretos y otros cambios Constitucionales registrados en
<https://www.diputados.gob.mx/LeyesBiblio/ref/cpeum_crono.htm>.

## Estructura del proyecto

- `CPEUM/`: contiene los artículos de la Constitución en formato `rst`,
  cuyo nombre de archivo es el número del artículo. Además de `toc.rst`,
  que es la tabla de contenidos e incluye cada artículo. Finalmente,
  están los artículos transitorios, cuyos nombres de archivos comienzan
  con la letra `T` y el número de transitorio.
- `css/`: las hojas de estilo usadas por el HTML generado a partir de
  los archivos en `rst`.
- `scripts/`: scripts en bash o Python para automatizar diferentes
  tareas identificadas en este proyecto.
- `html/`: donde se genera. en formato HTML, la Constitución y
  documentos derivados.

## Scripts

- `scripts/rst2html5.py`: es un script en Python que, utilizado como
  dependencia [`docutils`](https://www.docutils.org/) convierte los
  archivos en `restructuredText` en un sitio en HTML.

  Para ejecutar el script se ejecutan los siguientes comandos:

  ```bash
  cd CPEUM
  uv run ../scripts/rst2html5.py toc.rst ../html/index.html
  ```

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

## pre-commit

El proyecto utiliza `pre-commit` para realizar revisiones automáticas a
cada commit.

## Ortografía

Para revisar la ortografía se utiliza `pyspelling`:

```bash
uv run pyspelling -n ortografia
```

Las palabras no reconocidas se añaden al final de archivo `es-local.dic`
y se ejecuta el script `uv run scripts/corregir_diccionario.py` para
procesar el directorio. Las palabras que se añaden pueden ser nombres
propios o *palabras correctas* pero no registradas.

## Validación del formato `restructuredText`

Para validar que el formato de los archivos en `rst` sea correcto se usa
`rstcheck`.

```bash
uv run rstcheck CPEUM/*.rst
```

## Formato del mensajes de `commit`

*No* utilizar la especificación de `conventional commits`. En cambio, si
cambia algo en los `css`, el prefijo es `css`. Si cambia algo en los
`scripts`, el prefijo es `scripts`.

### Decretos y cambios Constitucionales

El formato del mensaje de `commit` para cambios y Decretos
Constitucionales tiene el siguiente formato:

```text
  Artículo[s] <lista con el número de artículo de los artículos
  modificados>

  DECRETO con el que … <resumen del decreto incluido en el Decreto>.

  President[e,a] Nombre del Presidente de la República que firmó el
  Decreto

  Publicado en el Diario Oficial de la Federación el <fecha de
  publicación en formato `[día] del [mes] del [año]`>
  <url del Diario Oficial de la Federación (dof) con el Decreto>

  <Explicación opcional del decreto incluido en la página del Congreso>
  <Lista de cambios realizados por artículo>
```
