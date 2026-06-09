#!/usr/bin/env python3
from __future__ import annotations

import html
import re
import shlex


VOID_TAGS = {"br", "hr", "img", "meta", "link", "input"}
TAG_RE = re.compile(r"^%([A-Za-z][\w:-]*)(?:\(([^)]*)\))?(?:\s+(.*))?$")


def _indent_of(line: str) -> int:
    expanded = line.replace("\t", "  ")
    return len(expanded) - len(expanded.lstrip(" "))


def _parse_attrs(attrs_raw: str | None) -> str:
    if not attrs_raw:
        return ""
    parts = []
    for token in shlex.split(attrs_raw):
        if "=" in token:
            key, value = token.split("=", 1)
            parts.append(f'{html.escape(key, quote=True)}="{html.escape(value, quote=True)}"')
        else:
            parts.append(html.escape(token, quote=True))
    return (" " + " ".join(parts)) if parts else ""


def render_mesh_markup(source: str) -> str:
    output: list[str] = []
    stack: list[tuple[int, str]] = []

    lines = source.splitlines()
    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue

        indent = _indent_of(raw)
        stripped = raw.strip()

        while stack and indent <= stack[-1][0]:
            _, open_tag = stack.pop()
            output.append(f"</{open_tag}>")

        if stripped.startswith("!doctype"):
            output.append("<!doctype html>")
            continue

        if stripped.startswith("|"):
            output.append(html.escape(stripped[1:].lstrip()))
            continue

        match = TAG_RE.match(stripped)
        if not match:
            output.append(html.escape(stripped))
            continue

        tag, attrs_raw, inline_text = match.groups()
        attrs = _parse_attrs(attrs_raw)
        inline = html.escape(inline_text) if inline_text else ""

        if tag in VOID_TAGS:
            output.append(f"<{tag}{attrs}>")
            continue

        output.append(f"<{tag}{attrs}>")
        if inline:
            output.append(inline)
        stack.append((indent, tag))

    while stack:
        _, open_tag = stack.pop()
        output.append(f"</{open_tag}>")

    return "\n".join(output) + "\n"

