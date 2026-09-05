#!/usr/bin/env bash
set -euo pipefail

##########
# Compilar y servir el sitio CPEUM localmente
##########

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="${SCRIPT_DIR}/scripts"
HTML_DIR="${SCRIPT_DIR}/html"
DECRETOS_DIR="${SCRIPT_DIR}/cpeum-decretos"
DECRETOS_SCRIPT_DIR="${DECRETOS_DIR}/scripts"

export DOCUTILSCONFIG="${SCRIPT_DIR}/docutils.conf"

# Paso 1: Regenerar el JSON de decretos si tiene más de un mes
DECRETOS_JSON="${HTML_DIR}/decretos.json"
LIMITE=$(date -d "-1 month" +%s)
if [ -f "${DECRETOS_JSON}" ]; then
    CREACION=$(stat -c %W "${DECRETOS_JSON}")
    if [ "${CREACION}" -le "${LIMITE}" ]; then
        echo "==> Regenerando decretos.json (tiene más de un mes)..."
        uv run "${DECRETOS_SCRIPT_DIR}/extraer_decretos.py" "${DECRETOS_JSON}"
    fi
else
    echo "==> Generando decretos.json (no existe)..."
    uv run "${DECRETOS_SCRIPT_DIR}/extraer_decretos.py" "${DECRETOS_JSON}"
fi

# Paso 2: Compilar el sitio
echo "==> Compilando sitio..."

cd "${DECRETOS_DIR}/CPEUM"
uv run "${SCRIPTS_DIR}/rst2html5.py" cpeum.rst "${HTML_DIR}/index.html"

uv run "${SCRIPTS_DIR}/rst2html5.py" "${SCRIPT_DIR}/CPEUM/acercade.rst" "${HTML_DIR}/acercade.html"
uv run "${SCRIPTS_DIR}/rst2html5.py" "${SCRIPT_DIR}/CPEUM/estadisticas.rst" "${HTML_DIR}/estadisticas.html"

# Paso 3: Generar los diffs de las reformas y su índice
echo "==> Generando reformas..."
cd "${SCRIPT_DIR}"
node "${SCRIPTS_DIR}/generar_reformas.js"

# Paso 4: Generar las gráficas estadísticas
echo "==> Generando gráficas..."
uv run "${SCRIPTS_DIR}/generar_graficos.py"

# Paso 5: Iniciar servidor HTTP en segundo plano
echo "==> Iniciando servidor HTTP en puerto 8000..."
cd "${HTML_DIR}"
python3 -m http.server 8000 &
SERVER_PID=$!
echo "==> PID del servidor: ${SERVER_PID}"

# Limpiar al salir
trap 'echo "==> Deteniendo servidor..."; kill ${SERVER_PID} 2>/dev/null' EXIT

# Paso 6: Abrir navegador
sleep 0.5
xdg-open http://127.0.0.1:8000

# Esperar al proceso del servidor
wait "${SERVER_PID}"
