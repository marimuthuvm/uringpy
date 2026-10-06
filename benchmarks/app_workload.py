#!/usr/bin/env python3
"""Realistic per-request work shared by the uringpy-app and asyncio-app servers.

Both engines call this identical handler, so the comparison isolates *where* the
per-request Python work runs, not what it does. It parses the HTTP request line
and computes a small path-dependent checksum -- representative of real routing /
application logic, unlike the canned-echo path.
"""

from __future__ import annotations

import os

_HDR = (b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        b"Connection: keep-alive\r\n"
        b"Content-Length: ")

# Pad the response body to RESP_SIZE bytes (0 = natural size) for the size sweep.
_PAD_TO = int(os.environ.get("RESP_SIZE") or 0)

# HANDLER_WORK=<n> adds n iterations of pure-Python arithmetic to every request
# (default 0). The handler-cost sweep uses it to vary how long each request
# holds the GIL while everything else stays the same.
_WORK = int(os.environ.get("HANDLER_WORK") or 0)


def handle_request(data: bytes) -> bytes:
    """Parse the request line, do a little work, return a full HTTP response."""
    line_end = data.find(b"\r\n")
    path = b"/"
    if line_end > 0:
        parts = data[:line_end].split(b" ")
        if len(parts) >= 2:
            path = parts[1]
    acc = 0
    for c in path:  # per-request Python work (a path checksum)
        acc = (acc * 131 + c) & 0xFFFFFFFF
    body = b'{"path":"' + path + b'","h":' + str(acc).encode() + b'}'
    if _PAD_TO and len(body) < _PAD_TO:
        body += b" " * (_PAD_TO - len(body))
    return _HDR + str(len(body)).encode() + b"\r\n\r\n" + body


def _handle_request_with_work(data: bytes) -> bytes:
    """handle_request plus _WORK extra iterations of interpreted arithmetic."""
    acc = 0
    for i in range(_WORK):
        acc = (acc * 131 + i) & 0xFFFFFFFF
    return _base_handle_request(data)


# With HANDLER_WORK unset the handler is exactly the function above, untouched.
_base_handle_request = handle_request
if _WORK > 0:
    handle_request = _handle_request_with_work
