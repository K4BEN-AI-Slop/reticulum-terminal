#!/usr/bin/env python3
import argparse
import os
import signal
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional

import RNS

from rfsh_common import APP_NAMESPACE, APP_ROLE, dump_message, load_message


ANSI_GRAY = "\033[90m"
ANSI_RESET = "\033[0m"


def now_ms() -> int:
    return int(time.time() * 1000)


def clean_hash(hex_hash: str) -> bytes:
    cleaned = hex_hash.strip().lower().replace(":", "")
    if cleaned.startswith("0x"):
        cleaned = cleaned[2:]
    return bytes.fromhex(cleaned)


@dataclass
class PendingResponse:
    done: threading.Event = field(default_factory=threading.Event)
    started_ms: int = field(default_factory=now_ms)
    chunks: Dict[int, str] = field(default_factory=dict)
    eof: bool = False

    def add(self, seq: int, data: str, eof: bool) -> None:
        self.chunks[seq] = data
        self.eof = self.eof or eof
        if self.eof:
            self.done.set()

    def text(self) -> str:
        return "".join(v for _, v in sorted(self.chunks.items()))


class TargetAnnounceHandler:
    def __init__(self, target_hash: Optional[bytes], on_match):
        self.aspect_filter = f"{APP_NAMESPACE}.{APP_ROLE}"
        self.target_hash = target_hash
        self.on_match = on_match

    def received_announce(self, destination_hash, announced_identity, app_data):
        if self.target_hash and destination_hash != self.target_hash:
            return
        self.on_match(destination_hash, announced_identity, app_data)


class RfshClient:
    def __init__(self, target_hash: Optional[bytes], timeout: int = 20):
        self.target_hash = target_hash
        self.timeout = timeout
        self.destination = None
        self.link = None
        self.running = True
        self.connected = threading.Event()
        self.destination_seen = threading.Event()
        self.pending: Dict[str, PendingResponse] = {}
        self.lock = threading.Lock()

        handler = TargetAnnounceHandler(target_hash, self._on_announce)
        RNS.Transport.register_announce_handler(handler)

    def _log(self, msg: str) -> None:
        print(msg, flush=True)

    def _log_muted(self, msg: str) -> None:
        # Respect NO_COLOR, and only emit ANSI color in interactive terminals.
        if os.getenv("NO_COLOR") or not sys.stdout.isatty():
            self._log(msg)
            return
        self._log(f"{ANSI_GRAY}{msg}{ANSI_RESET}")

    def _on_announce(self, destination_hash, announced_identity, _app_data):
        if self.destination_seen.is_set():
            return
        self.destination = RNS.Destination(
            announced_identity,
            RNS.Destination.OUT,
            RNS.Destination.SINGLE,
            APP_NAMESPACE,
            APP_ROLE,
        )
        self.destination_seen.set()
        self._log(f"resolved destination: {RNS.prettyhexrep(destination_hash)}")

    def open_link(self):
        self._log("resolving path...")
        if self.target_hash and not RNS.Transport.has_path(self.target_hash):
            RNS.Transport.request_path(self.target_hash)
        started = time.time()
        while not self.destination_seen.is_set():
            if time.time() - started > self.timeout:
                raise TimeoutError(
                    "timed out waiting for server announce; ensure server is running and announcing"
                )
            time.sleep(0.2)

        self._log("opening link...")
        self.link = RNS.Link(self.destination)
        self.link.set_link_established_callback(self._on_link_established)
        self.link.set_link_closed_callback(self._on_link_closed)
        self.link.set_packet_callback(self._on_packet)
        if not self.connected.wait(self.timeout):
            raise TimeoutError("timed out opening link")
        self._log("link established.")

    def _on_link_established(self, _link):
        self.connected.set()

    def _on_link_closed(self, _link):
        self._log("link closed")
        self.running = False
        self.connected.clear()

    def _on_packet(self, data, _packet):
        try:
            msg = load_message(data)
        except Exception:
            return
        if msg.get("t") != "out":
            return
        req_id = msg.get("id")
        if not req_id:
            return
        with self.lock:
            pending = self.pending.get(req_id)
        if not pending:
            return
        pending.add(int(msg.get("seq", 0)), msg.get("data", ""), bool(msg.get("eof", False)))

    def request(self, command: str) -> str:
        req_id = str(uuid.uuid4())
        pending = PendingResponse()
        with self.lock:
            self.pending[req_id] = pending
        payload = {"t": "cmd", "id": req_id, "cmd": command}
        encoded = dump_message(payload)
        tx_bytes = len(encoded)
        started = now_ms()
        packet = RNS.Packet(self.link, encoded)
        packet.send()
        self._log_muted(f"[tx {tx_bytes} bytes]")
        if not pending.done.wait(self.timeout):
            with self.lock:
                self.pending.pop(req_id, None)
            raise TimeoutError("timeout waiting for response")
        elapsed = now_ms() - started
        response = pending.text()
        rx_bytes = len(response.encode("utf-8"))
        with self.lock:
            self.pending.pop(req_id, None)
        self._log_muted(f"[rx {rx_bytes} bytes, {elapsed/1000:.1f}s]")
        return response

    def repl(self):
        prompt = "ben@uugnet-rf> "
        while self.running:
            try:
                raw = input(prompt)
            except EOFError:
                print()
                break
            command = raw.strip()
            if not command:
                continue
            try:
                output = self.request(command)
            except TimeoutError as exc:
                self._log(f"error: {exc}")
                continue
            text = output.strip("\n")
            if text == "__CLIENT_CLEAR__":
                os.system("clear")
                continue
            if text == "__CLIENT_EXIT__":
                self._log("remote requested exit")
                break
            self._log(text)
        self.running = False


def parse_args():
    parser = argparse.ArgumentParser(description="RF shell client for Reticulum over RNode")
    parser.add_argument(
        "destination_hash",
        nargs="?",
        help="Destination hash from server (hex). Optional: if omitted, first announce is used.",
    )
    parser.add_argument("--timeout", type=int, default=30, help="Request and link timeout in seconds")
    return parser.parse_args()


def main():
    args = parse_args()
    target_hash = clean_hash(args.destination_hash) if args.destination_hash else None
    RNS.Reticulum()
    client = RfshClient(target_hash=target_hash, timeout=args.timeout)

    def _stop(*_):
        client.running = False
        sys.exit(0)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    print("BENNET RF SHELL")
    print("path: LoRa/RNode/Reticulum")
    client.open_link()
    client.repl()


if __name__ == "__main__":
    main()
