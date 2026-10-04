---
title: 'uringpy: A GIL-aware io_uring runtime for CPython'
tags:
  - Python
  - io_uring
  - asyncio
  - concurrency
  - Global Interpreter Lock
  - free threading
  - performance
authors:
  - name: Marimuthu Velayutham
    orcid: 0000-0000-0000-0000
    affiliation: 1
affiliations:
  - name: Independent Researcher
    index: 1
date: 3 October 2026
bibliography: paper.bib
---

# Summary

`uringpy` is a completion-reaping network runtime for CPython built on the Linux
`io_uring` interface [@axboe]. Unlike `asyncio` and existing `io_uring`-backed
event loops, which dispatch every I/O completion through interpreted Python,
`uringpy` reaps completions and drives the entire accept/receive/send protocol
inside a single C region that runs with the Global Interpreter Lock (GIL)
released. Because no Python object is created per completion, independent worker
threads — each owning a private `io_uring` instance and a `SO_REUSEPORT` socket —
run concurrently across CPU cores *within one interpreter*. The extension is
built with Cython and declares free-threading compatibility, so it also runs
without re-enabling the GIL on free-threaded (no-GIL) CPython builds introduced
by PEP 703 [@pep703].

The package ships a reproducible benchmark harness: a single-node scaling matrix,
an isolated two-node driver, a response-size sweep, and a microbenchmark that
isolates GIL-contention cost from system-call count. Every reported number is
produced by a re-runnable script.

# Statement of need

Python servers that use `asyncio` [@asyncio] or faster drop-in loops such as
`uvloop` [@uvloop] cannot scale across cores inside a single process, because the
GIL serializes the per-event Python work that these loops perform on every
completion. The common workaround is to run one process per core, which
sacrifices shared in-process state and adds inter-process coordination.

Recent `io_uring` event loops for Python [@uringloop; @uringcore] reduce
system-call overhead by reaping many completions per `io_uring_enter`, but they
still dispatch each completion in Python and therefore inherit the same
single-interpreter scaling wall. `uringpy` targets this gap: by keeping the
completion hot path in C, it lets worker threads scale across cores in one
interpreter for I/O-framing-bound services, and it provides the instrumentation
needed to attribute throughput to GIL contention rather than to system-call
count. It is intended for researchers and engineers studying Python concurrency,
`io_uring`, and the ongoing GIL/free-threading transition, and as a building
block for high-throughput, single-interpreter network services.

# Functionality

- A Cython `URingEngine` exposing submission/completion primitives over
  `liburing`, a fixed-size slab allocator for I/O buffers, and a C-side reactor
  (`serve_forever_echo`) that runs the connection state machine with the GIL
  released.
- An optional application-handler reactor (`serve_forever_app`) that invokes a
  Python callback per request, used to characterize the boundary where
  per-request Python work reintroduces GIL contention.
- A multi-worker, `SO_REUSEPORT`-sharded server launcher supporting both thread
  and process models for direct comparison against `asyncio`.
- Benchmark scripts for single-node and two-node measurement, a response-size
  sweep, and a GIL-vs-syscall isolation probe.

# Benchmarks and reproducibility

On an isolated two-node deployment, `uringpy` scales across cores within a single
interpreter where `asyncio` thread-pools collapse under GIL contention, and it
remains faster in absolute terms on free-threaded CPython because it performs no
per-completion interpreter work. The harness also documents the honest
boundaries of the approach: workloads dominated by per-request Python logic
require process-level parallelism, and tiny-response throughput is network-bound.
All experiments are scripted and container-based for independent re-execution.

# Acknowledgements

We acknowledge the `io_uring` and `liburing` maintainers, whose interface this
work builds upon.

# References
