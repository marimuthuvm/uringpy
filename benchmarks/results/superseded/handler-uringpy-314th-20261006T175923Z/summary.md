# Benchmark summary

- experiment: handler   started (UTC): 2026-10-06T17:59:23+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 2127826692)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_OFF

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy-app | thread | 1 | off | 13 | none | 0 | 5 | 122,974 | 3,770 | 2.5 | 1.00× | 3.20 | 3.70 | 28.8 | 97.6 | 38.7 | 0.006 | 372.8 | 8.20 | 1.34 | 0.05 |  |
| uringpy-app | thread | 1 | off | 13 | none | 30 | 5 | 90,169 | 433 | 0.4 | 1.00× | 4.40 | 4.92 | 27.6 | 98.0 | 27.3 | 0.006 | 378.3 | 11.16 | 4.38 | 0.05 |  |
| uringpy-app | thread | 1 | off | 13 | none | 100 | 5 | 54,781 | 530 | 0.8 | 1.00× | 7.27 | 7.90 | 26.5 | 97.9 | 15.1 | 0.006 | 374.3 | 18.37 | 11.33 | 0.05 |  |
| uringpy-app | thread | 1 | off | 13 | none | 300 | 5 | 25,743 | 254 | 0.8 | 1.00× | 15.47 | 320.06 | 25.7 | 97.8 | 8.0 | 0.007 | 348.5 | 39.08 | 31.99 | 0.05 |  |
| uringpy-app | thread | 1 | off | 13 | none | 1000 | 5 | 8,466 | 502 | 4.8 | 1.00× | 47.41 | 457.91 | 25.2 | 97.9 | 3.2 | 0.011 | 281.6 | 118.45 | 108.51 | 0.06 | socket errors or non-2xx responses |
| uringpy-app | thread | 1 | off | 13 | none | 3000 | 5 | 2,976 | 201 | 5.4 | 1.00× | 123.17 | 136.30 | 25.1 | 98.7 | 1.2 | 0.023 | 163.3 | 337.39 | 326.90 | 0.08 | CV > 5%; socket errors or non-2xx responses |
| uringpy-app | thread | 2 | off | 13 | none | 0 | 5 | 200,340 | 5,194 | 2.1 | 1.63× ± 0.07 | 1.93 | 2.41 | 58.0 | 98.3 | 54.8 | 0.012 | 172.6 | 10.04 | 1.94 | 0.07 |  |
| uringpy-app | thread | 2 | off | 13 | none | 30 | 5 | 149,079 | 1,093 | 0.6 | 1.65× ± 0.01 | 2.64 | 3.05 | 55.0 | 98.2 | 38.4 | 0.011 | 187.5 | 13.50 | 5.84 | 0.06 |  |
| uringpy-app | thread | 2 | off | 13 | none | 100 | 5 | 86,834 | 1,792 | 1.7 | 1.59× ± 0.04 | 4.52 | 5.23 | 52.3 | 97.8 | 26.2 | 0.011 | 191.0 | 23.11 | 16.03 | 0.06 |  |
| uringpy-app | thread | 2 | off | 13 | none | 300 | 5 | 38,010 | 1,268 | 2.7 | 1.48× ± 0.05 | 10.52 | 11.56 | 50.9 | 98.2 | 11.4 | 0.012 | 187.1 | 52.77 | 45.87 | 0.07 |  |
| uringpy-app | thread | 2 | off | 13 | none | 1000 | 5 | 12,843 | 691 | 4.3 | 1.52× ± 0.12 | 30.90 | 373.68 | 49.9 | 98.4 | 3.9 | 0.014 | 173.9 | 156.94 | 149.72 | 0.08 |  |
| uringpy-app | thread | 2 | off | 13 | none | 3000 | 5 | 4,427 | 34 | 0.6 | 1.49× ± 0.10 | 87.53 | 524.53 | 49.7 | 98.5 | 1.7 | 0.021 | 143.5 | 453.00 | 442.20 | 0.10 | socket errors or non-2xx responses |
| uringpy-app | thread | 4 | off | 13 | none | 0 | 5 | 260,705 | 51,716 | 16.0 | 2.12× ± 0.43 | 1.30 | 3.07 | 92.4 | 93.0 | 75.3 | 0.063 | 31.9 | 14.28 | 3.58 | 0.13 | CV > 5% |
| uringpy-app | thread | 4 | off | 13 | none | 30 | 5 | 192,822 | 30,442 | 12.7 | 2.14× ± 0.34 | 1.95 | 3.28 | 94.9 | 95.4 | 59.3 | 0.038 | 52.7 | 20.06 | 11.70 | 0.10 | CV > 5% |
| uringpy-app | thread | 4 | off | 13 | none | 100 | 5 | 93,153 | 2,127 | 1.8 | 1.70× ± 0.04 | 4.36 | 5.80 | 97.9 | 98.4 | 25.6 | 0.021 | 97.3 | 43.00 | 35.94 | 0.08 |  |
| uringpy-app | thread | 4 | off | 13 | none | 300 | 5 | 30,931 | 450 | 1.2 | 1.20× ± 0.02 | 14.63 | 18.27 | 98.2 | 98.5 | 10.6 | 0.022 | 94.7 | 129.88 | 123.44 | 0.08 |  |
| uringpy-app | thread | 4 | off | 13 | none | 1000 | 5 | 9,054 | 159 | 1.4 | 1.07× ± 0.07 | 49.94 | 204.48 | 98.1 | 98.5 | 4.5 | 0.027 | 86.0 | 441.98 | 433.27 | 0.10 |  |
| uringpy-app | thread | 4 | off | 13 | none | 3000 | 5 | 3,002 | 25 | 0.7 | 1.01× ± 0.07 | 146.21 | 549.56 | 98.4 | 98.8 | 1.3 | 0.037 | 76.9 | 1,332.84 | 1,321.84 | 0.14 | socket errors or non-2xx responses |
