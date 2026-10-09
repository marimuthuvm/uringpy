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

from uringpy import BatchIO, EpollEngine, URingEngine


def _response(body: bytes) -> bytes:
    return (b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(body)).encode()
            + b"\r\nConnection: keep-alive\r\n\r\n" + body)


REQUEST = b"GET /hello HTTP/1.1\r\nHost: x\r\n\r\n"


class Server:
    """Runs one engine in a thread; stop() wakes it with a throwaway connect."""

    def __init__(self, response=None, handler=None, sndbuf=None, kind="uring",
                 max_batch=0, gil_timing=False, gil_batch=False, batch_max=0,
                 expect_error=False):
        self.expect_error = expect_error
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
        if gil_batch:
            self.engine.set_gil_batching(True, batch_max)
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
        if not self.expect_error:
            assert self.error is None, self.error

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.stop()


def settled_stats(engine, requests, timeout=2.0):
    """Counters once the reactor has counted `requests` responses. A client can
    read a response before the server has processed that send's completion, so
    reading the counters straight after the last recv would be a race."""
    deadline = time.time() + timeout
    while True:
        stats = engine.get_stats()
        if stats["requests"] >= requests or time.time() > deadline:
            return stats
        time.sleep(0.005)


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
        stats = settled_stats(srv.engine, 40)
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
        stats = settled_stats(srv.engine, 2)
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
        st = settled_stats(srv.engine, 16 * 20)
    assert st["requests"] == 16 * 20
    # The loop makes exactly one io_uring_enter per iteration; a blocked wait
    # that has not returned yet accounts for the possible difference of one.
    assert st["waits"] <= st["enters"] <= st["waits"] + 1
    # Every request is a recv completion plus a send completion.
    assert st["completions"] >= 2 * st["requests"]


def test_max_batch_caps_completions_per_enter():
    with Server(response=_response(b"Hello, world!"), max_batch=1) as srv:
        _burst(srv)
        capped = settled_stats(srv.engine, 16 * 20)
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


@pytest.mark.parametrize("release_gil", [True, False])
def test_python_loop_flush_with_and_without_gil(release_gil):
    # The Python-level API (submit_* / flush / get_events), as the py-uring
    # benchmark engine uses it. flush() releases the GIL around the submit
    # system call by default and keeps it when asked; both must serve correctly.
    try:
        engine = URingEngine(entries=64, slot_size=4096, total_slots=64)
    except OSError as e:
        pytest.skip(f"io_uring unavailable: {e}")
    ACCEPT, RECV, SEND = 1, 2, 3
    resp = _response(b"Hello, world!")
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    port = listener.getsockname()[1]
    stop = threading.Event()
    served = []

    def loop():
        engine.submit_accept(listener.fileno())
        assert engine.flush(release_gil) >= 1
        while not stop.is_set():
            for op, fd, res, _data in engine.get_events(max_events=64, wait=True,
                                                         copy_data=False):
                if op == ACCEPT:
                    engine.submit_accept(listener.fileno())
                    if res >= 0:
                        engine.submit_recv(res)
                elif op == RECV:
                    if res <= 0:
                        os.close(fd)
                    else:
                        served.append(fd)  # counted here: the client cannot
                        engine.submit_send(fd, resp)  # see a reply before this
                elif op == SEND:
                    engine.submit_recv(fd)
            engine.flush(release_gil)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    c = socket.create_connection(("127.0.0.1", port), timeout=5)
    c.settimeout(5)
    for _ in range(3):
        c.sendall(REQUEST)
        assert recv_exact(c, len(resp)) == resp
    stop.set()
    c.close()  # the close completes a recv, which lets the loop see the flag
    t.join(timeout=5)
    assert not t.is_alive()
    listener.close()
    assert len(served) == 3


@pytest.mark.parametrize("gil_batch", [False, True])
def test_gil_batching_same_responses_fewer_acquisitions(gil_batch):
    # With batching the GIL is taken once for all requests found in one pass
    # over the completion queue; the responses must be exactly the same.
    def handler(data):
        path = data.split(b" ")[1]
        if path.startswith(b"/c0-"):
            time.sleep(0.03)  # stalls the reactor so the other requests pile up
        return _response(b"path=" + path)

    with Server(handler=handler, gil_batch=gil_batch) as srv:
        conns = [srv.connect() for _ in range(24)]
        for rnd in range(3):
            for i, c in enumerate(conns):
                c.sendall(b"GET /c%d-r%d HTTP/1.1\r\n\r\n" % (i, rnd))
            for i, c in enumerate(conns):
                want = _response(b"path=/c%d-r%d" % (i, rnd))
                assert recv_exact(c, len(want)) == want
        for c in conns:
            c.close()
        st = settled_stats(srv.engine, 72)
    assert st["handler_calls"] == 72 and st["handler_errors"] == 0
    assert st["requests"] == 72
    if gil_batch:
        assert st["gil_acquires"] <= st["handler_calls"] // 2
    else:
        assert st["gil_acquires"] == st["handler_calls"]


