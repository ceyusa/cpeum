#!/usr/bin/env python3
# :Copyright: © 2025 Víctor Jáquez.
# :License: Released under the terms of the `2-Clause BSD license`_, in short:
#
#    Copying and distribution of this file, with or without modification,
#    are permitted in any medium without royalty provided the copyright
#    notice and this notice are preserved.
#    This file is offered as-is, without any warranty.
#
# .. _2-Clause BSD license: https://opensource.org/licenses/BSD-2-Clause

"""Genera el `sitemap.xml` del sitio web de la CPEUM en un directorio dado."""

import argparse
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

REPO_ROOT = Path(__file__).resolve().parent.parent
SITEMAP_URL = "https://cpeum.mx/"
SITEMAP_FILENAME = "sitemap.xml"
SITEMAP_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
)
SITEMAP_FOOTER = "</urlset>\n"


def _last_modified() -> str:
    """Devuelve la fecha del último cambio del sitio o de sus datos."""
    fechas: list[date] = []
    for repositorio in (REPO_ROOT, REPO_ROOT / "cpeum-decretos"):
        try:
            salida = subprocess.run(
                ["git", "-C", str(repositorio), "log", "-1", "--format=%cI"],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            ).stdout.strip()
            if salida:
                fechas.append(datetime.fromisoformat(salida).date())
        except (OSError, ValueError, subprocess.SubprocessError):
            continue
    if fechas:
        return max(fechas).isoformat()
    return datetime.now(timezone.utc).date().isoformat()


def _urls(output_dir: Path) -> list[str]:
    """Lista las URLs de las páginas HTML generadas, en orden estable."""
    urls = []
    for ruta in sorted(output_dir.rglob("*.html")):
        relativa = ruta.relative_to(output_dir).as_posix()
        sufijo = "" if relativa == "index.html" else relativa
        urls.append(f"{SITEMAP_URL}{sufijo}")
    return urls or [SITEMAP_URL]


def _entry(url: str, lastmod: str) -> str:
    """Devuelve la entrada ``<url>`` de una página."""
    return (
        "  <url>\n"
        f"    <loc>{escape(url)}</loc>\n"
        f"    <lastmod>{lastmod}</lastmod>\n"
        "    <changefreq>monthly</changefreq>\n"
        "  </url>\n"
    )


def generate_sitemap(output_dir: Path) -> Path:
    """Escribe el sitemap en `output_dir` y devuelve la ruta generada."""
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / SITEMAP_FILENAME
    lastmod = _last_modified()
    contenido = (
        SITEMAP_HEADER
        + "".join(_entry(url, lastmod) for url in _urls(output_dir))
        + SITEMAP_FOOTER
    )
    destination.write_text(contenido, encoding="utf-8")
    return destination


def main() -> None:
    """Punto de entrada principal del script."""
    parser = argparse.ArgumentParser(description="Genera el sitemap.xml del sitio.")
    parser.add_argument(
        "output_dir",
        type=Path,
        help="directorio de salida donde se escribe sitemap.xml",
    )
    args = parser.parse_args()

    destination = generate_sitemap(args.output_dir)
    print(f"Generado {destination}")


if __name__ == "__main__":
    main()
