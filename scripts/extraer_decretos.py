#!/usr/bin/env python3
"""Extrae los decretos de reformas constitucionales de la página cronológica de
la Cámara de Diputados y los guarda como JSON.

Fuente: https://www.diputados.gob.mx/LeyesBiblio/ref/cpeum_crono.htm
"""

import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import urlopen

from bs4 import BeautifulSoup

BASE = "https://www.diputados.gob.mx/LeyesBiblio/ref/"
URL = "https://www.diputados.gob.mx/LeyesBiblio/ref/cpeum_crono.htm"


CAMPOS = (
    "numero",
    "decreto",
    "resumen",
    "proceso_legislativo",
    "publicacion",
    "word",
    "pdf",
    "imagen",
)
NUM_ESPERADO = 284


def fecha_iso(fecha):
    """Convierte una fecha `dd/mm/aaaa` en ISO 8601 (`aaaa-mm-dd`)."""
    dia, mes, anio = fecha.split("/")
    return f"{int(anio):04d}-{int(mes):02d}-{int(dia):02d}"


def limpiar(texto):
    """Une los saltos de línea y normaliza los espacios en blanco."""
    texto = texto.replace("\r", " ")
    texto = texto.replace("\n", " ")
    # quitar los espacios que quedan al rellenar las líneas del HTML
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def parrafos_de_decreto(celda):
    """Devuelve los párrafos de texto de un decreto: el título y el resumen.

    Se descartan los párrafos vacíos y los metadatos ("Nuevo", "Nota:" y los
    enlaces de navegación como "| Proceso Legislativo |" o "Fe de erratas").
    El primer párrafo devuelto es el título del decreto; el resto, su resumen.
    """
    parrafos = []
    for p in celda.find_all("p", recursive=True):
        texto = limpiar(p.get_text(" ", strip=True))
        if not texto:
            continue
        if texto == "Nuevo" or texto.startswith("Nota:") or "|" in texto:
            continue
        parrafos.append(texto)
    return parrafos


def main():
    """Extrae los decretos del HTML descargado y los guarda como JSON validado."""
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("html/decretos.json")

    try:
        with urlopen(URL) as respuesta:
            # La página está codificada en latin-1
            html = io.TextIOWrapper(respuesta, encoding="latin-1").read()
    except OSError as error:
        print(f"No se pudo descargar {URL}: {error}")
        return 1

    soup = BeautifulSoup(html, "lxml")
    filas = soup.find_all("tr")

    decretos = []
    for tr in filas:
        fila = decreto_de_celda(tr)
        if fila is not None:
            decretos.append(fila)

    validar(decretos)

    salida = json.dumps(decretos, ensure_ascii=False, indent=2) + "\n"
    if destino.name == "-":
        print(salida, end="")
    else:
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(salida, encoding="utf-8")
        print(f"Se extrajeron {len(decretos)} decretos en {destino}.")
    return 0


def decreto_de_celda(fila):
    """Convierte una fila `<tr>` en el objeto JSON de un decreto.

    Devuelve `None` si la fila no corresponde a un decreto (cabecera, origen o
    pie de página).
    """
    celdas = fila.find_all("td")
    if len(celdas) != 4:
        return None

    numero = limpiar(celdas[0].get_text(" ", strip=True))
    if not numero.isdigit():
        # fila de cabecera (No. / Decreto / Publicación)
        return None

    parrafos = parrafos_de_decreto(celdas[1])
    proceso_legislativo = None
    for a in celdas[1].find_all("a", href=True):
        if "Proceso" in a.get_text(" ", strip=True):
            proceso_legislativo = urljoin(BASE, a["href"])
            break
    publicacion = limpiar(celdas[2].get_text(" ", strip=True))

    enlaces = {"Imagen": None, "PDF": None, "Word": None}
    for a in celdas[3].find_all("a", href=True):
        etiqueta = a.get_text(" ", strip=True).strip()
        if etiqueta in enlaces:
            href = a["href"]
            if href.startswith("dof/"):
                enlaces[etiqueta] = BASE + href

    return {
        "numero": int(numero),
        "decreto": parrafos[0],
        "resumen": " ".join(parrafos[1:]) or None,
        "proceso_legislativo": proceso_legislativo,
        "publicacion": fecha_iso(publicacion),
        "word": enlaces["Word"],
        "pdf": enlaces["PDF"],
        "imagen": enlaces["Imagen"],
    }


def validar(datos):
    """Valida los decretos: número de elementos, consecutividad, campos y fechas."""
    if len(datos) != NUM_ESPERADO:
        raise SystemExit(
            f"Error: el JSON tiene {len(datos)} decretos, se esperaban {NUM_ESPERADO}."
        )
    numeros = sorted(x["numero"] for x in datos)
    esperados = list(range(1, NUM_ESPERADO + 1))
    if numeros != esperados:
        faltan = sorted(set(esperados) - set(numeros))
        raise SystemExit(
            f"Error: los números no son consecutivos 1..{NUM_ESPERADO}. "
            f"Faltan: {faltan}."
        )
    for x in datos:
        faltan = [c for c in CAMPOS if c not in x]
        if faltan:
            raise SystemExit(f"Faltan campos {faltan} en el decreto {x.get('numero')}.")
        # ValueError si la fecha no es ISO 8601 válida
        datetime.fromisoformat(x["publicacion"])


if __name__ == "__main__":
    raise SystemExit(main())
