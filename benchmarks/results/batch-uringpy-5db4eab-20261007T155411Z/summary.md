# Benchmark summary

- experiment: batch   started (UTC): 2026-10-07T15:54:11+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 1827276540)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | conns | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | GIL rel. or acq./req | vol. ctx sw./req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy | thread | 1 | on | 13 | 1 | 0 | 400 | 5 | 116,369 | 1,070 | 0.7 | 1.00× | 3.42 | 3.62 | 28.9 | 98.1 | 34.1 | 2.001 | 1.0 | 8.66 | - | - | - | 0.000 |  |
| uringpy | thread | 1 | on | 13 | 4 | 0 | 400 | 5 | 133,194 | 2,275 | 1.4 | 1.00× | 2.99 | 3.19 | 29.5 | 97.9 | 39.0 | 0.501 | 4.0 | 7.55 | - | - | - | 0.000 |  |
| uringpy | thread | 1 | on | 13 | 16 | 0 | 400 | 5 | 138,254 | 3,221 | 1.9 | 1.00× | 2.87 | 3.11 | 29.6 | 97.9 | 40.1 | 0.126 | 16.0 | 7.27 | - | - | - | 0.000 |  |
| uringpy | thread | 1 | on | 13 | 64 | 0 | 400 | 5 | 143,079 | 6,958 | 3.9 | 1.00× | 2.78 | 3.07 | 29.8 | 97.8 | 41.2 | 0.032 | 63.3 | 7.05 | - | - | - | 0.000 |  |
| uringpy | thread | 1 | on | 13 | 256 | 0 | 400 | 5 | 141,225 | 3,988 | 2.3 | 1.00× | 2.81 | 3.04 | 29.7 | 97.9 | 39.8 | 0.009 | 234.6 | 7.12 | - | - | - | 0.000 |  |
| uringpy | thread | 1 | on | 13 | none | 0 | 400 | 5 | 142,965 | 3,235 | 1.8 | 1.00× | 2.77 | 3.03 | 29.8 | 97.8 | 41.2 | 0.006 | 357.7 | 7.05 | - | - | - | 0.000 |  |
