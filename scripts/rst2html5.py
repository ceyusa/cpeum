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

"""A minimal front end to the Docutils Publisher, producing HTML5 documents."""

import json
import logging
import re
import subprocess
import unicodedata
from pathlib import Path

from chevron import render
from docutils import nodes
from docutils.core import default_description, publish_cmdline
from docutils.parsers.rst import Parser, directives
from docutils.parsers.rst.directives import misc
from docutils.writers.html5_polyglot import HTMLTranslator, Writer

DESCRIPTION = "Generador HTML5 de la CPEUM" + default_description

logger = logging.getLogger(__name__)

# Datos y plantillas del "chrome" del sitio, compartidos con
# scripts/generar_reformas.js (véase templates/site.json). El render se hace
# con Mustache (chevron) usando el contexto de cada página.
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def _load_site_data() -> dict:
    """Carga templates/site.json con los datos del sitio."""
    with (_TEMPLATES_DIR / "site.json").open(encoding="utf-8") as handle:
        return json.load(handle)


SITE = _load_site_data()
GITHUB_URL = SITE["github_url"]

_BANNER_TEMPLATE = (_TEMPLATES_DIR / "banner.mustache").read_text(encoding="utf-8")
_HEAD_META_TEMPLATE = (_TEMPLATES_DIR / "head_meta.mustache").read_text(
    encoding="utf-8"
)

# Spanish month names (lowercase) mapped to their ISO 8601 numeric value.

# Path to the decretos directory
_DECRETOS_ROOT = Path(__file__).resolve().parent.parent

# Ruta del catálogo de decretos, relativa a este script, usado por
# scripts/generar_reformas.js para generar las páginas de diffs.
_DECRETOS_JSON = _DECRETOS_ROOT / "html" / "decretos.json"

SPANISH_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def _normalize_text(text: str) -> str:
    """Normaliza un texto para comparar títulos de decretos (ignora
    mayúsculas, acentos y espacios/puntuación). Imita normalizeText()."""
    return (
        unicodedata.normalize("NFD", text or "")
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
        .replace(" ", "")
    )


def _load_decretos() -> list[dict]:
    """Carga decretos.json y devuelve la lista ordenada por número.

    Devuelve una lista vacía si el archivo no existe o no es válido.
    """
    try:
        with _DECRETOS_JSON.open(encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError) as exc:
        logger.warning("No se pudo cargar %s: %s", _DECRETOS_JSON, exc)
        return []
    return sorted(raw, key=lambda d: d.get("numero", 0))


def _build_decreto_index() -> tuple[dict[str, list[dict]], dict[str, dict]]:
    """Construye los índices de decretos por fecha y por título.

    Devuelve una tupla ((por_fecha, por_titulo)) para el emparejamiento
    de los commits con su decreto correspondiente.
    """
    por_fecha: dict[str, list[dict]] = {}
    por_titulo: dict[str, dict] = {}
    for decreto in _load_decretos():
        publicacion = decreto.get("publicacion")
        if publicacion:
            if publicacion not in por_fecha:
                por_fecha[publicacion] = []
            por_fecha[publicacion].append(decreto)
        titulo = _normalize_text(decreto.get("decreto", ""))
        if titulo and titulo not in por_titulo:
            por_titulo[titulo] = decreto
    return por_fecha, por_titulo


_DECRETO_INDEX: dict = {}


def _match_decreto_numero(iso: str | None, decreto: str) -> int | None:
    """Devuelve el número del decreto al que corresponde un commit.

    El emparejamiento imita a generar_reformas.js: primero por fecha de
    publicación (DOF) y, si no coincide, por el título del decreto.
    """
    if "_value" not in _DECRETO_INDEX:
        _DECRETO_INDEX["_value"] = _build_decreto_index()
    por_fecha, por_titulo = _DECRETO_INDEX["_value"]

    titulo = _normalize_text(decreto)

    if iso and iso in por_fecha:
        grupo = por_fecha[iso]
        if grupo:
            coincidencia = next(
                (d for d in grupo if _normalize_text(d.get("decreto", "")) == titulo),
                None,
            )
            return (coincidencia or grupo[0]).get("numero")

    d = por_titulo.get(titulo)
    return d.get("numero") if d else None


