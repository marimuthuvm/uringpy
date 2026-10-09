#!/usr/bin/env python3
"""
Multi-worker sharded HTTP server -- the server side of every experiment.

N workers each own a SO_REUSEPORT listener on the same port, so the kernel
shards connections across workers. All engines reply once per recv() with the
same bytes, so they differ only in how the I/O loop is built.

Engines (--engine):

  The 2x2 ablation: kernel interface x where the per-event loop runs.

                    | loop in C, GIL released | loop in Python
    ----------------+-------------------------+----------------
    io_uring        | uringpy                 | py-uring
    epoll           | c-epoll                 | py-epoll

    uringpy   URingEngine.serve_forever_echo(): whole protocol in one nogil
              C region.
    c-epoll   EpollEngine.serve_forever_echo(): the same C loop on epoll, one
              recv() and one send() system call per request.
    py-uring  URingEngine.get_events(): io_uring batching, every completion
              dispatched by Python bytecode. The GIL is released while waiting
              and while submitting, i.e. twice per batch.
    py-epoll  select.epoll with a minimal Python loop. CPython releases the
              GIL around each of its system calls, i.e. about twice per
              request.

  Two more Python loops, each differing from a cell above in one thing only.
  They are not cells of the design; they separate "how often the GIL is given
  up" and "what runs while it is held" from the interface and the language:

    py-epoll-batch  py-epoll with the recv() and send() of every ready socket
              done by one C call that releases the GIL once (BatchIO): the
              same interface and the same two system calls per request as
              py-epoll, but the GIL is given up twice per pass, like py-uring.
    py-uring-held   py-uring holding the GIL while it submits (the kernel does
              the queued sends inside that call): as few GIL releases as
              py-uring, but most of a request's processor time under the GIL.

    (The Python loops send each response with a single send, so they are for
    small responses only.)

  Existing event loops (asyncio streams server, loop implementation swapped):
    asyncio   stdlib loop          uvloop     libuv-based loop
    uringcore io_uring loop        uringloop  io_uring loop
    (the last three are used only if installed in the image)

  The same loops through asyncio's Protocol API instead of streams -- no
  StreamReader/StreamWriter layer, the reply is written from data_received.
  This is the fastest way to use an asyncio loop and so the stronger baseline.
    asyncio-proto   stdlib loop    uvloop-proto   libuv-based loop

  Application workload: every request goes through the same Python handler
  (app_workload.handle_request).
    uringpy-app  URingEngine.serve_forever_app(): transport in C, GIL taken
                 only for the handler call, once per request.
    uringpy-app-batch  the same, with the GIL taken once for all requests
                 found in one pass over the completion queue.
    uringpy-app-batch<N>  (N = 1, 2, 4, 8, 16, 64) the same, with at most N
                 requests served per GIL acquisition.
    c-epoll-app, c-epoll-app-batch  EpollEngine.serve_forever_app(): the same
                 two variants on epoll, to see whether GIL batching depends on
                 the interface.
    asyncio-app  handler called inside the asyncio stream handler.
    asyncio-proto-app, uvloop-proto-app  handler called from data_received of
                 the Protocol API, the faster way to use either loop.

Modes (--mode):
  thread    all workers in ONE process/interpreter (shared GIL).
  process   one process per worker (independent GILs).

Usage:
    python3 benchmarks/sharded_server.py --engine uringpy --mode thread  --workers 4
    python3 benchmarks/sharded_server.py --engine asyncio --mode process --workers 4

Env:
  URINGPY_STATS=1        print each worker's counters on exit, one line per
                         worker: "[worker N] key=value ...".
  RESP_SIZE=<bytes>      response body size (default: the 13-byte
                         "Hello, world!"). The echo engines send a body of
                         exactly that size; the app engines pad the handler's
                         JSON body up to it (see app_workload.py).
  HANDLER_WORK=<n>       app engines: n extra iterations of Python arithmetic
                         per request (see app_workload.py).
  URINGPY_GIL_TIMING=1   uringpy-app only: record per-request GIL wait and
                         hold time (gil_wait_ns / gil_hold_ns in the counters).
  URINGPY_MAX_BATCH=<n>  uringpy / uringpy-app only: process at most n
                         completions per io_uring_enter (0 = unlimited).
"""

