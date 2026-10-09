# Benchmark summary

- experiment: app   started (UTC): 2026-10-08T12:20:37+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 150783310)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1013-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1013-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | conns | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | GIL rel. or acq./req | GIL switches/req | vol. ctx sw./req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy-app | thread | 1 | on | 13 | none | 0 | 400 | 5 | 114,517 | 4,078 | 2.9 | 1.00× | 3.47 | 3.83 | 29.0 | 97.7 | 31.3 | 0.005 | 386.5 | 8.77 | - | - | 1.000 | 0.000 | 0.000 |  |
| uringpy-app | thread | 2 | on | 13 | none | 0 | 400 | 5 | 182,695 | 4,302 | 1.9 | 1.60× ± 0.07 | 2.15 | 2.69 | 56.5 | 92.0 | 47.8 | 0.011 | 183.5 | 10.82 | - | - | 1.000 | 0.020 | 0.030 |  |
| uringpy-app | thread | 4 | on | 13 | none | 0 | 400 | 5 | 205,927 | 7,581 | 3.0 | 1.80× ± 0.09 | 1.86 | 3.32 | 85.1 | 86.2 | 50.7 | 0.022 | 92.0 | 15.73 | - | - | 1.000 | 0.080 | 0.294 |  |
| uringpy-app-batch | thread | 1 | on | 13 | none | 0 | 400 | 5 | 117,685 | 1,944 | 1.3 | 1.00× | 3.39 | 3.71 | 29.1 | 98.1 | 31.1 | 0.005 | 386.8 | 8.56 | - | - | 0.005 | 0.000 | 0.000 |  |
| uringpy-app-batch | thread | 2 | on | 13 | none | 0 | 400 | 5 | 189,790 | 7,737 | 3.3 | 1.61× ± 0.07 | 2.08 | 2.55 | 56.8 | 89.7 | 49.1 | 0.011 | 179.9 | 10.36 | - | - | 0.011 | 0.008 | 0.002 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 0 | 400 | 5 | 265,818 | 7,872 | 2.4 | 2.26× ± 0.08 | 1.47 | 2.05 | 93.8 | 94.9 | 67.1 | 0.021 | 93.6 | 14.12 | - | - | 0.021 | 0.021 | 0.012 |  |
| c-epoll-app | thread | 1 | on | 13 | none | 0 | 400 | 5 | 96,661 | 1,291 | 1.1 | 1.00× | 4.07 | 8.05 | 28.5 | 98.4 | 27.7 | 2.004 | - | 10.36 | - | - | 1.000 | 0.000 | 0.000 |  |
| c-epoll-app | thread | 2 | on | 13 | none | 0 | 400 | 5 | 120,739 | 8,990 | 6.0 | 1.25× ± 0.09 | 3.14 | 6.50 | 50.4 | 75.6 | 37.1 | 2.008 | - | 14.81 | - | - | 1.000 | 0.681 | 0.151 | CV > 5% |
| c-epoll-app | thread | 4 | on | 13 | none | 0 | 400 | 5 | 75,929 | 5,653 | 6.0 | 0.79× ± 0.06 | 5.10 | 10.49 | 60.0 | 61.1 | 25.2 | 2.013 | - | 27.96 | - | - | 1.000 | 0.914 | 1.396 | CV > 5% |
| c-epoll-app-batch | thread | 1 | on | 13 | none | 0 | 400 | 5 | 110,659 | 4,684 | 3.4 | 1.00× | 3.54 | 7.03 | 29.2 | 98.4 | 31.3 | 2.004 | - | 9.08 | - | - | 0.003 | 0.000 | 0.000 |  |
| c-epoll-app-batch | thread | 2 | on | 13 | none | 0 | 400 | 5 | 178,270 | 2,565 | 1.2 | 1.61× ± 0.07 | 2.13 | 4.40 | 57.0 | 97.7 | 49.9 | 2.007 | - | 11.09 | - | - | 0.006 | 0.006 | 0.002 |  |
| c-epoll-app-batch | thread | 4 | on | 13 | none | 0 | 400 | 5 | 263,816 | 3,801 | 1.2 | 2.38× ± 0.11 | 1.34 | 2.96 | 95.7 | 96.3 | 70.0 | 2.013 | - | 14.66 | - | - | 0.013 | 0.013 | 0.006 |  |
| asyncio-app | thread | 1 | on | 13 | none | 0 | 400 | 5 | 58,210 | 1,965 | 2.7 | 1.00× | 6.87 | 7.23 | 27.0 | 97.8 | 17.2 | - | - | - | - | - | - | - | - |  |
| asyncio-app | thread | 2 | on | 13 | none | 0 | 400 | 5 | 40,301 | 1,572 | 3.1 | 0.69× ± 0.04 | 9.80 | 13.63 | 37.2 | 52.0 | 14.7 | - | - | - | - | - | - | - | - |  |
| asyncio-app | thread | 4 | on | 13 | none | 0 | 400 | 5 | 29,939 | 1,779 | 4.8 | 0.51× ± 0.04 | 13.35 | 17.49 | 41.6 | 43.5 | 11.6 | - | - | - | - | - | - | - | - |  |
| asyncio-proto-app | thread | 1 | on | 13 | none | 0 | 400 | 5 | 78,246 | 1,095 | 1.1 | 1.00× | 5.04 | 9.96 | 27.8 | 98.2 | 21.5 | - | - | - | - | - | - | - | - |  |
| asyncio-proto-app | thread | 2 | on | 13 | none | 0 | 400 | 5 | 66,220 | 1,678 | 2.0 | 0.85× ± 0.02 | 5.84 | 11.35 | 43.0 | 68.6 | 21.3 | - | - | - | - | - | - | - | - |  |
| asyncio-proto-app | thread | 4 | on | 13 | none | 0 | 400 | 5 | 39,741 | 922 | 1.9 | 0.51× ± 0.01 | 9.94 | 16.86 | 49.4 | 50.2 | 15.0 | - | - | - | - | - | - | - | - |  |
| uvloop-proto-app | thread | 1 | on | 13 | none | 0 | 400 | 5 | 80,340 | 1,421 | 1.4 | 1.00× | 4.90 | 49.42 | 27.9 | 97.8 | 24.2 | - | - | - | - | - | - | - | - |  |
| uvloop-proto-app | thread | 2 | on | 13 | none | 0 | 400 | 5 | 66,651 | 1,717 | 2.1 | 0.83× ± 0.03 | 5.75 | 13.50 | 37.6 | 50.8 | 21.9 | - | - | - | - | - | - | - | - |  |
| uvloop-proto-app | thread | 4 | on | 13 | none | 0 | 400 | 5 | 30,438 | 448 | 1.2 | 0.38× ± 0.01 | 12.47 | 36.92 | 36.2 | 37.4 | 12.2 | - | - | - | - | - | - | - | - |  |
