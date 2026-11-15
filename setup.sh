#!/usr/bin/env sh
# Cardia: puesta en marcha completa en macOS / Linux.
#   ./setup.sh [opciones]          (opciones: --help)
# Instala uv si falta y ejecuta scripts/bootstrap.py, que hace el resto.
set -e
cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
  echo "Instalando uv (gestor de Python de Astral)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  PATH="$HOME/.local/bin:$PATH"
fi

export PYTHONUTF8=1
exec uv run --no-project --python 3.11 scripts/bootstrap.py "$@"
