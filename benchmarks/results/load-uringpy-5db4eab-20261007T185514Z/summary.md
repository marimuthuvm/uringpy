# Benchmark summary

- experiment: load   started (UTC): 2026-10-07T18:55:14+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 1960860298)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | conns | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | GIL rel. or acq./req | vol. ctx sw./req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy | thread | 1 | on | 13 | none | 0 | 1600 | 5 | 141,690 | 1,972 | 1.1 | 1.00× | 11.20 | 246.54 | 30.3 | 97.7 | 37.6 | 0.003 | 1,101.8 | 7.11 | - | - | - | 0.000 | socket errors or non-2xx responses |
| uringpy | thread | 4 | on | 13 | none | 0 | 1600 | 5 | 330,508 | 7,586 | 1.8 | 2.33× ± 0.06 | 4.62 | 6.33 | 97.8 | 98.1 | 76.5 | 0.008 | 248.5 | 11.86 | - | - | - | 0.001 |  |
| py-uring | thread | 1 | on | 13 | none | 0 | 1600 | 5 | 127,307 | 2,088 | 1.3 | 1.00× | 12.45 | 183.90 | 29.5 | 97.7 | 33.4 | 0.005 | - | 7.89 | - | - | 0.005 | 0.000 | socket errors or non-2xx responses |
| py-uring | thread | 4 | on | 13 | none | 0 | 1600 | 5 | 298,956 | 8,353 | 2.3 | 2.35× ± 0.08 | 5.12 | 7.08 | 95.1 | 96.0 | 72.7 | 0.012 | - | 12.77 | - | - | 0.012 | 0.005 |  |
| py-epoll | thread | 1 | on | 13 | none | 0 | 1600 | 5 | 103,579 | 1,854 | 1.4 | 1.00× | 15.37 | 16.43 | 28.7 | 98.2 | 29.6 | 2.005 | - | 9.69 | - | - | 2.005 | 0.000 |  |
| py-epoll | thread | 4 | on | 13 | none | 0 | 1600 | 5 | 65,962 | 925 | 1.1 | 0.64× ± 0.01 | 23.99 | 28.29 | 62.4 | 63.0 | 24.9 | 2.010 | - | 33.17 | - | - | 2.010 | 2.050 |  |
| uringpy-app | thread | 1 | on | 13 | none | 0 | 1600 | 5 | 119,116 | 665 | 0.4 | 1.00× | 13.32 | 136.29 | 29.2 | 98.0 | 30.6 | 0.003 | 1,041.9 | 8.42 | - | - | 1.000 | 0.000 | socket errors or non-2xx responses |
| uringpy-app | thread | 4 | on | 13 | none | 0 | 1600 | 5 | 184,848 | 8,649 | 3.8 | 1.55× ± 0.07 | 8.36 | 13.69 | 81.7 | 82.1 | 45.3 | 0.007 | 332.0 | 16.60 | - | - | 1.000 | 0.428 |  |
| uringpy-app-batch | thread | 1 | on | 13 | none | 0 | 1600 | 5 | 121,978 | 1,193 | 0.8 | 1.00× | 12.99 | 151.09 | 29.4 | 97.8 | 30.7 | 0.003 | 1,047.1 | 8.24 | - | - | 0.002 | 0.000 | socket errors or non-2xx responses |
| uringpy-app-batch | thread | 4 | on | 13 | none | 0 | 1600 | 5 | 279,541 | 8,923 | 2.6 | 2.29× ± 0.08 | 5.49 | 7.74 | 92.9 | 94.7 | 71.6 | 0.007 | 297.8 | 13.16 | - | - | 0.006 | 0.006 |  |
