# Benchmark summary

- experiment: factorial   started (UTC): 2026-10-08T11:40:16+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 1954760610)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1013-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1013-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | conns | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | GIL rel. or acq./req | GIL switches/req | vol. ctx sw./req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy | thread | 1 | on | 13 | none | 0 | 400 | 5 | 134,928 | 2,565 | 1.5 | 1.00× | 2.96 | 3.23 | 30.2 | 98.2 | 36.5 | 0.006 | 343.5 | 7.50 | - | - | - | 0.000 | 0.000 |  |
| uringpy | thread | 2 | on | 13 | none | 0 | 400 | 5 | 217,608 | 6,483 | 2.4 | 1.61× ± 0.06 | 1.81 | 2.15 | 59.5 | 97.7 | 57.1 | 0.012 | 169.1 | 9.24 | - | - | - | 0.000 | 0.001 |  |
| uringpy | thread | 4 | on | 13 | none | 0 | 400 | 5 | 309,460 | 4,675 | 1.2 | 2.29× ± 0.06 | 1.24 | 2.27 | 97.7 | 98.3 | 76.3 | 0.021 | 96.3 | 12.34 | - | - | - | 0.000 | 0.001 |  |
| c-epoll | thread | 1 | on | 13 | none | 0 | 400 | 5 | 119,059 | 2,791 | 1.9 | 1.00× | 3.29 | 6.52 | 29.6 | 98.1 | 34.4 | 2.004 | - | 8.41 | - | - | - | 0.000 | 0.000 |  |
| c-epoll | thread | 2 | on | 13 | none | 0 | 400 | 5 | 192,315 | 3,432 | 1.4 | 1.62× ± 0.05 | 1.98 | 4.13 | 58.3 | 97.8 | 56.9 | 2.007 | - | 10.41 | - | - | - | 0.000 | 0.001 |  |
| c-epoll | thread | 4 | on | 13 | none | 0 | 400 | 5 | 283,542 | 4,002 | 1.1 | 2.38× ± 0.07 | 1.31 | 2.96 | 97.7 | 98.3 | 74.8 | 2.014 | - | 14.02 | - | - | - | 0.000 | 0.001 |  |
| py-uring | thread | 1 | on | 13 | none | 0 | 400 | 5 | 124,574 | 4,399 | 2.8 | 1.00× | 3.20 | 3.52 | 29.6 | 89.7 | 34.2 | 0.011 | - | 8.11 | - | - | 0.011 | 0.000 | 0.000 |  |
| py-uring | thread | 2 | on | 13 | none | 0 | 400 | 5 | 198,269 | 6,348 | 2.6 | 1.59× ± 0.08 | 1.99 | 2.37 | 58.2 | 97.4 | 52.9 | 0.022 | - | 10.07 | - | - | 0.022 | 0.010 | 0.002 |  |
| py-uring | thread | 4 | on | 13 | none | 0 | 400 | 5 | 280,820 | 4,500 | 1.3 | 2.25× ± 0.09 | 1.37 | 2.00 | 95.6 | 96.1 | 69.9 | 0.041 | - | 13.45 | - | - | 0.041 | 0.021 | 0.010 |  |
| py-epoll | thread | 1 | on | 13 | none | 0 | 400 | 5 | 99,079 | 1,911 | 1.6 | 1.00× | 3.97 | 7.82 | 28.7 | 97.7 | 27.6 | 2.004 | - | 10.13 | - | - | 2.004 | 0.000 | 0.000 |  |
| py-epoll | thread | 2 | on | 13 | none | 0 | 400 | 5 | 132,656 | 14,108 | 8.6 | 1.34× ± 0.14 | 2.91 | 5.99 | 52.2 | 78.5 | 40.4 | 2.007 | - | 13.75 | - | - | 2.007 | 1.007 | 0.094 | CV > 5% |
| py-epoll | thread | 4 | on | 13 | none | 0 | 400 | 5 | 69,310 | 6,436 | 7.5 | 0.70× ± 0.07 | 5.65 | 11.26 | 63.0 | 64.9 | 22.7 | 2.012 | - | 31.93 | - | - | 2.012 | 1.458 | 1.928 | CV > 5% |
| py-epoll-batch | thread | 1 | on | 13 | none | 0 | 400 | 5 | 117,541 | 2,148 | 1.5 | 1.00× | 3.34 | 6.62 | 29.5 | 98.2 | 33.8 | 2.004 | - | 8.54 | - | - | 0.007 | 0.000 | 0.000 |  |
| py-epoll-batch | thread | 2 | on | 13 | none | 0 | 400 | 5 | 190,848 | 5,028 | 2.1 | 1.62× ± 0.05 | 2.00 | 4.20 | 58.3 | 98.2 | 56.5 | 2.007 | - | 10.48 | - | - | 0.013 | 0.006 | 0.001 |  |
| py-epoll-batch | thread | 4 | on | 13 | none | 0 | 400 | 5 | 281,409 | 1,155 | 0.3 | 2.39× ± 0.04 | 1.30 | 2.92 | 97.8 | 98.2 | 74.9 | 2.013 | - | 14.13 | - | - | 0.026 | 0.015 | 0.003 |  |
| py-uring-held | thread | 1 | on | 13 | none | 0 | 400 | 5 | 122,711 | 1,919 | 1.3 | 1.00× | 3.25 | 3.56 | 29.4 | 98.0 | 33.7 | 0.011 | - | 8.20 | - | - | 0.005 | 0.000 | 0.000 |  |
| py-uring-held | thread | 2 | on | 13 | none | 0 | 400 | 5 | 121,797 | 2,697 | 1.8 | 0.99× ± 0.03 | 1.73 | 983.61 | 34.7 | 55.4 | 34.1 | 0.021 | - | 8.44 | - | - | 0.011 | 0.000 | 0.011 | socket errors or non-2xx responses |
| py-uring-held | thread | 4 | on | 13 | none | 0 | 400 | 5 | 119,719 | 2,586 | 1.7 | 0.98× ± 0.03 | 0.92 | 1,002.12 | 37.9 | 47.6 | 34.9 | 0.039 | - | 8.77 | - | - | 0.019 | 0.000 | 0.021 | socket errors or non-2xx responses |
