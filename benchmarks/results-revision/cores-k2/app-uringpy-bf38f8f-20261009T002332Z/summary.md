# Benchmark summary

- experiment: app   started (UTC): 2026-10-09T00:23:32+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 879910662)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1013-gcp
- server: t2d-standard-4, 2 CPUs, kernel 7.0.0-1013-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | conns | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | GIL rel. or acq./req | GIL switches/req | vol. ctx sw./req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy | thread | 1 | on | 13 | none | 0 | 400 | 5 | 108,057 | 2,277 | 1.7 | 1.00× | 3.70 | 4.04 | 60.4 | 98.6 | 29.2 | 0.005 | 384.6 | 9.32 | - | - | - | 0.000 | 0.000 |  |
| uringpy | thread | 2 | on | 13 | none | 0 | 400 | 5 | 156,970 | 2,984 | 1.5 | 1.45× ± 0.04 | 2.52 | 3.17 | 98.5 | 98.7 | 41.8 | 0.011 | 188.3 | 12.79 | - | - | - | 0.000 | 0.000 |  |
| uringpy | process | 2 | on | 13 | none | 0 | 400 | 5 | 159,013 | 3,098 | 1.6 | - | 2.46 | 3.20 | 98.5 | 98.7 | 42.6 | 0.012 | 176.7 | 12.62 | - | - | - | 0.000 | 0.000 |  |
| py-epoll | thread | 1 | on | 13 | none | 0 | 400 | 5 | 84,709 | 1,377 | 1.3 | 1.00× | 4.66 | 9.06 | 58.5 | 98.4 | 23.6 | 2.004 | - | 11.86 | - | - | 2.004 | 0.000 | 0.000 |  |
| py-epoll | thread | 2 | on | 13 | none | 0 | 400 | 5 | 102,270 | 3,143 | 2.5 | 1.21× ± 0.04 | 3.78 | 7.76 | 93.3 | 93.7 | 31.1 | 2.006 | - | 17.33 | - | - | 2.006 | 0.846 | 0.096 |  |
| py-epoll | process | 2 | on | 13 | none | 0 | 400 | 5 | 125,406 | 1,062 | 0.7 | - | 3.12 | 6.41 | 98.5 | 98.8 | 37.1 | 2.006 | - | 15.89 | - | - | 2.006 | 0.000 | 0.000 |  |
| uringpy-app | thread | 1 | on | 13 | none | 0 | 400 | 5 | 94,899 | 2,342 | 2.0 | 1.00× | 4.21 | 4.59 | 58.3 | 98.8 | 26.0 | 0.006 | 383.3 | 10.53 | - | - | 1.000 | 0.000 | 0.000 |  |
| uringpy-app | thread | 2 | on | 13 | none | 0 | 400 | 5 | 140,521 | 3,202 | 1.8 | 1.48× ± 0.05 | 2.80 | 3.57 | 97.6 | 98.2 | 37.5 | 0.011 | 186.1 | 14.07 | - | - | 1.000 | 0.020 | 0.028 |  |
| uringpy-app | process | 2 | on | 13 | none | 0 | 400 | 5 | 144,018 | 920 | 0.5 | - | 2.74 | 3.29 | 98.4 | 98.7 | 38.9 | 0.011 | 186.4 | 13.89 | - | - | 1.000 | 0.000 | 0.000 |  |
| uringpy-app-batch | thread | 1 | on | 13 | none | 0 | 400 | 5 | 100,927 | 2,891 | 2.3 | 1.00× | 3.96 | 4.38 | 60.0 | 98.2 | 26.5 | 0.006 | 385.2 | 10.02 | - | - | 0.005 | 0.000 | 0.000 |  |
| uringpy-app-batch | thread | 2 | on | 13 | none | 0 | 400 | 5 | 145,852 | 2,242 | 1.2 | 1.45× ± 0.05 | 2.67 | 3.43 | 97.5 | 98.0 | 37.8 | 0.011 | 186.0 | 13.55 | - | - | 0.011 | 0.008 | 0.002 |  |
| uringpy-app-batch | process | 2 | on | 13 | none | 0 | 400 | 5 | 147,926 | 2,857 | 1.6 | - | 2.59 | 3.38 | 98.3 | 98.7 | 38.2 | 0.011 | 183.8 | 13.54 | - | - | 0.011 | 0.000 | 0.000 |  |
| c-epoll-app | thread | 1 | on | 13 | none | 0 | 400 | 5 | 82,350 | 2,436 | 2.4 | 1.00× | 4.80 | 9.24 | 58.2 | 98.7 | 23.4 | 2.004 | - | 12.18 | - | - | 1.000 | 0.000 | 0.000 |  |
| c-epoll-app | thread | 2 | on | 13 | none | 0 | 400 | 5 | 97,168 | 1,062 | 0.9 | 1.18× ± 0.04 | 3.94 | 8.28 | 92.7 | 93.2 | 29.4 | 2.007 | - | 18.00 | - | - | 1.000 | 0.582 | 0.137 |  |
| c-epoll-app | process | 2 | on | 13 | none | 0 | 400 | 5 | 121,740 | 169 | 0.1 | - | 3.20 | 6.65 | 98.4 | 98.8 | 36.9 | 2.007 | - | 16.35 | - | - | 1.000 | 0.000 | 0.000 |  |
| c-epoll-app-batch | thread | 1 | on | 13 | none | 0 | 400 | 5 | 91,109 | 3,378 | 3.0 | 1.00× | 4.32 | 8.44 | 59.1 | 98.6 | 24.6 | 2.004 | - | 10.97 | - | - | 0.003 | 0.000 | 0.000 |  |
| c-epoll-app-batch | thread | 2 | on | 13 | none | 0 | 400 | 5 | 134,960 | 1,036 | 0.6 | 1.48× ± 0.06 | 2.83 | 5.82 | 97.5 | 97.9 | 38.4 | 2.007 | - | 14.65 | - | - | 0.006 | 0.006 | 0.002 |  |
| c-epoll-app-batch | process | 2 | on | 13 | none | 0 | 400 | 5 | 136,859 | 1,274 | 0.7 | - | 2.79 | 5.76 | 98.4 | 98.7 | 38.8 | 2.007 | - | 14.56 | - | - | 0.006 | 0.000 | 0.000 |  |
