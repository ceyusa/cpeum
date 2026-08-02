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

"""Genera gráficas de barras horizontales (SVG) sobre las reformas a la CPEUM.

Cada reforma constitucional está representada como un *commit* en el
repositorio. Este script recorre ese historial para obtener los datos que
se muestran en cuatro gráficas:

1. Cuántas reformas se hicieron por presidencia.
2. Número de artículos modificados por presidencia.
3. Número de líneas nuevas o modificadas por presidencia.
4. Cuántas veces ha sido reformado cada artículo.

El resultado se guarda como archivos ``.svg`` en ``html/graficos/``.
"""

from __future__ import annotations

import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

# -----------------------------------------------------------------------------
# Configuración
# -----------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "html" / "graficos"

ARTICLE_RE = re.compile(r"^CPEUM/(\d{3})\.rst$")
TRANSTORIO_RE = re.compile(r"^CPEUM/T\d{3}\.rst$")

PRESIDENT_RE = re.compile(r"^President(a|e)\s+(.+)$")
PRESIDENT_NAME_RE = re.compile(r"^[A-Z][A-Za-zÁÉÍÓÚÑáéíóúñü. º]*$")

# Colores para las barras (matiz por índice).
COLORS = [
    "#1f6fb0",
    "#2f9e77",
    "#c0563c",
    "#8e54a6",
    "#d4931f",
    "#3b82b0",
    "#6b8a3d",
]

# Colores para el tema (texto, ejes, fondo).
AXIS_COLOR = "#444"
TEXT_COLOR = "#222"
GRID_COLOR = "#d9d9d9"
BACKGROUND = "#ffffff"


# -----------------------------------------------------------------------------
# Acceso a git
# -----------------------------------------------------------------------------


def run_git(args: list[str]) -> str:
    """Ejecuta un comando ``git`` en la raíz del repositorio y devuelve su salida."""
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
        timeout=30,
    ).stdout


def reform_commits() -> list[dict]:
    """Devuelve los commits de reforma constitucional en orden cronológico.

    Igual que ``scripts/generar_reformas.js``, se buscan los commits cuyo
    mensaje menciona "Artículo"/"Articulo". Se conserva el hash y el cuerpo
    del mensaje (donde aparece el presidente que firmó el decreto).
    """
    output = run_git(
        [
            "log",
            "--reverse",
            "--grep=Artículo",
            "--grep=Articulo",
            "--format=%H%n%b%n@@@@@",
        ]
    )
    commits = []
    for block in output.split("@@@@@"):
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        body = "\n".join(lines[1:])
        commits.append({"hash": lines[0].strip(), "body": body})
    return commits


# -----------------------------------------------------------------------------
# Extracción de datos
# -----------------------------------------------------------------------------


def extract_president(body: str) -> str | None:
    """Devuelve el nombre normalizado del presidente que firma el decreto.

    El nombre se lee de la línea ``Presidente/Presidenta <Nombres>`` del
    cuerpo del commit. Se exigen al menos dos palabras capitalizadas para
    descartar falsos positivos (p. ej. "Presidente de la República...",
    "Presidente para ausentarse..."), que provienen de citas del texto
    constitucional dentro del mensaje.
    """
    for line in body.splitlines():
        match = PRESIDENT_RE.match(line.rstrip())
        if not match:
            continue
        rest = match.group(2).strip()
        if not PRESIDENT_NAME_RE.fullmatch(rest):
            continue
        if len(rest.split()) < 2:
            continue
        return rest
    return None


def rst_files_for_commit(commit_hash: str) -> list[str]:
    """Lista de archivos ``.rst`` modificados por un commit."""
    output = run_git(["diff-tree", "--no-commit-id", "-r", "--name-only", commit_hash])
    return [f for f in output.split() if f.endswith(".rst")]