class IncludeWithSection(misc.Include):
    """Custom include directive handler."""

    _git_root_cache: str | None = None

    def run(self) -> list[nodes.Node]:
        """Process the include directive with section wrapping."""
        source_dir = Path(self.state.document.current_source).parent
        filename = self.arguments[0]
        base_name = Path(filename).stem

        # if Transitorio go as normal include
        if base_name.startswith("T"):
            self.arguments[0] = filename
            return super().run()

        # Update the argument to use the resolved path
        self.arguments[0] = filename

        # custom parser
        self.options["parser"] = Parser
        # Get the result from the parent class
        result = super().run()
        # delete custom parser
        del self.options["parser"]
        # Create a section node to wrap the included content
        section = nodes.section(classes=["articulo"])
        section["ids"].append(base_name)

        aside = None
        # Get git commit history for the included file
        git_fn = source_dir / self.arguments[0]
        git_history = self._parse_git_history(str(git_fn))
        if git_history:
            aside = nodes.container(classes=["git-history"])
            aside["git-history"] = git_history
            aside["git-article"] = base_name

        # Move all the result nodes into the section
        for node in result:
            section.append(node)

        # Add the git-history aside at the end of the section
        if aside is not None:
            section.append(aside)

        return [section]

    def _get_git_root(self, filename: str) -> str:
        """Ensure we operate from the git repository root. Result is cached."""
        if self._git_root_cache is not None:
            return self._git_root_cache
        file_dir = Path(filename).parent
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                cwd=str(file_dir),
                check=True,
            )
            IncludeWithSection._git_root_cache = result.stdout.strip()
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ) as e:
            logger.warning("Could not determine git root from %s: %s", filename, e)
            IncludeWithSection._git_root_cache = str(file_dir)
        return self._git_root_cache

    def _get_commit_blocks(self, git_root: str, rel_filename: str) -> list[str]:
        """Run git log filtered by 'Artículo' (y variantes) and return raw commit blocks."""
        try:
            result = subprocess.run(
                [
                    "git",
                    "log",
                    "--grep",
                    "Artículo",
                    "--grep",
                    "Articulo",
                    "--format=%H%n%n%b%n---END-COMMIT---",
                    "--",
                    rel_filename,
                ],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=git_root,
                check=True,
            )
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ) as e:
            logger.warning("Could not get git history for %s: %s", rel_filename, e)
            return []

        return result.stdout.split("---END-COMMIT---")

    def _parse_git_history(self, filename: str) -> list[dict[str, str]]:
        """Parse git log to extract relevant commit information."""
        abs_filename = str(Path(filename).resolve())
        git_root = self._get_git_root(abs_filename)
        rel_filename = str(Path(abs_filename).relative_to(git_root))

        commits = []

        for block in self._get_commit_blocks(git_root, rel_filename):
            commit_info = self._parse_commit_block(block)
            if commit_info:
                commits.append(commit_info)
        return commits

    @staticmethod
    def _parse_commit_block(block: str) -> dict[str, str] | None:
        """Parse a single commit block into a structured dict."""
        lines = [i.replace("\n", " ") for i in block.strip().split("\n\n")]
        if not lines:
            return None

        try:
            commit_hash = lines[0].strip()

            # Validate commit hash (supports SHA-1 and SHA-256)
            if not re.match(r"^[a-f0-9]{40,}$", commit_hash):
                return None

            body = "\n".join(lines[1:]).strip()

            # Match "Publicado en el Diario Oficial de la Federación [el] [date]"
            pub_pattern = (
                r"Publicado\s+en\s+el\s+Diario\s+Oficial\s+de\s+la\s+"
                r"Federación\s+(?:el\s+)?([^\.\n\r\t]+?)\s*(?:\.|$|\n|http)"
            )

            pub_date = None
            match = re.search(pub_pattern, body, re.IGNORECASE)
            if match:
                pub_date = match.group(1).strip()
                pub_date = re.sub(r"[,\s\.]*$", "", pub_date)
                pub_date = re.sub(r"\s*https?://\S*$", "", pub_date)

            # If no specific publication date found in patterns, try
            # to find any date in the body
            if not pub_date:
                date_pattern = r"(\d{1,2}\s+de\s+[A-Za-z]+\s+(?:de|del)\s+\d{4})"
                match = re.search(date_pattern, body)
                if match:
                    pub_date = match.group(1)

            if not pub_date:
                raise ValueError(
                    f"No se encontró fecha de publicación en el commit {commit_hash[:8]}"
                )

            summary_pattern = (
                r"(?m)(?:DECRETO|REFORMA|REFORMAS|DECLARATORIA|LEY|)[ ]+.+"
            )
            match = re.search(summary_pattern, body, re.IGNORECASE)
            if not match:
                raise ValueError(
                    "No se encontró el resumen del decreto (DECRETO, REFORMA, "
                    f"REFORMAS, DECLARATORIA o LEY) en el commit {commit_hash[:8]}: {body}"
                )
            decreto = match.group(0).strip()
            iso = pub_date_to_iso(pub_date)

            return {
                "hash": commit_hash[:8],
                "pub_date": pub_date,
                "iso": iso,
                "decreto": decreto,
            }
        except (IndexError, AttributeError, ValueError) as e:
            logger.warning("Skipping malformed commit block: %s", e)
            return None


