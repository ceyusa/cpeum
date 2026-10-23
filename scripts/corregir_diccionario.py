#!/usr/bin/env python3
"""Limpia y optimiza el diccionario personal es-local.dic.

Realiza las siguientes operaciones:
1. Conserva la primera línea (header)
2. Ordena alfabéticamente case-insensitive
3. Elimina duplicados case-insensitive
4. Busca cada palabra en CPEUM/*.rst y elimina las no usadas
5. Actualiza el header con el conteo final de palabras
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# --- Constantes ---

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DICT_PATH = PROJECT_ROOT / "es-local.dic"
CONTENT_GLOB = "CPEUM/*.rst"

# Header esperado al inicio del diccionario
HEADER_RE = re.compile(r"^personal_ws-1\.1 es (\d+) utf-8$")


def extraer_texto_de_rst() -> str:
    """Devuelve el texto en minúsculas de todos los archivos rst."""
    textos = []
    for archivo in sorted(PROJECT_ROOT.glob(CONTENT_GLOB)):
        try:
            textos.append(archivo.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
    return "\n".join(textos).lower()


def leer_diccionario(ruta: Path) -> list[str]:
    """Lee el archivo de diccionario y devuelve sus palabras.

    Args:
        ruta: Ruta al archivo es-local.dic.

    Returns:
        Lista de palabras, sin el header ni las líneas vacías.
    """
    if not ruta.exists():
        print(f"Error: {ruta} no existe", file=sys.stderr)
        sys.exit(1)

    with open(ruta, encoding="utf-8") as fh:
        lineas = [line.rstrip("\n") for line in fh]

    if not lineas:
        print(f"Error: {ruta} está vacío", file=sys.stderr)
        sys.exit(1)

    header = lineas[0]
    if not HEADER_RE.match(header):
        print(
            f"Advertencia: la primera línea no coincide con el formato esperado: "
            f"{header!r}",
            file=sys.stderr,
        )

    return [line for line in lineas[1:] if line.strip()]


def deduplicar_case_insensitive(palabras: list[str]) -> list[str]:
    """Elimina duplicados case-insensitive y convierte a minúsculas."""
    return list(dict.fromkeys(palabra.lower() for palabra in palabras))


def filtrar_palabras_usadas(palabras: list[str], corpus: str) -> list[str]:
    """Filtra las palabras que no aparecen en los archivos rst.

    La búsqueda es una subcadena en el texto completo en minúsculas, de modo
    que ``pvfs`` encuentra ``pvfs2`` y las palabras con puntos o guiones se
    buscan literalmente. Las palabras alfanuméricas de menos de tres
    caracteres se conservan para evitar falsos positivos por subcadenas muy
    cortas.

    Args:
        palabras: Lista de palabras del diccionario.
        corpus: Texto en minúsculas de todos los archivos rst.

    Returns:
        Lista de palabras que sí aparecen en los rst (se conservan).
    """
    return [
        palabra
        for palabra in palabras
        if palabra in corpus
        or (len(palabra) < 3 and palabra.replace("-", "").isalnum())
    ]


def main() -> None:
    """Punto de entrada principal."""
    # 1. Leer header y palabras
    print("Leyendo diccionario...")
    palabras = leer_diccionario(DICT_PATH)
    print(f"  Palabras leídas: {len(palabras)}")

    # 2. Deduplicar case-insensitive (y convertir a minúsculas)
    print("Deduplicando (y pasando a minúsculas)...")
    palabras_sin_dupes = deduplicar_case_insensitive(palabras)
    duplicados = len(palabras) - len(palabras_sin_dupes)
    if duplicados:
        print(f"  Eliminados {duplicados} duplicados")

    # 3. Ordenar case-insensitive
    print("Ordenando...")
    palabras_ordenadas = sorted(palabras_sin_dupes, key=str.lower)

    # 4. Extraer el texto de los rst y filtrar
    print("Extrayendo texto de los rst...")
    corpus = extraer_texto_de_rst()

    # 5. Filtrar: mantener solo las que aparecen en los rst
    print("Filtrando palabras no usadas...")
    palabras_finales = filtrar_palabras_usadas(palabras_ordenadas, corpus)
    eliminadas = len(palabras_ordenadas) - len(palabras_finales)
    print(f"  Eliminadas {eliminadas} palabras no encontradas en los rst")

    # 6. Escribir archivo con header actualizado
    print("Escribiendo diccionario...")
    nuevo_header = f"personal_ws-1.1 es {len(palabras_finales)} utf-8"
    with open(DICT_PATH, "w", encoding="utf-8") as fh:
        fh.write(nuevo_header + "\n")
        fh.writelines(palabra + "\n" for palabra in palabras_finales)

    print(f"Listo. Diccionario actualizado: {len(palabras_finales)} palabras.")


if __name__ == "__main__":
    main()
