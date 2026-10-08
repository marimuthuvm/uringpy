"""uringpy._gilstat reads CPython's own count of GIL hand-offs between threads."""
import socket
import sys
import threading

import pytest

gilstat = pytest.importorskip("uringpy._gilstat")
GIL_ON = getattr(sys, "_is_gil_enabled", lambda: True)()
needs_gil = pytest.mark.skipif(not GIL_ON, reason="no GIL in this interpreter")


@needs_gil
def test_one_thread_makes_no_handoffs():
    before = gilstat.switch_count()
    total = 0
    for i in range(200_000):
        total += i
    assert gilstat.switch_count() == before


@needs_gil
def test_ping_pong_hands_the_gil_over_twice_per_round_trip():
    # Each message wakes the other thread, which must take the GIL from the
    # sender: two changes of owner per round trip.
    a, b = socket.socketpair()
    c, d = socket.socketpair()
    rounds = 2000

    def ping():
        for _ in range(rounds):
            a.send(b"x")
            d.recv(1)

    def pong():
        for _ in range(rounds):
            b.recv(1)
            c.send(b"y")

    before = gilstat.switch_count()
    threads = [threading.Thread(target=ping), threading.Thread(target=pong)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    per_round = (gilstat.switch_count() - before) / rounds
    for s in (a, b, c, d):
        s.close()
    assert 1.9 <= per_round <= 2.2
