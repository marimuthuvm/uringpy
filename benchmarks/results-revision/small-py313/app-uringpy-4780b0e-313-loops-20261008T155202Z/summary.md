# Benchmark summary

- experiment: app   started (UTC): 2026-10-08T15:52:02+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 1698872874)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1013-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1013-gcp, interpreter 3.13.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | conns | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | GIL rel. or acq./req | GIL switches/req | vol. ctx sw./req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| asyncio-proto-app | thread | 1 | on | 13 | none | 0 | 400 | 5 | 75,930 | 1,097 | 1.2 | 1.00× | 5.19 | 10.26 | 27.8 | 97.7 | 21.6 | - | - | - | - | - | - | - | - |  |
| asyncio-proto-app | thread | 4 | on | 13 | none | 0 | 400 | 5 | 38,101 | 819 | 1.7 | 0.50× ± 0.01 | 10.34 | 18.09 | 49.7 | 50.7 | 14.4 | - | - | - | - | - | - | - | - |  |
| asyncio-proto-app | process | 1 | on | 13 | none | 0 | 400 | 5 | 76,363 | 2,233 | 2.4 | 1.00× | 5.16 | 10.21 | 27.8 | 98.0 | 21.3 | - | - | - | - | - | - | - | - |  |
| asyncio-proto-app | process | 4 | on | 13 | none | 0 | 400 | 5 | 197,730 | 2,856 | 1.2 | 2.59× ± 0.08 | 1.93 | 4.16 | 97.7 | 98.3 | 59.4 | - | - | - | - | - | - | - | - |  |
| uvloop-proto-app | thread | 1 | on | 13 | none | 0 | 400 | 5 | 80,641 | 1,510 | 1.5 | 1.00× | 4.88 | 59.66 | 28.0 | 97.9 | 24.7 | - | - | - | - | - | - | - | - |  |
| uvloop-proto-app | thread | 4 | on | 13 | none | 0 | 400 | 5 | 29,581 | 1,146 | 3.1 | 0.37× ± 0.02 | 12.67 | 39.02 | 37.9 | 38.9 | 12.1 | - | - | - | - | - | - | - | - |  |
| uvloop-proto-app | process | 1 | on | 13 | none | 0 | 400 | 5 | 79,906 | 993 | 1.0 | 1.00× | 4.91 | 74.96 | 28.0 | 98.2 | 23.9 | - | - | - | - | - | - | - | - |  |
| uvloop-proto-app | process | 4 | on | 13 | none | 0 | 400 | 5 | 210,818 | 4,156 | 1.6 | 2.64× ± 0.06 | 1.77 | 3.99 | 97.8 | 98.3 | 62.0 | - | - | - | - | - | - | - | - |  |
| uringpy-app | thread | 1 | on | 13 | none | 0 | 400 | 5 | 114,428 | 2,756 | 1.9 | 1.00× | 3.48 | 3.79 | 29.1 | 98.3 | 31.5 | 0.006 | 378.3 | 8.77 | - | - | 1.000 | 0.000 | 0.000 |  |
| uringpy-app | thread | 4 | on | 13 | none | 0 | 400 | 5 | 201,020 | 4,816 | 1.9 | 1.76× ± 0.06 | 1.90 | 3.45 | 85.3 | 86.1 | 50.1 | 0.022 | 91.8 | 16.11 | - | - | 1.000 | 0.082 | 0.301 |  |
| uringpy-app | process | 1 | on | 13 | none | 0 | 400 | 5 | 114,246 | 4,283 | 3.0 | 1.00× | 3.48 | 3.85 | 29.2 | 98.2 | 31.3 | 0.006 | 382.2 | 8.76 | - | - | 1.000 | 0.000 | 0.000 |  |
| uringpy-app | process | 4 | on | 13 | none | 0 | 400 | 5 | 277,201 | 2,015 | 0.6 | 2.43× ± 0.09 | 1.41 | 1.95 | 97.9 | 98.3 | 68.9 | 0.022 | 92.8 | 14.42 | - | - | 1.000 | 0.000 | 0.001 |  |
| uringpy-app-batch | thread | 1 | on | 13 | none | 0 | 400 | 5 | 118,797 | 4,089 | 2.8 | 1.00× | 3.36 | 3.62 | 29.3 | 98.2 | 31.5 | 0.005 | 387.2 | 8.43 | - | - | 0.005 | 0.000 | 0.000 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 0 | 400 | 5 | 267,088 | 914 | 0.3 | 2.25× ± 0.08 | 1.45 | 2.08 | 93.9 | 95.3 | 67.2 | 0.022 | 92.8 | 13.97 | - | - | 0.021 | 0.021 | 0.012 |  |
| uringpy-app-batch | process | 1 | on | 13 | none | 0 | 400 | 5 | 118,891 | 981 | 0.7 | 1.00× | 3.35 | 3.62 | 29.2 | 98.1 | 31.6 | 0.006 | 378.2 | 8.41 | - | - | 0.005 | 0.000 | 0.000 |  |
| uringpy-app-batch | process | 4 | on | 13 | none | 0 | 400 | 5 | 279,593 | 1,442 | 0.4 | 2.35× ± 0.02 | 1.34 | 2.08 | 98.1 | 98.4 | 68.5 | 0.023 | 88.8 | 14.31 | - | - | 0.022 | 0.000 | 0.001 |  |