def test_gil_batching_error_closes_only_that_connection(capfd):
    def handler(data):
        if b"/slow" in data:
            time.sleep(0.05)  # the next two requests arrive during this call
        if b"/boom" in data:
            raise RuntimeError("boom")
        return _response(b"ok")

    want = _response(b"ok")
    with Server(handler=handler, gil_batch=True) as srv:
        slow, bad, good = srv.connect(), srv.connect(), srv.connect()
        slow.sendall(b"GET /slow HTTP/1.1\r\n\r\n")
        time.sleep(0.01)
        bad.sendall(b"GET /boom HTTP/1.1\r\n\r\n")
        good.sendall(REQUEST)
        assert recv_exact(slow, len(want)) == want
        assert bad.recv(1) == b""  # closed by the server
        assert recv_exact(good, len(want)) == want
        good.sendall(REQUEST)  # and still usable
        assert recv_exact(good, len(want)) == want
        for c in (slow, bad, good):
            c.close()
        st = srv.engine.get_stats()
    assert st["handler_errors"] == 1 and st["handler_calls"] == 4
    assert "RuntimeError: boom" in capfd.readouterr().err


def test_gil_batching_timing_and_guards():
    def handler(data):
        time.sleep(0.002)
        return _response(b"ok")

    want = _response(b"ok")
    with Server(handler=handler, gil_timing=True, gil_batch=True) as srv:
        with pytest.raises(RuntimeError):
            srv.engine.set_gil_batching(False)  # not while serving
        c = srv.connect()
        for _ in range(5):
            c.sendall(REQUEST)
            assert recv_exact(c, len(want)) == want
        c.close()
        st = srv.engine.get_stats()
    assert st["handler_calls"] == 5
    assert 5 * 2_000_000 <= st["gil_hold_ns"] < 5 * 200_000_000
    assert st["gil_wait_ns"] < st["gil_hold_ns"]


# --- handler mode on both interfaces, GIL per request and per batch -----------

KINDS = [("uring", False), ("uring", True), ("epoll", False), ("epoll", True)]


@pytest.mark.parametrize("variant", KINDS)
def test_handler_variants_give_the_same_responses(variant):
    kind, gil_batch = variant

    def handler(data):
        path = data.split(b" ")[1]
        if path.startswith(b"/c0-"):
            time.sleep(0.03)  # stalls the reactor so the other requests pile up
        return _response(b"path=" + path)

    with Server(handler=handler, kind=kind, gil_batch=gil_batch) as srv:
        conns = [srv.connect() for _ in range(24)]
        for rnd in range(3):
            for i, c in enumerate(conns):
                c.sendall(b"GET /c%d-r%d HTTP/1.1\r\n\r\n" % (i, rnd))
            for i, c in enumerate(conns):
                want = _response(b"path=/c%d-r%d" % (i, rnd))
                assert recv_exact(c, len(want)) == want
        for c in conns:
            c.close()
        st = settled_stats(srv.engine, 72)
    assert st["handler_calls"] == 72 and st["handler_errors"] == 0
    assert st["requests"] == 72
    if gil_batch:
        assert st["gil_acquires"] <= st["handler_calls"] // 2
    else:
        assert st["gil_acquires"] == st["handler_calls"]


@pytest.mark.parametrize("variant", KINDS)
def test_handler_variants_large_and_failing_responses(variant):
    kind, gil_batch = variant

    def handler(data):
        if b"/boom" in data:
            raise RuntimeError("boom")
        n = int(data.split(b" ")[1][1:])
        return _response(bytes([65 + n % 26]) * n)

    with Server(handler=handler, kind=kind, gil_batch=gil_batch) as srv:
        a, b, bad = srv.connect(), srv.connect(), srv.connect()
        a.sendall(b"GET /300000 HTTP/1.1\r\n\r\n")   # needs several sends
        b.sendall(b"GET /7 HTTP/1.1\r\n\r\n")
        bad.sendall(b"GET /boom HTTP/1.1\r\n\r\n")
        want_a = _response(bytes([65 + 300000 % 26]) * 300000)
        want_b = _response(bytes([65 + 7]) * 7)
        assert recv_exact(b, len(want_b)) == want_b
        assert recv_exact(a, len(want_a)) == want_a
        assert bad.recv(1) == b""          # only the failing connection is closed
        a.sendall(b"GET /5 HTTP/1.1\r\n\r\n")          # and the others still work
        want = _response(bytes([65 + 5]) * 5)
        assert recv_exact(a, len(want)) == want
        for c in (a, b, bad):
            c.close()
        assert srv.engine.get_stats()["handler_errors"] == 1


