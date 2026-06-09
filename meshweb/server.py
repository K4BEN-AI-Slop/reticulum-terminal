#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from templating import render_mesh_markup


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _html_shell(title: str, body: str) -> bytes:
    page = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 2rem; max-width: 860px; }}
    a {{ color: #0a58ca; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    code {{ background: #f3f4f6; padding: 0.1rem 0.35rem; border-radius: 0.25rem; }}
    .muted {{ color: #6b7280; }}
    ul {{ line-height: 1.5; }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""
    return page.encode("utf-8")


class MeshSiteHandler(BaseHTTPRequestHandler):
    server_version = "MeshWeb/0.1"

    @property
    def root(self) -> Path:
        return self.server.root  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        rel = unquote(parsed.path).lstrip("/") or "."
        requested = (self.root / rel).resolve()

        if not _is_within_root(requested, self.root):
            self._send_text(403, "Forbidden")
            return

        if requested.is_dir():
            self._serve_directory(requested, parsed.path.rstrip("/") or "/")
            return

        if not requested.exists() and requested.suffix == "":
            candidate = requested.with_suffix(".msh")
            if candidate.exists():
                requested = candidate

        if not requested.exists():
            self._send_text(404, "Not found")
            return

        if requested.suffix == ".msh":
            self._serve_msh_file(requested)
            return

        if requested.suffix in {".html", ".htm"}:
            self._serve_bytes(200, requested.read_bytes(), "text/html; charset=utf-8")
            return

        mime, _ = mimetypes.guess_type(str(requested))
        self._serve_bytes(200, requested.read_bytes(), mime or "application/octet-stream")

    def _serve_directory(self, directory: Path, url_path: str) -> None:
        for index_name in ("index.msh", "index.html", "index.htm"):
            index_path = directory / index_name
            if index_path.exists():
                if index_name.endswith(".msh"):
                    self._serve_msh_file(index_path)
                else:
                    self._serve_bytes(200, index_path.read_bytes(), "text/html; charset=utf-8")
                return

        rel_dir = directory.relative_to(self.root)
        title = f"Index of /{rel_dir}" if str(rel_dir) != "." else "Index of /"
        items = []
        if str(rel_dir) != ".":
            parent = str((Path(url_path) / "..").resolve())  # fallback string, not fs path
            items.append('<li><a href="../">../</a></li>')

        for child in sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            name = child.name + ("/" if child.is_dir() else "")
            href = name
            if child.suffix == ".msh":
                href = child.stem
                name = child.stem
            items.append(f'<li><a href="{html.escape(href)}">{html.escape(name)}</a></li>')

        body = f"<h1>{html.escape(title)}</h1><ul>{''.join(items)}</ul>"
        self._serve_bytes(200, _html_shell(title, body), "text/html; charset=utf-8")

    def _serve_msh_file(self, file_path: Path) -> None:
        rendered = render_mesh_markup(file_path.read_text(encoding="utf-8"))
        title = file_path.stem
        if "<html" in rendered.lower():
            payload = rendered.encode("utf-8")
        else:
            payload = _html_shell(title, rendered)
        self._serve_bytes(200, payload, "text/html; charset=utf-8")

    def _serve_text(self, status: int, text: str) -> None:
        self._serve_bytes(status, text.encode("utf-8"), "text/plain; charset=utf-8")

    def _serve_bytes(self, status: int, data: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Tiny filesystem wiki/site server for .msh pages")
    parser.add_argument("--root", default="meshweb/sites", help="Content root directory")
    parser.add_argument("--host", default="127.0.0.1", help="Host bind address")
    parser.add_argument("--port", type=int, default=8080, help="Server port")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    httpd = ThreadingHTTPServer((args.host, args.port), MeshSiteHandler)
    httpd.root = root  # type: ignore[attr-defined]

    print(f"[meshweb] serving {root} at http://{args.host}:{args.port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()