def pub_date_to_iso(pub_date: str) -> str | None:
    """Convert a Spanish pub_date to an ISO 8601 date string.

    Handles the inconsistent wording found in the federal register, for
    example "10 de junio del 2011", "1ro de julio de 1994",
    "13 septiembre de 1999", "10 de julio 2015" or
    "26 de marzo del año 2019". Returns None when it cannot be parsed.
    """
    if not pub_date or pub_date == "Sin fecha":
        return None

    match = re.fullmatch(
        r"(\d{1,2})(?:[roº]+)?\.?"
        r"(?:\s+de)?\s+([A-Za-záéíóúñü]+)"
        r"\s+(?:(?:de|del)\s+)?(?:año\s+)?(\d{3,4})",
        pub_date.strip(),
        re.IGNORECASE,
    )
    if not match:
        return None

    day, month_name, year = match.group(1), match.group(2), match.group(3)
    month = SPANISH_MONTHS.get(month_name.lower())
    if month is None:
        return None

    year = int(year)
    day = int(day)
    if not (1 <= day <= 31) or year < 1900:
        return None

    return f"{year:04d}-{month:02d}-{day:02d}"


class CustomHTMLTranslator(HTMLTranslator):
    """Custom HTML translator with git-history sidebar support."""

    def visit_section(self, node: nodes.section) -> None:
        """Render sections as HTML5 <section> tags."""
        self.section_level += 1
        self.body.append(self.starttag(node, "section"))

    def depart_section(self, _: nodes.section) -> None:
        """Close the <section> tag."""
        self.section_level -= 1
        self.body.append("</section>\n")

    @staticmethod
    def _is_git_history(node: nodes.container) -> bool:
        """Check if a container node holds git-history data."""
        return (
            "git-history" in node.attributes
            and "classes" in node.attributes
            and "git-history" in node["classes"]
            and node.get("git-history")
        )

    def visit_container(self, node: nodes.container) -> None:
        """Render git-history containers as HTML aside with commit list."""
        if self._is_git_history(node):
            self.body.append('<aside class="sidebar git-history">\n')

            article = node.get("git-article")
            if article:
                number = article.lstrip("0") or "0"
                self.body.append(
                    f'<p class="sidebar-title">Reformas al artículo {number}</p>\n'
                )

            commits = node["git-history"]
            if commits:
                self.body.append("<ul>\n")
                for commit in commits:
                    numero = _match_decreto_numero(commit.get("iso"), commit["decreto"])
                    if numero is not None:
                        url = f'href="decretos/{numero}.html"'
                    else:
                        commit_hash = commit["hash"]
                        url = (
                            f'rel="external noreferrer" target="_blank"'
                            f'href="{GITHUB_URL}/commit/{commit_hash}"'
                        )
                    decreto = commit["decreto"].strip()
                    datetime = pub_date_to_iso(commit["pub_date"])
                    time_attr = f' datetime="{datetime}"' if datetime else ""
                    self.body.append(
                        f'<li class="git-commit"><a {url}>'
                        f"<time{time_attr}>{commit['pub_date']}</time></a>"
                        f'<p class="decreto">{decreto}</p></li>\n',
                    )
                self.body.append("</ul>\n")
        else:
            HTMLTranslator.visit_container(self, node)

    def depart_container(self, node: nodes.container) -> None:
        """Close the git-history aside or delegate to parent."""
        if self._is_git_history(node):
            self.body.append("</aside>\n")
        else:
            HTMLTranslator.depart_container(self, node)

    def visit_document(self, node) -> None:
        """Add a fixed top banner right after <body>."""
        super().visit_document(node)
        self.body_prefix.append(
            render(
                _BANNER_TEMPLATE,
                {
                    **SITE,
                    "cpeum_href": "index.html",
                    "decretos_href": "decretos/index.html",
                    "estadisticas_href": "estadisticas.html",
                    "acerca_href": "acercade.html",
                },
            )
        )

    def depart_document(self, node) -> None:
        """Inject site header, metadata, and translate footer to Spanish."""
        super().depart_document(node)
        # Translate footer
        self.body_suffix = [
            line.replace("Generated on:", "Generado el") for line in self.body_suffix
        ]
        # Add responsive hamburger menu script
        script = (
            "<script>\n"
            "(function () {\n"
            "  var toggle = document.getElementById('menu-toggle');\n"
            "  var contents = document.querySelector('nav.contents');\n"
            "  if (!toggle || !contents) { return; }\n"
            "  function setOpen(open) {\n"
            "    document.body.classList.toggle('menu-open', open);\n"
            "    toggle.setAttribute('aria-expanded', open);\n"
            "    toggle.setAttribute('aria-label', open ? 'Cerrar menú' : 'Abrir menú');\n"
            "  }\n"
            "  toggle.addEventListener('click', function () {\n"
            "    setOpen(!document.body.classList.contains('menu-open'));\n"
            "  });\n"
            "  contents.addEventListener('click', function (e) {\n"
            "    if (e.target.closest('a')) { setOpen(false); }\n"
            "  });\n"
            "  document.addEventListener('keydown', function (e) {\n"
            "    if (e.key === 'Escape') { setOpen(false); }\n"
            "  });\n"
            "  window.addEventListener('resize', function () {\n"
            "    if (window.innerWidth > 768) { setOpen(false); }\n"
            "  });\n"
            "})();\n"
            "</script>\n"
        )
        # Insert before the closing </body></html> tags so the script stays
        # inside the document body.
        for index, line in enumerate(self.body_suffix):
            if "</body>" in line:
                self.body_suffix.insert(index, script)
                break
        # Add resource links and metadata to <head> from the shared template.
        self.head.extend(
            [
                render(
                    _HEAD_META_TEMPLATE,
                    {
                        **SITE,
                        "og_title": "Constitución Política de los Estados "
                        "Unidos Mexicanos",
                        "og_description": SITE["description"],
                        "og_type": "website",
                        "og_url": SITE["site_url"],
                        "twitter_title": "Constitución Política de los Estados "
                        "Unidos Mexicanos",
                        "canonical": SITE["site_url"],
                        "icon_base": "",
                    },
                )
            ]
        )

    def unimplemented_visit(self, node):
        logger.warning("Unimplemented visit for node type: %s", type(node).__name__)


class CustomHTML5Writer(Writer):
    """Custom HTML5 writer using our translator."""

    def __init__(self) -> None:
        """Initialize writer with custom translator class."""
        Writer.__init__(self)
        self.translator_class = CustomHTMLTranslator


# Register our custom directive
directives.register_directive("include", IncludeWithSection)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

overrides = {
    "stylesheet_dirs": [str(_DECRETOS_ROOT)],
}

publish_cmdline(
    writer=CustomHTML5Writer(), description=DESCRIPTION, settings_overrides=overrides
)
