#!/usr/bin/env python3
import argparse
import os
import signal
import threading
import time
import uuid
from pathlib import Path
from typing import Dict

import RNS

from rfsh_common import (
    APP_NAMESPACE,
    APP_ROLE,
    CommandContext,
    chunk_text,
    dump_message,
    execute_command,
    load_message,
    make_server_announce_data,
)


class RfshServer:
    def __init__(
        self,
        announce_idle_interval: int = 5,
        announce_connected_interval: int = 30,
        node_name: str = "ben-pi-rnode",
        node_site: str = "Arlington Mesh Lab",
    ):
        self.announce_idle_interval = max(2, announce_idle_interval)
        self.announce_connected_interval = max(5, announce_connected_interval)
        self.ctx = CommandContext(node_name=node_name, node_site=node_site)
        self.running = True
        self.links: Dict[bytes, RNS.Link] = {}
        self.lock = threading.Lock()

        identity_path = Path(os.path.expanduser("~/.reticulum/rfsh_server_identity"))
        identity_path.parent.mkdir(parents=True, exist_ok=True)
        if identity_path.exists():
            self.identity = RNS.Identity.from_file(str(identity_path))
            self._log("Identity loaded")
        else:
            self.identity = RNS.Identity()
            self.identity.to_file(str(identity_path))
            self._log("Identity created")

        self.destination = RNS.Destination(
            self.identity,
            RNS.Destination.IN,
            RNS.Destination.SINGLE,
            APP_NAMESPACE,
            APP_ROLE,
        )
        self.destination.set_link_established_callback(self._on_link_established)

    def _log(self, msg: str) -> None:
        print(f"[RFSH] {msg}", flush=True)

    def _on_link_established(self, link):
        with self.lock:
            self.links[link.link_id] = link
        self._log(f"Link from {RNS.prettyhexrep(link.link_id)}")
        link.set_packet_callback(self._on_packet)
        link.set_link_closed_callback(self._on_link_closed)

    def _on_link_closed(self, link):
        with self.lock:
            self.links.pop(link.link_id, None)
        self._log(f"Link closed {RNS.prettyhexrep(link.link_id)}")

    def _active_link_count(self) -> int:
        with self.lock:
            return len(self.links)

    def _announce_interval(self) -> int:
        if self._active_link_count() > 0:
            return self.announce_connected_interval
        return self.announce_idle_interval

    def _send_response(self, link, request_id: str, text: str) -> None:
        chunks = chunk_text(text)
        total_bytes = 0
        for idx, chunk in enumerate(chunks):
            total_bytes += len(chunk.encode("utf-8"))
            msg = {
                "t": "out",
                "id": request_id,
                "seq": idx,
                "eof": idx == len(chunks) - 1,
                "data": chunk,
            }
            packet = RNS.Packet(link, dump_message(msg))
            packet.send()
        self._log(f"response: {len(chunks)} chunks / {total_bytes} bytes")

    def _on_packet(self, data, packet):
        try:
            msg = load_message(data)
        except Exception as exc:
            self._log(f"dropped non-json packet: {exc}")
            return
        if msg.get("t") != "cmd":
            return
        request_id = msg.get("id", str(uuid.uuid4()))
        command = str(msg.get("cmd", "")).strip()
        self._log(f"command: {command}")
        response = execute_command(command, self.ctx)
        self._send_response(packet.link, request_id, response + "\n")

    def announce_loop(self):
        while self.running:
            interval = self._announce_interval()
            try:
                self.destination.announce(app_data=make_server_announce_data(self.ctx))
                self._log(
                    f"announced: {RNS.prettyhexrep(self.destination.hash)} "
                    f"(interval={interval}s, links={self._active_link_count()})"
                )
            except Exception as exc:
                self._log(f"announce failed: {exc}")
            for _ in range(interval):
                if not self.running:
                    return
                time.sleep(1)

    def run(self):
        self._log("Reticulum started")
        self._log(f"Destination hash: {RNS.prettyhexrep(self.destination.hash)}")
        self._log("Waiting for links...")
        announcer = threading.Thread(target=self.announce_loop, daemon=True)
        announcer.start()
        while self.running:
            time.sleep(0.2)

    def stop(self):
        self.running = False


def parse_args():
    parser = argparse.ArgumentParser(description="RF shell server for Reticulum over RNode")
    parser.add_argument(
        "--announce-idle-interval",
        type=int,
        default=5,
        help="Announce interval in seconds when no client links are connected",
    )
    parser.add_argument(
        "--announce-connected-interval",
        type=int,
        default=30,
        help="Announce interval in seconds when at least one client is connected",
    )
    parser.add_argument("--node-name", default="ben-pi-rnode", help="Node name shown in id/node commands")
    parser.add_argument("--node-site", default="Pi RNode", help="Node site shown in id/node commands")
    return parser.parse_args()


def main():
    args = parse_args()
    RNS.Reticulum()
    server = RfshServer(
        announce_idle_interval=args.announce_idle_interval,
        announce_connected_interval=args.announce_connected_interval,
        node_name=args.node_name,
        node_site=args.node_site,
    )

    def _stop(*_):
        server.stop()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    server.run()


if __name__ == "__main__":
    main()
