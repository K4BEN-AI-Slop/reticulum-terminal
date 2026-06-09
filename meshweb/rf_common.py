#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
from typing import List


APP_NAMESPACE = "meshweb"
APP_ROLE = "http"
PROTOCOL_VERSION = 1
MAX_CHUNK_BYTES = 170


def dump_message(message: dict) -> bytes:
    return json.dumps(message, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def load_message(data: bytes) -> dict:
    return json.loads(data.decode("utf-8"))


def chunk_bytes(data: bytes, max_bytes: int = MAX_CHUNK_BYTES) -> List[bytes]:
    if not data:
        return [b""]
    return [data[i : i + max_bytes] for i in range(0, len(data), max_bytes)]


def b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def b64d(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))