from __future__ import annotations

import argparse
import os
import resource
import signal
import socket
import sys
import threading
import time


def _echo_body():
    # RESP_SIZE unset or 13 gives the original b"Hello, world!" byte for byte.
    base = b"Hello, world!"
    size = int(os.environ.get("RESP_SIZE") or 0)
    if size <= 0:
        return base
    return (base * (size // len(base) + 1))[:size]


_BODY = _echo_body()
HTTP_RESPONSE = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: text/plain\r\n"
    b"Content-Length: " + str(len(_BODY)).encode() + b"\r\n"
    b"Connection: keep-alive\r\n"
    b"\r\n" + _BODY
)

STATS = os.environ.get("URINGPY_STATS", "0") == "1"
MAX_BATCH = int(os.environ.get("URINGPY_MAX_BATCH") or 0)
GIL_TIMING = os.environ.get("URINGPY_GIL_TIMING", "0") == "1"

# (wid, get_stats) for every worker in THIS process that keeps counters, so the
# shutdown handler can print them.
_STAT_SOURCES = []


def _fmt(value):
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def _gil_switches():
    """How often this interpreter's GIL was taken by a thread other than its
    previous holder: CPython's own counter, read by uringpy._gilstat. None
    where it cannot be read (module not built, or no GIL)."""
    try:
        from uringpy import _gilstat
    except ImportError:
        return None
    return _gilstat.switch_count()


def _print_stats():
    # CPU time (user + system) this process has used, for cost-per-request,
    # and its context switches: a thread that has to wait for the GIL sleeps,
    # which the kernel counts as a voluntary context switch. gil_switches is
    # the number of times the GIL changed owner, counted by the interpreter.
    ru = resource.getrusage(resource.RUSAGE_SELF)
    switches = _gil_switches()
    extra = f" gil_switches={switches}" if switches is not None else ""
    print(f"[proc] cpu_ns={time.process_time_ns()} nvcsw={ru.ru_nvcsw} "
          f"nivcsw={ru.ru_nivcsw}{extra}", flush=True)
    for wid, get_stats in _STAT_SOURCES:
        stats = get_stats()
        print(f"[worker {wid}] " + " ".join(f"{k}={_fmt(v)}" for k, v in stats.items()),
              flush=True)


def _install_term_handler():
    # signal.signal() only works in the main thread. In --mode process every
    # worker IS its process's main thread and installs this itself; in --mode
    # thread the parent installs it once for the whole process (see run()).
    if threading.current_thread() is not threading.main_thread():
        return

    def _term(*_):
        if STATS:
            _print_stats()
        os._exit(0)

    signal.signal(signal.SIGTERM, _term)
    signal.signal(signal.SIGINT, _term)


def make_reuseport_listener(host, port, backlog=1024):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    # Accepted sockets inherit TCP_NODELAY from the listener on Linux. asyncio
    # and uvloop set it on every connection; setting it here gives every engine
    # the same socket options.
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.bind((host, port))
    sock.listen(backlog)
    return sock


# --- C reactors ---------------------------------------------------------------

def uringpy_worker(host, port, wid, app=False, gil_batch=False, batch_max=0):
    """io_uring, loop in C. app=True calls the shared Python handler per request;
    gil_batch=True takes the GIL once per batch of requests instead of once per
    request, serving at most batch_max requests per acquisition (0 = no cap)."""
    from uringpy import URingEngine

    listener = make_reuseport_listener(host, port)
    engine = URingEngine(entries=8192, slot_size=4096, total_slots=32768)
    if MAX_BATCH:
        engine.set_max_batch(MAX_BATCH)
    if app:
        from app_workload import handle_request
        if GIL_TIMING:
            engine.set_gil_timing(True)
        if gil_batch:
            engine.set_gil_batching(True, batch_max)
    else:
        engine.set_response(HTTP_RESPONSE)
    _STAT_SOURCES.append((wid, engine.get_stats))
    _install_term_handler()
    if app:
        engine.serve_forever_app(listener.fileno(), handle_request)
    else:
        engine.serve_forever_echo(listener.fileno())


def c_epoll_worker(host, port, wid, app=False, gil_batch=False):
    """epoll, loop in C: the same reactor as uringpy on the readiness interface,
    with the same two handler variants."""
    from uringpy import EpollEngine

    listener = make_reuseport_listener(host, port)
    engine = EpollEngine()
    if app:
        from app_workload import handle_request
        if GIL_TIMING:
            engine.set_gil_timing(True)
        if gil_batch:
            engine.set_gil_batching(True)
    else:
        engine.set_response(HTTP_RESPONSE)
    _STAT_SOURCES.append((wid, engine.get_stats))
    _install_term_handler()
    if app:
        engine.serve_forever_app(listener.fileno(), handle_request)
    else:
        engine.serve_forever_echo(listener.fileno())


# --- Python-dispatch loops ----------------------------------------------------

def py_uring_worker(host, port, wid, release_gil=True):
    """io_uring, loop in Python: completions are batched by the kernel but each
    one is dispatched by interpreted code."""
    from uringpy import URingEngine

    ACCEPT, RECV, SEND = 1, 2, 3
    listener = make_reuseport_listener(host, port)
    lfd = listener.fileno()
    # submit_send copies the response into one buffer slot, so it must fit.
    slot = max(4096, len(HTTP_RESPONSE))
    engine = URingEngine(entries=8192, slot_size=slot,
                         total_slots=32768 if slot == 4096 else 2048)
    counters = {"requests": 0}

    def get_stats():
        st = engine.get_stats()
        # get_events issues at most one io_uring_enter per wait and flush()
        # exactly one, so waits + submits is an upper bound on system calls.
        syscalls = st["waits"] + st["submits"]
        req = counters["requests"]
        # GIL releases: one per get_events(wait=True), and one per flush()
        # unless this is the variant that holds the GIL while submitting.
        releases = st["waits"] + (st["submits"] if release_gil else 0)
        return {"completions_per_wait": st["completions_per_wait"],
                "waits": st["waits"], "completions": st["completions"],
                "requests": req, "syscalls": syscalls, "gil_releases": releases,
                "syscalls_per_request": (syscalls / req) if req else 0.0}

    _STAT_SOURCES.append((wid, get_stats))
    _install_term_handler()

    engine.submit_accept(lfd)
    engine.flush(release_gil)
    resp = HTTP_RESPONSE
    while True:
        try:
            events = engine.get_events(max_events=1024, wait=True, copy_data=False)
        except InterruptedError:
            continue  # a signal arrived; its handler runs on the next bytecode
        for op, fd, res, _data in events:
            if op == ACCEPT:
                engine.submit_accept(lfd)
                if res >= 0:
                    engine.submit_recv(res)
            elif op == RECV:
                if res <= 0:
                    os.close(fd)
                else:
                    engine.submit_send(fd, resp)
            elif op == SEND:
                if res <= 0:
                    os.close(fd)
                else:
                    counters["requests"] += 1
                    engine.submit_recv(fd)
        engine.flush(release_gil)


def py_epoll_worker(host, port, wid):
    """epoll, loop in Python: a minimal readiness loop, one recv() and one
    send() per request, all dispatched by interpreted code."""
    import select

    listener = make_reuseport_listener(host, port)
    listener.setblocking(False)
    lfd = listener.fileno()
    ep = select.epoll()
    ep.register(lfd, select.EPOLLIN)
    conns = {}
    counters = {"requests": 0, "syscalls": 1, "waits": 0, "events": 0}

    def get_stats():
        req = counters["requests"]
        out = dict(counters)
        # Every system call this loop makes goes through CPython, which
        # releases the GIL around it.
        out["gil_releases"] = counters["syscalls"]
        out["events_per_wait"] = (counters["events"] / counters["waits"]
                                  if counters["waits"] else 0.0)
        out["syscalls_per_request"] = (counters["syscalls"] / req) if req else 0.0
        return out

    _STAT_SOURCES.append((wid, get_stats))
    _install_term_handler()

    resp = HTTP_RESPONSE
    while True:
        events = ep.poll()
        counters["syscalls"] += 1
        counters["waits"] += 1
        counters["events"] += len(events)
        for fd, _what in events:
            if fd == lfd:
                while True:
                    try:
                        conn, _addr = listener.accept()
                        counters["syscalls"] += 1
                    except BlockingIOError:
                        counters["syscalls"] += 1
                        break
                    conn.setblocking(False)
                    conns[conn.fileno()] = conn
                    ep.register(conn.fileno(), select.EPOLLIN)
                    counters["syscalls"] += 1
                continue
            conn = conns.get(fd)
            if conn is None:
                continue
            try:
                data = conn.recv(4096)
                counters["syscalls"] += 1
                if data:
                    conn.send(resp)
                    counters["syscalls"] += 1
                    counters["requests"] += 1
                    continue
            except BlockingIOError:
                continue
            except OSError:
                pass
            del conns[fd]
            conn.close()  # also removes it from the epoll set
            counters["syscalls"] += 1


def py_epoll_batch_worker(host, port, wid):
    """epoll, loop in Python, I/O batched in C: the loop of py_epoll_worker,
    except that the recv() and send() of all ready sockets are done by one
    BatchIO.run() call, which releases the GIL once. Same interface and same
    two system calls per request as py-epoll; the GIL is given up twice per
    pass over the ready list (epoll.poll and run) instead of twice per request.
    Each ready socket is still dispatched by interpreted code (one queue()
    call), as each completion is in py-uring."""
    import select
    from uringpy import BatchIO

    listener = make_reuseport_listener(host, port)
    listener.setblocking(False)
    lfd = listener.fileno()
    ep = select.epoll()
    ep.register(lfd, select.EPOLLIN)
    io = BatchIO()
    io.set_response(HTTP_RESPONSE)
    # Counted here: the system calls made from Python (each releases the GIL).
    counters = {"syscalls": 1, "waits": 0, "events": 0}

    def get_stats():
        st = io.get_stats()
        req = st["requests"]
        syscalls = counters["syscalls"] + st["syscalls"]
        return {"requests": req, "syscalls": syscalls, "waits": counters["waits"],
                "events": counters["events"],
                "gil_releases": counters["syscalls"] + st["runs"],
                "events_per_wait": (counters["events"] / counters["waits"]
                                    if counters["waits"] else 0.0),
                "syscalls_per_request": (syscalls / req) if req else 0.0}

    _STAT_SOURCES.append((wid, get_stats))
    _install_term_handler()

    queue, run = io.queue, io.run
    while True:
        events = ep.poll()
        counters["syscalls"] += 1
        counters["waits"] += 1
        counters["events"] += len(events)
        for fd, _what in events:
            if fd == lfd:
                while True:
                    try:
                        conn, _addr = listener.accept()
                        counters["syscalls"] += 1
                    except BlockingIOError:
                        counters["syscalls"] += 1
                        break
                    conn.setblocking(False)
                    cfd = conn.detach()  # BatchIO owns and closes the socket
                    ep.register(cfd, select.EPOLLIN)
                    counters["syscalls"] += 1
                continue
            queue(fd)
        run()


# --- asyncio-family event loops -----------------------------------------------

def _new_loop(name):
    import asyncio

    if name == "uvloop":
        import uvloop
        return uvloop.new_event_loop()
    if name == "uringcore":
        import uringcore
        # uringcore's loop creates its engine with default settings, and the
        # default buffer pool runs out ("No buffers available") once a few
        # hundred connections are open, which ends the loop. The engine has a
        # buffer_count parameter, but the loop class does not pass one on, so
        # the constructor the loop calls is wrapped. Set by the run script
        # through URINGCORE_BUFFER_COUNT; without it nothing is changed.
        count = int(os.environ.get("URINGCORE_BUFFER_COUNT") or 0)
        if count:
            import functools
            import uringcore.loop as uring_loop
            if not isinstance(uring_loop.UringCore, functools.partial):
                uring_loop.UringCore = functools.partial(uring_loop.UringCore,
                                                         buffer_count=count)
        loop = uringcore.EventLoopPolicy().new_event_loop()
        if count and not getattr(_new_loop, "reported", False):
            _new_loop.reported = True
            try:
                stats = loop.get_buffer_stats()
            except Exception as e:      # the statistics are for the log only
                stats = f"unavailable ({e})"
            print(f"[uringcore] buffer_count={count} buffer statistics: {stats}",
                  file=sys.stderr, flush=True)
        return loop
    if name == "uringloop":
        import uringloop
        # The loop class has been published under several names; 0.1.0 calls
        # it IouringProactorEventLoop.
        for name in ("IouringProactorEventLoop", "IoUringProactorEventLoop",
                     "URingEventLoop"):
            factory = getattr(uringloop, name, None)
            if factory is not None:
                return factory()
        raise AttributeError("uringloop: no event loop class found among "
                             + ", ".join(n for n in dir(uringloop) if not n.startswith("_")))
    return asyncio.new_event_loop()


def asyncio_worker(host, port, wid, app=False, loop_name="asyncio"):
    """One event-loop worker: own loop, own SO_REUSEPORT socket, asyncio streams.

    app=True answers each request with the shared Python handler instead of the
    canned response -- the same handler uringpy-app calls.
    """
    import asyncio

    if app:
        from app_workload import handle_request

    async def handle(reader, writer):
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                writer.write(handle_request(data) if app else HTTP_RESPONSE)
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            writer.close()

    listener = make_reuseport_listener(host, port)
    loop = _new_loop(loop_name)
    asyncio.set_event_loop(loop)
    # backlog: asyncio calls listen() again with its own default of 100.
    server = loop.run_until_complete(
        asyncio.start_server(handle, sock=listener, backlog=1024))
    _run_loop(loop, server)


def _run_loop(loop, server):
    # signal.signal() only works in the main thread; in --mode thread the parent
    # installs the handler instead (see run()).
    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGTERM, lambda *_: loop.call_soon_threadsafe(loop.stop))
        signal.signal(signal.SIGINT, lambda *_: loop.call_soon_threadsafe(loop.stop))
    try:
        loop.run_forever()
    finally:
        server.close()
        loop.close()


