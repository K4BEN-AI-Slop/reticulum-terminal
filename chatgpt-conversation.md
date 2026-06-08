# Me:

give me a detailed rnode stack that's very ben style that i could get demo ready in 1 afternoon cram. two nodes, one heltec v4 (connected to pi) and one t-echo (connected to laptop). i want to build a terminal style demo where i can open a socket type thing, and interact via a terminal. i'm thinking this would be cooler than using the default messaging protocol, because that's just like meshtastic/meshcore but more boring

# ChatGPT:

Yes — make it not a messenger. Make it feel like a tiny cursed LoRa UNIX terminal where one machine opens a Reticulum service and the other gets an interactive shell-like session over RF.

The demo concept:

BenNet RNS Terminal
Laptop + T-Echo  <~~~~ LoRa / Reticulum ~~~~>  Pi + Heltec V4
You type commands on laptop.
Pi executes safe/demo commands.
Responses come back over Reticulum link.

Not real remote shell. More like a radio-native command socket with a REPL.

Reticulum is a good fit because a Link is explicitly meant to be an abstract channel to one destination and supports request/response, larger transfers, encryption, forward secrecy, and more capable app APIs than raw packet messaging.  ￼ The Python API examples include a Channel example for structured messages over an established Link, which is the exact shape you want for “terminal over LoRa.”  ￼

The stack I’d build

Node A: fixed “server”

Device: Heltec WiFi LoRa 32 V4
Connected to: Raspberry Pi
Role: RNode modem + Reticulum app host
App: rterm_server.py
Physical vibe: headless micro-BBS / field service endpoint

Node B: client “terminal”

Device: LilyGO T-Echo
Connected to: MacBook/laptop
Role: RNode modem + Reticulum app client
App: rterm_client.py
Physical vibe: portable LoRa terminal

Transport

Reticulum
  └── RNodeInterface
        └── USB serial
              └── RNode firmware on each board

RNode firmware supports Semtech SX1262/SX127x/SX1280-style LoRa transceivers, and its purpose is to turn LoRa boards into flexible network adapters for Reticulum and other use cases.  ￼ The Reticulum hardware manual says once RNode firmware is installed and provisioned, the board can be used by adding an RNodeInterface to the Reticulum config.  ￼

Reality check on your specific boards

Heltec V4

Good afternoon-cram candidate. There are recent Heltec V4 RNode resources, and the community CLI guide specifically uses a Heltec V4 with rnodeconf --autoinstall.  ￼

T-Echo

Likely workable, but more annoying than the Heltec. The upstream RNode firmware repo/search results show LilyGO T-Echo support, but there have been T-Echo-specific wrinkles. One Reticulum discussion says the T-Echo’s RNode Bootstrap Console may not be supported in Mark’s version, and a CE firmware release notes “fixed builds for the LilyGO T-Echo.”  ￼

For a one-afternoon demo, avoid BLE. Use USB serial on both sides.

Demo design: “RTerm”

Make this:

rterm server
  announces a Reticulum destination
  accepts links
  receives command frames
  runs allowed commands
  sends response frames
rterm client
  discovers/uses destination hash
  opens Reticulum Link
  gives you a prompt:
    rns://bennet >

Commands should feel terminal-ish, but safe:

help
id
uptime
date
whoami
radio
mesh
battery
heard
ping
fortune
cat /etc/motd
tail log
sys
clear
exit

Example demo flow:

$ python3 rterm_client.py 9f03b8c2e4a1cafe
BENNET RTERM
link: established
path: LoRa/RNode/Reticulum
cipher: RNS link
rns://bennet> id
pi-node / Heltec V4 / Arlington Mesh Lab
rns://bennet> radio
interface: RNodeInterface[heltec-v4]
freq: 915.000 MHz
bw: 125 kHz
sf: 9
cr: 5
tx: 17 dBm
rns://bennet> uptime
up 03:41:22
rns://bennet> cat /etc/motd
Welcome to BenNet RNS Terminal.
This is not IP. This is not Meshtastic. This is worse, and therefore better.
rns://bennet> fortune
LoRa is just packet radio with prettier YAML.

RF settings for the demo

Use something moderate. Do not start with ultra-slow settings unless you want to watch paint dry.

