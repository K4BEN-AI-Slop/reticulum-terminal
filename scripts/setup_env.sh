#!/usr/bin/env bash
set -euo pipefail

VENV_PATH="${1:-$HOME/rns-venv}"

echo "[rfsh] creating venv at: ${VENV_PATH}"
python3 -m venv "${VENV_PATH}"
source "${VENV_PATH}/bin/activate"

echo "[rfsh] upgrading pip/setuptools/wheel"
python -m pip install --upgrade pip setuptools wheel

echo "[rfsh] installing requirements"
python -m pip install -r requirements.txt

echo "[rfsh] validating Reticulum tools"
rnsd --version || true
rnodeconf --help >/dev/null
rnstatus --help >/dev/null

echo "[rfsh] done"
echo "activate with: source \"${VENV_PATH}/bin/activate\""
