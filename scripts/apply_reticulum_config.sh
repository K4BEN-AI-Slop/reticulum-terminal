#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Apply latest Reticulum RNode config.

Usage:
  scripts/apply_reticulum_config.sh --name "<Interface Name>" --port "<serial-port>"
  scripts/apply_reticulum_config.sh --name "<Interface Name>" --auto-port
  scripts/apply_reticulum_config.sh --name "Heltec V4 RNode" --port "/dev/serial/by-id/usb-..."
  scripts/apply_reticulum_config.sh --name "T-Echo RNode" --port "/dev/cu.usbmodem2101"

Optional tuning flags:
  --auto-port         auto-detect likely RNode serial port
  --prefer <string>   prefer auto-detect matches containing this text
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
AUTO_PORT="0"
PREFER=""
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
    --auto-port)
      AUTO_PORT="1"
      shift
      ;;
    --prefer)
      PREFER="${2:-}"
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

detect_port() {
  local candidates=()
  local path=""
  local lc_path=""
  local os_name
  os_name="$(uname -s)"

  if [[ "$os_name" == "Darwin" ]]; then
    for path in /dev/cu.usbmodem* /dev/cu.usbserial* /dev/cu.wchusbserial*; do
      [[ -e "$path" ]] || continue
      candidates+=("$path")
    done
  else
    for path in /dev/serial/by-id/* /dev/ttyACM* /dev/ttyUSB*; do
      [[ -e "$path" ]] || continue
      candidates+=("$path")
    done
  fi

  if [[ ${#candidates[@]} -eq 0 ]]; then
    return 1
  fi

  if [[ -n "$PREFER" ]]; then
    local lc_prefer
    lc_prefer="$(printf '%s' "$PREFER" | tr '[:upper:]' '[:lower:]')"
    for path in "${candidates[@]}"; do
      lc_path="$(printf '%s' "$path" | tr '[:upper:]' '[:lower:]')"
      if [[ "$lc_path" == *"$lc_prefer"* ]]; then
        printf '%s\n' "$path"
        return 0
      fi
    done
  fi

  printf '%s\n' "${candidates[0]}"
  return 0
}

if [[ -z "$PORT" && "$AUTO_PORT" == "1" ]]; then
  if ! PORT="$(detect_port)"; then
    echo "Error: --auto-port could not find a candidate serial device." >&2
    exit 1
  fi
  echo "Auto-detected port: $PORT"
fi

if [[ -z "$IF_NAME" || -z "$PORT" ]]; then
  echo "Error: --name is required and --port (or --auto-port) must be set." >&2
  usage
  exit 1
fi

CONFIG_DIR="$HOME/.reticulum"
CONFIG_PATH="$CONFIG_DIR/config"
mkdir -p "$CONFIG_DIR"

if [[ -f "$CONFIG_PATH" && "$AUTO_YES" != "1" ]]; then
  echo "About to overwrite: $CONFIG_PATH"
  read -r -p "Continue? [y/N] " ok
  ok_lc="$(printf '%s' "${ok:-}" | tr '[:upper:]' '[:lower:]')"
  if [[ "$ok_lc" != "y" ]]; then
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
