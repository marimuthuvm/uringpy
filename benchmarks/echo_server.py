#!/usr/bin/env python3
"""Minimal HTTP/1.1 keep-alive servers for a fair, load-driven comparison.

Three interchangeable implementations serve the *same* canned HTTP response so
an external load generator (wrk) can measure them under identical conditions:

    --engine uringpy : the io_uring runtime (accept/recv/send via URingEngine)
    --engine asyncio : stdlib asyncio.start_server baseline
    --engine uvloop  : asyncio backed by uvloop (libuv)

This is the multi-connection regime where io_uring's syscall amortization can
actually appear; the single-socket microbenchmark cannot show it. All numbers
are produced by wrk against these servers, not by this file.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys

# Canned HTTP/1.1 response (keep-alive). Body is a fixed 13-byte payload.
_BODY = b"Hello, world!"
HTTP_RESPONSE = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: text/plain\r\n"
    b"Content-Length: " + str(len(_BODY)).encode() + b"\r\n"
    b"Connection: keep-alive\r\n"
    b"\r\n" + _BODY
)

# op codes mirrored from URingEngine.get_events()
ACCEPT, RECV, SEND = 1, 2, 3


def make_listener(host, port, backlog=1024):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(backlog)
    return sock


def serve_uringpy(host, port):
    from uringpy import URingEngine

    listener = make_listener(host, port)
    lfd = listener.fileno()
    engine = URingEngine(entries=8192, slot_size=4096, total_slots=32768)

    engine.submit_accept(lfd)
    engine.flush()
    # URINGPY_COPY=1 forces the RECV bytes allocation (for A/B measuring the copy).
    copy_data = os.environ.get("URINGPY_COPY", "0") == "1"
    stats = os.environ.get("URINGPY_STATS", "0") == "1"
    print(f"[uringpy] serving on {host}:{port} (copy_data={copy_data}, stats={stats})", flush=True)

    served = 0
    if stats:
        import gc
        import resource
        import signal

        gc.collect()
        base_collections = sum(s["collections"] for s in gc.get_stats())

        def _report(*_):
            ru = resource.getrusage(resource.RUSAGE_SELF)
            cpu_s = ru.ru_utime + ru.ru_stime
            total_collections = sum(s["collections"] for s in gc.get_stats()) - base_collections
            cpu_us_per_req = (cpu_s / served * 1e6) if served else 0.0
            st = engine.get_stats()
            print(f"STATS copy={int(copy_data)} served={served} "
                  f"cpu_us_per_req={cpu_us_per_req:.3f} "
                  f"gc_collections={total_collections} "
                  f"maxrss_kb={ru.ru_maxrss} "
                  f"completions_per_wait={st['completions_per_wait']:.2f} "
                  f"waits={st['waits']} completions={st['completions']}",
                  flush=True)
            os._exit(0)

        signal.signal(signal.SIGTERM, _report)
        signal.signal(signal.SIGINT, _report)

    while True:
        events = engine.get_events(max_events=1024, wait=True, copy_data=copy_data)
        for op, fd, res, data in events:
            if op == ACCEPT:
                engine.submit_accept(lfd)          # re-arm the accept
                if res >= 0:
                    engine.submit_recv(res)        # first request on new conn
            elif op == RECV:
                if res <= 0:
                    os.close(fd)                   # peer closed / error
                else:
                    served += 1
                    engine.submit_send(fd, HTTP_RESPONSE)
            elif op == SEND:
                if res <= 0:
                    os.close(fd)
                else:
                    engine.submit_recv(fd)         # keep-alive: next request
        engine.flush()


def serve_uringpy_pbuf(host, port):
    from uringpy import URingEngine

    listener = make_listener(host, port)
    lfd = listener.fileno()
    engine = URingEngine(entries=8192, slot_size=4096, total_slots=32768)
    # Provided buffer ring feeds multishot receives; the kernel selects buffers.
    engine.setup_provided_buffers(nentries=4096, buf_size=2048, bgid=1)

    engine.submit_accept(lfd)
    engine.flush()
    print(f"[uringpy-pbuf] serving on {host}:{port}", flush=True)

    while True:
        events = engine.get_server_events(max_events=1024, wait=True, copy_data=False)
        for op, fd, res, data, more in events:
            if op == ACCEPT:
                engine.submit_accept(lfd)              # re-arm accept
                if res >= 0:
                    engine.arm_multishot_recv(res)     # one multishot recv per conn
            elif op == RECV:
                if res <= 0:
                    os.close(fd)                       # peer closed / error
                else:
                    engine.submit_send(fd, HTTP_RESPONSE)
                    if not more:
                        engine.arm_multishot_recv(fd)  # multishot ended; re-arm
            elif op == SEND:
                if res <= 0:
                    os.close(fd)
        engine.flush()


def serve_asyncio(host, port, use_uvloop=False):
    import asyncio

    if use_uvloop:
        import uvloop
        uvloop.install()

    async def handle(reader, writer):
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                writer.write(HTTP_RESPONSE)
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            writer.close()

    async def main():
        server = await asyncio.start_server(handle, host, port, backlog=1024)
        label = "uvloop" if use_uvloop else "asyncio"
        print(f"[{label}] serving on {host}:{port}", flush=True)
        async with server:
            await server.serve_forever()

    asyncio.run(main())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--engine", choices=["uringpy", "uringpy-pbuf", "asyncio", "uvloop"], required=True)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(argv)

    try:
        if args.engine == "uringpy":
            serve_uringpy(args.host, args.port)
        elif args.engine == "uringpy-pbuf":
            serve_uringpy_pbuf(args.host, args.port)
        elif args.engine == "uvloop":
            serve_asyncio(args.host, args.port, use_uvloop=True)
        else:
            serve_asyncio(args.host, args.port)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
