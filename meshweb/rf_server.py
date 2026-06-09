#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import mimetypes
import os
import signal
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

import RNS

from rf_common import APP_NAMESPACE, APP_ROLE, b64e, chunk_bytes, dump_message, load_message
from templating import render_mesh_markup


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _html_shell(title: str, body: str) -> bytes:
    page = f"""<!doctype html>
<html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
</head><body>{body}</body></html>"""
    return page.encode("utf-8")


def _resolve_content(root: Path, raw_path: str) -> tuple[int, str, bytes]:
    parsed = urlparse(raw_path)
    rel = unquote(parsed.path).lstrip("/") or "."
    requested = (root / rel).resolve()

    if not _is_within_root(requested, root):
        return 403, "text/plain; charset=utf-8", b"Forbidden\n"

    if requested.is_dir():
        for index_name in ("index.msh", "index.html", "index.htm"):
            idx = requested / index_name
            if idx.exists():
                requested = idx
                break
        else:
            items = []
            for child in sorted(requested.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                label = child.name + ("/" if child.is_dir() else "")
                href = child.name
                if child.suffix == ".msh":
                    href = child.stem
                    label = child.stem
                items.append(f'<li><a href="{html.escape(href)}">{html.escape(label)}</a></li>')
            body = f"<h1>Index</h1><ul>{''.join(items)}</ul>"
            return 200, "text/html; charset=utf-8", _html_shell("Index", body)

    if not requested.exists() and requested.suffix == "":
        msh = requested.with_suffix(".msh")
        if msh.exists():
            requested = msh

    if not requested.exists():
        return 404, "text/plain; charset=utf-8", b"Not found\n"

    if requested.suffix == ".msh":
        rendered = render_mesh_markup(requested.read_text(encoding="utf-8"))
        payload = rendered.encode("utf-8") if "<html" in rendered.lower() else _html_shell(requested.stem, rendered)
        return 200, "text/html; charset=utf-8", payload

    if requested.suffix in {".html", ".htm"}:
        return 200, "text/html; charset=utf-8", requested.read_bytes()

    mime, _ = mimetypes.guess_type(str(requested))
    return 200, mime or "application/octet-stream", requested.read_bytes()


class MeshRfServer:
    def __init__(self, root: Path, announce_interval: int = 5):
        self.root = root
        self.announce_interval = max(2, announce_interval)
        self.running = True
        self.links: dict[bytes, RNS.Link] = {}
        self.lock = threading.Lock()

        identity_path = Path(os.path.expanduser("~/.reticulum/meshweb_server_identity"))
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
        print(f"[MESHWEB-SRV] {msg}", flush=True)

    def _on_link_established(self, link):
        with self.lock:
            self.links[link.link_id] = link
        link.set_packet_callback(self._on_packet)
        link.set_link_closed_callback(self._on_link_closed)
        self._log(f"link from {RNS.prettyhexrep(link.link_id)}")

    def _on_link_closed(self, link):
        with self.lock:
            self.links.pop(link.link_id, None)
        self._log(f"link closed {RNS.prettyhexrep(link.link_id)}")

    def _send_http_response(self, link, req_id: str, status: int, content_type: str, body: bytes) -> None:
        chunks = chunk_bytes(body)
        for idx, chunk in enumerate(chunks):
            msg = {
                "t": "http_res",
                "id": req_id,
                "seq": idx,
                "eof": idx == len(chunks) - 1,
                "status": status,
                "content_type": content_type,
                "data_b64": b64e(chunk),
            }
            RNS.Packet(link, dump_message(msg)).send()
        self._log(f"response {status} {len(body)} bytes")

    def _on_packet(self, data, packet):
        try:
            msg = load_message(data)
        except Exception as exc:
            self._log(f"dropped bad packet: {exc}")
            return
        if msg.get("t") != "http_req":
            return

        req_id = msg.get("id", str(uuid.uuid4()))
        method = (msg.get("method") or "GET").upper()
        path = msg.get("path") or "/"
        if method != "GET":
            self._send_http_response(packet.link, req_id, 405, "text/plain; charset=utf-8", b"Method not allowed\n")
            return

        status, content_type, body = _resolve_content(self.root, path)
        self._send_http_response(packet.link, req_id, status, content_type, body)

    def _announce_loop(self):
        while self.running:
            try:
                app_data = dump_message({"name": "meshweb-rf", "root": str(self.root)})
                self.destination.announce(app_data=app_data)
                self._log(f"announced destination {RNS.prettyhexrep(self.destination.hash)}")
            except Exception as exc:
                self._log(f"announce failed: {exc}")
            for _ in range(self.announce_interval):
                if not self.running:
                    return
                time.sleep(1)

    def run(self):
        self._log(f"root: {self.root}")
        self._log(f"destination: {RNS.prettyhexrep(self.destination.hash)}")
        threading.Thread(target=self._announce_loop, daemon=True).start()
        while self.running:
            time.sleep(0.2)

    def stop(self):
        self.running = False


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve meshweb files over Reticulum RF")
    parser.add_argument("--root", default="meshweb/sites", help="Content root directory")
    parser.add_argument("--announce-interval", type=int, default=5, help="Announce interval (seconds)")
    args = parser.parse_args()

    RNS.Reticulum()
    root = Path(args.root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    server = MeshRfServer(root=root, announce_interval=args.announce_interval)

    def _stop(*_):
        server.stop()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    server.run()


if __name__ == "__main__":
    main()

