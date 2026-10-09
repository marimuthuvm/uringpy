# Benchmark summary

- experiment: handler   started (UTC): 2026-10-08T13:43:41+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 1861257380)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1013-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1013-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | conns | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | GIL rel. or acq./req | GIL switches/req | vol. ctx sw./req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy-app | thread | 1 | on | 13 | none | 0 | 400 | 5 | 115,588 | 3,176 | 2.2 | 1.00× | 3.44 | 3.75 | 29.4 | 98.0 | 31.8 | 0.005 | 383.3 | 8.75 | 1.17 | 0.06 | 1.000 | 0.000 | 0.000 |  |
| uringpy-app | thread | 1 | on | 13 | none | 5 | 400 | 5 | 107,429 | 2,693 | 2.0 | 1.00× | 3.70 | 4.07 | 28.9 | 97.9 | 29.0 | 0.005 | 386.6 | 9.37 | 1.61 | 0.06 | 1.000 | 0.000 | 0.000 |  |
| uringpy-app | thread | 1 | on | 13 | none | 10 | 400 | 5 | 103,295 | 2,839 | 2.2 | 1.00× | 3.86 | 4.13 | 28.7 | 97.6 | 28.2 | 0.006 | 385.4 | 9.74 | 1.99 | 0.06 | 1.000 | 0.000 | 0.000 |  |
| uringpy-app | thread | 1 | on | 13 | none | 20 | 400 | 5 | 94,154 | 1,141 | 1.0 | 1.00× | 4.23 | 4.57 | 28.3 | 97.9 | 25.0 | 0.006 | 382.8 | 10.70 | 2.92 | 0.06 | 1.000 | 0.000 | 0.000 |  |
| uringpy-app | thread | 1 | on | 13 | none | 30 | 400 | 5 | 85,473 | 1,346 | 1.3 | 1.00× | 4.66 | 5.02 | 27.9 | 98.0 | 22.5 | 0.006 | 383.3 | 11.78 | 4.01 | 0.06 | 1.000 | 0.000 | 0.000 |  |
| uringpy-app | thread | 1 | on | 13 | none | 100 | 400 | 5 | 54,684 | 740 | 1.1 | 1.00× | 7.29 | 7.76 | 26.9 | 98.0 | 14.2 | 0.006 | 373.6 | 18.42 | 10.61 | 0.06 | 1.000 | 0.000 | 0.000 |  |
| uringpy-app | thread | 4 | on | 13 | none | 0 | 400 | 5 | 197,372 | 3,721 | 1.5 | 1.71× ± 0.06 | 1.95 | 3.43 | 84.4 | 85.4 | 48.6 | 0.022 | 93.2 | 16.19 | 2.10 | 6.36 | 1.000 | 0.092 | 0.332 |  |
| uringpy-app | thread | 4 | on | 13 | none | 5 | 400 | 5 | 160,946 | 3,945 | 2.0 | 1.50× ± 0.05 | 2.43 | 4.14 | 78.7 | 79.6 | 40.5 | 0.022 | 93.7 | 18.06 | 2.68 | 10.19 | 1.000 | 0.113 | 0.562 |  |
| uringpy-app | thread | 4 | on | 13 | none | 10 | 400 | 5 | 137,326 | 4,124 | 2.4 | 1.33× ± 0.05 | 2.86 | 4.71 | 75.4 | 76.5 | 35.8 | 0.021 | 96.0 | 20.00 | 3.27 | 13.57 | 1.000 | 0.148 | 0.753 |  |
| uringpy-app | thread | 4 | on | 13 | none | 20 | 400 | 5 | 108,251 | 1,584 | 1.2 | 1.15× ± 0.02 | 3.62 | 6.08 | 70.4 | 71.4 | 28.6 | 0.021 | 96.7 | 23.35 | 4.25 | 19.79 | 1.000 | 0.112 | 1.144 |  |
| uringpy-app | thread | 4 | on | 13 | none | 30 | 400 | 5 | 94,646 | 919 | 0.8 | 1.11× ± 0.02 | 4.06 | 7.88 | 67.8 | 68.9 | 26.2 | 0.021 | 96.6 | 25.65 | 5.28 | 24.19 | 1.000 | 0.071 | 1.396 |  |
| uringpy-app | thread | 4 | on | 13 | none | 100 | 400 | 5 | 61,213 | 767 | 1.0 | 1.12× ± 0.02 | 6.03 | 16.08 | 50.3 | 51.5 | 18.1 | 0.021 | 97.0 | 29.92 | 12.39 | 42.19 | 1.000 | 0.029 | 1.088 |  |
| uringpy-app-batch | thread | 1 | on | 13 | none | 0 | 400 | 5 | 114,910 | 3,492 | 2.4 | 1.00× | 3.43 | 3.91 | 29.1 | 97.7 | 31.3 | 0.006 | 375.5 | 8.69 | 1.20 | 0.00 | 0.005 | 0.000 | 0.000 |  |
| uringpy-app-batch | thread | 1 | on | 13 | none | 5 | 400 | 5 | 112,301 | 2,257 | 1.6 | 1.00× | 3.53 | 3.88 | 29.1 | 98.3 | 29.3 | 0.005 | 384.7 | 8.97 | 1.63 | 0.00 | 0.005 | 0.000 | 0.000 |  |
| uringpy-app-batch | thread | 1 | on | 13 | none | 10 | 400 | 5 | 107,341 | 2,483 | 1.9 | 1.00× | 3.70 | 4.05 | 28.9 | 98.3 | 28.7 | 0.006 | 383.6 | 9.36 | 2.01 | 0.00 | 0.005 | 0.000 | 0.000 |  |
| uringpy-app-batch | thread | 1 | on | 13 | none | 20 | 400 | 5 | 97,908 | 2,080 | 1.7 | 1.00× | 4.05 | 4.45 | 28.5 | 97.4 | 25.4 | 0.006 | 383.0 | 10.29 | 2.94 | 0.00 | 0.005 | 0.000 | 0.000 |  |
| uringpy-app-batch | thread | 1 | on | 13 | none | 30 | 400 | 5 | 89,806 | 2,639 | 2.4 | 1.00× | 4.43 | 4.78 | 28.2 | 98.2 | 22.8 | 0.006 | 382.2 | 11.21 | 3.95 | 0.00 | 0.005 | 0.000 | 0.000 |  |
| uringpy-app-batch | thread | 1 | on | 13 | none | 100 | 400 | 5 | 55,730 | 998 | 1.4 | 1.00× | 7.15 | 7.65 | 27.0 | 98.0 | 14.4 | 0.006 | 374.3 | 18.09 | 10.72 | 0.00 | 0.005 | 0.000 | 0.000 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 0 | 400 | 5 | 263,236 | 4,130 | 1.3 | 2.29× ± 0.08 | 1.48 | 2.06 | 94.4 | 95.4 | 65.8 | 0.021 | 93.6 | 14.18 | 2.23 | 1.32 | 0.021 | 0.021 | 0.012 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 5 | 400 | 5 | 247,908 | 2,700 | 0.9 | 2.21× ± 0.05 | 1.58 | 2.16 | 91.6 | 93.7 | 63.5 | 0.021 | 95.8 | 14.42 | 2.97 | 2.07 | 0.021 | 0.021 | 0.015 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 10 | 400 | 5 | 229,499 | 3,756 | 1.3 | 2.14× ± 0.06 | 1.71 | 2.38 | 87.4 | 89.9 | 59.9 | 0.021 | 93.8 | 14.49 | 3.62 | 3.40 | 0.021 | 0.021 | 0.019 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 20 | 400 | 5 | 189,274 | 2,329 | 1.0 | 1.93× ± 0.05 | 2.09 | 2.94 | 76.8 | 79.7 | 50.9 | 0.021 | 95.5 | 14.53 | 4.77 | 7.11 | 0.021 | 0.021 | 0.022 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 30 | 400 | 5 | 158,621 | 3,409 | 1.7 | 1.77× ± 0.06 | 2.51 | 3.52 | 68.5 | 71.2 | 42.8 | 0.021 | 96.2 | 14.77 | 5.84 | 10.98 | 0.021 | 0.021 | 0.022 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 100 | 400 | 5 | 74,147 | 1,944 | 2.1 | 1.33× ± 0.04 | 5.38 | 6.29 | 43.3 | 52.2 | 22.4 | 0.021 | 96.1 | 20.44 | 13.06 | 34.08 | 0.021 | 0.021 | 0.021 |  |
