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

## 3) Configure Reticulum on each host

Generate defaults once if needed:

```bash
rnsd
# Ctrl-C after it starts
```

Then copy templates:

- Pi: `config/pi.reticulum.config.example` -> `~/.reticulum/config`
- Laptop: `config/laptop.reticulum.config.example` -> `~/.reticulum/config`

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
python3 rfsh_server.py
```

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

