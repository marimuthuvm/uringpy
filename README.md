# uringpy

[![PyPI](https://img.shields.io/pypi/v/uringpy.svg)](https://pypi.org/project/uringpy/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23129560.svg)](https://doi.org/10.5281/zenodo.23129560)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A **GIL-aware `io_uring` runtime for CPython**: it reaps completions and drives
the entire accept/recv/send protocol inside a single `nogil` C region, so that
worker threads scale across cores **within one interpreter** on a standard
(GIL) build, where `asyncio` and `uvloop` threads lose throughput.

> **Core finding.** The system-call interface and the placement of the event
> loop are separate levers. `io_uring` and its batching set how fast *one*
> worker is (1.16-1.26x over `epoll`; batching is worth about 20%, all of it by
> 16 completions per call). Whether *more worker threads* add throughput is
> decided by whether the loop holds the GIL, on either interface.

## Headline results

Two Google Cloud VMs (4-core server, 8-core client, one vCPU per physical
core), CPython 3.14.7, 13-byte response, 5 interleaved repetitions per
configuration. Thousands of requests per second, mean ± 95% confidence
half-width; scaling is four workers over one.

| Engine | Workers as | 1 worker | 4 workers | Scaling |
| --- | --- | ---: | ---: | ---: |
| **uringpy** | **threads** | 140.7 ± 3.0 | **328.4 ± 0.8** | **2.33×** |
| uringpy | processes | 144.4 ± 3.8 | 328.9 ± 1.2 | 2.28× |
| asyncio (Protocol API) | threads | 93.6 ± 1.6 | 45.0 ± 0.9 | 0.48× |
| asyncio (Protocol API) | processes | 94.3 ± 1.6 | 235.3 ± 1.7 | 2.50× |
| uvloop (Protocol API) | threads | 98.0 ± 2.3 | 35.0 ± 0.2 | 0.36× |
| uvloop (Protocol API) | processes | 96.5 ± 1.8 | 247.0 ± 0.6 | 2.56× |

- **Threads that scale under the GIL.** uringpy's worker threads deliver what
  its worker processes deliver, and 1.33× the best process-per-worker baseline.
  The server has four cores and one worker already uses 1.2 of them (kernel
  network processing), which is why scaling is 2.3× and not 4×; the baselines'
  processes are limited the same way.
- **It is the loop placement, not the interface, that scales.** In a 2×2
  experiment, both C loops scale at four threads (`io_uring` 2.24×, `epoll`
  2.34×) and both Python loops do not (0.96×, 0.64×).
- **Limits, measured.**
  - On the **free-threaded** build `asyncio` threads scale again (2.50-2.64×);
    uringpy is unchanged and keeps a constant 1.5-2.0× advantage.
  - With a **Python handler on every request**, uringpy's thread scaling under
    the GIL stops at 1.57× (processes: 2.36×; free-threaded threads: 2.31×).
  - With responses of **16 KiB or more** the network, not the server, was the
    limit.

The raw runs are in [`benchmarks/results/`](benchmarks/results/), and
`python3 benchmarks/make_tables.py` regenerates every result table from them.
What each experiment tests and how every number is computed is in
[`benchmarks/EXPERIMENTS.md`](benchmarks/EXPERIMENTS.md). A manuscript
describing the methodology and measurements is in preparation.

## Architecture

- **Kernel interface:** Cython bindings to `liburing` submission/completion rings.
- **C-side reactor:** `URingEngine.serve_forever_echo()` runs the connection
  state machine in one `nogil` region — no per-completion Python object.
- **Application reactor:** `URingEngine.serve_forever_app(fd, handler)` runs the
  same loop but calls a Python `handler(request_bytes) -> response_bytes` for
  each request, taking the GIL only for that call. This is the boundary case
  measured by the application workload (`--engine uringpy-app`).
- **Sharding:** N workers, each its own ring + `SO_REUSEPORT` socket; the kernel
  shards connections. No shared mutable state, no cross-worker locks.
- **Ablation baselines:** `EpollEngine.serve_forever_echo()` is the same C loop
  on `epoll` (one `recv` and one `send` system call per request), and
  `benchmarks/sharded_server.py` adds Python-dispatch loops on both interfaces
  (`py-uring`, `py-epoll`). Together they form a 2×2 design that separates the
  system-call interface from where the per-event loop runs.
  `URingEngine.set_max_batch(n)` caps completions per `io_uring_enter` to
  measure how much batching itself contributes.
- **Counters:** both C reactors count their system calls and completed
  requests exactly (`get_stats()`), so system calls per request is measured,
  not estimated.
- **Free-threading safe:** the extension declares free-threading compatibility.

## Requirements

- Linux kernel ≥ 5.6 (echo path); `liburing` ≥ 2.4 (the benchmark image builds 2.6)
- Python ≥ 3.9 (plus a free-threaded build for the no-GIL results)
- GCC / Clang

## Quick start

```bash
sudo apt-get install -y liburing-dev gcc
pip install uringpy        # or: pip install -e .  (from a clone)
pytest
```

## Usage

Run a sharded HTTP server with 2 worker threads, each a `nogil` C reactor on its
own `io_uring` ring and `SO_REUSEPORT` socket:

```bash
python3 benchmarks/sharded_server.py --engine uringpy --mode thread --workers 2 --port 8080
# in another shell:
curl http://127.0.0.1:8080/
```

Or drive the engine directly:

```python
import socket
from uringpy import URingEngine

RESPONSE = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: keep-alive\r\n\r\nOK"

lst = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
lst.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
lst.bind(("0.0.0.0", 8080))
lst.listen(1024)

engine = URingEngine(entries=8192, slot_size=4096, total_slots=32768)
engine.set_response(RESPONSE)
engine.serve_forever_echo(lst.fileno())  # runs the accept/recv/send loop in C (GIL released)
```

To run Python for each request, pass a handler instead of a fixed response.
Accept, receive and send still run in C with the GIL released; the GIL is held
only for the handler:

```python
def handler(request: bytes) -> bytes:
    return RESPONSE

engine = URingEngine(entries=8192, slot_size=4096, total_slots=32768)
engine.set_gil_batching(True)   # optional: take the GIL once per batch of requests
engine.serve_forever_app(lst.fileno(), handler)
```

Without `set_gil_batching(True)` the GIL is taken once per request. With it,
the requests found in one pass over the completion queue are handled under a
single acquisition. It is meant for several worker threads running short
handlers; whether and how much it helps is measured by the `uringpy-app-batch`
engine of the benchmarks.

> Note: `io_uring` requires Linux; under Docker, add `--security-opt seccomp=unconfined`.

## Reproduce the benchmarks

Every number comes from a re-runnable script.

### Publication measurements (two machines)

`benchmarks/bench_matrix.py` runs on the client machine and drives the server
machine over ssh. It measures every cell several times in interleaved, shuffled
order and writes the raw runs, the machine and software details, and a summary
with means and 95% confidence intervals to `benchmarks/results/`.

```bash
# on the server VM: build both interpreters from one recipe (they differ only
# in --disable-gil); each build fails if the GIL is not in the requested state
docker build -f Dockerfile.bench -t uringpy:314 .
docker build -f Dockerfile.bench --build-arg FREE_THREADED=1 -t uringpy:314t .

# on the client VM (needs python3 and wrk)
export SERVER=user@10.0.0.2 SERVER_IP=10.0.0.2 IMAGE=uringpy:314
python3 benchmarks/bench_matrix.py --experiment scaling     # uringpy vs asyncio (streams and Protocol), thread vs process
python3 benchmarks/bench_matrix.py --experiment app         # with a Python handler per request (uringpy, asyncio streams/Protocol, uvloop)
python3 benchmarks/bench_matrix.py --experiment baselines   # asyncio and uvloop, streams and Protocol API
python3 benchmarks/bench_matrix.py --experiment factorial   # {io_uring, epoll} x {C loop, Python loop}
python3 benchmarks/bench_matrix.py --experiment batch       # completions-per-enter cap, 1 .. unlimited
python3 benchmarks/bench_matrix.py --experiment size        # response size, 64 B .. 1 MiB, one process per worker
python3 benchmarks/bench_matrix.py --experiment handler     # per-request Python work, none .. heavy
```

Defaults: 5 repetitions of 20 s after a 5 s warm-up, 400 connections; each
experiment takes roughly 15 to 55 minutes. Use `--image uringpy:314t` for the
free-threaded build (uvloop is left out of that image because it is not
free-threading-ready). For the `app` experiment on that image pass
`--engines "uringpy-app asyncio-app asyncio-proto-app"`. Every run records the Python version and the GIL state
the server process reported, and the summary shows it. The `loops` experiment
(uringcore, uringloop) needs the image from
`benchmarks/crossruntime/Dockerfile.py313`. The summary flags
cells where the client was above 85% CPU, since there the load generator, not
the server, may be the limit.

The `handler` experiment varies how much interpreted work each request does
(`HANDLER_WORK`) and switches on `URingEngine.set_gil_timing()`, so every run
also reports how long a request waits for the GIL and how long it holds it.
Those two numbers are what a GIL-contention model needs as inputs, measured
instead of assumed.

`python3 benchmarks/make_tables.py` turns everything under
`benchmarks/results/` into the result tables (LaTeX), and
`python3 benchmarks/make_tables.py --dump` prints every configuration's
statistics as text.

`python3 benchmarks/bench_matrix.py --experiment scaling --local` runs
everything on one machine as a smoke test; do not report those numbers.

What each experiment tests, the meaning of every output column, and the
formula behind every reported number are in
[`benchmarks/EXPERIMENTS.md`](benchmarks/EXPERIMENTS.md).

### Quick single-pass scripts

```bash
# Build the container (io_uring needs an unrestricted seccomp profile)
docker build -t uringpy:gil .

# Single-node scaling matrix (uringpy vs asyncio, thread vs process)
docker run --rm --security-opt seccomp=unconfined uringpy:gil \
    bash benchmarks/scaling_matrix.sh

# Application workload: the same Python handler under both engines
docker run --rm --security-opt seccomp=unconfined \
    -e ENGINES="uringpy-app asyncio-app" uringpy:gil \
    bash benchmarks/scaling_matrix.sh

# GIL-vs-syscall isolation probe (no io_uring required)
python3 benchmarks/setup_gilprobe.py build_ext --inplace
python3 benchmarks/gil_experiment.py
```

Two-node (isolated load generator — the fair measurement) runs on any two Linux
hosts via [`benchmarks/twonode_bench.sh`](benchmarks/twonode_bench.sh) (set
`SERVER` / `SERVER_IP`). Free-threaded (no-GIL) image:
[`Dockerfile.freethreaded`](Dockerfile.freethreaded).

The same two-node driver runs the application workload and the response-size
sweep:

```bash
# on the client VM
ENGINES="uringpy-app asyncio-app" SERVER=user@host SERVER_IP=10.0.0.2 \
    bash benchmarks/twonode_bench.sh
SERVER=user@host SERVER_IP=10.0.0.2 bash benchmarks/bodysize_bench.sh
```

`RESP_SIZE=<bytes>` sets the response body size for every engine of
`benchmarks/sharded_server.py` (default: the 13-byte `Hello, world!`).

## Limitations

- Evaluated on one protocol, one kernel and one machine family, with a 4-core
  server whose cores are shared by the workers and the kernel's network stack
  (one worker already keeps about 1.2 cores busy).
- The multicore thread-scaling benefit applies to I/O-framing-dominated
  services; per-request Python logic requires process-level parallelism.
- Not a drop-in `asyncio` replacement — it is a specialized reactor.
- Both reactors reply once per `recv()` and do not parse HTTP framing, so
  pipelined or fragmented requests are not handled. Responses must be shorter
  than 16 MiB.

## Citation

If you use this work, please cite it (see [`CITATION.cff`](CITATION.cff)).

## License

MIT — see [`LICENSE`](LICENSE).
