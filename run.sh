#!/usr/bin/env bash
set -euo pipefail

##########
# Compilar y servir el sitio CPEUM localmente
##########

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="${SCRIPT_DIR}/scripts"
HTML_DIR="${SCRIPT_DIR}/html"

# Paso 1: Compilar el sitio
echo "==> Compilando sitio..."
cd "${SCRIPT_DIR}/CPEUM"
uv run "${SCRIPTS_DIR}/rst2html5.py" toc.rst "${HTML_DIR}/index.html"
uv run "${SCRIPTS_DIR}/rst2html5.py" acercade.rst "${HTML_DIR}/acercade.html"

# Paso 2: Iniciar servidor HTTP en segundo plano
echo "==> Iniciando servidor HTTP en puerto 8000..."
cd "${HTML_DIR}"
python3 -m http.server 8000 &
SERVER_PID=$!
echo "==> PID del servidor: ${SERVER_PID}"

# Limpiar al salir
trap 'echo "==> Deteniendo servidor..."; kill ${SERVER_PID} 2>/dev/null' EXIT

# Paso 3: Abrir navegador
sleep 0.5
xdg-open http://127.0.0.1:8000

# Esperar al proceso del servidor
wait "${SERVER_PID}"
