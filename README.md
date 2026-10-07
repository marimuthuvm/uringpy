# uringpy

[![PyPI](https://img.shields.io/pypi/v/uringpy.svg)](https://pypi.org/project/uringpy/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23129560.svg)](https://doi.org/10.5281/zenodo.23129560)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A **GIL-aware `io_uring` runtime for CPython**: it reaps completions in C and
can run the entire accept/recv/send protocol inside a single `nogil` region, so
that worker threads scale across cores **within one interpreter** on a standard
(GIL) build, where `asyncio` and `uvloop` threads lose throughput.

> **Core finding.** For worker threads under the GIL, what batching buys is not
> mainly fewer system calls but fewer **GIL hand-offs**. On one worker
> `io_uring` and its batching are worth 1.14-1.25x over `epoll` (batching about
> 20%, all of it by 16 completions per call). With four worker threads, what
> decides scaling is how often the GIL changes hands per request, whether the
> loop is written in C or in Python.

## Headline results

Two Google Cloud VMs (4-core server, 8-core client, one vCPU per physical
core), CPython 3.14.7, 13-byte response, 5 interleaved repetitions per
configuration. Thousands of requests per second, mean ± 95% confidence
half-width; scaling is four workers over one.

**Transport only (no Python per request), GIL build**

| Engine | Workers as | 1 worker | 4 workers | Scaling |
| --- | --- | ---: | ---: | ---: |
| **uringpy** | **threads** | 140.7 ± 3.0 | **328.4 ± 0.8** | **2.33×** |
| uringpy | processes | 144.4 ± 3.8 | 328.9 ± 1.2 | 2.28× |
| asyncio (Protocol API) | threads | 93.6 ± 1.6 | 45.0 ± 0.9 | 0.48× |
| asyncio (Protocol API) | processes | 94.3 ± 1.6 | 235.3 ± 1.7 | 2.50× |
| uvloop (Protocol API) | threads | 98.0 ± 2.3 | 35.0 ± 0.2 | 0.36× |
| uvloop (Protocol API) | processes | 96.5 ± 1.8 | 247.0 ± 0.6 | 2.56× |

The server has four cores and one worker already uses 1.2 of them (kernel
network processing), which is why scaling is 2.3× and not 4×; the baselines'
processes are limited the same way.

**Thread scaling against GIL hand-offs per request (four threads, GIL build)**

| Configuration | Hand-offs per request | 4 workers | Scaling |
| --- | ---: | ---: | ---: |
| C loop on `io_uring`, no Python (`uringpy`) | 0 | 329.0 ± 0.8 | 2.34× |
| C loop on `epoll`, no Python (`c-epoll`) | 0 | 297.7 ± 0.8 | 2.41× |
| C loop + Python handler, GIL per batch (`uringpy-app-batch`) | 0.022 | 275.6 ± 5.6 | 2.12× |
| Python loop on `io_uring` (`py-uring`) | 0.042 | 295.1 ± 0.7 | 2.21× |
| C loop + Python handler, GIL per request (`uringpy-app`) | 1.000 | 196.3 ± 4.5 | 1.55× |
| Python loop on `epoll` (`py-epoll`) | 2.012 | 68.1 ± 0.9 | 0.64× |
| Python loop on `io_uring`, GIL held while submitting (`py-uring-held`) | 0.020 | 128.6 ± 2.3 | 0.98× |

- **The loop does not have to be in C to scale.** A Python loop on `io_uring`
  that releases the GIL around its two system calls per batch scales nearly as
  well as the C loop. The same loop holding the GIL during its submitting call
  (the last row) does not scale at all, because the kernel does the sends under
  the GIL.
- **GIL batching.** With a Python handler on every request, taking the GIL once
  per batch instead of once per request (`engine.set_gil_batching(True)`) lifts
  four-thread throughput from 196k to 276k requests per second. That is 0.93 of
  four processes and 1.25× the best process-per-worker baseline measured
  (uvloop Protocol API, 220k).
- **Limits, measured.**
  - Once the handler itself holds the GIL for most of a request (about 30 µs
    and more here), no design recovers thread scaling under the GIL.
  - On the **free-threaded** build `asyncio` threads scale again
    (2.50-2.64×); uringpy is unchanged and keeps a 1.5-2.0× advantage in speed.
  - With responses of **16 KiB or more** the network, not the server, was the
    limit.
  - On the transport path the C loop is only 1.05-1.11× faster than the Python
    loop on `io_uring`.

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
python3 benchmarks/bench_matrix.py --experiment factorial   # {io_uring, epoll} x {C loop, Python loop}, plus the two hand-off controls
python3 benchmarks/bench_matrix.py --experiment gilbatch    # requests served per GIL acquisition, 1 .. a whole pass
python3 benchmarks/bench_matrix.py --experiment load        # 16 .. 1600 client connections
python3 benchmarks/bench_matrix.py --experiment batch       # completions-per-enter cap, 1 .. unlimited
python3 benchmarks/bench_matrix.py --experiment size        # response size, 64 B .. 1 MiB, one process per worker
python3 benchmarks/bench_matrix.py --experiment handler     # per-request Python work, none .. heavy

# or everything the paper reports, on both builds, at the checked-out commit:
# builds the images on the server, runs the tests in them, then every experiment
bash benchmarks/run_paper_experiments.sh
```

Defaults: 5 repetitions of 20 s after a 5 s warm-up, 400 connections; one
experiment takes between 15 minutes and 4.5 hours (about 33 s per run), and
`run_paper_experiments.sh` about 18 hours. Use `--image uringpy:314t` for the
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