def added_lines_for_commit(commit_hash: str) -> int:
    """Número de líneas añadidas (nuevas o modificadas) por un commit.

    Se suman las adiciones de ``git show --numstat`` de los archivos
    ``.rst`` relacionados con artículos o transitorios (se descarta ``toc``).
    """
    output = run_git(["show", "--numstat", "--format=", commit_hash])
    total = 0
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        filename = parts[2]
        if not (ARTICLE_RE.fullmatch(filename) or TRANSTORIO_RE.fullmatch(filename)):
            continue
        if parts[0].isdigit():
            total += int(parts[0])
    return total


def is_article_file(filename: str) -> bool:
    """``True`` si el archivo es un artículo de la Constitución (no transitorio)."""
    return ARTICLE_RE.fullmatch(filename) is not None


def collect_data() -> tuple[Counter, Counter, Counter, Counter]:
    """Recopila los datos para las cuatro gráficas.

    Devuelve cuatro contadores:
    - ``reformas_por_presidente``: cuántos decretos firmó cada presidente.
    - ``articulos_por_presidente``: artículos (no transitorios) modificados.
    - ``lineas_por_presidente``: líneas nuevas o modificadas.
    - ``reformas_por_articulo``: cuántas veces se reformó cada artículo.
    """
    reformas_por_presidente: Counter[str] = Counter()
    lineas_por_presidente: Counter[str] = Counter()
    reformas_por_articulo: Counter[str] = Counter()

    articulos_por_presidente: defaultdict[str, set[str]] = defaultdict(set)

    for commit in reform_commits():
        president = extract_president(commit["body"])
        if president is None:
            # Commits sin presidente identificable no aportan a las gráficas
            # por presidencia, pero sí al conteo por artículo.
            pass

        rst_files = rst_files_for_commit(commit["hash"])

        # Conteo por artículo (independiente de la presidencia).
        for filename in rst_files:
            if is_article_file(filename):
                reformas_por_articulo[filename] += 1

        if president is None:
            continue

        reformas_por_presidente[president] += 1
        lineas_por_presidente[president] += added_lines_for_commit(commit["hash"])
        for filename in rst_files:
            if is_article_file(filename):
                articulos_por_presidente[president].add(filename)

    articulos_por_presidente_count = Counter(
        {name: len(files) for name, files in articulos_por_presidente.items()}
    )

    return (
        reformas_por_presidente,
        articulos_por_presidente_count,
        lineas_por_presidente,
        reformas_por_articulo,
    )


# -----------------------------------------------------------------------------
# Generación de SVG de barras horizontales
# -----------------------------------------------------------------------------


def article_label(filename: str) -> str:
    """Convierte ``CPEUM/073.rst`` en la etiqueta ``Artículo 73``."""
    number = ARTICLE_RE.fullmatch(filename).group(1)
    return f"Artículo {int(number)}"


