# Benchmark summary

- experiment: size   started (UTC): 2026-10-07T16:07:52+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 1308849493)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | conns | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | GIL rel. or acq./req | vol. ctx sw./req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy | process | 4 | on | 64 | none | 0 | 400 | 5 | 325,892 | 1,020 | 0.3 | - | 1.17 | 1.67 | 97.8 | 98.2 | 76.9 | 0.023 | 86.5 | 12.27 | - | - | - | 0.001 |  |
| uringpy | process | 4 | on | 1024 | none | 0 | 400 | 5 | 319,526 | 586 | 0.1 | - | 1.20 | 1.67 | 97.7 | 98.2 | 75.6 | 0.024 | 84.7 | 12.51 | - | - | - | 0.001 |  |
| uringpy | process | 4 | on | 16384 | none | 0 | 400 | 5 | 119,235 | 643 | 0.4 | - | 3.15 | 7.93 | 82.3 | 84.8 | 60.1 | 0.645 | 3.1 | 21.99 | - | - | - | 0.198 |  |
| uringpy | process | 4 | on | 65536 | none | 0 | 400 | 5 | 30,018 | 154 | 0.4 | - | 12.89 | 45.31 | 35.8 | 37.4 | 35.2 | 0.717 | 2.8 | 30.67 | - | - | - | 0.273 |  |
| uringpy | process | 4 | on | 262144 | none | 0 | 400 | 5 | 7,507 | 11 | 0.1 | - | 50.10 | 302.56 | 31.5 | 33.8 | 33.2 | 1.159 | 1.7 | 83.54 | - | - | - | 0.491 |  |
| uringpy | process | 4 | on | 1048576 | none | 0 | 400 | 5 | 1,863 | 10 | 0.4 | - | 206.82 | 433.13 | 40.4 | 43.0 | 45.3 | 2.453 | 1.2 | 353.17 | - | - | - | 1.476 |  |
| asyncio-proto | process | 4 | on | 64 | none | 0 | 400 | 5 | 231,800 | 1,236 | 0.4 | - | 1.61 | 3.54 | 98.0 | 98.4 | 67.2 | - | - | - | - | - | - | - |  |
| asyncio-proto | process | 4 | on | 1024 | none | 0 | 400 | 5 | 227,395 | 1,618 | 0.6 | - | 1.68 | 3.71 | 98.2 | 98.5 | 66.2 | - | - | - | - | - | - | - |  |
| asyncio-proto | process | 4 | on | 16384 | none | 0 | 400 | 5 | 118,847 | 961 | 0.7 | - | 3.18 | 8.17 | 91.2 | 92.9 | 59.4 | - | - | - | - | - | - | - |  |
| asyncio-proto | process | 4 | on | 65536 | none | 0 | 400 | 5 | 30,020 | 124 | 0.3 | - | 13.02 | 37.11 | 39.0 | 40.5 | 34.7 | - | - | - | - | - | - | - |  |
| asyncio-proto | process | 4 | on | 262144 | none | 0 | 400 | 5 | 7,495 | 33 | 0.4 | - | 50.04 | 268.03 | 34.0 | 35.7 | 32.9 | - | - | - | - | - | - | - |  |
| asyncio-proto | process | 4 | on | 1048576 | none | 0 | 400 | 5 | 1,870 | 1 | 0.0 | - | 203.88 | 440.14 | 44.0 | 47.9 | 44.1 | - | - | - | - | - | - | - | socket errors or non-2xx responses |