@pytest.mark.parametrize("variant", KINDS)
def test_keyboard_interrupt_in_handler_stops_the_reactor_and_propagates(variant):
    # KeyboardInterrupt and SystemExit are not handler failures. They must not
    # be swallowed at the C boundary (which would send a stale buffer): the
    # connection is closed and serve_forever_app() raises the exception.
    kind, gil_batch = variant
    seen = []

    def handler(data):
        seen.append(data)
        if b"/interrupt" in data:
            raise KeyboardInterrupt
        return _response(b"ok")

    want = _response(b"ok")
    srv = Server(handler=handler, kind=kind, gil_batch=gil_batch, expect_error=True)
    c = srv.connect()
    c.sendall(REQUEST)
    assert recv_exact(c, len(want)) == want
    c.sendall(b"GET /interrupt HTTP/1.1\r\n\r\n")
    assert c.recv(1) == b""                # closed, no stale response
    srv.thread.join(timeout=5)
    assert not srv.thread.is_alive(), "reactor did not stop"
    assert isinstance(srv.error, KeyboardInterrupt)
    c.close()
    srv.listener.close()
    assert len(seen) == 2


@pytest.mark.parametrize("batch_max", [1, 4])
def test_gil_batching_request_cap(batch_max):
    # set_gil_batching(True, n): at most n requests per GIL acquisition.
    def handler(data):
        path = data.split(b" ")[1]
        if path.startswith(b"/c0-"):
            time.sleep(0.03)
        return _response(b"path=" + path)

    with Server(handler=handler, gil_batch=True, batch_max=batch_max) as srv:
        conns = [srv.connect() for _ in range(24)]
        for rnd in range(3):
            for i, c in enumerate(conns):
                c.sendall(b"GET /c%d-r%d HTTP/1.1\r\n\r\n" % (i, rnd))
            for i, c in enumerate(conns):
                want = _response(b"path=/c%d-r%d" % (i, rnd))
                assert recv_exact(c, len(want)) == want
        for c in conns:
            c.close()
        st = settled_stats(srv.engine, 72)
    assert st["handler_calls"] == 72
    assert st["gil_acquires"] >= 72 // batch_max          # the cap is respected
    if batch_max == 1:
        assert st["gil_acquires"] == 72
    else:
        assert st["gil_acquires"] < 72                    # and batching still happens


def test_batch_io_serves_queued_sockets_in_one_call():
    # BatchIO: the helper behind the py-epoll-batch benchmark engine.
    resp = _response(b"Hello, world!")
    io = BatchIO()
    with pytest.raises(RuntimeError):
        io.run()                                   # no response set yet
    io.set_response(resp)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    port = listener.getsockname()[1]
    clients, server_fds = [], []
    for _ in range(3):
        c = socket.create_connection(("127.0.0.1", port), timeout=5)
        c.settimeout(5)
        conn, _addr = listener.accept()
        conn.setblocking(False)
        clients.append(c)
        server_fds.append(conn.detach())           # BatchIO owns the socket now
    for c in clients:
        c.sendall(REQUEST)
    time.sleep(0.05)
    for fd in server_fds:
        io.queue(fd)
    assert io.run() == 3
    for c in clients:
        assert recv_exact(c, len(resp)) == resp
    # A socket with nothing to read is skipped; one whose peer closed is closed.
    clients[0].close()
    time.sleep(0.05)
    io.queue(server_fds[0])
    io.queue(server_fds[1])
    assert io.run() == 0
    with pytest.raises(OSError):
        os.fstat(server_fds[0])                    # closed by BatchIO
    os.fstat(server_fds[1])                        # still open
    st = io.get_stats()
    assert st["requests"] == 3 and st["runs"] == 2
    # 3 recv + 3 send, then recv + close for the closed peer and one recv (EAGAIN)
    assert st["syscalls"] == 9
    for c in clients[1:]:
        c.close()
    for fd in server_fds[1:]:
        os.close(fd)
    listener.close()
