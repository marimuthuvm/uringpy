# Benchmark summary

- experiment: size   started (UTC): 2026-10-06T14:55:40+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 1092469886)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up.

| engine | mode | workers | GIL | body B | batch cap | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy | thread | 4 | on | 64 | none | 5 | 328,092 | 2,166 | 0.5 | - | 1.15 | 1.77 | 98.1 | 98.5 | 77.5 | 0.022 | 90.9 |  |
| uringpy | thread | 4 | on | 1024 | none | 5 | 321,257 | 781 | 0.2 | - | 1.19 | 1.69 | 97.9 | 98.3 | 76.2 | 0.022 | 91.4 |  |
| uringpy | thread | 4 | on | 16384 | none | 5 | 119,416 | 200 | 0.1 | - | 3.18 | 7.72 | 82.7 | 84.7 | 60.5 | 0.579 | 3.5 |  |
| uringpy | thread | 4 | on | 65536 | none | 5 | 29,978 | 174 | 0.5 | - | 12.98 | 46.20 | 34.2 | 35.9 | 35.9 | 0.655 | 3.1 |  |
| uringpy | thread | 4 | on | 262144 | none | 5 | 7,479 | 45 | 0.5 | - | 51.00 | 254.16 | 30.1 | 31.6 | 33.9 | 1.088 | 1.9 |  |
| uringpy | thread | 4 | on | 1048576 | none | 5 | 1,863 | 10 | 0.5 | - | 206.10 | 431.28 | 39.7 | 41.2 | 45.6 | 2.499 | 1.2 |  |
| asyncio | thread | 4 | on | 64 | none | 5 | 34,181 | 381 | 0.9 | - | 11.57 | 15.89 | 44.1 | 44.7 | 14.9 | - | - |  |
| asyncio | thread | 4 | on | 1024 | none | 5 | 33,795 | 483 | 1.2 | - | 11.83 | 15.28 | 44.0 | 44.5 | 14.5 | - | - |  |
| asyncio | thread | 4 | on | 16384 | none | 5 | 29,650 | 172 | 0.5 | - | 13.21 | 16.79 | 48.3 | 49.4 | 18.5 | - | - |  |
| asyncio | thread | 4 | on | 65536 | none | 5 | 27,251 | 207 | 0.6 | - | 14.53 | 18.25 | 59.4 | 60.6 | 29.3 | - | - |  |
| asyncio | thread | 4 | on | 262144 | none | 5 | 7,503 | 6 | 0.1 | - | 50.91 | 238.57 | 35.9 | 38.6 | 33.2 | - | - |  |
| asyncio | thread | 4 | on | 1048576 | none | 5 | 1,865 | 8 | 0.3 | - | 206.10 | 427.87 | 44.7 | 47.2 | 45.9 | - | - |  |
