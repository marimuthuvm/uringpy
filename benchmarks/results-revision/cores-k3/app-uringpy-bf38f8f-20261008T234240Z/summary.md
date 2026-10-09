# Benchmark summary

- experiment: app   started (UTC): 2026-10-08T23:42:40+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 428379290)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1013-gcp
- server: t2d-standard-4, 3 CPUs, kernel 7.0.0-1013-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | conns | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | GIL rel. or acq./req | GIL switches/req | vol. ctx sw./req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy | thread | 1 | on | 13 | none | 0 | 400 | 5 | 126,053 | 18,288 | 11.7 | 1.00× | 3.20 | 3.51 | 40.7 | 98.2 | 35.9 | 0.006 | 374.0 | 8.04 | - | - | - | 0.000 | 0.000 | CV > 5% |
| uringpy | thread | 3 | on | 13 | none | 0 | 400 | 5 | 233,703 | 4,041 | 1.4 | 1.85× ± 0.27 | 1.46 | 3.74 | 98.3 | 98.5 | 61.9 | 0.017 | 119.8 | 12.81 | - | - | - | 0.000 | 0.001 |  |
| uringpy | process | 3 | on | 13 | none | 0 | 400 | 5 | 236,844 | 5,011 | 1.7 | - | 1.38 | 4.02 | 98.2 | 98.5 | 62.0 | 0.017 | 120.8 | 12.69 | - | - | - | 0.000 | 0.000 |  |
| py-epoll | thread | 1 | on | 13 | none | 0 | 400 | 5 | 94,536 | 13,167 | 11.2 | 1.00× | 4.21 | 8.30 | 39.1 | 98.4 | 28.8 | 2.004 | - | 10.77 | - | - | 2.004 | 0.000 | 0.000 | CV > 5% |
| py-epoll | thread | 3 | on | 13 | none | 0 | 400 | 5 | 97,633 | 3,439 | 2.8 | 1.03× ± 0.15 | 3.86 | 8.09 | 78.6 | 83.7 | 31.8 | 2.009 | - | 21.53 | - | - | 2.009 | 1.286 | 0.586 |  |
| py-epoll | process | 3 | on | 13 | none | 0 | 400 | 5 | 188,098 | 737 | 0.3 | - | 1.78 | 4.64 | 98.3 | 98.5 | 56.6 | 2.010 | - | 15.88 | - | - | 2.010 | 0.000 | 0.001 |  |
| uringpy-app | thread | 1 | on | 13 | none | 0 | 400 | 5 | 109,151 | 12,704 | 9.4 | 1.00× | 3.68 | 3.95 | 39.3 | 98.2 | 31.2 | 0.005 | 384.6 | 9.30 | - | - | 1.000 | 0.000 | 0.000 | CV > 5% |
| uringpy-app | thread | 3 | on | 13 | none | 0 | 400 | 5 | 188,885 | 4,529 | 1.9 | 1.73× ± 0.21 | 1.81 | 4.10 | 93.2 | 95.3 | 49.6 | 0.016 | 123.9 | 14.62 | - | - | 1.000 | 0.043 | 0.103 |  |
| uringpy-app | process | 3 | on | 13 | none | 0 | 400 | 5 | 215,543 | 2,595 | 1.0 | - | 1.56 | 3.86 | 98.1 | 98.5 | 57.7 | 0.017 | 118.3 | 13.90 | - | - | 1.000 | 0.000 | 0.001 |  |
| uringpy-app-batch | thread | 1 | on | 13 | none | 0 | 400 | 5 | 118,209 | 2,191 | 1.5 | 1.00× | 3.37 | 3.67 | 41.1 | 98.1 | 32.7 | 0.006 | 375.9 | 8.55 | - | - | 0.005 | 0.000 | 0.000 |  |
| uringpy-app-batch | thread | 3 | on | 13 | none | 0 | 400 | 5 | 209,755 | 1,751 | 0.7 | 1.77× ± 0.04 | 1.67 | 3.75 | 93.3 | 97.1 | 54.7 | 0.016 | 123.3 | 13.51 | - | - | 0.016 | 0.015 | 0.005 |  |
| uringpy-app-batch | process | 3 | on | 13 | none | 0 | 400 | 5 | 219,933 | 3,931 | 1.4 | - | 1.55 | 3.64 | 98.0 | 98.6 | 58.1 | 0.016 | 124.2 | 13.68 | - | - | 0.016 | 0.000 | 0.000 |  |
| c-epoll-app | thread | 1 | on | 13 | none | 0 | 400 | 5 | 89,652 | 10,329 | 9.3 | 1.00× | 4.42 | 8.75 | 38.5 | 98.1 | 27.6 | 2.004 | - | 11.31 | - | - | 1.000 | 0.000 | 0.000 | CV > 5% |
| c-epoll-app | thread | 3 | on | 13 | none | 0 | 400 | 5 | 87,785 | 2,532 | 2.3 | 0.98× ± 0.12 | 4.27 | 8.88 | 75.7 | 81.3 | 28.5 | 2.010 | - | 22.63 | - | - | 1.000 | 0.837 | 0.689 |  |
| c-epoll-app | process | 3 | on | 13 | none | 0 | 400 | 5 | 183,035 | 1,046 | 0.5 | - | 1.80 | 4.82 | 98.1 | 98.5 | 56.2 | 2.011 | - | 16.32 | - | - | 1.000 | 0.000 | 0.001 |  |
| c-epoll-app-batch | thread | 1 | on | 13 | none | 0 | 400 | 5 | 108,365 | 3,048 | 2.3 | 1.00× | 3.59 | 7.16 | 41.3 | 98.5 | 32.3 | 2.004 | - | 9.37 | - | - | 0.003 | 0.000 | 0.000 |  |
| c-epoll-app-batch | thread | 3 | on | 13 | none | 0 | 400 | 5 | 197,351 | 1,418 | 0.6 | 1.82× ± 0.05 | 1.56 | 5.75 | 96.6 | 97.3 | 55.9 | 2.010 | - | 14.89 | - | - | 0.010 | 0.009 | 0.003 |  |
| c-epoll-app-batch | process | 3 | on | 13 | none | 0 | 400 | 5 | 203,723 | 1,170 | 0.5 | - | 1.70 | 4.94 | 98.3 | 98.5 | 56.8 | 2.010 | - | 14.66 | - | - | 0.010 | 0.000 | 0.001 |  |
