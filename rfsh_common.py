#!/usr/bin/env python3
import datetime as dt
import getpass
import json
import os
import platform
import random
import shlex
import socket
import textwrap
import time
from dataclasses import dataclass, field
from typing import Dict, List


APP_NAMESPACE = "rfsh"
APP_ROLE = "server"
PROTOCOL_VERSION = 1
MAX_CHUNK_BYTES = 180


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat(timespec="seconds")


def uptime_string(started_at: float) -> str:
    elapsed = max(0, int(time.time() - started_at))
    hours, rem = divmod(elapsed, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"up {hours:02d}:{minutes:02d}:{seconds:02d}"


def dump_message(message: dict) -> bytes:
    return json.dumps(message, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def load_message(data: bytes) -> dict:
    return json.loads(data.decode("utf-8"))


def chunk_text(payload: str, max_bytes: int = MAX_CHUNK_BYTES) -> List[str]:
    chunks: List[str] = []
    current: List[str] = []
    current_bytes = 0
    for line in payload.splitlines(True):
        line_bytes = len(line.encode("utf-8"))
        if line_bytes > max_bytes:
            for wrapped in textwrap.wrap(line.rstrip("\n"), width=max_bytes // 2) or [""]:
                wrapped_line = wrapped + "\n"
                chunks.extend(chunk_text(wrapped_line, max_bytes=max_bytes))
            continue
        if current and current_bytes + line_bytes > max_bytes:
            chunks.append("".join(current))
            current = [line]
            current_bytes = line_bytes
        else:
            current.append(line)
            current_bytes += line_bytes
    if current:
        chunks.append("".join(current))
    return chunks or [""]


@dataclass
class CommandContext:
    node_name: str = "ben-pi-rnode"
    node_site: str = "Arlington Mesh Lab"
    started_at: float = field(default_factory=time.time)
    command_log: List[str] = field(default_factory=list)
    beacons: int = 0

    def log_command(self, command: str) -> None:
        stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.command_log.append(f"{stamp} {command}")
        self.command_log = self.command_log[-200:]


FORTUNES = [
    "LoRa is just packet radio with prettier YAML.",
    "No IP. No cloud. No mercy.",
    "Meshtastic is group chat. this is a haunted serial cable.",
    "Reticulum is where weird apps go to thrive.",
]


HELP_TEXT = """\
Available commands:
  help               Show this help
  id                 Node identity banner
  uptime             Demo node uptime
  date               Current server date/time
  whoami             User running rfsh_server.py
  radio              Radio profile configured for this node
  mesh               Mesh transport hint
  battery            Synthetic battery telemetry
  heard              Last heard command history
  ping               Radio ping response
  fortune            Random rf quote
  motd               Show demo MOTD
  cat /etc/motd      Alias for motd
  tail log           Tail command log
  sys                Platform/system details
  stack              Stack breakdown
  node               Node role + site details
  vibe               One-line pitch for demo
  beacon             Log a beacon event
  clear              Client-side clear screen hint
  exit               End client session
"""


def execute_command(command: str, ctx: CommandContext) -> str:
    normalized = " ".join(shlex.split(command)) if command.strip() else ""
    command_key = normalized.lower()
    ctx.log_command(normalized or "<empty>")

    if command_key in {"help", "?"}:
        return HELP_TEXT.strip()
    if command_key == "id":
        return f"{ctx.node_name} / Heltec V4 / {ctx.node_site}"
    if command_key == "uptime":
        return uptime_string(ctx.started_at)
    if command_key == "date":
        return dt.datetime.now().astimezone().isoformat(timespec="seconds")
    if command_key == "whoami":
        return getpass.getuser()
    if command_key == "radio":
        return "\n".join(
            [
                "interface: RNodeInterface[heltec-v4]",
                f"freq: {os.getenv('RFSH_FREQ', '915.000')} MHz",
                f"bw: {os.getenv('RFSH_BW', '125')} kHz",
                f"sf: {os.getenv('RFSH_SF', '9')}",
                f"cr: {os.getenv('RFSH_CR', '5')}",
                f"tx: {os.getenv('RFSH_TX', '17')} dBm",
            ]
        )
    if command_key == "mesh":
        return "direct LoRa link, no IP route"
    if command_key == "battery":
        pct = 76 + random.randint(-5, 5)
        return f"battery: {pct}% (synthetic)"
    if command_key == "heard":
        lines = ctx.command_log[-8:]
        return "\n".join(lines) if lines else "heard: no commands yet"
    if command_key == "ping":
        return "pong"
    if command_key == "fortune":
        return random.choice(FORTUNES)
    if command_key in {"motd", "cat /etc/motd"}:
        return "\n".join(
            [
                "BENNET RF SHELL",
                "No IP. No cloud. No mercy.",
                "Heltec V4 over RNode/Reticulum",
            ]
        )
    if command_key == "tail log":
        tail = ctx.command_log[-10:]
        return "\n".join(tail) if tail else "log is empty"
    if command_key == "sys":
        return "\n".join(
            [
                f"host: {socket.gethostname()}",
                f"platform: {platform.system()} {platform.release()}",
                f"python: {platform.python_version()}",
                f"arch: {platform.machine()}",
            ]
        )
    if command_key == "stack":
        return "\n".join(
            [
                "app: rfsh",
                "session: RNS Link",
                "transport: Reticulum",
                "modem: RNode",
                "phy: LoRa 915 MHz",
            ]
        )
    if command_key == "node":
        return "\n".join(
            [
                f"name: {ctx.node_name}",
                "role: fixed terminal endpoint",
                f"site: {ctx.node_site}",
            ]
        )
    if command_key == "vibe":
        return "meshtastic is group chat. this is a haunted serial cable."
    if command_key == "beacon":
        ctx.beacons += 1
        return f"sent demo beacon to local log (count={ctx.beacons})"
    if command_key == "clear":
        return "__CLIENT_CLEAR__"
    if command_key == "exit":
        return "__CLIENT_EXIT__"
    return f"unknown command: {normalized or '<empty>'}. try 'help'"


def make_server_announce_data(ctx: CommandContext) -> bytes:
    payload = {
        "name": ctx.node_name,
        "site": ctx.node_site,
        "version": PROTOCOL_VERSION,
        "motd": "No IP. No cloud. No mercy.",
        "time": iso_now(),
    }
    return dump_message(payload)
