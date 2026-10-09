# Benchmark summary

- experiment: handler   started (UTC): 2026-10-06T16:11:08+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 1341479721)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy-app | thread | 1 | on | 13 | none | 0 | 5 | 123,224 | 1,781 | 1.2 | 1.00× | 3.22 | 3.48 | 28.9 | 98.3 | 34.5 | 0.005 | 387.4 | 8.16 | 1.20 | 0.06 |  |
| uringpy-app | thread | 1 | on | 13 | none | 30 | 5 | 91,341 | 1,082 | 1.0 | 1.00× | 4.35 | 4.74 | 27.8 | 98.1 | 25.0 | 0.006 | 382.5 | 11.00 | 4.11 | 0.06 |  |
| uringpy-app | thread | 1 | on | 13 | none | 100 | 5 | 55,441 | 1,300 | 1.9 | 1.00× | 7.19 | 7.78 | 26.6 | 98.1 | 15.3 | 0.006 | 373.5 | 18.14 | 11.09 | 0.06 |  |
| uringpy-app | thread | 1 | on | 13 | none | 300 | 5 | 26,510 | 193 | 0.6 | 1.00× | 15.03 | 338.38 | 25.7 | 98.0 | 7.4 | 0.007 | 349.9 | 37.94 | 30.75 | 0.06 |  |
| uringpy-app | thread | 1 | on | 13 | none | 1000 | 5 | 8,618 | 379 | 3.5 | 1.00× | 46.49 | 496.12 | 25.2 | 98.1 | 3.1 | 0.011 | 284.3 | 116.34 | 106.23 | 0.07 | socket errors or non-2xx responses |
| uringpy-app | thread | 1 | on | 13 | none | 3000 | 5 | 3,071 | 29 | 0.7 | 1.00× | 120.88 | 131.82 | 25.1 | 98.4 | 1.1 | 0.022 | 167.0 | 326.85 | 315.80 | 0.10 | socket errors or non-2xx responses |
| uringpy-app | thread | 2 | on | 13 | none | 0 | 5 | 189,881 | 5,191 | 2.2 | 1.54× ± 0.05 | 2.05 | 2.60 | 56.0 | 93.8 | 47.7 | 0.011 | 183.6 | 10.34 | 1.70 | 0.65 |  |
| uringpy-app | thread | 2 | on | 13 | none | 30 | 5 | 133,767 | 3,461 | 2.1 | 1.46× ± 0.04 | 2.84 | 4.20 | 51.4 | 77.6 | 36.4 | 0.011 | 191.1 | 13.97 | 5.09 | 2.04 |  |
| uringpy-app | thread | 2 | on | 13 | none | 100 | 5 | 68,227 | 2,127 | 2.5 | 1.23× ± 0.05 | 5.73 | 9.06 | 42.7 | 60.2 | 19.8 | 0.011 | 191.8 | 23.88 | 12.57 | 8.59 |  |
| uringpy-app | thread | 2 | on | 13 | none | 300 | 5 | 27,749 | 1,335 | 3.9 | 1.05× ± 0.05 | 14.36 | 21.85 | 33.1 | 39.9 | 8.1 | 0.012 | 185.1 | 46.84 | 33.75 | 29.87 |  |
| uringpy-app | thread | 2 | on | 13 | none | 1000 | 5 | 9,085 | 131 | 1.2 | 1.05× ± 0.05 | 43.89 | 585.45 | 28.3 | 39.9 | 3.3 | 0.016 | 166.6 | 124.59 | 107.52 | 101.07 | socket errors or non-2xx responses |
| uringpy-app | thread | 2 | on | 13 | none | 3000 | 5 | 3,008 | 252 | 6.8 | 0.98× ± 0.08 | 132.87 | 359.52 | 26.9 | 43.4 | 1.1 | 0.027 | 123.6 | 350.59 | 326.96 | 324.50 | CV > 5%; socket errors or non-2xx responses |
| uringpy-app | thread | 4 | on | 13 | none | 0 | 5 | 184,759 | 3,035 | 1.3 | 1.50× ± 0.03 | 2.09 | 3.68 | 79.6 | 80.7 | 46.4 | 0.022 | 92.4 | 16.04 | 2.21 | 8.51 |  |
| uringpy-app | thread | 4 | on | 13 | none | 30 | 5 | 91,567 | 1,131 | 1.0 | 1.00× ± 0.02 | 4.19 | 8.58 | 63.6 | 64.6 | 25.9 | 0.021 | 96.1 | 24.98 | 5.42 | 26.36 |  |
| uringpy-app | thread | 4 | on | 13 | none | 100 | 5 | 61,359 | 870 | 1.1 | 1.11× ± 0.03 | 6.01 | 16.11 | 47.8 | 49.2 | 19.0 | 0.021 | 96.4 | 28.65 | 12.61 | 43.09 |  |
| uringpy-app | thread | 4 | on | 13 | none | 300 | 5 | 27,602 | 728 | 2.1 | 1.04× ± 0.03 | 13.41 | 37.63 | 34.9 | 36.1 | 9.1 | 0.022 | 95.4 | 47.94 | 33.38 | 103.26 |  |
| uringpy-app | thread | 4 | on | 13 | none | 1000 | 5 | 8,436 | 145 | 1.4 | 0.98× ± 0.05 | 43.33 | 204.28 | 34.5 | 40.4 | 3.2 | 0.026 | 89.7 | 135.71 | 113.08 | 348.42 |  |
| uringpy-app | thread | 4 | on | 13 | none | 3000 | 5 | 3,067 | 26 | 0.7 | 1.00× ± 0.01 | 111.48 | 592.08 | 30.3 | 34.9 | 1.4 | 0.036 | 77.5 | 347.87 | 320.40 | 969.16 | socket errors or non-2xx responses |
| uringpy-app | process | 1 | on | 13 | none | 0 | 5 | 122,898 | 6,813 | 4.5 | 1.00× | 3.19 | 5.03 | 29.2 | 98.1 | 35.6 | 0.005 | 387.1 | 8.18 | 1.24 | 0.07 |  |
| uringpy-app | process | 1 | on | 13 | none | 30 | 5 | 90,681 | 934 | 0.8 | 1.00× | 4.38 | 4.80 | 27.7 | 91.1 | 25.5 | 0.006 | 381.0 | 11.06 | 4.08 | 0.06 |  |
| uringpy-app | process | 1 | on | 13 | none | 100 | 5 | 55,978 | 1,235 | 1.8 | 1.00× | 7.12 | 7.84 | 26.6 | 98.0 | 15.4 | 0.006 | 373.7 | 17.94 | 10.91 | 0.06 |  |
| uringpy-app | process | 1 | on | 13 | none | 300 | 5 | 26,506 | 75 | 0.2 | 1.00× | 15.03 | 307.49 | 25.7 | 91.2 | 7.5 | 0.007 | 351.4 | 37.87 | 30.77 | 0.06 |  |
| uringpy-app | process | 1 | on | 13 | none | 1000 | 5 | 8,784 | 55 | 0.5 | 1.00× | 45.58 | 496.07 | 25.2 | 98.0 | 3.1 | 0.011 | 285.1 | 113.84 | 104.01 | 0.07 | socket errors or non-2xx responses |
| uringpy-app | process | 1 | on | 13 | none | 3000 | 5 | 3,067 | 49 | 1.3 | 1.00× | 120.67 | 131.47 | 25.1 | 98.4 | 1.1 | 0.022 | 166.6 | 326.33 | 315.96 | 0.09 | socket errors or non-2xx responses |
| uringpy-app | process | 2 | on | 13 | none | 0 | 5 | 201,072 | 1,073 | 0.4 | 1.64× ± 0.09 | 1.94 | 2.33 | 58.2 | 98.3 | 50.6 | 0.012 | 176.3 | 10.03 | 1.76 | 0.09 |  |
| uringpy-app | process | 2 | on | 13 | none | 30 | 5 | 156,565 | 2,004 | 1.0 | 1.73× ± 0.03 | 2.52 | 2.89 | 55.4 | 98.1 | 40.6 | 0.011 | 187.1 | 12.85 | 5.03 | 0.08 |  |
| uringpy-app | process | 2 | on | 13 | none | 100 | 5 | 102,420 | 967 | 0.8 | 1.83× ± 0.04 | 3.83 | 4.40 | 53.1 | 98.1 | 28.0 | 0.011 | 192.9 | 19.59 | 12.33 | 0.07 |  |
| uringpy-app | process | 2 | on | 13 | none | 300 | 5 | 49,398 | 2,362 | 3.9 | 1.86× ± 0.09 | 7.84 | 8.95 | 51.2 | 98.3 | 13.6 | 0.011 | 188.9 | 40.63 | 33.68 | 0.07 |  |
| uringpy-app | process | 2 | on | 13 | none | 1000 | 5 | 17,637 | 351 | 1.6 | 2.01× ± 0.04 | 22.12 | 139.98 | 50.1 | 98.3 | 5.3 | 0.013 | 178.9 | 113.74 | 106.72 | 0.08 |  |
| uringpy-app | process | 2 | on | 13 | none | 3000 | 5 | 6,045 | 203 | 2.7 | 1.97× ± 0.07 | 62.32 | 620.95 | 49.9 | 98.5 | 2.3 | 0.018 | 153.1 | 331.52 | 321.08 | 0.10 | socket errors or non-2xx responses |
| uringpy-app | process | 4 | on | 13 | none | 0 | 5 | 289,547 | 2,060 | 0.6 | 2.36× ± 0.13 | 1.32 | 1.86 | 98.0 | 98.4 | 68.9 | 0.023 | 88.9 | 13.80 | 2.78 | 0.15 |  |
| uringpy-app | process | 4 | on | 13 | none | 30 | 5 | 239,059 | 1,627 | 0.5 | 2.64× ± 0.03 | 1.64 | 2.16 | 97.8 | 98.3 | 58.6 | 0.022 | 93.0 | 16.75 | 7.28 | 0.12 |  |
| uringpy-app | process | 4 | on | 13 | none | 100 | 5 | 172,335 | 2,266 | 1.1 | 3.08× ± 0.08 | 2.28 | 2.81 | 98.2 | 98.5 | 44.9 | 0.021 | 94.6 | 23.25 | 15.22 | 0.10 |  |
| uringpy-app | process | 4 | on | 13 | none | 300 | 5 | 93,059 | 711 | 0.6 | 3.51× ± 0.03 | 4.28 | 4.91 | 97.9 | 98.5 | 26.5 | 0.021 | 96.1 | 43.08 | 36.18 | 0.09 |  |
| uringpy-app | process | 4 | on | 13 | none | 1000 | 5 | 34,408 | 201 | 0.5 | 3.92× ± 0.03 | 11.49 | 13.05 | 98.1 | 98.4 | 10.8 | 0.022 | 95.6 | 116.51 | 110.08 | 0.08 |  |
| uringpy-app | process | 4 | on | 13 | none | 3000 | 5 | 12,199 | 108 | 0.7 | 3.98× ± 0.07 | 32.06 | 43.83 | 98.1 | 98.5 | 4.1 | 0.024 | 92.2 | 328.43 | 321.61 | 0.10 |  |
