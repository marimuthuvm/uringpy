#!/usr/bin/env python3
"""Check that an event loop serves the benchmark's load before it is measured.

Runs inside a benchmark image. It starts benchmarks/sharded_server.py with one
worker on localhost and makes two checks, each on a fresh server:

  sequential  one connection, requests sent one after another, up to
              --sequential of them: how many are answered before the server
              stops answering (a leak of a per-request resource shows here);
  concurrent  --conns connections opened together, --per-conn requests on
              each: how many replies arrive and whether the server survives.

Prints one "[check] ..." line per check and a final "[result] ..." line, and
exits with status 0 only if every request was answered and the server was
still running at the end. Standard library only.

    python3 benchmarks/check_loop.py --engine uringcore
    python3 benchmarks/check_loop.py --engine asyncio --sequential 20000
"""

from __future__ import annotations

import argparse
import asyncio
import os
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REQUEST = b"GET / HTTP/1.1\r\nHost: check\r\n\r\n"


def start_server(engine, port):
    proc = subprocess.Popen(
        [sys.executable, os.path.join(HERE, "sharded_server.py"), "--engine", engine,
         "--mode", "process", "--workers", "1", "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    deadline = time.time() + 15
    while time.time() < deadline:
        if proc.poll() is not None:
            break
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
            return proc
        except OSError:
            time.sleep(0.1)
    return proc


def stop_server(proc):
    alive = proc.poll() is None
    if alive:
        proc.terminate()
    try:
        out, _ = proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, _ = proc.communicate()
    tail = [line for line in (out or "").strip().splitlines() if line.strip()][-4:]
    return alive, tail


def read_response(sock, buf):
    """Read one HTTP response; return the bytes left over after it."""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(65536)
        if not chunk:
            raise ConnectionError("closed by server")
        buf += chunk
    head, rest = buf.split(b"\r\n\r\n", 1)
    length = 0
    for line in head.split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1])
    while len(rest) < length:
        chunk = sock.recv(65536)
        if not chunk:
            raise ConnectionError("closed by server")
        rest += chunk
    return rest[length:]


def sequential(port, limit):
    answered, error = 0, ""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2) as sock:
            buf = b""
            for _ in range(limit):
                sock.sendall(REQUEST)
                buf = read_response(sock, buf)
                answered += 1
    except (OSError, ConnectionError) as exc:
        error = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
    return answered, error


async def _one_connection(port, per_conn, counts):
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection("127.0.0.1", port), timeout=10)
    except (OSError, asyncio.TimeoutError):
        counts["connect failed"] += 1
        return
    counts["opened"] += 1
    try:
        for _ in range(per_conn):
            writer.write(REQUEST)
            await writer.drain()
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=10)
            length = 0
            for line in head.split(b"\r\n"):
                if line.lower().startswith(b"content-length:"):
                    length = int(line.split(b":", 1)[1])
            await asyncio.wait_for(reader.readexactly(length), timeout=10)
            counts["replies"] += 1
    except (OSError, asyncio.IncompleteReadError, asyncio.TimeoutError,
            asyncio.LimitOverrunError):
        counts["closed or timed out"] += 1
    finally:
        writer.close()


def concurrent(port, conns, per_conn):
    counts = {"opened": 0, "replies": 0, "connect failed": 0, "closed or timed out": 0}

    async def main():
        await asyncio.gather(*(_one_connection(port, per_conn, counts) for _ in range(conns)))

    asyncio.run(main())
    return counts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--engine")
    ap.add_argument("--versions", action="store_true",
                    help="print the versions of the event-loop packages and exit")
    ap.add_argument("--port", type=int, default=18080)
    ap.add_argument("--sequential", type=int, default=20000,
                    help="requests on one connection (default 20000)")
    ap.add_argument("--conns", type=int, default=400)
    ap.add_argument("--per-conn", type=int, default=3)
    args = ap.parse_args(argv)
    if args.versions:
        from importlib import metadata
        parts = [f"python {sys.version.split()[0]}"]
        for name in ("uvloop", "uringcore", "uringloop"):
            try:
                parts.append(f"{name} {metadata.version(name)}")
            except metadata.PackageNotFoundError:
                parts.append(f"{name} not installed")
        print("; ".join(parts))
        return 0
    if not args.engine:
        ap.error("--engine is required")
    ok = True

    proc = start_server(args.engine, args.port)
    answered, error = sequential(args.port, args.sequential)
    alive, tail = stop_server(proc)
    passed = answered == args.sequential and alive
    ok &= passed
    print(f"[check] sequential engine={args.engine} answered={answered}/{args.sequential} "
          f"server_alive={int(alive)}" + (f" error={error!r}" if error else ""), flush=True)
    if not passed:
        for line in tail:
            print(f"    server: {line[:200]}", flush=True)

    proc = start_server(args.engine, args.port + 1)
    counts = concurrent(args.port + 1, args.conns, args.per_conn)
    alive, tail = stop_server(proc)
    want = args.conns * args.per_conn
    passed = counts["replies"] == want and alive
    ok &= passed
    print(f"[check] concurrent engine={args.engine} conns={args.conns} "
          f"replies={counts['replies']}/{want} "
          f"connect_failed={counts['connect failed']} "
          f"closed_or_timed_out={counts['closed or timed out']} server_alive={int(alive)}",
          flush=True)
    if not passed:
        for line in tail:
            print(f"    server: {line[:200]}", flush=True)

    print(f"[result] engine={args.engine} python={sys.version.split()[0]} "
          f"{'PASS' if ok else 'FAIL'}", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
