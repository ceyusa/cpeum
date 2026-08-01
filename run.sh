#!/usr/bin/env bash
set -euo pipefail

##########
# Compilar y servir el sitio CPEUM localmente
##########

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="${SCRIPT_DIR}/scripts"
HTML_DIR="${SCRIPT_DIR}/html"

# Paso 1: Regenerar el JSON de decretos si tiene más de un mes
DECRETOS_JSON="${HTML_DIR}/decretos.json"
LIMITE=$(date -d "-1 month" +%s)
if [ -f "${DECRETOS_JSON}" ]; then
    CREACION=$(stat -c %W "${DECRETOS_JSON}")
    if [ "${CREACION}" -le "${LIMITE}" ]; then
        echo "==> Regenerando decretos.json (tiene más de un mes)..."
        uv run "${SCRIPTS_DIR}/extraer_decretos.py" "${DECRETOS_JSON}"
    fi
else
    echo "==> Generando decretos.json (no existe)..."
    uv run "${SCRIPTS_DIR}/extraer_decretos.py" "${DECRETOS_JSON}"
fi

# Paso 2: Compilar el sitio
echo "==> Compilando sitio..."
cd "${SCRIPT_DIR}/CPEUM"
uv run "${SCRIPTS_DIR}/rst2html5.py" toc.rst "${HTML_DIR}/index.html"
uv run "${SCRIPTS_DIR}/rst2html5.py" acercade.rst "${HTML_DIR}/acercade.html"

# Paso 3: Generar los diffs de las reformas y su índice
echo "==> Generando reformas..."
cd "${SCRIPT_DIR}"
node "${SCRIPTS_DIR}/generar_reformas.js"

# Paso 4: Iniciar servidor HTTP en segundo plano
echo "==> Iniciando servidor HTTP en puerto 8000..."
cd "${HTML_DIR}"
python3 -m http.server 8000 &
SERVER_PID=$!
echo "==> PID del servidor: ${SERVER_PID}"

# Limpiar al salir
trap 'echo "==> Deteniendo servidor..."; kill ${SERVER_PID} 2>/dev/null' EXIT

# Paso 5: Abrir navegador
sleep 0.5
xdg-open http://127.0.0.1:8000

# Esperar al proceso del servidor
wait "${SERVER_PID}"
