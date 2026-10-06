"""End-to-end tests for the C reactors: URingEngine.serve_forever_echo / _app
and the epoll twin EpollEngine.serve_forever_echo.

Each test starts a real engine on a loopback port in a background thread and
talks to it over plain sockets. Skipped where io_uring is unavailable.
"""

import os
import signal
import socket
import subprocess
import sys
import textwrap
import threading
import time

import pytest

from uringpy import EpollEngine, URingEngine


def _response(body: bytes) -> bytes:
    return (b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(body)).encode()
            + b"\r\nConnection: keep-alive\r\n\r\n" + body)


REQUEST = b"GET /hello HTTP/1.1\r\nHost: x\r\n\r\n"


class Server:
    """Runs one engine in a thread; stop() wakes it with a throwaway connect."""

    def __init__(self, response=None, handler=None, sndbuf=None, kind="uring",
                 max_batch=0, gil_timing=False):
        if kind == "epoll":
            self.engine = EpollEngine()
        else:
            try:
                self.engine = URingEngine(entries=256, slot_size=4096, total_slots=256)
            except OSError as e:
                pytest.skip(f"io_uring unavailable: {e}")
            if max_batch:
                self.engine.set_max_batch(max_batch)
            if gil_timing:
                self.engine.set_gil_timing(True)
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if sndbuf:  # inherited by accepted sockets
            self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, sndbuf)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(64)
        self.port = self.listener.getsockname()[1]
        self.error = None
        if handler is None:
            self.engine.set_response(response)
            target = lambda: self.engine.serve_forever_echo(self.listener.fileno())
        else:
            target = lambda: self.engine.serve_forever_app(self.listener.fileno(), handler)

        def run():
            try:
                target()
            except BaseException as e:  # surfaced by the test via .error
                self.error = e

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def connect(self):
        s = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        s.settimeout(5)
        return s

    def stop(self):
        self.engine.stop()
        try:  # one more completion so the loop re-checks the stop flag
            self.connect().close()
        except OSError:
            pass
        self.thread.join(timeout=5)
        assert not self.thread.is_alive(), "reactor did not stop"
        self.listener.close()
        assert self.error is None, self.error

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.stop()


def recv_exact(sock, n):
    chunks, got = [], 0
    while got < n:
        chunk = sock.recv(min(65536, n - got))
        if not chunk:
            break
        chunks.append(chunk)
        got += len(chunk)
    return b"".join(chunks)


@pytest.mark.parametrize("kind", ["uring", "epoll"])
def test_echo_keepalive_and_many_connections(kind):
    resp = _response(b"Hello, world!")
    with Server(response=resp, kind=kind) as srv:
        conns = [srv.connect() for _ in range(8)]
        for _ in range(5):  # several requests per connection (keep-alive)
            for c in conns:
                c.sendall(REQUEST)
            for c in conns:
                assert recv_exact(c, len(resp)) == resp
        for c in conns:
            c.close()
        stats = srv.engine.get_stats()
    assert stats["requests"] == 40
    assert stats["syscalls"] > 0 and stats["syscalls_per_request"] > 0


@pytest.mark.parametrize("size", [1, 4096, 4097, 65536, 1 << 20])
def test_echo_large_response_is_sent_in_full(size):
    # Responses larger than a slab slot / the socket buffer need several sends.
    body = bytes(i % 251 for i in range(size))
    resp = _response(body)
    for kind in ("uring", "epoll"):
        with Server(response=resp, kind=kind) as srv:
            c = srv.connect()
            for _ in range(2):
                c.sendall(REQUEST)
                assert recv_exact(c, len(resp)) == resp
            c.close()