def render_bar_chart(
    title: str,
    labels: list[str],
    values: list[int],
) -> str:
    """Genera el XML de una gráfica de barras horizontales.

    ``labels`` y ``values`` deben estar en el mismo orden (una por fila).
    Las barras se dibujan de mayor a menor.
    """
    # pylint: disable=too-many-locals
    if len(labels) != len(values):
        raise ValueError("labels y values deben tener la misma longitud")

    rows = list(zip(labels, values))
    rows.sort(key=lambda item: item[1], reverse=True)

    lay = {
        "width": 940,
        "left": 250,
        "right": 70,
        "top": 84,
        "bottom": 30,
        "bar": 26,
        "gap": 14,
    }
    lay["chart_y"] = lay["top"] + lay["bar"]

    max_value = max((v for _, v in rows), default=0)
    max_value = max(max_value, 1)
    plot_width = lay["width"] - lay["left"] - lay["right"]

    body = []
    body.append(
        f'<rect x="0" y="0" width="{lay["width"]}" '
        f'height="{lay["chart_y"] * len(rows) + lay["bottom"]}" fill="{BACKGROUND}"/>'
    )
    body.append(
        f'<text x="{lay["width"] / 2:.0f}" y="40" text-anchor="middle" '
        f'font-family="Georgia, serif" font-size="26" font-weight="bold" '
        f'fill="{TEXT_COLOR}">{_xml_escape(title)}</text>'
    )

    body.append(
        f'<line x1="{lay["left"]}" x2="{lay["width"] - lay["right"]}" '
        f'y1="{lay["top"]}" y2="{lay["top"]}" stroke="{GRID_COLOR}" stroke-width="1"/>'
    )
    tick_step = _nice_step(max_value / 5)
    if tick_step <= 0:
        tick_step = 1
    tick = 0
    while tick <= max_value:
        x = lay["left"] + plot_width * (tick / max_value)
        body.append(
            f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{lay["top"]}" y2="{lay["top"] - 6}" '
            f'stroke="{GRID_COLOR}" stroke-width="1"/>'
        )
        body.append(
            f'<text x="{x:.1f}" y="{lay["top"] - 14}" text-anchor="middle" '
            f'font-family="Arial, sans-serif" font-size="13" fill="{AXIS_COLOR}">'
            f"{int(tick)}</text>"
        )
        tick += tick_step

    for index, (label, value) in enumerate(rows):
        y = lay["top"] + index * (lay["bar"] + lay["gap"])
        bar_width = plot_width * (value / max_value)

        # Etiqueta a la izquierda, alineada a la derecha.
        body.append(
            f'<text x="{lay["left"] - 12}" y="{y + lay["bar"] - 6}" '
            f'text-anchor="end" font-family="Arial, sans-serif" font-size="15" '
            f'fill="{TEXT_COLOR}">{_xml_escape(label)}</text>'
        )

        color = COLORS[index % len(COLORS)]
        body.append(
            f'<rect x="{lay["left"]}" y="{y}" width="{bar_width:.1f}" '
            f'height="{lay["bar"]}" rx="6" fill="{color}"/>'
        )

        body.append(
            f'<text x="{lay["left"] + bar_width + 10:.1f}" y="{y + lay["bar"] - 6}" '
            f'font-family="Arial, sans-serif" font-size="15" font-weight="bold" '
            f'fill="{TEXT_COLOR}">{value}</text>'
        )

    height = (
        lay["top"] + len(rows) * (lay["bar"] + lay["gap"]) - lay["gap"] + lay["bottom"]
    )
    body_svg = "".join(body)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {lay["width"]} {height}" '
        f'width="100%" height="auto" role="img" aria-label="{_xml_escape(title)}">'
        f"{body_svg}</svg>\n"
    )


def _nice_step(raw: float) -> int:
    """Redondea ``raw`` al paso más cercano de 1/2/5 para los ejes."""
    for step in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000):
        if raw <= step:
            return step
    return int(raw)


def _xml_escape(text: str) -> str:
    """Escapa caracteres especiales para texto XML."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# -----------------------------------------------------------------------------
# Punto de entrada
# -----------------------------------------------------------------------------


def label_for_president(name: str) -> str:
    """Etiqueta (nombre completo) del presidente en la gráfica."""
    return name


def main() -> None:
    """Genera las cuatro gráficas SVG en ``html/graficos/``."""
    (
        reformas_por_presidente,
        articulos_por_presidente,
        lineas_por_presidente,
        reformas_por_articulo,
    ) = collect_data()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    charts = [
        (
            "Reformas por presidencia",
            "reformas_por_presidente.svg",
            reformas_por_presidente,
            label_for_president,
        ),
        (
            "Artículos modificados por presidencia",
            "articulos_por_presidente.svg",
            articulos_por_presidente,
            label_for_president,
        ),
        (
            "Líneas nuevas o modificadas por presidencia",
            "lineas_por_presidente.svg",
            lineas_por_presidente,
            label_for_president,
        ),
        (
            "Veces que ha sido reformado cada artículo",
            "reformas_por_articulo.svg",
            reformas_por_articulo,
            article_label,
        ),
    ]

    for title, filename, counter, label_fn in charts:
        labels = [label_fn(name) for name in counter]
        values = list(counter.values())
        svg = render_bar_chart(title, labels, values)
        destination = OUTPUT_DIR / filename
        destination.write_text(svg, encoding="utf-8")
        print(f"Generado {destination}")


if __name__ == "__main__":
    main()
