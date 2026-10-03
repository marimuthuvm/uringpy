#!/usr/bin/env python3
"""Uniform asyncio HTTP/1.1 keep-alive server for cross-runtime comparison.

The *identical* server code runs under any asyncio-compatible event loop; only
the loop implementation is swapped via --loop. This is the fairest possible
comparison (exactly how uvloop is benchmarked): same request handling, same
response, only the loop differs.

Supported loops: asyncio (stdlib), uvloop, uringcore, uringloop.
(uringpy is not asyncio-compatible; it is benchmarked via its own server.)
"""

from __future__ import annotations

import argparse
import asyncio

_BODY = b"Hello, world!"
HTTP_RESPONSE = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: text/plain\r\n"
    b"Content-Length: " + str(len(_BODY)).encode() + b"\r\n"
    b"Connection: keep-alive\r\n"
    b"\r\n" + _BODY
)


def make_loop(name):
    if name == "uvloop":
        import uvloop
        return uvloop.new_event_loop()
    if name == "uringcore":
        import uringcore
        return uringcore.EventLoopPolicy().new_event_loop()
    if name == "uringloop":
        from uringloop import URingEventLoop
        return URingEventLoop()
    return asyncio.new_event_loop()


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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--loop", choices=["asyncio", "uvloop", "uringcore", "uringloop"],
                        required=True)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(argv)

    loop = make_loop(args.loop)
    asyncio.set_event_loop(loop)
    server = loop.run_until_complete(
        asyncio.start_server(handle, args.host, args.port, backlog=1024))
    print(f"[{args.loop}] serving on {args.host}:{args.port}", flush=True)
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()


if __name__ == "__main__":
    main()
