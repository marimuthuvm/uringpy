#!/usr/bin/env python3
"""Correctness demo for io_uring provided buffer rings + multishot receive.

Registers a provided-buffer ring, arms a single multishot recv, sends several
datagrams, and verifies each completion returns the correct payload from the
kernel-selected buffer. Datagram boundaries make the 1-send -> 1-completion
mapping unambiguous. Proves the mechanism works end to end.

Run inside the container (io_uring >= 5.19 required):
    python3 benchmarks/pbuf_demo.py
"""

from __future__ import annotations

import socket
import sys

RECV = 2  # matches the op encoding in URingEngine


def main():
    try:
        from uringpy import URingEngine
    except Exception as e:  # noqa: BLE001
        print(f"uringpy unavailable: {e}")
        return 1

    engine = URingEngine(entries=256, slot_size=4096, total_slots=16)
    try:
        engine.setup_provided_buffers(nentries=64, buf_size=2048, bgid=1)
    except OSError as e:
        print(f"provided buffer rings unavailable (kernel too old?): {e}")
        return 1

    reader, writer = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
    reader.setblocking(True)
    writer.setblocking(True)

    engine.arm_multishot_recv(reader.fileno())

    msgs = [f"provided-buffer-msg-{i}".encode() for i in range(6)]
    for m in msgs:
        writer.send(m)

    received = []
    rearms = 0
    while len(received) < len(msgs):
        for fd, res, data, more in engine.get_buf_events(wait=True):
            if res > 0 and data is not None:
                received.append(bytes(data))
            if not more:
                engine.arm_multishot_recv(reader.fileno())  # multishot ended; re-arm
                rearms += 1

    reader.close()
    writer.close()

    ok = received == msgs
    print("sent    :", msgs)
    print("received:", received)
    print("re-arms :", rearms)
    print("RESULT  :", "PASS - provided buffer rings work" if ok else "FAIL - data mismatch")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
