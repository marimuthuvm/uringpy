# Benchmark summary

- experiment: handler   started (UTC): 2026-10-06T20:40:33+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 42790355)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy-app-batch | thread | 1 | on | 13 | none | 0 | 5 | 126,585 | 2,050 | 1.3 | 1.00× | 3.14 | 3.38 | 28.8 | 97.9 | 33.6 | 0.006 | 379.8 | 7.91 | 1.24 | 0.00 |  |
| uringpy-app-batch | thread | 1 | on | 13 | none | 30 | 5 | 96,200 | 929 | 0.8 | 1.00× | 4.13 | 4.46 | 27.7 | 98.1 | 25.4 | 0.006 | 383.0 | 10.50 | 4.00 | 0.00 |  |
| uringpy-app-batch | thread | 1 | on | 13 | none | 100 | 5 | 57,773 | 182 | 0.3 | 1.00× | 6.89 | 7.44 | 26.6 | 97.9 | 15.4 | 0.006 | 376.3 | 17.41 | 10.87 | 0.00 |  |
| uringpy-app-batch | thread | 1 | on | 13 | none | 300 | 5 | 27,105 | 378 | 1.1 | 1.00× | 14.70 | 269.22 | 25.7 | 97.7 | 7.2 | 0.007 | 349.9 | 37.13 | 30.51 | 0.00 |  |
| uringpy-app-batch | thread | 1 | on | 13 | none | 1000 | 5 | 8,992 | 124 | 1.1 | 1.00× | 44.55 | 507.28 | 25.2 | 97.9 | 2.5 | 0.011 | 287.1 | 111.50 | 102.44 | 0.01 | socket errors or non-2xx responses |
| uringpy-app-batch | thread | 1 | on | 13 | none | 3000 | 5 | 3,139 | 68 | 1.8 | 1.00× | 119.54 | 128.37 | 25.1 | 98.2 | 1.0 | 0.022 | 169.1 | 319.65 | 310.27 | 0.01 | socket errors or non-2xx responses |
| uringpy-app-batch | thread | 2 | on | 13 | none | 0 | 5 | 203,898 | 4,594 | 1.8 | 1.61× ± 0.04 | 1.92 | 2.33 | 57.0 | 97.6 | 50.6 | 0.011 | 186.4 | 9.67 | 1.71 | 0.24 |  |
| uringpy-app-batch | thread | 2 | on | 13 | none | 30 | 5 | 148,364 | 6,341 | 3.4 | 1.54× ± 0.07 | 2.67 | 3.06 | 51.5 | 93.3 | 39.5 | 0.011 | 189.2 | 12.56 | 5.20 | 0.96 |  |
| uringpy-app-batch | thread | 2 | on | 13 | none | 100 | 5 | 76,883 | 977 | 1.0 | 1.33× ± 0.02 | 5.16 | 5.70 | 39.5 | 67.3 | 21.1 | 0.011 | 192.0 | 19.21 | 12.65 | 7.03 |  |
| uringpy-app-batch | thread | 2 | on | 13 | none | 300 | 5 | 29,430 | 1,251 | 3.4 | 1.09× ± 0.05 | 13.54 | 14.94 | 30.5 | 46.9 | 8.3 | 0.012 | 185.3 | 40.09 | 33.70 | 28.43 |  |
| uringpy-app-batch | thread | 2 | on | 13 | none | 1000 | 5 | 9,180 | 539 | 4.7 | 1.02× ± 0.06 | 43.10 | 578.90 | 27.5 | 45.6 | 2.8 | 0.016 | 166.4 | 118.60 | 167.28 | 41.89 | socket errors or non-2xx responses |
| uringpy-app-batch | thread | 2 | on | 13 | none | 3000 | 5 | 3,144 | 30 | 0.8 | 1.00× ± 0.02 | 121.64 | 377.30 | 25.9 | 38.2 | 1.1 | 0.026 | 125.0 | 327.63 | 571.47 | 56.45 | socket errors or non-2xx responses |
| uringpy-app-batch | thread | 4 | on | 13 | none | 0 | 5 | 278,289 | 1,062 | 0.3 | 2.20× ± 0.04 | 1.39 | 1.95 | 93.1 | 94.7 | 67.2 | 0.022 | 93.3 | 13.16 | 2.42 | 1.60 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 30 | 5 | 156,346 | 2,657 | 1.4 | 1.63× ± 0.03 | 2.54 | 3.58 | 63.7 | 66.3 | 41.9 | 0.021 | 96.4 | 13.83 | 5.92 | 12.27 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 100 | 5 | 71,551 | 4,549 | 5.1 | 1.24× ± 0.08 | 5.56 | 6.65 | 39.9 | 51.3 | 21.9 | 0.021 | 96.3 | 19.74 | 13.44 | 36.70 | CV > 5% |
| uringpy-app-batch | thread | 4 | on | 13 | none | 300 | 5 | 28,061 | 965 | 2.8 | 1.04× ± 0.04 | 12.97 | 21.60 | 31.0 | 33.8 | 8.6 | 0.022 | 96.4 | 41.49 | 35.02 | 102.09 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 1000 | 5 | 9,035 | 70 | 0.6 | 1.00× ± 0.02 | 40.05 | 158.91 | 29.0 | 31.5 | 3.1 | 0.026 | 90.3 | 119.67 | 212.83 | 222.60 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 3000 | 5 | 3,086 | 18 | 0.5 | 0.98× ± 0.02 | 117.14 | 600.86 | 27.6 | 29.8 | 1.4 | 0.037 | 77.1 | 336.89 | 978.66 | 306.73 | socket errors or non-2xx responses |
