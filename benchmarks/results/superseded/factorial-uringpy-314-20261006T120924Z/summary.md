# Benchmark summary

- experiment: factorial   started (UTC): 2026-10-06T12:09:24+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 1281053867)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up.

| engine | mode | workers | GIL | body B | batch cap | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy | thread | 1 | on | 13 | none | 5 | 146,051 | 5,424 | 3.0 | 1.00× | 2.72 | 2.90 | 30.0 | 97.9 | 37.9 | 0.006 | 347.6 |  |
| uringpy | thread | 2 | on | 13 | none | 5 | 231,524 | 5,944 | 2.1 | 1.59× ± 0.07 | 1.69 | 2.02 | 59.7 | 98.3 | 55.6 | 0.012 | 173.1 |  |
| uringpy | thread | 4 | on | 13 | none | 5 | 327,864 | 1,228 | 0.3 | 2.24× ± 0.08 | 1.13 | 1.79 | 97.9 | 98.3 | 76.4 | 0.022 | 93.5 |  |
| c-epoll | thread | 1 | on | 13 | none | 5 | 126,426 | 3,786 | 2.4 | 1.00× | 3.09 | 6.17 | 29.4 | 97.9 | 35.2 | 2.004 | - |  |
| c-epoll | thread | 2 | on | 13 | none | 5 | 201,699 | 5,544 | 2.2 | 1.60× ± 0.06 | 1.89 | 3.91 | 58.5 | 98.3 | 57.3 | 2.008 | - |  |
| c-epoll | thread | 4 | on | 13 | none | 5 | 296,444 | 692 | 0.2 | 2.34× ± 0.07 | 1.21 | 2.75 | 97.5 | 98.2 | 75.9 | 2.014 | - |  |
| py-uring | thread | 1 | on | 13 | none | 5 | 133,329 | 2,114 | 1.3 | 1.00× | 2.98 | 3.19 | 29.3 | 98.2 | 35.3 | 0.011 | - |  |
| py-uring | thread | 2 | on | 13 | none | 5 | 129,736 | 1,784 | 1.1 | 0.97× ± 0.02 | 1.61 | 952.77 | 33.2 | 52.9 | 34.9 | 0.021 | - |  |
| py-uring | thread | 4 | on | 13 | none | 5 | 128,333 | 515 | 0.3 | 0.96× ± 0.02 | 0.88 | 953.49 | 38.1 | 44.0 | 34.2 | 0.040 | - |  |
| py-epoll | thread | 1 | on | 13 | none | 5 | 105,651 | 2,384 | 1.8 | 1.00× | 3.71 | 7.39 | 28.5 | 97.7 | 30.0 | 2.004 | - |  |
| py-epoll | thread | 2 | on | 13 | none | 5 | 140,285 | 2,247 | 1.3 | 1.33× ± 0.04 | 2.75 | 5.66 | 52.2 | 71.1 | 43.5 | 2.007 | - |  |
| py-epoll | thread | 4 | on | 13 | none | 5 | 67,269 | 1,241 | 1.5 | 0.64× ± 0.02 | 5.85 | 11.68 | 61.5 | 62.5 | 22.1 | 2.012 | - |  |
