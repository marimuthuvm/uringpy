# uringpy

[![PyPI](https://img.shields.io/pypi/v/uringpy.svg)](https://pypi.org/project/uringpy/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23129560.svg)](https://doi.org/10.5281/zenodo.23129560)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A **GIL-aware `io_uring` runtime for CPython**: it reaps completions in C and
can run the entire accept/recv/send protocol inside a single `nogil` region, so
that worker threads scale across cores **within one interpreter** on a standard
(GIL) build, where `asyncio` and `uvloop` threads lose throughput.

> **Core finding.** For worker threads under the GIL, what batching buys is not
> mainly fewer system calls but fewer **GIL hand-offs**. On one worker the
> system-call interface and its batching are worth a modest factor. With several
> worker threads, what decides scaling is how often the GIL changes hands per
> request. That holds on `io_uring` and on `epoll`, and whether the loop is
> written in C or in Python.

## Headline results

Two Google Cloud VMs (4-core server, 8-core client, one vCPU per physical
core), CPython 3.14.7, 13-byte response, 400 keep-alive connections, 5
interleaved repetitions per configuration.

<!-- results:start (written by benchmarks/make_tables.py --readme; do not edit) -->

All numbers below were measured at commit `5db4eab` and are written into this file by `benchmarks/make_tables.py --readme README.md` from the raw runs in `benchmarks/results/`. Thousands of requests per second, mean ± 95% confidence half-width; scaling is four workers over one worker of the same engine.

**Transport only (no Python per request), GIL build**

| Engine | Workers as | 1 worker | 4 workers | Scaling |
| --- | --- | ---: | ---: | ---: |
| **uringpy** | threads | 144.8 ± 2.3 | 329.5 ± 0.6 | 2.28× |
| **uringpy** | processes | 144.0 ± 4.3 | 329.6 ± 0.6 | 2.29× |
| asyncio (Protocol API) | threads | 93.6 ± 1.2 | 44.7 ± 0.3 | 0.48× |
| asyncio (Protocol API) | processes | 92.0 ± 1.1 | 234.3 ± 1.0 | 2.55× |
| uvloop (Protocol API) | threads | 97.5 ± 2.3 | 35.1 ± 0.2 | 0.36× |
| uvloop (Protocol API) | processes | 98.6 ± 2.8 | 247.4 ± 0.7 | 2.51× |

**The same server loop built six ways (four worker threads)**

| Loop | System calls per request | GIL releases per request | Context switches per request | 4 threads | Scaling | Scaling without the GIL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| C loop on `io_uring`, no Python (`uringpy`) | 0.02 | 0 | 0.001 | 328.7 ± 0.7 | 2.28× | 2.30× |
| C loop on `epoll`, no Python (`c-epoll`) | 2.01 | 0 | 0.001 | 296.9 ± 0.6 | 2.36× | 2.38× |
| Python loop on `io_uring`, GIL released per pass (`py-uring`) | 0.04 | 0.042 | 0.013 | 293.8 ± 2.3 | 2.19× | 2.33× |
| Python loop on `epoll`, GIL released per system call (`py-epoll`) | 2.01 | 2.012 | 2.048 | 66.7 ± 1.7 | 0.62× | 2.40× |
| the same `epoll` loop, GIL released per pass (`py-epoll-batch`) | 2.01 | 0.026 | 0.003 | 292.0 ± 1.1 | 2.35× | 2.33× |
| the `io_uring` loop holding the GIL while it submits (`py-uring-held`) | 0.04 | 0.020 | 0.021 | 127.6 ± 0.4 | 0.94× | 2.30× |

**With a Python handler on every request (GIL build)**

| Server | 4 threads | Thread scaling | Context switches per request | 4 processes |
| --- | ---: | ---: | ---: | ---: |
| `io_uring` reactor, GIL per request (`uringpy-app`) | 201.8 ± 6.3 | 1.61× | 0.36 | 295.1 ± 4.0 |
| `io_uring` reactor, GIL per batch (`uringpy-app-batch`) | 279.5 ± 4.5 | 2.18× | 0.01 | 299.2 ± 2.0 |
| `epoll` reactor, GIL per request (`c-epoll-app`) | 72.0 ± 0.5 | 0.70× | 1.44 | 256.2 ± 2.1 |
| `epoll` reactor, GIL per batch (`c-epoll-app-batch`) | 268.4 ± 2.1 | 2.33× | 0.01 | 282.2 ± 1.0 |
| asyncio (Protocol API) (`asyncio-proto-app`) | 38.6 ± 0.2 | 0.49× | 3.03 | 177.8 ± 42.0 |
| uvloop (Protocol API) (`uvloop-proto-app`) | 29.8 ± 0.3 | 0.35× | 3.83 | 218.7 ± 4.8 |

- **It is the GIL hand-offs, not the system calls.** The Python loop on `epoll` makes the same two system calls per request in both of its variants. Releasing the GIL once per pass instead of once per system call takes four threads from 0.62× to 2.35× the throughput of one. The Python loop on `io_uring` scales by 2.19×, and by 0.94× if it merely holds the GIL during its submitting call. Without the GIL all six loops scale alike.
- **GIL batching.** With a Python handler on every request, taking the GIL once per batch instead of once per request (`engine.set_gil_batching(True)`) lifts four-thread throughput from 201.8 to 279.5 thousand requests per second. That is 0.93 of four processes of the same reactor and 1.28× the best process-per-worker baseline measured (uvloop, Protocol API). The same batching rescues the `epoll` reactor.
- **Limits, measured.**
  - **Handler length.** The handler above holds the GIL for 1.21 µs per request. With one that holds it for 4.04 µs, batched threads deliver 0.65 of what processes do, and less with longer ones. No design recovers thread scaling once the lock itself is busy.
  - **Light load.** Batches need a backlog. With 64 connections instead of 400, batched threads scale by 1.64× instead of 2.19×.
  - **Free-threaded build.** `asyncio` threads scale there (2.48×); uringpy keeps an advantage in speed per worker (1.46× at four workers on the transport path) and no longer one in scaling.
  - **Large responses.** With bodies of 16 KiB or more the network, not the server, was the limit.
  - On the transport path the C loop is only 1.12× faster at four workers than the Python loop on `io_uring`.

<!-- results:end -->

The server has four cores, and one worker already keeps more than one of them
busy with kernel network processing. That is why scaling stays well below 4x
for every engine, and processes are limited in the same way.

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
# afterwards, on the same images: 1600 connections and the io_uring-based
# asyncio loop with the container's limits raised, and three more handler sizes
BASE_COMMIT=<commit of the images> bash benchmarks/run_supplement.sh
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
