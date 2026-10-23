# :Copyright: © 2026 Víctor Jáquez.
# :License: Released under the terms of the `2-Clause BSD license`_, in short:
#
#    Copying and distribution of this file, with or without modification,
#    are permitted in any medium without royalty provided the copyright
#    notice and this notice are preserved.
#    This file is offered as-is, without any warranty.
#
# .. _2-Clause BSD license: https://opensource.org/licenses/BSD-2-Clause

"""Índice compartido de decretos.

Concentra la lectura de ``html/decretos.json`` y el emparejamiento entre
los commits de reforma y su decreto, para que la trazabilidad
(``generar_blame.py``) y el sidebar del texto vigente (``rst2html5.py``)
apliquen exactamente las mismas reglas.
"""

from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

Indice = tuple[dict[str, list[dict]], dict[str, dict]]


def normalizar(texto: str) -> str:
    """Normaliza un título para compararlo (sin acentos ni puntuación)."""
    sin_acentos = "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caracter) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", "", sin_acentos.lower())


def leer_decretos(ruta: Path) -> list[dict]:
    """Lee y devuelve el catálogo de decretos en formato JSON."""
    return json.loads(ruta.read_text(encoding="utf-8"))


def construir_indice(decretos: list[dict]) -> Indice:
    """Indexa los decretos por fecha de publicación y por título."""
    por_fecha: dict[str, list[dict]] = {}
    por_titulo: dict[str, dict] = {}
    ordenados = sorted(decretos, key=lambda decreto: decreto.get("numero") or 0)
    for decreto in ordenados:
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


def numero_decreto(iso: str | None, titulo: str, indice: Indice) -> int | None:
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
