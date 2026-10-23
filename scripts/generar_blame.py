#!/usr/bin/env python3
# :Copyright: © 2026 Víctor Jáquez.
# :License: Released under the terms of the `2-Clause BSD license`_, in short:
#
#    Copying and distribution of this file, with or without modification,
#    are permitted in any medium without royalty provided the copyright
#    notice and this notice are preserved.
#    This file is offered as-is, without any warranty.
#
# .. _2-Clause BSD license: https://opensource.org/licenses/BSD-2-Clause

"""Genera una página de trazabilidad (git blame) por cada artículo.

Cada reforma constitucional del submódulo ``cpeum-decretos`` es un *commit*.
Este script reconstruye, párrafo a párrafo, qué commit modificó por última
vez el texto de cada artículo y escribe una página HTML con esa atribución.

El agrupamiento es por párrafos (bloques separados por líneas en blanco), no
por líneas sueltas: así un cambio de reflujo o de formato no “roba” la
atribución del decreto que realmente cambió la redacción. Para cada bloque se
muestra el número de decreto, su fecha de publicación en el DOF, el título,
la persona que lo firmó y los enlaces al diff y al commit.

El resultado se escribe en ``html/blame/``: una página por artículo, más un
índice en ``html/blame/index.html``.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

from chevron import render
from rst2html5 import pub_date_to_iso

# -----------------------------------------------------------------------------
# Configuración
# -----------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
DECRETOS_DIR = REPO_ROOT / "cpeum-decretos"
CPEUM_DIR = DECRETOS_DIR / "CPEUM"
TEMPLATES_DIR = REPO_ROOT / "templates"
CSS_DIR = REPO_ROOT / "css"
DECRETOS_JSON = REPO_ROOT / "html" / "decretos.json"
OUTPUT_DIR = REPO_ROOT / "html" / "blame"

ARCHIVO_RE = re.compile(r"^(?:\d{3}|T\d{3})\.rst$")

PUBLICADO_RE = re.compile(
    r"Publicado\s+en\s+el\s+Diario\s+Oficial\s+de\s+la\s+Federaci[oó]n"
    r"\s+(?:el\s+)?(\d{1,2})(?:[roº]+)?\.?\s+(?:de\s+)?"
    r"([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)\s+(?:de|del)?\s*(?:año\s+)?(\d{3,4})",
    re.IGNORECASE,
)
DOF_RE = re.compile(r"https?://(?:www\.)?dof\.gob\.mx\S+", re.IGNORECASE)
PRESIDENTE_RE = re.compile(r"^President[ea]\s+(.+)$", re.MULTILINE)

MESES_LARGOS = [
    "",
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]

# Paleta para distinguir los bloques. El color se elige por número de decreto.
PALETA = [
    "#1f5f8b",
    "#8a4b12",
    "#2f6b3a",
    "#7a2f2f",
    "#4a4a8a",
    "#6b5b1f",
    "#1f6b6b",
    "#7a3e65",
    "#3f6b8a",
    "#5c4b2f",
]

SITIO = json.loads((TEMPLATES_DIR / "site.json").read_text(encoding="utf-8"))
BANNER_TEMPLATE = (TEMPLATES_DIR / "banner.mustache").read_text(encoding="utf-8")
HEAD_META_TEMPLATE = (TEMPLATES_DIR / "head_meta.mustache").read_text(encoding="utf-8")
SITIO_CSS = (CSS_DIR / "sitio.css").read_text(encoding="utf-8")
BLAME_CSS = (CSS_DIR / "blame.css").read_text(encoding="utf-8")


# -----------------------------------------------------------------------------
# Utilidades
# -----------------------------------------------------------------------------


def escapar(texto: str, *, atributo: bool = False) -> str:
    """Escapa texto para HTML (también comillas si es un atributo)."""
    return html.escape(texto, quote=atributo)


def normalizar(texto: str) -> str:
    """Normaliza un título para compararlo (sin acentos ni puntuación)."""
    sin_acentos = "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caracter) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", "", sin_acentos.lower())


def fecha_larga(iso: str | None) -> str:
    """Convierte una fecha ISO en una fecha legible en español."""
    if not iso:
        return ""
    dia = date.fromisoformat(iso)
    return f"{dia.day} de {MESES_LARGOS[dia.month]} de {dia.year}"


def iso_de_fecha(texto: str) -> str | None:
    """Extrae la fecha de publicación en el DOF y la devuelve en ISO 8601."""
    coincidencia = PUBLICADO_RE.search(texto)
    if not coincidencia:
        return None
    dia, mes, anio = coincidencia.groups()
    return pub_date_to_iso(f"{dia} de {mes} de {anio}")


def run_git(*args: str) -> str:
    """Ejecuta git en el submódulo y devuelve la salida estándar."""
    resultado = subprocess.run(
        ["git", "-C", str(DECRETOS_DIR), *args],
        capture_output=True,
        check=True,
        text=True,
        timeout=120,
    )
    return resultado.stdout


# -----------------------------------------------------------------------------
# Catálogo de decretos
# -----------------------------------------------------------------------------


def cargar_indice_decretos() -> tuple[dict[str, list[dict]], dict[str, dict]]:
    """Carga html/decretos.json y lo indexa por fecha y por título."""
    por_fecha: dict[str, list[dict]] = {}
    por_titulo: dict[str, dict] = {}
    try:
        decretos = json.loads(DECRETOS_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print(
            f"AVISO: no se pudo leer {DECRETOS_JSON}; "
            "los commits se enlazarán a GitHub.",
            file=sys.stderr,
        )
        return por_fecha, por_titulo
    for decreto in decretos:
        publicacion = decreto.get("publicacion")
        if publicacion:
            por_fecha.setdefault(publicacion, []).append(decreto)
        clave = normalizar(decreto.get("decreto", ""))
        if clave:
            por_titulo.setdefault(clave, decreto)
    return por_fecha, por_titulo


def _mejor_coincidencia(clave: str, grupo: list[dict]) -> dict | None:
    """Busca el título del grupo más parecido al normalizado dado."""
    mejor: dict | None = None
    mejor_ratio = 0.0
    for decreto in grupo:
        ratio = SequenceMatcher(
            None, clave, normalizar(decreto.get("decreto", ""))
        ).ratio()
        if ratio > mejor_ratio:
            mejor, mejor_ratio = decreto, ratio
    return mejor if mejor_ratio >= 0.85 else None


def numero_decreto(
    iso: str | None,
    titulo: str,
    indice: tuple[dict[str, list[dict]], dict[str, dict]],
) -> int | None:
    """Devuelve el número del decreto que corresponde a un commit.

    Busca por fecha de publicación y título exacto; si en esa fecha hay
    varios decretos, acepta el título más parecido. Si hay ambigüedad
    prefiere no asignar un número antes que asignar el decreto equivocado.
    """
    por_fecha, por_titulo = indice
    clave = normalizar(titulo)
    if iso and iso in por_fecha:
        grupo = por_fecha[iso]
        for decreto in grupo:
            if normalizar(decreto.get("decreto", "")) == clave:
                return decreto.get("numero")
        if len(grupo) == 1:
            return grupo[0].get("numero")
        mejor = _mejor_coincidencia(clave, grupo)
        if mejor is not None:
            return mejor.get("numero")
    decreto = por_titulo.get(clave)
    return decreto.get("numero") if decreto else None


# -----------------------------------------------------------------------------
# Commits y su clasificación
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Fuente:
    """Un commit que modificó un artículo, con los datos para mostrarlo."""

    # pylint: disable=too-many-instance-attributes
    hash: str
    asunto: str
    resumen: str
    fecha: str | None
    presidente: str | None
    url_dof: str | None
    numero: int | None
    tipo: str


@dataclass
class Bloque:
    """Un párrafo (o grupo de líneas) con su atribución."""

    lineas: list[str] = field(default_factory=list)
    inicio: int = 0
    fuente: Fuente | None = None


def _primer_parrafo(cuerpo: str, asunto: str) -> str:
    """Devuelve el primer párrafo del cuerpo, con los saltos colapsados."""
    for parrafo in re.split(r"\n\s*\n", cuerpo.strip()):
        texto = " ".join(parrafo.split())
        if texto:
            return texto
    return asunto


def _clasificar(
    commit: str,
    asunto: str,
    cuerpo: str,
    raices: set[str],
    indice: tuple[dict[str, list[dict]], dict[str, dict]],
) -> tuple[str, int | None, str, str | None, str | None, str | None]:
    """Clasifica un commit y extrae sus datos de decreto."""
    asunto_normalizado = normalizar(asunto)
    texto_plano = " ".join(cuerpo.split())
    fecha = iso_de_fecha(texto_plano)
    coincidencia = DOF_RE.search(cuerpo)
    url_dof = coincidencia.group(0).rstrip(".,;:)") if coincidencia else None

    if commit in raices or asunto_normalizado.startswith("constitucion"):
        resumen = (
            "Constitución Política de los Estados Unidos Mexicanos "
            "(texto original de 1917)"
        )
        return "original", None, resumen, fecha, None, url_dof

    resumen = _primer_parrafo(cuerpo, asunto)
    coincidencia = PRESIDENTE_RE.search(cuerpo)
    presidente = " ".join(coincidencia.group(1).split()) if coincidencia else None

    if asunto_normalizado.startswith("fedeerratas"):
        return "errata", None, resumen, fecha, presidente, url_dof
    if asunto_normalizado.startswith("aclaracion"):
        return "aclaracion", None, resumen, fecha, presidente, url_dof
    if asunto_normalizado.startswith("articulo"):
        numero = numero_decreto(fecha, resumen, indice)
        return "decreto", numero, resumen, fecha, presidente, url_dof
    return "otro", None, resumen, fecha, presidente, url_dof


def _crear_fuente(
    commit: str,
    asunto: str,
    cuerpo: str,
    raices: set[str],
    indice: tuple[dict[str, list[dict]], dict[str, dict]],
) -> Fuente:
    """Construye la Fuente de un commit a partir de su mensaje."""
    tipo, numero, resumen, fecha, presidente, url_dof = _clasificar(
        commit, asunto, cuerpo, raices, indice
    )
    return Fuente(
        hash=commit,
        asunto=asunto,
        resumen=resumen,
        fecha=fecha,
        presidente=presidente,
        url_dof=url_dof,
        numero=numero,
        tipo=tipo,
    )


def cargar_fuentes(
    indice: tuple[dict[str, list[dict]], dict[str, dict]],
) -> dict[str, Fuente]:
    """Lee el historial completo y devuelve un mapa hash → Fuente."""
    raices = set(run_git("rev-list", "--max-parents=0", "HEAD").split())
    salida = run_git("log", "--format=%H%x1f%as%x1f%s%x1f%b%x1e", "HEAD")
    fuentes: dict[str, Fuente] = {}

    for bloque in salida.split("\x1e"):
        bloque = bloque.strip("\n")
        if not bloque:
            continue
        partes = bloque.split("\x1f", 3)
        if len(partes) != 4:
            continue
        commit, _fecha_commit, asunto, cuerpo = partes
        fuentes[commit] = _crear_fuente(commit, asunto, cuerpo, raices, indice)

    return fuentes


# -----------------------------------------------------------------------------
# Atribución por párrafo
# -----------------------------------------------------------------------------


def bloques_de_texto(texto: str) -> list[list[str]]:
    """Divide un texto en bloques de líneas no vacías."""
    bloques: list[list[str]] = []
    actual: list[str] = []
    for linea in texto.splitlines():
        if linea.strip():
            actual.append(linea)
        elif actual:
            bloques.append(actual)
            actual = []
    if actual:
        bloques.append(actual)
    return bloques


def clave_bloque(bloque: list[str]) -> str:
    """Calcula una clave estable para un párrafo, insensible al reflujo.

    Se conserva la sangría de la primera línea (que puede cambiar la
    estructura reST), pero se colapsan los espacios internos y los saltos de
    línea, de modo que un reajuste de líneas no altera la atribución.
    """
    lineas = [linea for linea in bloque if linea.strip()]
    if not lineas:
        return ""
    sangria = len(lineas[0]) - len(lineas[0].lstrip(" "))
    cuerpo = " ".join(" ".join(linea.split()) for linea in lineas)
    return f"{sangria}:{cuerpo}"


def _siguiente_estado(
    estado: dict[tuple[str, int], str], texto: str, commit: str
) -> dict[tuple[str, int], str]:
    """Actualiza la atribución con el contenido de un commit."""
    contador: Counter[str] = Counter()
    nuevo: dict[tuple[str, int], str] = {}
    for bloque in bloques_de_texto(texto):
        clave = clave_bloque(bloque)
        ocurrencia = contador[clave]
        contador[clave] += 1
        nuevo[(clave, ocurrencia)] = estado.get((clave, ocurrencia), commit)
    return nuevo


def atribuir_historial(
    commits: list[str], ruta_relativa: str
) -> dict[tuple[str, int], str]:
    """Atribuye cada párrafo al commit que cambió su texto por última vez."""
    estado: dict[tuple[str, int], str] = {}
    for commit in commits:
        texto = run_git("show", f"{commit}:{ruta_relativa}")
        estado = _siguiente_estado(estado, texto, commit)
    return estado


def agrupar_lineas(lineas: list[str]) -> list[list[str]]:
    """Agrupa las líneas en párrafos, adjuntando los blancos al anterior."""
    bloques: list[list[str]] = []
    actual: list[str] = []
    for linea in lineas:
        if linea.strip():
            if actual and not actual[-1].strip():
                bloques.append(actual)
                actual = []
            actual.append(linea)
        elif actual:
            actual.append(linea)
        elif bloques:
            bloques[-1].append(linea)
        else:
            actual.append(linea)
    if actual:
        bloques.append(actual)
    return bloques


def procesar_archivo(
    ruta: Path, fuentes: dict[str, Fuente]
) -> tuple[str, list[Bloque]]:
    """Calcula el título y los bloques atribuidos de un artículo."""
    ruta_relativa = f"CPEUM/{ruta.name}"
    commits = run_git("log", "--reverse", "--format=%H", "--", ruta_relativa).split()
    estado = atribuir_historial(commits, ruta_relativa)
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    titulo = titulo_seccion(ruta.stem, titulo_de_archivo(ruta))

    contador: Counter[str] = Counter()
    bloques: list[Bloque] = []
    inicio = 0
    for grupo in agrupar_lineas(lineas):
        clave = clave_bloque(grupo)
        ocurrencia = contador[clave]
        contador[clave] += 1
        commit = estado.get((clave, ocurrencia))
        if commit is None and commits:
            commit = commits[-1]
        fuente = fuentes.get(commit) if commit else None
        bloques.append(Bloque(lineas=grupo, inicio=inicio, fuente=fuente))
        inicio += len(grupo)

    return titulo, bloques


# -----------------------------------------------------------------------------
# Generación de HTML
# -----------------------------------------------------------------------------


def formatear_linea(linea: str) -> str:
    """Escapa una línea y convierte el énfasis reST más común."""
    texto = escapar(linea)
    texto = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", texto)
    return texto or "&nbsp;"


def _documento(*, titulo: str, ruta: str, cuerpo: str) -> str:
    """Envuelve el cuerpo de una página con el chrome del sitio."""
    head_meta = render(
        HEAD_META_TEMPLATE,
        {
            **SITIO,
            "og_title": titulo,
            "og_description": SITIO["description"],
            "og_type": "article" if ruta else "website",
            "og_url": f"https://cpeum.mx/blame/{ruta}",
            "twitter_title": titulo,
            "canonical": f"https://cpeum.mx/blame/{ruta}",
            "icon_base": "../",
        },
    )
    banner = render(
        BANNER_TEMPLATE,
        {
            **SITIO,
            "cpeum_href": "../index.html",
            "decretos_href": "../decretos/index.html",
            "estadisticas_href": "../estadisticas.html",
            "acerca_href": "../acercade.html",
        },
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="es">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{escapar(titulo)}</title>\n"
        f"{head_meta}"
        "<style>\n"
        f"{SITIO_CSS}\n{BLAME_CSS}"
        "</style>\n"
        "</head>\n"
        '<body class="blame">\n'
        f"{banner}\n"
        f"{cuerpo}\n"
        "</body>\n"
        "</html>\n"
    )


def etiqueta_fuente(fuente: Fuente) -> str:
    """Devuelve la etiqueta visible de una fuente."""
    if fuente.tipo == "decreto":
        return f"Decreto {fuente.numero}" if fuente.numero else "Decreto"
    if fuente.tipo == "errata":
        return "Fe de erratas"
    if fuente.tipo == "aclaracion":
        return "Aclaración"
    if fuente.tipo == "original":
        return "Texto original"
    return f"Commit {fuente.hash[:7]}"


def url_fuente(fuente: Fuente, stem: str) -> tuple[str, bool]:
    """Devuelve el enlace principal de una fuente y si es externo."""
    if fuente.tipo == "decreto" and fuente.numero is not None:
        return f"../decretos/{fuente.numero}.html#{stem}", False
    return f"{SITIO['github_url']}/commit/{fuente.hash}", True


def _enlace(texto: str, url: str, *, externo: bool, clase: str) -> str:
    """Construye un enlace HTML."""
    atributos = f'class="{clase}" href="{escapar(url, atributo=True)}"'
    if externo:
        atributos += ' rel="external noreferrer" target="_blank"'
    return f"<a {atributos}>{texto}</a>"


def render_anotacion(fuente: Fuente | None, stem: str) -> str:
    """Genera la anotación (cabecera) de un bloque."""
    if fuente is None:
        return '<div class="blame-anotacion">Origen desconocido</div>\n'

    url, externo = url_fuente(fuente, stem)
    partes = [
        f'<span class="blame-insignia">{escapar(etiqueta_fuente(fuente))}</span>',
        _enlace(
            escapar(fuente.resumen or fuente.asunto),
            url,
            externo=externo,
            clase="blame-titulo",
        ),
    ]
    if fuente.fecha:
        partes.append(
            f'<time datetime="{fuente.fecha}">{fecha_larga(fuente.fecha)}</time>'
        )
    if fuente.presidente:
        partes.append(
            f'<span class="blame-presidente">{escapar(fuente.presidente)}</span>'
        )
    if fuente.url_dof:
        partes.append(
            _enlace("DOF ↗", fuente.url_dof, externo=True, clase="blame-enlace")
        )
    if not externo:
        partes.append(
            _enlace(
                f"commit {fuente.hash[:7]}",
                f"{SITIO['github_url']}/commit/{fuente.hash}",
                externo=True,
                clase="blame-enlace",
            )
        )
    return f'<div class="blame-anotacion">{"".join(partes)}</div>\n'


def _color_bloque(fuente: Fuente | None, anterior: int | None) -> tuple[str, int]:
    """Elige un color estable para el bloque, distinto del anterior."""
    if fuente is None:
        indice = 0
    elif fuente.numero is not None:
        indice = fuente.numero % len(PALETA)
    else:
        indice = int(fuente.hash[:6], 16) % len(PALETA)
    if indice == anterior:
        indice = (indice + 1) % len(PALETA)
    return PALETA[indice], indice


def _resumen_articulo(bloques: list[Bloque]) -> str:
    """Genera el párrafo introductorio con los conteos de un artículo."""
    lineas = sum(len(bloque.lineas) for bloque in bloques)
    decretos = {
        bloque.fuente.numero
        for bloque in bloques
        if bloque.fuente and bloque.fuente.numero
    }
    fuentes = {bloque.fuente.hash for bloque in bloques if bloque.fuente is not None}
    return (
        '<p class="blame-intro">'
        f"{lineas} líneas en {len(bloques)} bloques; "
        f"{len(decretos)} decretos y {len(fuentes)} fuentes. "
        "Cada bloque corresponde a un párrafo y apunta al decreto que "
        "modificó su texto por última vez (git blame a nivel de párrafo, "
        "insensible al reflujo de líneas). "
        '<a href="../decretos/index.html">Índice de decretos ↗</a>'
        "</p>\n"
    )


def _render_bloques(bloques: list[Bloque], stem: str) -> str:
    """Genera el HTML de todos los bloques de un artículo."""
    partes: list[str] = []
    anterior: int | None = None
    for bloque in bloques:
        color, anterior = _color_bloque(bloque.fuente, anterior)
        partes.append(f'<section class="blame-bloque" style="--blame-color:{color}">\n')
        partes.append(render_anotacion(bloque.fuente, stem))
        partes.append('<div class="blame-codigo">\n')
        for desplazamiento, linea in enumerate(bloque.lineas):
            numero = bloque.inicio + desplazamiento + 1
            clase = "blame-linea"
            if not linea.strip():
                clase += " blame-vacia"
            partes.append(
                f'<div class="{clase}">'
                f'<span class="blame-num">{numero}</span>'
                f'<span class="blame-texto">{formatear_linea(linea)}</span>'
                "</div>\n"
            )
        partes.append("</div>\n</section>\n")
    return "".join(partes)


def escribir_articulo(
    stem: str, titulo: str, bloques: list[Bloque], salida: Path
) -> None:
    """Escribe la página de trazabilidad de un artículo."""
    partes = ['<nav class="blame-nav">\n']
    partes.append('<a href="index.html">← Índice de trazabilidad</a>\n')
    if stem.isdigit():
        partes.append(f'<a href="../index.html#{stem}">Texto vigente ↗</a>\n')
    partes.append("</nav>\n")
    partes.append(f"<h1>{escapar(titulo)}</h1>\n")
    partes.append(_resumen_articulo(bloques))
    partes.append(_render_bloques(bloques, stem))

    partes.append(
        '<p class="blame-nota">'
        "La atribución se calcula a partir del historial de git del "
        "repositorio de datos; las fe de erratas y aclaraciones aparecen "
        "como fuentes propias. "
        f'<a href="{SITIO["github_url"]}" rel="external noreferrer" '
        'target="_blank">Código y datos en GitHub ↗</a>'
        "</p>\n"
    )

    destino = salida / f"{stem}.html"
    destino.write_text(
        _documento(
            titulo=f"CPEUM — {titulo} — trazabilidad",
            ruta=f"{stem}.html",
            cuerpo="".join(partes),
        ),
        encoding="utf-8",
    )
    print(f"Generado {destino}")


def titulo_seccion(stem: str, titulo: str) -> str:
    """Devuelve el título de la página según el tipo de archivo."""
    if stem == "T000":
        return "Artículos transitorios originales (1917)"
    if stem.startswith("T"):
        return f"Transitorios del Decreto {int(stem[1:])}"
    return titulo


def titulo_de_archivo(ruta: Path) -> str:
    """Obtiene el título de un artículo a partir de su primera línea."""
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        texto = linea.strip().strip("*").strip()
        if texto:
            return texto
    if ruta.stem.isdigit():
        return f"Artículo {int(ruta.stem)}"
    return f"Transitorio {ruta.stem}"


def _orden_archivo(ruta: Path) -> tuple[int, int]:
    """Ordena artículos primero y transitorios después."""
    if ruta.stem.isdigit():
        return (0, int(ruta.stem))
    return (1, int(ruta.stem[1:]))


def todos_los_archivos() -> list[Path]:
    """Devuelve los archivos de artículo del submódulo, en orden."""
    return sorted(
        (ruta for ruta in CPEUM_DIR.glob("*.rst") if ARCHIVO_RE.match(ruta.name)),
        key=_orden_archivo,
    )


def _indice_lista(rutas: list[Path], *, transitorios: bool) -> list[str]:
    """Genera una lista de enlaces del índice."""
    partes = ['<ul class="blame-indice">\n']
    for ruta in rutas:
        if transitorios:
            etiqueta = titulo_seccion(ruta.stem, "")
        else:
            etiqueta = f"Artículo {int(ruta.stem)}"
        partes.append(f'<li><a href="{ruta.stem}.html">{escapar(etiqueta)}</a></li>\n')
    partes.append("</ul>\n")
    return partes


def escribir_indice(salida: Path) -> None:
    """Escribe el índice de todas las páginas de trazabilidad."""
    archivos = todos_los_archivos()
    articulos = [ruta for ruta in archivos if ruta.stem.isdigit()]
    transitorios = [ruta for ruta in archivos if ruta.stem.startswith("T")]

    partes = [
        (
            '<nav class="blame-nav">\n'
            '<a href="../index.html">← Texto de la Constitución</a>\n'
            '<a href="../decretos/index.html">Índice de decretos</a>\n'
            "</nav>\n"
            "<h1>Trazabilidad de los artículos</h1>\n"
            '<p class="blame-intro">'
            "Cada página muestra el texto de un artículo agrupado por párrafos. "
            "Cada bloque apunta al decreto que modificó su redacción por última "
            "vez, con su fecha de publicación en el DOF, el diff del decreto y "
            "el commit correspondiente. La atribución se obtiene del historial "
            "de git del repositorio de datos y no se ve afectada por el reflujo "
            "de líneas."
            "</p>\n"
            "<h2>Artículos</h2>\n"
        )
    ]
    partes.extend(_indice_lista(articulos, transitorios=False))
    partes.append("<h2>Artículos transitorios</h2>\n")
    partes.extend(_indice_lista(transitorios, transitorios=True))
    partes.append(
        '<p class="blame-nota">'
        "Los artículos transitorios se agrupan por decreto (un archivo por "
        "decreto). Las fe de erratas y las aclaraciones aparecen como "
        "fuentes propias cuando modificaron el texto. "
        f'<a href="{SITIO["github_url"]}" rel="external noreferrer" '
        'target="_blank">Código y datos en GitHub ↗</a>'
        "</p>\n"
    )

    destino = salida / "index.html"
    destino.write_text(
        _documento(
            titulo="CPEUM — Trazabilidad de los artículos",
            ruta="",
            cuerpo="".join(partes),
        ),
        encoding="utf-8",
    )
    print(f"Generado {destino}")


# -----------------------------------------------------------------------------
# Punto de entrada
# -----------------------------------------------------------------------------


def _normalizar_stem(argumento: str) -> str:
    """Normaliza un número de artículo o un nombre de archivo."""
    nombre = Path(argumento).name
    nombre = nombre.removesuffix(".rst")
    if nombre.isdigit():
        return f"{int(nombre):03d}"
    if nombre[:1].upper() == "T" and nombre[1:].isdigit():
        return f"T{int(nombre[1:]):03d}"
    return nombre


def _seleccionar_archivos(argumentos: list[str]) -> list[Path]:
    """Resuelve los argumentos de la línea de comandos a archivos."""
    disponibles = {ruta.stem: ruta for ruta in todos_los_archivos()}
    if not argumentos:
        return list(disponibles.values())
    seleccionados: list[Path] = []
    for argumento in argumentos:
        stem = _normalizar_stem(argumento)
        if stem not in disponibles:
            raise SystemExit(f"No se encontró el artículo: {argumento}")
        seleccionados.append(disponibles[stem])
    return seleccionados


def main() -> None:
    """Punto de entrada principal."""
    parser = argparse.ArgumentParser(
        description=(
            "Genera una página HTML de trazabilidad (git blame por párrafo) "
            "para cada artículo de la CPEUM."
        )
    )
    parser.add_argument(
        "archivos",
        nargs="*",
        metavar="ARTÍCULO",
        help=(
            "artículos a generar (p. ej. 1, 001, T123). "
            "Sin argumentos se generan todos."
        ),
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=OUTPUT_DIR,
        help=f"directorio de salida (por omisión: {OUTPUT_DIR})",
    )
    parser.add_argument(
        "--sin-indice",
        action="store_true",
        help="no generar html/blame/index.html",
    )
    args = parser.parse_args()

    if not CPEUM_DIR.is_dir():
        parser.error(f"No se encontró el submódulo: {CPEUM_DIR}")

    archivos = _seleccionar_archivos(args.archivos)
    indice = cargar_indice_decretos()
    fuentes = cargar_fuentes(indice)
    args.salida.mkdir(parents=True, exist_ok=True)

    for ruta in archivos:
        titulo, bloques = procesar_archivo(ruta, fuentes)
        escribir_articulo(ruta.stem, titulo, bloques, args.salida)

    if not args.sin_indice:
        escribir_indice(args.salida)


if __name__ == "__main__":
    main()