def test_epoll_short_sends_are_resumed():
    resp = _response(bytes(i % 251 for i in range(1 << 20)))
    with Server(response=resp, kind="epoll", sndbuf=4096) as srv:
        c = srv.connect()
        for _ in range(2):
            c.sendall(REQUEST)
            time.sleep(0.3)
            assert recv_exact(c, len(resp)) == resp
        c.close()
        stats = srv.engine.get_stats()
    assert stats["requests"] == 2
    # 2 recv + 2 send would be 4 I/O calls; many more means sends were split.
    assert stats["syscalls"] > 20


def _burst(srv, n_conn=16, rounds=20):
    resp = _response(b"Hello, world!")
    conns = [srv.connect() for _ in range(n_conn)]
    for _ in range(rounds):
        for c in conns:
            c.sendall(REQUEST)
        for c in conns:
            assert recv_exact(c, len(resp)) == resp
    for c in conns:
        c.close()


def test_one_enter_per_wait_and_exact_counters():
    with Server(response=_response(b"Hello, world!")) as srv:
        _burst(srv)
        st = srv.engine.get_stats()
    assert st["requests"] == 16 * 20
    # The loop makes exactly one io_uring_enter per iteration; a blocked wait
    # that has not returned yet accounts for the possible difference of one.
    assert st["waits"] <= st["enters"] <= st["waits"] + 1
    # Every request is a recv completion plus a send completion.
    assert st["completions"] >= 2 * st["requests"]


def test_max_batch_caps_completions_per_enter():
    with Server(response=_response(b"Hello, world!"), max_batch=1) as srv:
        _burst(srv)
        capped = srv.engine.get_stats()
    assert capped["requests"] == 16 * 20
    # With a cap of 1, no io_uring_enter may yield more than one completion.
    assert capped["completions"] <= capped["enters"]
    assert capped["completions_per_enter"] <= 1.0


@pytest.mark.parametrize("app", [False, True])
def test_short_sends_are_resumed(app):
    # A tiny send buffer and a slow reader force the kernel to complete the
    # send in pieces; the reactor must resume from the right offset.
    resp = _response(bytes(i % 251 for i in range(1 << 20)))
    kw = {"handler": (lambda data: resp)} if app else {"response": resp}
    with Server(sndbuf=4096, **kw) as srv:
        c = srv.connect()
        c.sendall(REQUEST)
        time.sleep(0.3)  # let the server fill the socket before we read
        assert recv_exact(c, len(resp)) == resp
        c.sendall(REQUEST)  # the connection is still usable afterwards
        assert recv_exact(c, len(resp)) == resp
        c.close()
        # accept + 2 recv + 2 send would be 5; more means sends were split.
        assert srv.engine.get_stats()["completions"] > 5


@pytest.mark.parametrize("kind", ["uring", "epoll"])
def test_signal_handler_runs_while_serving_on_main_thread(kind):
    # The reactor blocks in C with the GIL released. A Python signal handler
    # must still run (and may raise) when the wait is interrupted -- this is
    # how a process-mode worker is shut down.
    child = textwrap.dedent("""
        import signal, socket, sys
        from uringpy import EpollEngine, URingEngine
        def term(*_):
            sys.exit(7)
        signal.signal(signal.SIGTERM, term)
        lst = socket.socket()
        lst.bind(("127.0.0.1", 0)); lst.listen(8)
        try:
            eng = (EpollEngine() if sys.argv[1] == "epoll" else
                   URingEngine(entries=64, slot_size=1024, total_slots=64))
        except OSError:
            print("skip", flush=True); sys.exit(0)
        eng.set_response(b"x")
        print("ready", flush=True)
        eng.serve_forever_echo(lst.fileno())
    """)
    proc = subprocess.Popen([sys.executable, "-c", child, kind], stdout=subprocess.PIPE,
                            env=dict(os.environ))
    try:
        line = proc.stdout.readline().strip()
        if line == b"skip":
            pytest.skip("io_uring unavailable")
        assert line == b"ready"
        time.sleep(0.2)  # now parked in io_uring_enter
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=5) == 7
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.stdout.close()


