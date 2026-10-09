# Benchmark summary

- experiment: scaling   started (UTC): 2026-10-06T11:15:36+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 1632166231)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up.

| engine | mode | workers | GIL | body B | batch cap | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy | thread | 1 | on | 13 | none | 5 | 140,744 | 3,006 | 1.7 | 1.00× | 2.83 | 2.99 | 29.5 | 98.2 | 37.1 | 0.006 | 370.6 |  |
| uringpy | thread | 2 | on | 13 | none | 5 | 228,329 | 6,025 | 2.1 | 1.62× ± 0.06 | 1.72 | 2.05 | 58.8 | 97.7 | 56.0 | 0.012 | 175.3 |  |
| uringpy | thread | 3 | on | 13 | none | 5 | 286,539 | 3,930 | 1.1 | 2.04× ± 0.05 | 1.35 | 1.77 | 82.3 | 98.1 | 66.7 | 0.017 | 116.9 |  |
| uringpy | thread | 4 | on | 13 | none | 5 | 328,389 | 789 | 0.2 | 2.33× ± 0.05 | 1.16 | 1.68 | 97.9 | 98.3 | 75.1 | 0.022 | 89.8 |  |
| uringpy | process | 1 | on | 13 | none | 5 | 144,381 | 3,792 | 2.1 | 1.00× | 2.76 | 2.93 | 29.7 | 97.9 | 37.6 | 0.006 | 354.2 |  |
| uringpy | process | 2 | on | 13 | none | 5 | 230,406 | 6,997 | 2.4 | 1.60× ± 0.06 | 1.70 | 2.01 | 59.3 | 98.3 | 56.1 | 0.011 | 179.1 |  |
| uringpy | process | 3 | on | 13 | none | 5 | 288,510 | 1,922 | 0.5 | 2.00× ± 0.05 | 1.32 | 1.83 | 82.8 | 98.3 | 67.4 | 0.017 | 115.8 |  |
| uringpy | process | 4 | on | 13 | none | 5 | 328,889 | 1,241 | 0.3 | 2.28× ± 0.06 | 1.18 | 1.60 | 97.9 | 98.4 | 75.8 | 0.023 | 89.1 |  |
| asyncio | thread | 1 | on | 13 | none | 5 | 66,760 | 1,075 | 1.3 | 1.00× | 5.97 | 6.24 | 26.8 | 97.4 | 18.3 | - | - |  |
| asyncio | thread | 2 | on | 13 | none | 5 | 47,822 | 796 | 1.3 | 0.72× ± 0.02 | 8.33 | 9.74 | 38.6 | 59.8 | 16.0 | - | - |  |
| asyncio | thread | 3 | on | 13 | none | 5 | 35,494 | 126 | 0.3 | 0.53× ± 0.01 | 11.23 | 13.81 | 41.3 | 46.5 | 13.0 | - | - |  |
| asyncio | thread | 4 | on | 13 | none | 5 | 34,387 | 180 | 0.4 | 0.52× ± 0.01 | 11.54 | 15.38 | 44.1 | 44.6 | 12.5 | - | - |  |
| asyncio | process | 1 | on | 13 | none | 5 | 68,066 | 970 | 1.1 | 1.00× | 5.85 | 6.11 | 26.9 | 98.2 | 18.9 | - | - |  |
| asyncio | process | 2 | on | 13 | none | 5 | 116,801 | 1,359 | 0.9 | 1.72× ± 0.03 | 3.41 | 3.73 | 54.1 | 98.1 | 33.5 | - | - |  |
| asyncio | process | 3 | on | 13 | none | 5 | 151,667 | 2,707 | 1.4 | 2.23× ± 0.05 | 2.67 | 3.03 | 77.9 | 98.4 | 43.5 | - | - |  |
| asyncio | process | 4 | on | 13 | none | 5 | 179,605 | 784 | 0.4 | 2.64× ± 0.04 | 2.18 | 2.66 | 97.9 | 98.4 | 53.0 | - | - |  |
| asyncio-proto | thread | 1 | on | 13 | none | 5 | 93,640 | 1,643 | 1.4 | 1.00× | 4.18 | 8.36 | 28.0 | 98.2 | 26.4 | - | - |  |
| asyncio-proto | thread | 2 | on | 13 | none | 5 | 95,182 | 1,610 | 1.4 | 1.02× ± 0.02 | 4.08 | 8.29 | 46.5 | 75.0 | 28.8 | - | - |  |
| asyncio-proto | thread | 3 | on | 13 | none | 5 | 59,902 | 494 | 0.7 | 0.64× ± 0.01 | 6.57 | 13.00 | 51.2 | 59.9 | 19.3 | - | - |  |
| asyncio-proto | thread | 4 | on | 13 | none | 5 | 45,042 | 879 | 1.6 | 0.48× ± 0.01 | 8.81 | 16.68 | 54.2 | 55.4 | 15.3 | - | - |  |
| asyncio-proto | process | 1 | on | 13 | none | 5 | 94,295 | 1,566 | 1.3 | 1.00× | 4.15 | 8.30 | 28.0 | 98.1 | 26.6 | - | - |  |
| asyncio-proto | process | 2 | on | 13 | none | 5 | 157,600 | 4,212 | 2.2 | 1.67× ± 0.05 | 2.47 | 5.10 | 56.3 | 98.1 | 46.1 | - | - |  |
| asyncio-proto | process | 3 | on | 13 | none | 5 | 201,158 | 3,436 | 1.4 | 2.13× ± 0.05 | 1.87 | 4.07 | 80.2 | 98.3 | 58.5 | - | - |  |
| asyncio-proto | process | 4 | on | 13 | none | 5 | 235,334 | 1,667 | 0.6 | 2.50× ± 0.05 | 1.58 | 3.53 | 97.6 | 98.3 | 66.5 | - | - |  |
