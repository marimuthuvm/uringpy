# Benchmark summary

- experiment: gilbatch   started (UTC): 2026-10-07T03:13:57+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 2049931924)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | conns | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | GIL rel. or acq./req | vol. ctx sw./req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy-app | thread | 1 | on | 13 | none | 0 | 400 | 5 | 123,231 | 2,032 | 1.3 | 1.00× | 3.23 | 3.42 | 28.8 | 98.1 | 30.3 | 0.005 | 382.8 | 8.16 | 1.17 | 0.06 | 1.000 | 0.000 |  |
| uringpy-app | thread | 2 | on | 13 | none | 0 | 400 | 5 | 189,798 | 4,539 | 1.9 | 1.54× ± 0.04 | 2.06 | 2.60 | 56.1 | 93.6 | 43.7 | 0.011 | 187.8 | 10.36 | 1.67 | 0.59 | 1.000 | 0.035 |  |
| uringpy-app | thread | 4 | on | 13 | none | 0 | 400 | 5 | 193,858 | 2,522 | 1.0 | 1.57× ± 0.03 | 2.00 | 3.53 | 80.9 | 81.9 | 42.8 | 0.022 | 92.4 | 15.56 | 2.12 | 7.70 | 1.000 | 0.407 |  |
| uringpy-app-batch1 | thread | 1 | on | 13 | none | 0 | 400 | 5 | 122,762 | 2,458 | 1.6 | 1.00× | 3.24 | 3.44 | 28.8 | 98.0 | 29.7 | 0.005 | 384.6 | 8.18 | 1.24 | 0.06 | 1.000 | 0.000 |  |
| uringpy-app-batch1 | thread | 2 | on | 13 | none | 0 | 400 | 5 | 190,973 | 3,630 | 1.5 | 1.56× ± 0.04 | 2.05 | 2.58 | 56.1 | 95.5 | 43.7 | 0.011 | 183.5 | 10.29 | 1.61 | 0.60 | 1.000 | 0.036 |  |
| uringpy-app-batch1 | thread | 4 | on | 13 | none | 0 | 400 | 5 | 190,205 | 6,596 | 2.8 | 1.55× ± 0.06 | 2.06 | 3.50 | 80.0 | 80.9 | 42.5 | 0.021 | 94.4 | 15.73 | 2.16 | 8.01 | 1.000 | 0.431 |  |
| uringpy-app-batch2 | thread | 1 | on | 13 | none | 0 | 400 | 5 | 124,457 | 2,553 | 1.7 | 1.00× | 3.20 | 3.39 | 28.8 | 98.2 | 31.0 | 0.006 | 380.0 | 8.08 | 1.20 | 0.03 | 0.501 | 0.000 |  |
| uringpy-app-batch2 | thread | 2 | on | 13 | none | 0 | 400 | 5 | 194,409 | 4,068 | 1.7 | 1.56× ± 0.05 | 2.02 | 2.46 | 56.4 | 97.2 | 45.4 | 0.011 | 178.0 | 10.11 | 1.64 | 0.48 | 0.503 | 0.029 |  |
| uringpy-app-batch2 | thread | 4 | on | 13 | none | 0 | 400 | 5 | 221,486 | 8,288 | 3.0 | 1.78× ± 0.08 | 1.74 | 2.95 | 84.9 | 85.7 | 49.4 | 0.021 | 94.4 | 14.56 | 2.17 | 5.36 | 0.505 | 0.248 |  |
| uringpy-app-batch4 | thread | 1 | on | 13 | none | 0 | 400 | 5 | 127,488 | 2,055 | 1.3 | 1.00× | 3.12 | 3.34 | 29.0 | 98.0 | 31.2 | 0.006 | 379.7 | 7.90 | 1.16 | 0.02 | 0.252 | 0.000 |  |
| uringpy-app-batch4 | thread | 2 | on | 13 | none | 0 | 400 | 5 | 198,008 | 3,939 | 1.6 | 1.55× ± 0.04 | 1.98 | 2.46 | 56.9 | 87.2 | 46.2 | 0.011 | 188.9 | 9.97 | 1.66 | 0.39 | 0.254 | 0.021 |  |
| uringpy-app-batch4 | thread | 4 | on | 13 | none | 0 | 400 | 5 | 245,778 | 5,578 | 1.8 | 1.93× ± 0.05 | 1.55 | 2.63 | 88.9 | 89.9 | 56.4 | 0.021 | 94.0 | 14.02 | 2.25 | 3.54 | 0.258 | 0.128 |  |
| uringpy-app-batch8 | thread | 1 | on | 13 | none | 0 | 400 | 5 | 128,243 | 2,176 | 1.4 | 1.00× | 3.10 | 3.31 | 29.1 | 98.1 | 31.1 | 0.006 | 380.7 | 7.88 | 1.16 | 0.01 | 0.127 | 0.000 |  |
| uringpy-app-batch8 | thread | 2 | on | 13 | none | 0 | 400 | 5 | 198,852 | 3,351 | 1.4 | 1.55× ± 0.04 | 1.99 | 2.40 | 56.5 | 96.5 | 47.4 | 0.011 | 179.0 | 9.95 | 1.68 | 0.30 | 0.130 | 0.014 |  |
| uringpy-app-batch8 | thread | 4 | on | 13 | none | 0 | 400 | 5 | 262,156 | 2,232 | 0.7 | 2.04× ± 0.04 | 1.47 | 2.30 | 91.6 | 92.3 | 59.9 | 0.021 | 93.8 | 13.69 | 2.33 | 2.51 | 0.134 | 0.066 |  |
| uringpy-app-batch16 | thread | 1 | on | 13 | none | 0 | 400 | 5 | 127,745 | 3,457 | 2.2 | 1.00× | 3.12 | 3.31 | 29.1 | 98.5 | 31.3 | 0.006 | 379.5 | 7.90 | 1.17 | 0.01 | 0.065 | 0.000 |  |
| uringpy-app-batch16 | thread | 2 | on | 13 | none | 0 | 400 | 5 | 202,139 | 3,533 | 1.4 | 1.58× ± 0.05 | 1.95 | 2.29 | 57.2 | 96.7 | 47.8 | 0.011 | 179.3 | 9.84 | 1.63 | 0.20 | 0.068 | 0.007 |  |
| uringpy-app-batch16 | thread | 4 | on | 13 | none | 0 | 400 | 5 | 271,031 | 2,051 | 0.6 | 2.12× ± 0.06 | 1.42 | 2.21 | 92.3 | 93.5 | 61.7 | 0.022 | 93.4 | 13.41 | 2.35 | 2.03 | 0.072 | 0.037 |  |
| uringpy-app-batch64 | thread | 1 | on | 13 | none | 0 | 400 | 5 | 126,967 | 2,334 | 1.5 | 1.00× | 3.13 | 3.33 | 28.8 | 98.0 | 30.8 | 0.005 | 384.2 | 7.92 | 1.19 | 0.01 | 0.018 | 0.000 |  |
| uringpy-app-batch64 | thread | 2 | on | 13 | none | 0 | 400 | 5 | 202,618 | 4,246 | 1.7 | 1.60× ± 0.04 | 1.95 | 2.30 | 56.9 | 88.7 | 46.9 | 0.011 | 184.3 | 9.74 | 1.67 | 0.23 | 0.021 | 0.004 |  |
| uringpy-app-batch64 | thread | 4 | on | 13 | none | 0 | 400 | 5 | 279,616 | 1,374 | 0.4 | 2.20× ± 0.04 | 1.39 | 2.01 | 92.7 | 93.8 | 64.0 | 0.021 | 94.6 | 13.08 | 2.34 | 1.63 | 0.023 | 0.015 |  |
| uringpy-app-batch | thread | 1 | on | 13 | none | 0 | 400 | 5 | 129,020 | 1,524 | 1.0 | 1.00× | 3.08 | 3.29 | 29.0 | 98.0 | 30.4 | 0.005 | 386.0 | 7.81 | 1.19 | 0.00 | 0.005 | 0.000 |  |
| uringpy-app-batch | thread | 2 | on | 13 | none | 0 | 400 | 5 | 207,432 | 5,376 | 2.1 | 1.61× ± 0.05 | 1.89 | 2.29 | 57.6 | 89.8 | 47.3 | 0.011 | 179.6 | 9.52 | 1.64 | 0.22 | 0.011 | 0.002 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 0 | 400 | 5 | 280,328 | 2,180 | 0.6 | 2.17× ± 0.03 | 1.39 | 1.92 | 93.2 | 94.5 | 64.4 | 0.021 | 94.8 | 13.08 | 2.36 | 1.55 | 0.021 | 0.013 |  |
