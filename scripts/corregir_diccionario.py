#!/usr/bin/env python3
"""Limpia y optimiza el diccionario personal es-local.dic.

Realiza las siguientes operaciones:
1. Conserva la primera línea (header)
2. Ordena alfabéticamente case-insensitive
3. Elimina duplicados case-insensitive
4. Busca cada palabra en content/**.md y elimina las no usadas
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

# Regex para extraer tokens alfanuméricos de los archivos rst
WORD_RE = re.compile(r"\b\w+\b")

# Header esperado al inicio del diccionario
HEADER_RE = re.compile(r"^personal_ws-1\.1 es (\d+) utf-8$")


def extraer_palabras_de_rst() -> set[str]:
    """Extrae todas las palabras de content/**.md y las devuelve en lowercase.

    Recorre todos los archivos .md bajo content/, extrae tokens alfanuméricos
    con regex \\b\\w+\\b y los acumula en un set en minúsculas para búsqueda rápida.

    Returns:
        Conjunto de palabras en minúsculas encontradas en los rst.
    """
    palabras: set[str] = set()
    content_dir = PROJECT_ROOT
    archivos = sorted(content_dir.glob(CONTENT_GLOB))

    for archivo in archivos:
        try:
            texto = archivo.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        for match in WORD_RE.finditer(texto):
            palabras.add(match.group().lower())

    return palabras


def leer_diccionario(ruta: Path) -> tuple[str, list[str]]:
    """Lee el archivo de diccionario y separa header de palabras.

    Args:
        ruta: Ruta al archivo es-local.dic.

    Returns:
        Tupla (header, lista_de_palabras).
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

    palabras = [line for line in lineas[1:] if line.strip()]
    return header, palabras


def deduplicar_case_insensitive(palabras: list[str]) -> list[str]:
    """Elimina duplicados case-insensitive y convierte a minúsculas.

    Args:
        palabras: Lista de palabras del diccionario.

    Returns:
        Lista sin duplicados case-insensitive, todas en minúsculas.
    """
    vistos: set[str] = set()
    resultado: list[str] = []

    for palabra in palabras:
        clave = palabra.lower()
        if clave not in vistos:
            vistos.add(clave)
            resultado.append(clave)

    return resultado


def filtrar_palabras_usadas(palabras: list[str], palabras_rst: set[str]) -> list[str]:
    """Filtra las palabras que no aparecen en los archivos rst.

    Para palabras sin caracteres especiales (solo alfanuméricas), verifica
    que la palabra aparezca como subcadena dentro de algún token extraído de
    los rst (para cubrir casos como 'pvfs' dentro de 'pvfs2').
    Para palabras con caracteres especiales (guiones, puntos, etc.), busca
    literalmente con git grep -F (sin -w, para permitir coincidencias
    parciales).

    Args:
        palabras: Lista de palabras del diccionario.
        palabras_rst: Conjunto de palabras en minúsculas extraídas de los
            archivos rst.

    Returns:
        Lista de palabras que sí aparecen en los rst (se conservan).
    """
    import subprocess  # pylint: disable=import-outside-toplevel

    resultado: list[str] = []
    for palabra in palabras:
        # Si es puramente alfanumérica (posiblemente con guiones), verificar
        # que aparezca como subcadena en algún token de los rst.
        # Así 'pvfs' matchea con 'pvfs2', 'covid' con 'covid19', etc.
        if palabra.replace("-", "").isalnum():
            # Solo filtrar palabras de 3+ caracteres para evitar falsos
            # positivos con subcadenas muy cortas ('a', 'in', 'er', etc.)
            if len(palabra) >= 3 and not any(
                palabra in token for token in palabras_rst
            ):
                continue
            resultado.append(palabra)
            continue

        # Para palabras con caracteres especiales (puntos, apóstrofes, etc.)
        # usar git grep literal case-insensitive (-i), sin word boundary
        # para permitir coincidencias parciales (ej. 'dnow' en '3DNow!')
        try:
            proc = subprocess.run(
                [
                    "git",
                    "grep",
                    "-i",
                    "-F",
                    "--",
                    palabra,
                    "--",
                    f"{CONTENT_GLOB}",
                ],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
                timeout=10,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                resultado.append(palabra)
        except (subprocess.TimeoutExpired, OSError):
            # Si falla la búsqueda, conservamos la palabra por seguridad
            resultado.append(palabra)

    return resultado


def main() -> None:
    """Punto de entrada principal."""
    # 1. Leer header y palabras
    print("Leyendo diccionario...")
    _, palabras = leer_diccionario(DICT_PATH)
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

    # 4. Extraer palabras de los rst y filtrar
    print("Extrayendo palabras de los rst...")
    palabras_rst = extraer_palabras_de_rst()
    print(f"  Palabras únicas encontradas: {len(palabras_rst)}")

    # 5. Filtrar: mantener solo las que aparecen en los markdown
    print("Filtrando palabras no usadas...")
    palabras_finales = filtrar_palabras_usadas(palabras_ordenadas, palabras_rst)
    eliminadas = len(palabras_ordenadas) - len(palabras_finales)
    print(f"  Eliminadas {eliminadas} palabras no encontradas en los markdown")

    # 6. Escribir archivo con header actualizado
    print("Escribiendo diccionario...")
    nuevo_header = f"personal_ws-1.1 es {len(palabras_finales)} utf-8"
    with open(DICT_PATH, "w", encoding="utf-8") as fh:
        fh.write(nuevo_header + "\n")
        fh.writelines(palabra + "\n" for palabra in palabras_finales)

    print(f"Listo. Diccionario actualizado: {len(palabras_finales)} palabras.")


if __name__ == "__main__":
    main()
