# Benchmark summary

- experiment: handler   started (UTC): 2026-10-07T15:13:18+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 23938898)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_OFF

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | conns | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | GIL rel. or acq./req | vol. ctx sw./req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy-app | thread | 1 | off | 13 | none | 0 | 400 | 5 | 120,201 | 3,546 | 2.4 | 1.00× | 3.31 | 3.55 | 28.8 | 97.9 | 33.5 | 0.005 | 385.6 | 8.36 | 1.31 | 0.05 | 1.000 | 0.000 |  |
| uringpy-app | thread | 1 | off | 13 | none | 30 | 400 | 5 | 89,315 | 2,170 | 2.0 | 1.00× | 4.45 | 4.85 | 27.6 | 98.3 | 24.6 | 0.006 | 382.4 | 11.23 | 4.27 | 0.05 | 1.000 | 0.000 |  |
| uringpy-app | thread | 1 | off | 13 | none | 100 | 400 | 5 | 54,491 | 518 | 0.8 | 1.00× | 7.30 | 7.89 | 26.6 | 98.2 | 15.6 | 0.006 | 371.6 | 18.47 | 11.46 | 0.05 | 1.000 | 0.000 |  |
| uringpy-app | thread | 1 | off | 13 | none | 300 | 400 | 5 | 25,198 | 397 | 1.3 | 1.00× | 15.81 | 392.91 | 25.7 | 98.0 | 7.2 | 0.007 | 350.2 | 39.92 | 32.60 | 0.05 | 1.000 | 0.000 |  |
| uringpy-app | thread | 1 | off | 13 | none | 1000 | 400 | 5 | 8,307 | 49 | 0.5 | 1.00× | 48.14 | 477.41 | 25.2 | 97.8 | 3.0 | 0.011 | 281.7 | 120.69 | 110.49 | 0.06 | 1.000 | 0.001 | socket errors or non-2xx responses |
| uringpy-app | thread | 1 | off | 13 | none | 3000 | 400 | 5 | 2,899 | 21 | 0.6 | 1.00× | 124.87 | 139.33 | 25.1 | 98.3 | 1.0 | 0.024 | 160.6 | 346.18 | 334.79 | 0.08 | 1.000 | 0.002 | socket errors or non-2xx responses |
| uringpy-app | thread | 2 | off | 13 | none | 0 | 400 | 5 | 199,676 | 5,786 | 2.3 | 1.66× ± 0.07 | 1.97 | 2.28 | 57.9 | 98.0 | 51.1 | 0.011 | 179.8 | 10.08 | 1.87 | 0.07 | 1.000 | 0.000 |  |
| uringpy-app | thread | 2 | off | 13 | none | 30 | 400 | 5 | 149,158 | 3,366 | 1.8 | 1.67× ± 0.06 | 2.63 | 3.10 | 55.3 | 98.1 | 40.7 | 0.011 | 187.6 | 13.48 | 5.89 | 0.06 | 1.000 | 0.000 |  |
| uringpy-app | thread | 2 | off | 13 | none | 100 | 400 | 5 | 88,019 | 1,928 | 1.8 | 1.62× ± 0.04 | 4.46 | 5.10 | 52.6 | 97.7 | 25.2 | 0.011 | 193.3 | 22.82 | 15.63 | 0.06 | 1.000 | 0.000 |  |
| uringpy-app | thread | 2 | off | 13 | none | 300 | 400 | 5 | 38,825 | 1,323 | 2.7 | 1.54× ± 0.06 | 10.21 | 11.28 | 50.8 | 98.4 | 11.8 | 0.011 | 189.0 | 51.76 | 44.81 | 0.07 | 1.000 | 0.000 |  |
| uringpy-app | thread | 2 | off | 13 | none | 1000 | 400 | 5 | 12,952 | 160 | 1.0 | 1.56× ± 0.02 | 30.42 | 330.16 | 49.7 | 98.1 | 4.0 | 0.014 | 172.5 | 155.17 | 147.79 | 0.07 | 1.000 | 0.001 |  |
| uringpy-app | thread | 2 | off | 13 | none | 3000 | 400 | 5 | 4,437 | 74 | 1.3 | 1.53× ± 0.03 | 87.48 | 506.79 | 49.8 | 98.5 | 1.6 | 0.021 | 143.3 | 451.99 | 440.63 | 0.09 | 1.000 | 0.002 | socket errors or non-2xx responses |
| uringpy-app | thread | 4 | off | 13 | none | 0 | 400 | 5 | 287,108 | 4,265 | 1.2 | 2.39× ± 0.08 | 1.33 | 1.89 | 97.4 | 97.9 | 70.2 | 0.024 | 82.6 | 13.87 | 3.05 | 0.11 | 1.000 | 0.001 |  |
| uringpy-app | thread | 4 | off | 13 | none | 30 | 400 | 5 | 210,691 | 2,178 | 0.8 | 2.36× ± 0.06 | 1.85 | 2.53 | 98.0 | 98.5 | 53.8 | 0.022 | 92.5 | 19.03 | 10.25 | 0.09 | 1.000 | 0.001 |  |
| uringpy-app | thread | 4 | off | 13 | none | 100 | 400 | 5 | 93,555 | 1,215 | 1.0 | 1.72× ± 0.03 | 4.46 | 5.68 | 98.2 | 98.5 | 27.0 | 0.021 | 96.9 | 42.80 | 35.66 | 0.08 | 1.000 | 0.000 |  |
| uringpy-app | thread | 4 | off | 13 | none | 300 | 400 | 5 | 31,872 | 526 | 1.3 | 1.26× ± 0.03 | 13.80 | 18.06 | 98.1 | 98.4 | 9.9 | 0.022 | 95.1 | 126.24 | 119.65 | 0.08 | 1.000 | 0.001 |  |
| uringpy-app | thread | 4 | off | 13 | none | 1000 | 400 | 5 | 9,257 | 357 | 3.1 | 1.11× ± 0.04 | 49.43 | 200.50 | 98.1 | 98.5 | 3.4 | 0.026 | 89.4 | 431.61 | 422.63 | 0.09 | 1.000 | 0.001 |  |
| uringpy-app | thread | 4 | off | 13 | none | 3000 | 400 | 5 | 2,994 | 140 | 3.8 | 1.03× ± 0.05 | 144.64 | 607.34 | 98.5 | 98.8 | 1.3 | 0.037 | 76.9 | 1,332.10 | 1,320.88 | 0.13 | 1.000 | 0.003 | socket errors or non-2xx responses |