def test_set_response_rejects_bad_sizes():
    with pytest.raises(ValueError):
        EpollEngine().set_response(b"")
    try:
        engine = URingEngine(entries=64, slot_size=1024, total_slots=64)
    except OSError as e:
        pytest.skip(f"io_uring unavailable: {e}")
    with pytest.raises(ValueError):
        engine.set_response(b"")


def test_app_handler_sees_request_and_controls_response():
    seen = []

    def handler(data):
        seen.append(data)
        return _response(b"path=" + data.split(b" ")[1])

    with Server(handler=handler) as srv:
        c = srv.connect()
        for path in (b"/a", b"/bb", b"/ccc"):
            c.sendall(b"GET " + path + b" HTTP/1.1\r\n\r\n")
            want = _response(b"path=" + path)
            assert recv_exact(c, len(want)) == want
        c.close()
        stats = srv.engine.get_stats()
    assert len(seen) == 3 and seen[0].startswith(b"GET /a ")
    assert stats["handler_calls"] == 3 and stats["handler_errors"] == 0


def test_app_per_connection_responses_do_not_mix():
    # Two connections with different-sized pending responses at the same time.
    def handler(data):
        n = int(data.split(b" ")[1][1:])
        return _response(bytes([65 + n % 26]) * n)

    with Server(handler=handler) as srv:
        a, b = srv.connect(), srv.connect()
        a.sendall(b"GET /300000 HTTP/1.1\r\n\r\n")
        b.sendall(b"GET /7 HTTP/1.1\r\n\r\n")
        want_b = _response(bytes([65 + 7]) * 7)
        want_a = _response(bytes([65 + 300000 % 26]) * 300000)
        assert recv_exact(b, len(want_b)) == want_b
        assert recv_exact(a, len(want_a)) == want_a
        a.close()
        b.close()


def test_app_handler_error_closes_only_that_connection(capfd):
    def handler(data):
        if b"/boom" in data:
            raise RuntimeError("boom")
        if b"/notbytes" in data:
            return "a str, not bytes"
        return _response(b"ok")

    with Server(handler=handler) as srv:
        bad = srv.connect()
        bad.sendall(b"GET /boom HTTP/1.1\r\n\r\n")
        assert bad.recv(1) == b""  # server closed it
        bad.close()

        bad2 = srv.connect()
        bad2.sendall(b"GET /notbytes HTTP/1.1\r\n\r\n")
        assert bad2.recv(1) == b""
        bad2.close()

        good = srv.connect()  # the reactor is still serving
        good.sendall(REQUEST)
        want = _response(b"ok")
        assert recv_exact(good, len(want)) == want
        good.close()
        assert srv.engine.get_stats()["handler_errors"] == 2
    assert "RuntimeError: boom" in capfd.readouterr().err


@pytest.mark.parametrize("enabled", [False, True])
def test_gil_timing_counts_only_when_enabled(enabled):
    def handler(data):
        time.sleep(0.002)  # held with the GIL from the reactor's point of view
        return _response(b"ok")

    want = _response(b"ok")
    with Server(handler=handler, gil_timing=enabled) as srv:
        c = srv.connect()
        for _ in range(5):
            c.sendall(REQUEST)
            assert recv_exact(c, len(want)) == want
        c.close()
        st = srv.engine.get_stats()
    assert st["handler_calls"] == 5
    if enabled:
        # Five calls of at least 2 ms each, and not absurdly more.
        assert 5 * 2_000_000 <= st["gil_hold_ns"] < 5 * 200_000_000
        assert st["gil_wait_ns"] < st["gil_hold_ns"]
    else:
        assert st["gil_hold_ns"] == 0 and st["gil_wait_ns"] == 0


def test_app_rejects_non_callable():
    try:
        engine = URingEngine(entries=64, slot_size=1024, total_slots=64)
    except OSError as e:
        pytest.skip(f"io_uring unavailable: {e}")
    with pytest.raises(TypeError):
        engine.serve_forever_app(0, "not callable")