def asyncio_proto_worker(host, port, wid, loop_name="asyncio", app=False):
    """One event-loop worker using the Protocol API: the response is written
    straight from data_received, with no streams layer in between.

    app=True answers each request with the shared Python handler instead of the
    canned response -- the same handler uringpy-app calls.
    """
    import asyncio

    resp = HTTP_RESPONSE
    if app:
        from app_workload import handle_request

        class Echo(asyncio.Protocol):
            __slots__ = ("transport",)

            def connection_made(self, transport):
                self.transport = transport

            def data_received(self, data):
                self.transport.write(handle_request(data))
    else:
        class Echo(asyncio.Protocol):
            __slots__ = ("transport",)

            def connection_made(self, transport):
                self.transport = transport

            def data_received(self, data):
                self.transport.write(resp)

    listener = make_reuseport_listener(host, port)
    loop = _new_loop(loop_name)
    asyncio.set_event_loop(loop)
    server = loop.run_until_complete(
        loop.create_server(Echo, sock=listener, backlog=1024))
    _run_loop(loop, server)


def _loop_worker(loop_name, proto=False, app=False):
    def worker(host, port, wid):
        if proto:
            asyncio_proto_worker(host, port, wid, loop_name=loop_name, app=app)
        else:
            asyncio_worker(host, port, wid, app=app, loop_name=loop_name)
    return worker


