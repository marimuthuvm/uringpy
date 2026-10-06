# Benchmark summary

- experiment: app   started (UTC): 2026-10-06T12:49:55+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 367053274)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up.

| engine | mode | workers | GIL | body B | batch cap | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy-app | thread | 1 | on | 13 | none | 5 | 122,256 | 2,962 | 2.0 | 1.00× | 3.25 | 3.48 | 29.0 | 98.2 | 32.6 | 0.006 | 376.1 |  |
| uringpy-app | thread | 2 | on | 13 | none | 5 | 189,510 | 5,790 | 2.5 | 1.55× ± 0.06 | 2.06 | 2.58 | 56.2 | 93.6 | 47.5 | 0.011 | 180.5 |  |
| uringpy-app | thread | 4 | on | 13 | none | 5 | 192,464 | 7,171 | 3.0 | 1.57× ± 0.07 | 2.01 | 3.52 | 81.2 | 81.9 | 47.6 | 0.022 | 93.5 |  |
| uringpy-app | process | 1 | on | 13 | none | 5 | 124,157 | 3,669 | 2.4 | 1.00× | 3.20 | 3.43 | 29.1 | 97.6 | 33.5 | 0.005 | 383.9 |  |
| uringpy-app | process | 2 | on | 13 | none | 5 | 200,261 | 5,703 | 2.3 | 1.61× ± 0.07 | 1.95 | 2.33 | 57.7 | 98.3 | 49.9 | 0.011 | 180.9 |  |
| uringpy-app | process | 4 | on | 13 | none | 5 | 292,863 | 1,396 | 0.4 | 2.36× ± 0.07 | 1.32 | 1.77 | 97.7 | 98.3 | 68.8 | 0.022 | 92.0 |  |
| asyncio-app | thread | 1 | on | 13 | none | 5 | 60,339 | 1,055 | 1.4 | 1.00× | 6.60 | 6.93 | 26.9 | 98.1 | 17.7 | - | - |  |
| asyncio-app | thread | 2 | on | 13 | none | 5 | 39,946 | 1,409 | 2.8 | 0.66× ± 0.03 | 9.98 | 11.72 | 37.2 | 47.6 | 15.1 | - | - |  |
| asyncio-app | thread | 4 | on | 13 | none | 5 | 30,515 | 385 | 1.0 | 0.51× ± 0.01 | 13.01 | 17.19 | 41.9 | 43.1 | 12.6 | - | - |  |
| asyncio-app | process | 1 | on | 13 | none | 5 | 59,855 | 1,738 | 2.3 | 1.00× | 6.65 | 7.02 | 26.8 | 97.8 | 17.7 | - | - |  |
| asyncio-app | process | 2 | on | 13 | none | 5 | 102,826 | 2,178 | 1.7 | 1.72× ± 0.06 | 3.88 | 4.23 | 53.5 | 98.2 | 32.8 | - | - |  |
| asyncio-app | process | 4 | on | 13 | none | 5 | 155,441 | 10,893 | 5.6 | 2.60× ± 0.20 | 2.44 | 3.94 | 98.3 | 98.5 | 48.2 | - | - | CV > 5% |
