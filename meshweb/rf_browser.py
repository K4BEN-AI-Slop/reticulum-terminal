#!/usr/bin/env python3
from __future__ import annotations

import argparse
import signal
import threading
import time
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Optional

import RNS

from rf_common import APP_NAMESPACE, APP_ROLE, b64d, dump_message, load_message


def now_ms() -> int:
    return int(time.time() * 1000)


def clean_hash(hex_hash: str) -> bytes:
    cleaned = hex_hash.strip().lower().replace(":", "")
    if cleaned.startswith("0x"):
        cleaned = cleaned[2:]
    return bytes.fromhex(cleaned)


@dataclass
class PendingHttpResponse:
    done: threading.Event = field(default_factory=threading.Event)
    status: int = 502
    content_type: str = "text/plain; charset=utf-8"
    chunks: Dict[int, bytes] = field(default_factory=dict)
    started_ms: int = field(default_factory=now_ms)

    def add(self, seq: int, eof: bool, status: int, content_type: str, data: bytes) -> None:
        self.chunks[seq] = data
        self.status = status
        self.content_type = content_type
        if eof:
            self.done.set()

    def body(self) -> bytes:
        return b"".join(v for _, v in sorted(self.chunks.items()))


class TargetAnnounceHandler:
    def __init__(self, target_hash: Optional[bytes], on_match):
        self.aspect_filter = f"{APP_NAMESPACE}.{APP_ROLE}"
        self.target_hash = target_hash
        self.on_match = on_match

    def received_announce(self, destination_hash, announced_identity, app_data):
        if self.target_hash and destination_hash != self.target_hash:
            return
        self.on_match(destination_hash, announced_identity, app_data)


class MeshRfClient:
    def __init__(self, target_hash: Optional[bytes], timeout: int = 30):
        self.target_hash = target_hash
        self.timeout = timeout
        self.destination = None
        self.link = None
        self.connected = threading.Event()
        self.destination_seen = threading.Event()
        self.pending: Dict[str, PendingHttpResponse] = {}
        self.lock = threading.Lock()
        self.running = True

        handler = TargetAnnounceHandler(target_hash, self._on_announce)
        RNS.Transport.register_announce_handler(handler)

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
        print(f"[MESHWEB-CLI] resolved destination {RNS.prettyhexrep(destination_hash)}", flush=True)

    def open_link(self):
        print("[MESHWEB-CLI] resolving path...", flush=True)
        if self.target_hash and not RNS.Transport.has_path(self.target_hash):
            RNS.Transport.request_path(self.target_hash)
        started = time.time()
        while not self.destination_seen.is_set():
            if time.time() - started > self.timeout:
                raise TimeoutError("timed out waiting for meshweb server announce")
            time.sleep(0.2)

        print("[MESHWEB-CLI] opening link...", flush=True)
        self.link = RNS.Link(self.destination)
        self.link.set_link_established_callback(self._on_link_established)
        self.link.set_link_closed_callback(self._on_link_closed)
        self.link.set_packet_callback(self._on_packet)
        if not self.connected.wait(self.timeout):
            raise TimeoutError("timed out opening link to meshweb server")
        print("[MESHWEB-CLI] link established", flush=True)

    def _on_link_established(self, _link):
        self.connected.set()

    def _on_link_closed(self, _link):
        self.connected.clear()
        self.running = False

    def _on_packet(self, data, _packet):
        try:
            msg = load_message(data)
        except Exception:
            return
        if msg.get("t") != "http_res":
            return
        req_id = msg.get("id")
        if not req_id:
            return
        with self.lock:
            pending = self.pending.get(req_id)
        if not pending:
            return
        pending.add(
            seq=int(msg.get("seq", 0)),
            eof=bool(msg.get("eof", False)),
            status=int(msg.get("status", 502)),
            content_type=str(msg.get("content_type", "text/plain; charset=utf-8")),
            data=b64d(msg.get("data_b64", "")),
        )

    def get(self, path: str) -> tuple[int, str, bytes]:
        if not self.connected.is_set():
            return 503, "text/plain; charset=utf-8", b"RNS mesh link is not connected\n"

        req_id = str(uuid.uuid4())
        pending = PendingHttpResponse()
        with self.lock:
            self.pending[req_id] = pending

        msg = {"t": "http_req", "id": req_id, "method": "GET", "path": path}
        RNS.Packet(self.link, dump_message(msg)).send()

        if not pending.done.wait(self.timeout):
            with self.lock:
                self.pending.pop(req_id, None)
            return 504, "text/plain; charset=utf-8", b"mesh request timeout\n"

        with self.lock:
            self.pending.pop(req_id, None)
        return pending.status, pending.content_type, pending.body()


def make_handler(mesh_client: MeshRfClient):
    class MeshBrowserHandler(BaseHTTPRequestHandler):
        server_version = "MeshWebBrowser/0.1"

        def do_GET(self):
            status, content_type, body = mesh_client.get(self.path)
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return MeshBrowserHandler


def main() -> None:
    parser = argparse.ArgumentParser(description="Local browser gateway for meshweb over Reticulum RF")
    parser.add_argument("destination_hash", nargs="?", help="Optional meshweb destination hash (hex)")
    parser.add_argument("--timeout", type=int, default=30, help="RNS link/request timeout seconds")
    parser.add_argument("--host", default="127.0.0.1", help="Local HTTP bind host")
    parser.add_argument("--port", type=int, default=8090, help="Local HTTP bind port")
    args = parser.parse_args()

    target_hash = clean_hash(args.destination_hash) if args.destination_hash else None
    RNS.Reticulum()
    client = MeshRfClient(target_hash=target_hash, timeout=args.timeout)
    client.open_link()

    httpd = ThreadingHTTPServer((args.host, args.port), make_handler(client))
    print(f"[MESHWEB-CLI] browser gateway at http://{args.host}:{args.port}", flush=True)

    def _stop(*_):
        client.running = False
        httpd.shutdown()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()