For tabletop / neighborhood:

Frequency: 915.000 MHz, or your legal/local 915-ish choice
Bandwidth: 125 kHz
Spreading Factor: 9
Coding Rate: 5
TX Power: modest indoors, maybe 10–17 dBm

For “it must work across the house / yard”:

BW: 125 kHz
SF: 10
CR: 5

For “I want it snappy on the desk”:

BW: 125 kHz
SF: 7 or 8
CR: 5

I would start:

SF9 / BW125 / CR5

That should feel noticeably more interactive than a LongSlow gimmick but still very LoRa.

Afternoon build schedule

0. Prep both hosts

On the Pi and laptop:

python3 -m venv ~/rns-venv
source ~/rns-venv/bin/activate
pip install --upgrade pip
pip install rns

Confirm tools:

rnsd --version
rnodeconf --help
rnstatus --help

1. Flash/provision RNode firmware

On each machine, plug in one board at a time.

source ~/rns-venv/bin/activate
rnodeconf --autoinstall

The official/older install docs and community guides point to rnodeconf --autoinstall as the normal fast path for RNode firmware installation.  ￼

For the Heltec V4, this is probably straightforward.

For the T-Echo, if rnodeconf --autoinstall gets weird, your fallback is a browser flasher or CE firmware image. There is a browser-based RNode flasher listing Heltec V4 and T-Echo/RAK4631-type targets, but I would still try rnodeconf first because the whole demo is terminal-centric.  ￼

2. Find serial ports

Linux Pi:

ls -l /dev/serial/by-id/

macOS:

ls /dev/cu.*

You want stable names if possible.

Examples:

Pi:     /dev/serial/by-id/usb-Heltec_V4_RNode-if00
Mac:    /dev/cu.usbmodemT-Echo1234

3. Create Reticulum configs

Reticulum config usually lives under:

~/.reticulum/config

You can let Reticulum generate a default once:

rnsd

Stop it with Ctrl-C, then edit.

Pi ~/.reticulum/config

Use the Heltec V4 serial device:

[reticulum]
enable_transport = No
share_instance = Yes
shared_instance_port = 37428
instance_control_port = 37429
panic_on_interface_error = No
[logging]
loglevel = 4
[interfaces]
  [[Heltec V4 RNode]]
    type = RNodeInterface
    enabled = Yes
    port = /dev/serial/by-id/YOUR_HELTEC_V4_HERE
    frequency = 915000000
    bandwidth = 125000
    txpower = 17
    spreadingfactor = 9
    codingrate = 5

Laptop ~/.reticulum/config

Use the T-Echo serial device:

[reticulum]
enable_transport = No
share_instance = Yes
shared_instance_port = 37428
instance_control_port = 37429
panic_on_interface_error = No
[logging]
loglevel = 4
[interfaces]
  [[T-Echo RNode]]
    type = RNodeInterface
    enabled = Yes
    port = /dev/cu.YOUR_TECHO_HERE
    frequency = 915000000
    bandwidth = 125000
    txpower = 17
    spreadingfactor = 9
    codingrate = 5

For a two-node direct demo, keep enable_transport = No. You are not trying to become a public Reticulum router yet.

4. Confirm basic Reticulum health

On both machines:

rnsd

In another terminal:

rnstatus

You want to see the RNode interface up.

If not:

rnodeconf --info

or reduce weirdness:

lsof | grep tty

Make sure Meshtastic, serial monitor, or another rnsd is not holding the port.

The actual app

You have two implementation options.

Option A: faster and demo-safe — Reticulum Request API

This is easiest for one afternoon. It feels like a terminal but every command is request/response.

client command -> Reticulum request -> server handler -> response

Pros:

* easiest to finish
* less state to debug
* good enough for demo
* very LoRa-friendly

Cons:

* not a true continuous stream

Option B: cooler — Link + Channel

This is closer to “socket-like.” Reticulum’s Channel example exists specifically to pass structured messages over a Link.  ￼

Pros:

* feels like a real terminal session
* better architecture
* lets you add streaming later

Cons:

* more moving parts
* slightly higher afternoon-cram risk

