# Benchmark summary

- experiment: factorial   started (UTC): 2026-10-06T18:58:24+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 70639362)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy | thread | 1 | on | 13 | none | 0 | 5 | 140,311 | 4,318 | 2.5 | 1.00× | 2.83 | 3.04 | 29.5 | 98.2 | 38.5 | 0.006 | 378.2 | 7.13 | - | - |  |
| uringpy | thread | 2 | on | 13 | none | 0 | 5 | 230,639 | 6,877 | 2.4 | 1.64× ± 0.07 | 1.70 | 2.02 | 59.8 | 98.3 | 55.8 | 0.011 | 179.6 | 8.72 | - | - |  |
| uringpy | thread | 4 | on | 13 | none | 0 | 5 | 328,993 | 786 | 0.2 | 2.34× ± 0.07 | 1.14 | 1.78 | 97.9 | 98.4 | 77.0 | 0.022 | 92.3 | 11.84 | - | - |  |
| c-epoll | thread | 1 | on | 13 | none | 0 | 5 | 123,384 | 2,902 | 1.9 | 1.00× | 3.16 | 6.32 | 29.0 | 97.9 | 37.9 | 2.004 | - | 8.12 | - | - |  |
| c-epoll | thread | 2 | on | 13 | none | 0 | 5 | 200,454 | 3,761 | 1.5 | 1.62× ± 0.05 | 1.91 | 4.05 | 58.0 | 98.3 | 58.0 | 2.007 | - | 9.93 | - | - |  |
| c-epoll | thread | 4 | on | 13 | none | 0 | 5 | 297,698 | 796 | 0.2 | 2.41× ± 0.06 | 1.21 | 2.77 | 97.9 | 98.3 | 75.5 | 2.014 | - | 13.39 | - | - |  |
| py-uring | thread | 1 | on | 13 | none | 0 | 5 | 133,491 | 2,635 | 1.6 | 1.00× | 2.98 | 3.19 | 29.4 | 98.1 | 37.3 | 0.011 | - | 7.55 | - | - |  |
| py-uring | thread | 2 | on | 13 | none | 0 | 5 | 212,398 | 2,863 | 1.1 | 1.59× ± 0.04 | 1.85 | 2.19 | 58.2 | 90.5 | 53.8 | 0.022 | - | 9.40 | - | - |  |
| py-uring | thread | 4 | on | 13 | none | 0 | 5 | 295,115 | 659 | 0.2 | 2.21× ± 0.04 | 1.30 | 1.89 | 95.2 | 96.0 | 69.4 | 0.042 | - | 12.91 | - | - |  |
| py-epoll | thread | 1 | on | 13 | none | 0 | 5 | 106,850 | 1,794 | 1.4 | 1.00× | 3.65 | 7.30 | 28.6 | 98.2 | 31.2 | 2.004 | - | 9.39 | - | - |  |
| py-epoll | thread | 2 | on | 13 | none | 0 | 5 | 141,570 | 2,677 | 1.5 | 1.32× ± 0.03 | 2.72 | 5.57 | 52.3 | 77.4 | 42.4 | 2.007 | - | 13.02 | - | - |  |
| py-epoll | thread | 4 | on | 13 | none | 0 | 5 | 68,148 | 906 | 1.1 | 0.64× ± 0.01 | 5.74 | 11.47 | 61.4 | 62.2 | 21.6 | 2.012 | - | 31.97 | - | - |  |
| py-uring-held | thread | 1 | on | 13 | none | 0 | 5 | 131,516 | 3,559 | 2.2 | 1.00× | 3.02 | 3.24 | 29.2 | 97.8 | 36.2 | 0.011 | - | 7.62 | - | - |  |
| py-uring-held | thread | 2 | on | 13 | none | 0 | 5 | 129,149 | 2,789 | 1.7 | 0.98× ± 0.03 | 1.61 | 824.15 | 33.2 | 48.0 | 35.5 | 0.022 | - | 7.96 | - | - |  |
| py-uring-held | thread | 4 | on | 13 | none | 0 | 5 | 128,632 | 2,314 | 1.4 | 0.98× ± 0.03 | 0.86 | 783.69 | 37.7 | 42.4 | 35.2 | 0.040 | - | 8.22 | - | - |  |
