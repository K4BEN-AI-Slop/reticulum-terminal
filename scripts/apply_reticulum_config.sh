#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Apply latest Reticulum RNode config.

Usage:
  scripts/apply_reticulum_config.sh --name "<Interface Name>" --port "<serial-port>"
  scripts/apply_reticulum_config.sh --name "Heltec V4 RNode" --port "/dev/serial/by-id/usb-..."
  scripts/apply_reticulum_config.sh --name "T-Echo RNode" --port "/dev/cu.usbmodem2101"

Optional tuning flags:
  --frequency <hz>    default: 915000000
  --bandwidth <hz>    default: 125000
  --txpower <dbm>     default: 17
  --sf <factor>       default: 7
  --cr <rate>         default: 5
  --yes               overwrite without prompt
EOF
}

IF_NAME=""
PORT=""
FREQ="915000000"
BW="125000"
TXP="17"
SF="7"
CR="5"
AUTO_YES="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)
      IF_NAME="${2:-}"
      shift 2
      ;;
    --port)
      PORT="${2:-}"
      shift 2
      ;;
    --frequency)
      FREQ="${2:-}"
      shift 2
      ;;
    --bandwidth)
      BW="${2:-}"
      shift 2
      ;;
    --txpower)
      TXP="${2:-}"
      shift 2
      ;;
    --sf)
      SF="${2:-}"
      shift 2
      ;;
    --cr)
      CR="${2:-}"
      shift 2
      ;;
    --yes)
      AUTO_YES="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$IF_NAME" || -z "$PORT" ]]; then
  echo "Error: --name and --port are required." >&2
  usage
  exit 1
fi

CONFIG_DIR="$HOME/.reticulum"
CONFIG_PATH="$CONFIG_DIR/config"
mkdir -p "$CONFIG_DIR"

if [[ -f "$CONFIG_PATH" && "$AUTO_YES" != "1" ]]; then
  echo "About to overwrite: $CONFIG_PATH"
  read -r -p "Continue? [y/N] " ok
  if [[ "${ok,,}" != "y" ]]; then
    echo "Aborted."
    exit 1
  fi
fi

cat > "$CONFIG_PATH" <<EOF
[reticulum]
enable_transport = No
share_instance = Yes
shared_instance_port = 37428
instance_control_port = 37429
panic_on_interface_error = No

[logging]
loglevel = 4

[interfaces]
  [[${IF_NAME}]]
    type = RNodeInterface
    enabled = Yes
    port = ${PORT}
    frequency = ${FREQ}
    bandwidth = ${BW}
    txpower = ${TXP}
    spreadingfactor = ${SF}
    codingrate = ${CR}
EOF

echo "Wrote $CONFIG_PATH"
echo "Interface: $IF_NAME"
echo "Port:      $PORT"
echo "Profile:   freq=$FREQ bw=$BW sf=$SF cr=$CR tx=$TXP"
echo
echo "Next:"
echo "  pkill rnsd || true"
echo "  rnsd"
echo "  rnstatus"
