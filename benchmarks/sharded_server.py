#!/usr/bin/env python3
"""
Multi-worker sharded HTTP server -- the core artifact for the GIL-aware thesis.

N workers each own a SO_REUSEPORT listener on the same port, so the kernel
shards connections across workers. Two axes:

  --engine uringpy : each worker drives URingEngine.serve_forever_echo(), which
                     runs the whole accept/recv/send protocol in a nogil C
                     region (GIL released for the worker's lifetime).
  --engine asyncio : each worker runs its own asyncio loop; every completion is
                     dispatched in Python bytecode.
  --engine uringpy-app / asyncio-app :
                     the application workload. Every request is passed to the
                     same Python handler (app_workload.handle_request). uringpy
                     runs it via URingEngine.serve_forever_app(), which keeps
                     accept/recv/send in C and takes the GIL only for the
                     handler call; asyncio runs it inside its stream handler.

  --mode thread    : all workers in ONE process/interpreter (shared GIL). This
                     is where the thesis bites: uringpy scales, asyncio can't.
  --mode process   : one process per worker (independent GILs) -- the honest
                     baseline where asyncio DOES scale. The novelty is that
                     uringpy matches it in a single interpreter with shared
                     memory, which processes cannot offer.

Usage:
    python3 benchmarks/sharded_server.py --engine uringpy --mode thread  --workers 4
    python3 benchmarks/sharded_server.py --engine asyncio --mode process --workers 4

Env: URINGPY_STATS=1 makes each uringpy worker print completions_per_wait on
     exit.
     RESP_SIZE=<bytes> sets the response body size (default: the 13-byte
     "Hello, world!"). The echo engines send a body of exactly that size; the
     app engines pad the handler's JSON body up to it (see app_workload.py).
"""

from __future__ import annotations

import argparse
import os
import signal
import socket
import sys
import threading

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

# (wid, engine) for every uringpy worker in THIS process, so a shutdown handler
# can read each ring's completions_per_wait (syscall-amortization evidence).
_ENGINES = []


def _print_stats():
    total_w = total_c = 0
    for wid, engine in _ENGINES:
        st = engine.get_stats()
        total_w += st["waits"]
        total_c += st["completions"]
        app = ""
        if st.get("handler_calls"):
            app = (f" handler_calls={st['handler_calls']}"
                   f" handler_errors={st['handler_errors']}")
        print(f"[worker {wid}] completions_per_wait={st['completions_per_wait']:.2f} "
              f"waits={st['waits']} completions={st['completions']}{app}", flush=True)
    if total_w:
        print(f"[all] completions_per_wait={total_c / total_w:.2f} "
              f"waits={total_w} completions={total_c}", flush=True)


def make_reuseport_listener(host, port, backlog=1024):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.bind((host, port))
    sock.listen(backlog)
    return sock


def uringpy_worker(host, port, wid, app=False):
    """One uringpy worker: own ring, own SO_REUSEPORT socket, nogil C reactor.

    app=False serves the canned response entirely in C (serve_forever_echo).
    app=True calls the shared Python handler per request (serve_forever_app).
    """
    from uringpy import URingEngine

    listener = make_reuseport_listener(host, port)
    engine = URingEngine(entries=8192, slot_size=4096, total_slots=32768)
    if app:
        from app_workload import handle_request
    else:
        engine.set_response(HTTP_RESPONSE)
    _ENGINES.append((wid, engine))

    # signal.signal() only works in the main thread; in --mode thread the parent
    # installs the handler instead (see run()). get_stats() only reads counters,
    # so it is safe to call from the handler even while the reactor is blocked.
    if threading.current_thread() is threading.main_thread():
        def _term(*_):
            if STATS:
                _print_stats()
            os._exit(0)
        signal.signal(signal.SIGTERM, _term)
        signal.signal(signal.SIGINT, _term)
    if app:
        engine.serve_forever_app(listener.fileno(), handle_request)
    else:
        engine.serve_forever_echo(listener.fileno())


def uringpy_app_worker(host, port, wid):
    uringpy_worker(host, port, wid, app=True)


def asyncio_worker(host, port, wid, app=False):
    """One asyncio worker: own loop, own SO_REUSEPORT socket.

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
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    server = loop.run_until_complete(asyncio.start_server(handle, sock=listener))

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


def asyncio_app_worker(host, port, wid):
    asyncio_worker(host, port, wid, app=True)


WORKERS = {
    "uringpy": uringpy_worker,
    "asyncio": asyncio_worker,
    "uringpy-app": uringpy_app_worker,
    "asyncio-app": asyncio_app_worker,
}


def run(worker_fn, workers, mode, host, port):
    if mode == "process":
        pids = []
        for wid in range(workers):
            pid = os.fork()
            if pid == 0:
                worker_fn(host, port, wid)  # child: runs until signalled
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
        def _term(*_):
            if STATS:
                _print_stats()
            os._exit(0)
        signal.signal(signal.SIGTERM, _term)
        signal.signal(signal.SIGINT, _term)
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
    print(f"[{args.engine}/{args.mode}] starting {args.workers} worker(s)",
          flush=True)
    run(worker_fn, args.workers, args.mode, args.host, args.port)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