WORKERS = {
    "uringpy": uringpy_worker,
    "c-epoll": c_epoll_worker,
    "py-uring": py_uring_worker,
    "py-uring-held": lambda host, port, wid: py_uring_worker(host, port, wid, release_gil=False),
    "py-epoll": py_epoll_worker,
    "py-epoll-batch": py_epoll_batch_worker,
    "asyncio": asyncio_worker,
    "asyncio-proto": _loop_worker("asyncio", proto=True),
    "uvloop": _loop_worker("uvloop"),
    "uvloop-proto": _loop_worker("uvloop", proto=True),
    "uringcore-proto": _loop_worker("uringcore", proto=True),
    "uringloop-proto": _loop_worker("uringloop", proto=True),
    "uringcore-proto-app": _loop_worker("uringcore", proto=True, app=True),
    "uringcore": _loop_worker("uringcore"),
    "uringloop": _loop_worker("uringloop"),
    "uringpy-app": lambda host, port, wid: uringpy_worker(host, port, wid, app=True),
    "uringpy-app-batch": lambda host, port, wid: uringpy_worker(host, port, wid, app=True,
                                                                gil_batch=True),
    "c-epoll-app": lambda host, port, wid: c_epoll_worker(host, port, wid, app=True),
    "c-epoll-app-batch": lambda host, port, wid: c_epoll_worker(host, port, wid, app=True,
                                                                gil_batch=True),
    "asyncio-app": _loop_worker("asyncio", app=True),
    "asyncio-proto-app": _loop_worker("asyncio", proto=True, app=True),
    "uvloop-proto-app": _loop_worker("uvloop", proto=True, app=True),
}


