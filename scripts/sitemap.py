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
from datetime import datetime, timezone
from pathlib import Path

SITEMAP_URL = "https://cpeum.mx/"
SITEMAP_FILENAME = "sitemap.xml"
SITEMAP_TEMPLATE = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    "  <url>\n"
    f"    <loc>{SITEMAP_URL}</loc>\n"
    "    <lastmod>{lastmod}</lastmod>\n"
    "    <changefreq>monthly</changefreq>\n"
    "    <priority>1.0</priority>\n"
    "  </url>\n"
    "</urlset>\n"
)


def generate_sitemap(output_dir: Path) -> Path:
    """Escribe el sitemap en `output_dir` y devuelve la ruta generada."""
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / SITEMAP_FILENAME
    lastmod = datetime.now(timezone.utc).date().isoformat()
    destination.write_text(SITEMAP_TEMPLATE.format(lastmod=lastmod), encoding="utf-8")
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
