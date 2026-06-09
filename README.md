# rfsh (Reticulum RF Shell)

`rfsh` is a demo-safe terminal-style app over Reticulum + RNode.

- Server: `rfsh_server.py` on Pi + Heltec V4
- Client: `rfsh_client.py` on laptop + T-Echo
- Protocol: encrypted Reticulum `Link` with JSON command/response frames
- Safety model: fixed allowlist commands (no arbitrary shell execution)

## What this gives you

- Interactive prompt over LoRa that feels like a tiny remote shell
- Visible LoRa-like `tx/rx` latency and byte counters
- Copy/paste demo flow (bring-up -> link -> commands)

## 1) One-time setup (both Pi and laptop)

Clone this repo on both machines, then run:

```bash
cd /path/to/reticulum-project
chmod +x scripts/setup_env.sh
./scripts/setup_env.sh
source ~/rns-venv/bin/activate
```

## 2) Flash/provision both radios

Do this once per board:

```bash
source ~/rns-venv/bin/activate
rnodeconf --autoinstall
```

If `--autoinstall` fails on T-Echo, use your preferred browser flasher/known-good image and come back.

### T-Echo recovery flow (skip reflashing)

If T-Echo fails with `EEPROM was written, but validation failed`, retry provisioning without rewriting firmware:

```bash
cd /path/to/reticulum-project
chmod +x scripts/rnode_recover.sh
scripts/rnode_recover.sh info /dev/cu.usbmodem2101
scripts/rnode_recover.sh provision-only /dev/cu.usbmodem2101 techo-17
```

This uses `rnodeconf --rom` (EEPROM bootstrap only).
For T-Echo, passing `techo-17` (915-ish) or `techo-16` (470-ish) also avoids a `rnodeconf` crash when EEPROM is blank.

If that still fails, retry with a slower flash speed on a full install:

```bash
source ~/rns-venv/bin/activate
rnodeconf --autoinstall --baud-flash 115200 /dev/cu.usbmodem2101
```

## 3) Configure Reticulum on each host

Generate defaults once if needed:

```bash
rnsd
# Ctrl-C after it starts
```

Then copy templates:

- Pi: `config/pi.reticulum.config.example` -> `~/.reticulum/config`
- Laptop: `config/laptop.reticulum.config.example` -> `~/.reticulum/config`

Or use the helper script to apply the latest tuned profile in one command:

```bash
cd /path/to/reticulum-project
chmod +x scripts/apply_reticulum_config.sh

# Pi example
scripts/apply_reticulum_config.sh --name "Heltec V4 RNode" --port "/dev/serial/by-id/usb-REPLACE_ME" --yes

# Laptop example
scripts/apply_reticulum_config.sh --name "T-Echo RNode" --port "/dev/cu.usbmodem2101" --yes

# Auto-detect port (picks first likely serial device)
scripts/apply_reticulum_config.sh --name "T-Echo RNode" --auto-port --yes

# Auto-detect with preference hint
scripts/apply_reticulum_config.sh --name "Heltec V4 RNode" --auto-port --prefer "heltec" --yes

# BLE target (enables allow_unbonded_ble automatically)
scripts/apply_reticulum_config.sh --name "T-Echo RNode" --port "ble://RNode 4B44" --yes
```

Edit the `port` on each machine:

- Pi likely `/dev/serial/by-id/...`
- macOS likely `/dev/cu.usbmodem...`

Helpful port checks:

```bash
# Pi
ls -l /dev/serial/by-id/

# macOS
ls /dev/cu.*
```

## 4) Validate interfaces before demo

On both machines:

```bash
source ~/rns-venv/bin/activate
rnsd
```

In a second terminal on each machine:

```bash
source ~/rns-venv/bin/activate
rnstatus
```

If interface is missing:

```bash
rnodeconf --info
lsof | rg tty
```

Make sure no serial monitor/Meshtastic process is holding the port.

## Fast demo tuning (higher data rate)

For faster round-trips, use this profile on both nodes:

- `frequency = 915000000`
- `bandwidth = 125000`
- `spreadingfactor = 7`
- `codingrate = 5`

This repo's example configs already use `SF7/BW125/CR5`.

## 5) Run the rfsh demo

### On Pi (server side)

Terminal A:

```bash
source ~/rns-venv/bin/activate
rnsd
```

Terminal B:

```bash
source ~/rns-venv/bin/activate
cd /path/to/reticulum-project
python3 rfsh_server.py --announce-idle-interval 3 --announce-connected-interval 20
```

The server now announces faster while idle, and backs off once a link is active.

Server prints a destination hash like:

```text
[RFSH] Destination hash: 9f03b8c2e4a1cafe
```

### On laptop (client side)

Terminal A:

```bash
source ~/rns-venv/bin/activate
rnsd
```

Terminal B:

```bash
source ~/rns-venv/bin/activate
cd /path/to/reticulum-project
python3 rfsh_client.py 9f03b8c2e4a1cafe
```

## 6) Demo command sequence

Run these on the client:

```text
help
stack
radio
uptime
motd
fortune
tail log
exit
```

## Supported commands

`help`, `id`, `uptime`, `date`, `whoami`, `radio`, `mesh`, `battery`, `heard`, `ping`, `fortune`, `motd`, `cat /etc/motd`, `tail log`, `sys`, `stack`, `node`, `vibe`, `beacon`, `clear`, `exit`.

## Notes

- `clear` and `exit` are handled safely by the client.
- No command executes arbitrary shell input.
- If startup is flaky, keep both radios close and try SF7/SF8 first.

## Mesh Web (super simple)

This repo now includes a tiny filesystem web/wiki server at `meshweb/server.py`.

- content root: `meshweb/sites`
- page extension: `.msh` (condensed HTML-like format)
- links can target files or directories (e.g. `/wiki/`, `/wiki/rf-notes`)
- directory browsing works when no `index.msh` exists

Run it:

```bash
source ~/rns-venv/bin/activate
python3 meshweb/server.py --host 127.0.0.1 --port 8080
```

Open: `http://127.0.0.1:8080`

### `.msh` quick syntax

- `%tag text` -> element with inline text
- `%tag(attr=value key="quoted value") text` -> element with attributes
- indent two spaces to nest children
- `| text` -> plain text node
- `# comment` -> ignored

Example:

```text
%main
  %h1 hello
  %p cute tiny page
  %a(href="/wiki/") open wiki
```