def _capped_batch_worker(batch_max):
    def worker(host, port, wid):
        uringpy_worker(host, port, wid, app=True, gil_batch=True, batch_max=batch_max)
    return worker


# uringpy-app-batch<N>: at most N requests per GIL acquisition.
for _n in (1, 2, 4, 8, 16, 64):
    WORKERS[f"uringpy-app-batch{_n}"] = _capped_batch_worker(_n)


def run(worker_fn, workers, mode, host, port):
    if mode == "process":
        pids = []
        for wid in range(workers):
            pid = os.fork()
            if pid == 0:
                worker_fn(host, port, wid)  # child: runs until signalled
                if STATS:  # workers that return (asyncio loops) report here
                    _print_stats()
                os._exit(0)
            pids.append(pid)

        def _term(*_):
            for p in pids:
                try:
                    os.kill(p, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            for p in pids:  # let children flush their stats before we exit
                try:
                    os.waitpid(p, 0)
                except ChildProcessError:
                    pass
            os._exit(0)

        signal.signal(signal.SIGTERM, _term)
        signal.signal(signal.SIGINT, _term)
        print(f"serving on {host}:{port} ({workers} process workers)", flush=True)
        for p in pids:
            os.waitpid(p, 0)
    else:  # thread
        threads = [threading.Thread(target=worker_fn, args=(host, port, wid),
                                    daemon=True)
                   for wid in range(workers)]
        # Workers are non-main threads and cannot install signal handlers, so the
        # main thread handles termination for the whole process.
        _install_term_handler()
        for t in threads:
            t.start()
        print(f"serving on {host}:{port} ({workers} thread workers)", flush=True)
        for t in threads:
            t.join()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--engine", choices=sorted(WORKERS), required=True)
    parser.add_argument("--mode", choices=["thread", "process"], default="thread")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(argv)

    worker_fn = WORKERS[args.engine]
    # Fail before starting any worker if this image lacks the engine, rather
    # than leaving a server with some workers dead.
    try:
        if args.engine.split("-")[0] in ("uvloop", "uringcore", "uringloop"):
            _new_loop(args.engine.split("-")[0]).close()
        elif args.engine.startswith(("c-epoll", "py-epoll-batch")):
            from uringpy import BatchIO, EpollEngine  # noqa: F401
        elif args.engine.startswith(("uringpy", "py-uring")):
            from uringpy import URingEngine  # noqa: F401
    except Exception as exc:
        sys.exit(f"[{args.engine}] engine unavailable in this environment: {exc!r}")
    # Record what actually runs. On a free-threaded build, importing an
    # extension that is not free-threading-ready turns the GIL back on, so the
    # state is read here, after the engine's modules have been imported.
    gil_check = getattr(sys, "_is_gil_enabled", None)
    gil_on = True if gil_check is None else bool(gil_check())
    print(f"[runtime] python={sys.version.split()[0]} gil_enabled={int(gil_on)}",
          flush=True)
    print(f"[{args.engine}/{args.mode}] starting {args.workers} worker(s)",
          flush=True)
    run(worker_fn, args.workers, args.mode, args.host, args.port)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
