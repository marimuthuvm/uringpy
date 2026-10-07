# Benchmark summary

- experiment: handler   started (UTC): 2026-10-06T17:32:21+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 1682686939)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| asyncio-app | thread | 1 | on | 13 | none | 0 | 5 | 59,659 | 826 | 1.1 | 1.00× | 6.68 | 6.99 | 26.8 | 98.4 | 17.2 | - | - | - | - | - |  |
| asyncio-app | thread | 1 | on | 13 | none | 30 | 5 | 48,726 | 1,250 | 2.1 | 1.00× | 8.18 | 8.54 | 26.5 | 98.1 | 14.9 | - | - | - | - | - |  |
| asyncio-app | thread | 1 | on | 13 | none | 100 | 5 | 36,256 | 360 | 0.8 | 1.00× | 10.99 | 11.41 | 26.2 | 98.1 | 12.3 | - | - | - | - | - |  |
| asyncio-app | thread | 1 | on | 13 | none | 300 | 5 | 20,369 | 306 | 1.2 | 1.00× | 19.58 | 20.22 | 25.8 | 97.9 | 7.9 | - | - | - | - | - |  |
| asyncio-app | thread | 1 | on | 13 | none | 1000 | 5 | 7,842 | 53 | 0.5 | 1.00× | 50.87 | 52.20 | 26.6 | 98.4 | 4.7 | - | - | - | - | - |  |
| asyncio-app | thread | 1 | on | 13 | none | 3000 | 5 | 2,834 | 262 | 7.5 | 1.00× | 141.69 | 143.81 | 25.5 | 98.6 | 1.5 | - | - | - | - | - | CV > 5% |
| asyncio-app | thread | 4 | on | 13 | none | 0 | 5 | 30,856 | 487 | 1.3 | 0.52× ± 0.01 | 12.88 | 16.88 | 42.0 | 43.0 | 12.8 | - | - | - | - | - |  |
| asyncio-app | thread | 4 | on | 13 | none | 30 | 5 | 27,267 | 205 | 0.6 | 0.56× ± 0.01 | 14.60 | 18.99 | 40.0 | 40.5 | 12.2 | - | - | - | - | - |  |
| asyncio-app | thread | 4 | on | 13 | none | 100 | 5 | 22,983 | 220 | 0.8 | 0.63× ± 0.01 | 17.28 | 22.68 | 37.4 | 38.1 | 10.5 | - | - | - | - | - |  |
| asyncio-app | thread | 4 | on | 13 | none | 300 | 5 | 15,220 | 109 | 0.6 | 0.75× ± 0.01 | 26.09 | 33.83 | 33.3 | 33.7 | 7.6 | - | - | - | - | - |  |
| asyncio-app | thread | 4 | on | 13 | none | 1000 | 5 | 6,748 | 40 | 0.5 | 0.86× ± 0.01 | 58.98 | 84.58 | 32.5 | 34.8 | 4.3 | - | - | - | - | - |  |
| asyncio-app | thread | 4 | on | 13 | none | 3000 | 5 | 2,795 | 36 | 1.0 | 0.99× ± 0.09 | 142.44 | 238.48 | 29.9 | 33.4 | 1.7 | - | - | - | - | - |  |
