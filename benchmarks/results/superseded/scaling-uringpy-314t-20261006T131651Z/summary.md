# Benchmark summary

- experiment: scaling   started (UTC): 2026-10-06T13:16:51+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 1804126661)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_OFF

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up.

| engine | mode | workers | GIL | body B | batch cap | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy | thread | 1 | off | 13 | none | 5 | 142,406 | 5,144 | 2.9 | 1.00× | 2.79 | 3.04 | 29.7 | 98.1 | 40.7 | 0.006 | 350.7 |  |
| uringpy | thread | 2 | off | 13 | none | 5 | 229,732 | 3,699 | 1.3 | 1.61× ± 0.06 | 1.69 | 2.08 | 59.3 | 98.0 | 57.8 | 0.011 | 177.0 |  |
| uringpy | thread | 3 | off | 13 | none | 5 | 285,827 | 5,316 | 1.5 | 2.01× ± 0.08 | 1.35 | 1.81 | 82.4 | 98.3 | 69.7 | 0.018 | 114.5 |  |
| uringpy | thread | 4 | off | 13 | none | 5 | 326,983 | 1,492 | 0.4 | 2.30× ± 0.08 | 1.16 | 1.75 | 97.9 | 98.3 | 76.9 | 0.023 | 85.7 |  |
| uringpy | process | 1 | off | 13 | none | 5 | 142,184 | 5,116 | 2.9 | 1.00× | 2.79 | 3.01 | 29.7 | 98.3 | 39.0 | 0.006 | 327.1 |  |
| uringpy | process | 2 | off | 13 | none | 5 | 227,989 | 3,649 | 1.3 | 1.60× ± 0.06 | 1.71 | 2.08 | 59.4 | 98.2 | 57.3 | 0.012 | 171.3 |  |
| uringpy | process | 3 | off | 13 | none | 5 | 287,754 | 2,255 | 0.6 | 2.02× ± 0.07 | 1.33 | 1.85 | 83.3 | 98.1 | 70.7 | 0.017 | 115.5 |  |
| uringpy | process | 4 | off | 13 | none | 5 | 325,234 | 1,607 | 0.4 | 2.29× ± 0.08 | 1.16 | 1.74 | 98.1 | 98.4 | 77.3 | 0.023 | 87.0 |  |
| asyncio | thread | 1 | off | 13 | none | 5 | 63,206 | 1,771 | 2.3 | 1.00× | 6.26 | 6.78 | 27.0 | 97.8 | 19.7 | - | - |  |
| asyncio | thread | 2 | off | 13 | none | 5 | 108,807 | 572 | 0.4 | 1.72× ± 0.05 | 3.63 | 4.09 | 54.0 | 98.2 | 34.5 | - | - |  |
| asyncio | thread | 3 | off | 13 | none | 5 | 140,955 | 2,465 | 1.4 | 2.23× ± 0.07 | 2.84 | 3.21 | 77.8 | 98.0 | 44.1 | - | - |  |
| asyncio | thread | 4 | off | 13 | none | 5 | 166,609 | 943 | 0.5 | 2.64× ± 0.08 | 2.36 | 2.81 | 98.2 | 98.5 | 50.4 | - | - |  |
| asyncio | process | 1 | off | 13 | none | 5 | 64,909 | 1,136 | 1.4 | 1.00× | 6.13 | 6.52 | 27.0 | 97.8 | 19.7 | - | - |  |
| asyncio | process | 2 | off | 13 | none | 5 | 110,977 | 1,640 | 1.2 | 1.71× ± 0.04 | 3.58 | 3.92 | 53.8 | 98.4 | 35.1 | - | - |  |
| asyncio | process | 3 | off | 13 | none | 5 | 146,109 | 2,400 | 1.3 | 2.25× ± 0.05 | 2.74 | 3.12 | 77.9 | 98.0 | 45.6 | - | - |  |
| asyncio | process | 4 | off | 13 | none | 5 | 172,531 | 2,607 | 1.2 | 2.66× ± 0.06 | 2.28 | 2.82 | 97.9 | 98.4 | 52.6 | - | - |  |
| asyncio-proto | thread | 1 | off | 13 | none | 5 | 90,004 | 1,782 | 1.6 | 1.00× | 4.34 | 8.68 | 28.0 | 97.9 | 27.8 | - | - |  |
| asyncio-proto | thread | 2 | off | 13 | none | 5 | 147,175 | 2,816 | 1.5 | 1.64× ± 0.05 | 2.64 | 5.45 | 55.5 | 98.0 | 45.2 | - | - |  |
| asyncio-proto | thread | 3 | off | 13 | none | 5 | 189,772 | 1,711 | 0.7 | 2.11× ± 0.05 | 1.98 | 4.27 | 79.3 | 98.0 | 58.3 | - | - |  |
| asyncio-proto | thread | 4 | off | 13 | none | 5 | 224,635 | 1,211 | 0.4 | 2.50× ± 0.05 | 1.62 | 3.66 | 97.6 | 98.2 | 66.6 | - | - |  |
| asyncio-proto | process | 1 | off | 13 | none | 5 | 91,269 | 1,091 | 1.0 | 1.00× | 4.28 | 8.57 | 28.0 | 98.3 | 28.2 | - | - |  |
| asyncio-proto | process | 2 | off | 13 | none | 5 | 151,701 | 1,720 | 0.9 | 1.66× ± 0.03 | 2.55 | 5.29 | 56.1 | 98.3 | 49.7 | - | - |  |
| asyncio-proto | process | 3 | off | 13 | none | 5 | 196,141 | 1,484 | 0.6 | 2.15× ± 0.03 | 1.96 | 4.13 | 80.0 | 98.0 | 59.7 | - | - |  |
| asyncio-proto | process | 4 | off | 13 | none | 5 | 230,405 | 1,309 | 0.5 | 2.52× ± 0.03 | 1.61 | 3.59 | 98.0 | 98.4 | 66.0 | - | - |  |
