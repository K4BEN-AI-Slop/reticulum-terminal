#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/rnode_recover.sh auto <serial-port> [techo-16|techo-17]
  scripts/rnode_recover.sh provision-only <serial-port> [techo-16|techo-17]
  scripts/rnode_recover.sh info <serial-port>

Modes:
  auto            Run full autoinstall (flash + provisioning)
  provision-only  Skip firmware flash, bootstrap EEPROM only
  info            Query current device info

Examples:
  scripts/rnode_recover.sh auto /dev/cu.usbmodem2101
  scripts/rnode_recover.sh provision-only /dev/cu.usbmodem2101
  scripts/rnode_recover.sh provision-only /dev/cu.usbmodem2101 techo-17
  scripts/rnode_recover.sh info /dev/cu.usbmodem2101
EOF
}

if [[ $# -lt 2 ]]; then
  usage
  exit 1
fi

MODE="$1"
PORT="$2"
PROFILE="${3:-generic}"

source "$HOME/rns-venv/bin/activate"

case "$MODE" in
  auto)
    echo "[rfsh] running full autoinstall on $PORT"
    rnodeconf --autoinstall "$PORT"
    ;;
  provision-only)
    echo "[rfsh] provisioning only (no flash) on $PORT"
    # rnodeconf can crash on blank EEPROM unless model metadata is provided.
    # Provide known-good T-Echo bootstrap IDs when requested.
    if [[ "$PROFILE" == "techo-17" ]]; then
      rnodeconf --rom --product 15 --model 17 --hwrev 1 "$PORT"
    elif [[ "$PROFILE" == "techo-16" ]]; then
      rnodeconf --rom --product 15 --model 16 --hwrev 1 "$PORT"
    else
      rnodeconf --rom "$PORT"
    fi
    ;;
  info)
    echo "[rfsh] reading device info from $PORT"
    rnodeconf --info "$PORT"
    ;;
  *)
    usage
    exit 1
    ;;
esac
