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

"""Script para publicar automáticamente en BlueSky cuando un PR fusionado
contiene cambios en artículos de la CPEUM."""

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

BSKY_PDS_URL = "https://bsky.social"
POST_CHAR_LIMIT = 300


def run_git(*args: str) -> str:
    """Ejecuta un comando git y devuelve la salida estándar."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def check_document_changes(since: str = "HEAD^") -> bool:
    """Comprueba si los commits desde `since` contienen cambios en artículos."""
    range_ = f"{since}..HEAD"
    subjects = run_git("log", "--format=%s", range_).casefold()
    has_keyword = "artículo" in subjects or "articulo" in subjects
    files = run_git("diff", "--name-only", range_).splitlines()
    has_docs = any(
        line.startswith("cpeum-decretos/CPEUM/") and line.endswith(".rst")
        for line in files
    )
    return has_keyword and has_docs


def get_commit_description() -> str:
    """Extrae el segundo párrafo del mensaje del último commit."""
    full_message = run_git("log", "-1", "--format=%B", "HEAD")

    # Split on blank lines to get paragraphs
    paragraphs = full_message.strip().split("\n\n")
    # First "paragraph" is the subject line and its continuation lines
    # Second paragraph is what we want (the description)
    if len(paragraphs) < 2:
        return ""

    desc = paragraphs[1].strip()
    # Replace newlines with spaces to get a single line
    return " ".join(desc.splitlines())


def _url_de_evento() -> str:
    """Extrae la URL del PR desde el evento de GitHub, si existe."""
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not (event_path and os.path.isfile(event_path)):
        return ""
    with open(event_path, encoding="utf-8") as handle:
        event = json.load(handle)
    return (
        event.get("pull_request", {}).get("_links", {}).get("html", {}).get("href", "")
    )


def build_post_text(desc: str, url: str) -> str:
    """Construye el texto del post con la descripción truncada y la URL."""
    desc_budget = max(POST_CHAR_LIMIT - len(url) - 2, 0)
    truncated = desc[:desc_budget]
    return f"{truncated}\n\n{url}"


def _post(xrpc: str, payload: dict, token: str | None = None) -> dict:
    """Envía una petición POST a la API XRPC de BlueSky."""
    request = urllib.request.Request(
        f"{BSKY_PDS_URL}/xrpc/{xrpc}",
        data=json.dumps(payload).encode(),
        method="POST",
    )
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


def bsky_login(handle: str, app_password: str) -> dict:
    """Inicia sesión en BlueSky y devuelve la sesión."""
    return _post(
        "com.atproto.server.createSession",
        {"identifier": handle, "password": app_password},
    )


def bsky_create_post(session: dict, text: str) -> dict:
    """Crea un post en BlueSky usando la sesión autenticada."""
    return _post(
        "com.atproto.repo.createRecord",
        {
            "repo": session["did"],
            "collection": "app.bsky.feed.post",
            "record": {
                "$type": "app.bsky.feed.post",
                "text": text,
                "createdAt": datetime.now(timezone.utc).isoformat(),
            },
        },
        token=session["accessJwt"],
    )


def main() -> None:
    """Punto de entrada principal del script."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra el post sin publicarlo",
    )
    parser.add_argument(
        "--since",
        default=None,
        metavar="COMMIT",
        help="Comprueba los commits desde este commit (en lugar de solo HEAD)",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="URL del PR (por defecto se usa GITHUB_EVENT_PATH para extraerla)",
    )
    args = parser.parse_args()

    if not check_document_changes(args.since or "HEAD^"):
        print("Sin cambios en artículos — omitiendo publicación.")
        return

    desc = get_commit_description()
    if not desc:
        print("Sin descripción en el commit — omitiendo publicación.")
        return

    pr_url = args.url or os.environ.get("PR_URL") or _url_de_evento()
    if not pr_url:
        print("No se pudo determinar la URL del PR — use --url")
        sys.exit(1)

    post_text = build_post_text(desc, pr_url)

    if args.dry_run:
        print("=== DRY RUN ===")
        print(post_text)
        print("===============")
        return

    handle = os.environ.get("BSKY_USERNAME", "")
    app_password = os.environ.get("BSKY_APP_PASSWORD", "")
    if not handle or not app_password:
        print("Falta BSKY_USERNAME o BSKY_APP_PASSWORD en el entorno.")
        sys.exit(1)

    session = bsky_login(handle, app_password)
    result = bsky_create_post(session, post_text)
    print(f"Publicado: {result.get('uri', 'desconocido')}")


if __name__ == "__main__":
    main()
