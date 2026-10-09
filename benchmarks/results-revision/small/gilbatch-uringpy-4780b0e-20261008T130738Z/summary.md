# Benchmark summary

- experiment: gilbatch   started (UTC): 2026-10-08T13:07:38+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 369551300)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1013-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1013-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | conns | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | GIL rel. or acq./req | GIL switches/req | vol. ctx sw./req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy-app | thread | 1 | on | 13 | none | 0 | 400 | 5 | 114,356 | 1,823 | 1.3 | 1.00× | 3.48 | 3.75 | 29.2 | 98.0 | 31.4 | 0.005 | 384.0 | 8.81 | 1.12 | 0.06 | 1.000 | 0.000 | 0.000 |  |
| uringpy-app | thread | 4 | on | 13 | none | 0 | 400 | 5 | 196,600 | 3,296 | 1.4 | 1.72× ± 0.04 | 1.95 | 3.48 | 84.5 | 85.2 | 49.6 | 0.022 | 93.4 | 16.22 | 2.11 | 6.41 | 1.000 | 0.092 | 0.328 |  |
| uringpy-app-batch1 | thread | 1 | on | 13 | none | 0 | 400 | 5 | 113,664 | 3,282 | 2.3 | 1.00× | 3.50 | 3.82 | 29.2 | 98.3 | 32.6 | 0.005 | 384.5 | 8.88 | 1.16 | 0.06 | 1.000 | 0.000 | 0.000 |  |
| uringpy-app-batch1 | thread | 4 | on | 13 | none | 0 | 400 | 5 | 192,195 | 3,507 | 1.5 | 1.69× ± 0.06 | 2.00 | 3.62 | 83.9 | 84.6 | 48.0 | 0.021 | 94.8 | 16.37 | 2.16 | 6.78 | 1.000 | 0.097 | 0.354 |  |
| uringpy-app-batch2 | thread | 1 | on | 13 | none | 0 | 400 | 5 | 114,900 | 4,401 | 3.1 | 1.00× | 3.46 | 3.86 | 29.2 | 98.1 | 32.0 | 0.006 | 381.8 | 8.77 | 1.19 | 0.03 | 0.501 | 0.000 | 0.000 |  |
| uringpy-app-batch2 | thread | 4 | on | 13 | none | 0 | 400 | 5 | 220,350 | 3,155 | 1.2 | 1.92× ± 0.08 | 1.74 | 2.93 | 87.9 | 88.5 | 55.6 | 0.022 | 92.0 | 15.32 | 2.14 | 4.43 | 0.505 | 0.056 | 0.198 |  |
| uringpy-app-batch4 | thread | 1 | on | 13 | none | 0 | 400 | 5 | 114,422 | 4,166 | 2.9 | 1.00× | 3.49 | 3.76 | 29.1 | 98.1 | 32.1 | 0.006 | 378.4 | 8.80 | 1.15 | 0.02 | 0.252 | 0.000 | 0.000 |  |
| uringpy-app-batch4 | thread | 4 | on | 13 | none | 0 | 400 | 5 | 241,771 | 2,742 | 0.9 | 2.11× ± 0.08 | 1.58 | 2.56 | 91.2 | 92.1 | 62.4 | 0.021 | 94.2 | 14.77 | 2.17 | 2.88 | 0.258 | 0.032 | 0.102 |  |
| uringpy-app-batch8 | thread | 1 | on | 13 | none | 0 | 400 | 5 | 116,210 | 3,790 | 2.6 | 1.00× | 3.42 | 3.71 | 29.3 | 98.0 | 32.5 | 0.005 | 383.6 | 8.68 | 1.16 | 0.01 | 0.127 | 0.000 | 0.000 |  |
| uringpy-app-batch8 | thread | 4 | on | 13 | none | 0 | 400 | 5 | 252,903 | 3,463 | 1.1 | 2.18× ± 0.08 | 1.52 | 2.34 | 93.0 | 93.8 | 64.9 | 0.022 | 92.6 | 14.52 | 2.19 | 2.07 | 0.135 | 0.023 | 0.054 |  |
| uringpy-app-batch16 | thread | 1 | on | 13 | none | 0 | 400 | 5 | 118,271 | 1,345 | 0.9 | 1.00× | 3.36 | 3.67 | 29.4 | 97.4 | 32.9 | 0.006 | 377.7 | 8.52 | 1.12 | 0.01 | 0.065 | 0.000 | 0.000 |  |
| uringpy-app-batch16 | thread | 4 | on | 13 | none | 0 | 400 | 5 | 257,474 | 2,378 | 0.7 | 2.18× ± 0.03 | 1.50 | 2.21 | 93.9 | 94.4 | 65.3 | 0.022 | 91.8 | 14.41 | 2.25 | 1.70 | 0.072 | 0.022 | 0.032 |  |
| uringpy-app-batch64 | thread | 1 | on | 13 | none | 0 | 400 | 5 | 117,324 | 3,254 | 2.2 | 1.00× | 3.39 | 3.68 | 29.3 | 97.9 | 31.9 | 0.005 | 382.8 | 8.57 | 1.22 | 0.00 | 0.018 | 0.000 | 0.000 |  |
| uringpy-app-batch64 | thread | 4 | on | 13 | none | 0 | 400 | 5 | 263,545 | 1,519 | 0.5 | 2.25× ± 0.06 | 1.46 | 2.18 | 94.0 | 95.0 | 67.0 | 0.021 | 93.9 | 14.10 | 2.27 | 1.47 | 0.024 | 0.021 | 0.014 |  |
| uringpy-app-batch | thread | 1 | on | 13 | none | 0 | 400 | 5 | 119,072 | 3,737 | 2.5 | 1.00× | 3.34 | 3.59 | 29.4 | 97.9 | 32.7 | 0.005 | 384.5 | 8.42 | 1.15 | 0.00 | 0.005 | 0.000 | 0.000 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 0 | 400 | 5 | 265,319 | 1,615 | 0.5 | 2.23× ± 0.07 | 1.46 | 2.06 | 94.0 | 95.0 | 67.3 | 0.022 | 91.9 | 14.08 | 2.24 | 1.32 | 0.021 | 0.021 | 0.012 |  |