My recommendation: build Option A first, name it RTerm anyway, then upgrade to Channel if there’s time.

Minimal command set

Hardcode commands. Do not expose a real shell.

COMMANDS = {
    "help": "...",
    "id": "...",
    "uptime": "...",
    "date": "...",
    "radio": "...",
    "mesh": "...",
    "fortune": "...",
    "motd": "...",
}

Avoid:

rm
curl
bash
python eval
arbitrary subprocess input

For demo commands that look shell-like, fake the filesystem:

cat /etc/motd
cat /proc/rnode
ls
tail /var/log/rterm.log

Server behavior

The Pi server should print:

[RTerm] Reticulum started
[RTerm] Identity loaded
[RTerm] Destination hash: <copy this to client>
[RTerm] Waiting for links...
[RTerm] Link from <client>
[RTerm] command: radio
[RTerm] response: 8 lines / 231 bytes

This gives you a visible “radio server” vibe.

Client behavior

Laptop client:

$ ./rterm 9f03b8c2e4a1cafe
resolving path...
opening link...
link established.
rns://9f03b8> help

Add small touches:

[tx 14 bytes]
[rx 212 bytes, 3.4s]

That makes LoRa latency feel like a feature.

The “Ben style” polish

Name it one of these:

bennet-rterm
rnshell
lorash
rns-tty
arlington-rterm
rfsh

I like:

rfsh

Prompt:

rfsh://heltec-v4 >

MOTD:

BENNET RF SHELL
No IP. No cloud. No mercy.
Heltec V4 over RNode/Reticulum

Command ideas:

rfsh://heltec-v4> path
direct LoRa link, no IP route
rfsh://heltec-v4> stack
app: rfsh
session: RNS Link
transport: Reticulum
modem: RNode
phy: LoRa 915 MHz
rfsh://heltec-v4> vibe
meshtastic is group chat. this is a haunted serial cable.
rfsh://heltec-v4> beacon
sent demo beacon to local log
rfsh://heltec-v4> node
name: ben-pi-rnode
role: fixed terminal endpoint
site: Arlington Mesh Lab

Demo script

Run this live:

On Pi

source ~/rns-venv/bin/activate
rnsd

Second Pi terminal:

source ~/rns-venv/bin/activate
python3 rterm_server.py

It prints:

destination: 9f03b8c2e4a1cafe

On laptop

source ~/rns-venv/bin/activate
rnsd

Second laptop terminal:

python3 rterm_client.py 9f03b8c2e4a1cafe

Then:

help
stack
radio
uptime
motd
fortune
tail log
exit

What makes it cooler than LXMF / Sideband

Sideband/LXMF is basically:

Reticulum as secure off-grid messaging

Your demo is:

Reticulum as a weird RF application substrate

That is the actual interesting part. Reticulum is not just “another Meshtastic.” It gives you identity, destinations, links, pathing, and app-level primitives. The manual’s API section describes Reticulum communication as built from classes like Destination, Link, Packet, and related APIs, not just a fixed chat UX.  ￼

So the sales pitch is:

Meshtastic/MeshCore: app-first radio mesh.
Reticulum/RNode: network stack + radio modem for building your own weird apps.

Scope cuts if things go wrong

If flashing the T-Echo wastes time:

Use Heltec V4 + any other confirmed RNode board.

If Reticulum path discovery wastes time:

Manually copy destination hash from server to client.

If Channel API wastes time:

Use request/response.

If RNode config wastes time:

Drop to SF7/BW125, put both radios 10–20 feet apart, verify rnstatus.

If everything explodes:

Run both Reticulum apps over TCPInterface on localhost/LAN first.
Then swap in RNodeInterface.

That last fallback is important: build the terminal app over Reticulum first, then make LoRa the interface. Don’t debug firmware, RF, and your app simultaneously.

Final recommended afternoon target

Build this exact deliverable:

rfsh
- Pi server on Heltec V4 RNode
- Laptop client on T-Echo RNode
- Reticulum request/response terminal
- 10 fake-but-useful commands
- visible latency + tx/rx byte counts
- MOTD and stack command
- no real shell execution

The result will feel like:

SSH over a haunted LoRa modem

That is way more interesting than recreating Meshtastic chat badly.