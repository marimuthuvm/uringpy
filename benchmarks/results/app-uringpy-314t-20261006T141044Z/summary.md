# Benchmark summary

- experiment: app   started (UTC): 2026-10-06T14:10:44+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 253294783)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_OFF

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up.

| engine | mode | workers | GIL | body B | batch cap | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy-app | thread | 1 | off | 13 | none | 5 | 123,914 | 3,887 | 2.5 | 1.00× | 3.20 | 3.54 | 29.0 | 98.2 | 40.1 | 0.005 | 382.3 |  |
| uringpy-app | thread | 2 | off | 13 | none | 5 | 199,904 | 3,086 | 1.2 | 1.61× ± 0.06 | 1.95 | 2.39 | 57.7 | 98.3 | 55.7 | 0.011 | 182.4 |  |
| uringpy-app | thread | 4 | off | 13 | none | 5 | 286,185 | 10,571 | 3.0 | 2.31× ± 0.11 | 1.30 | 2.02 | 97.2 | 97.8 | 73.1 | 0.027 | 73.8 |  |
| uringpy-app | process | 1 | off | 13 | none | 5 | 124,314 | 1,745 | 1.1 | 1.00× | 3.19 | 3.48 | 29.1 | 98.2 | 36.9 | 0.005 | 382.7 |  |
| uringpy-app | process | 2 | off | 13 | none | 5 | 200,512 | 4,554 | 1.8 | 1.61× ± 0.04 | 1.95 | 2.35 | 57.6 | 98.3 | 55.2 | 0.011 | 181.7 |  |
| uringpy-app | process | 4 | off | 13 | none | 5 | 283,082 | 16,435 | 4.7 | 2.28× ± 0.14 | 1.28 | 3.22 | 97.7 | 98.1 | 72.7 | 0.027 | 73.4 |  |
| asyncio-app | thread | 1 | off | 13 | none | 5 | 55,742 | 916 | 1.3 | 1.00× | 7.09 | 7.69 | 26.7 | 97.5 | 18.6 | - | - |  |
| asyncio-app | thread | 2 | off | 13 | none | 5 | 95,684 | 911 | 0.8 | 1.72× ± 0.03 | 4.14 | 4.63 | 53.2 | 97.8 | 33.7 | - | - |  |
| asyncio-app | thread | 4 | off | 13 | none | 5 | 149,379 | 1,123 | 0.6 | 2.68× ± 0.05 | 2.65 | 3.20 | 97.9 | 98.4 | 49.8 | - | - |  |
| asyncio-app | process | 1 | off | 13 | none | 5 | 56,557 | 1,190 | 1.7 | 1.00× | 7.04 | 7.46 | 26.7 | 98.0 | 18.1 | - | - |  |
| asyncio-app | process | 2 | off | 13 | none | 5 | 98,526 | 994 | 0.8 | 1.74× ± 0.04 | 4.04 | 4.45 | 53.5 | 98.5 | 34.9 | - | - |  |
| asyncio-app | process | 4 | off | 13 | none | 5 | 154,582 | 1,548 | 0.8 | 2.73× ± 0.06 | 2.54 | 3.17 | 97.7 | 98.3 | 51.5 | - | - |  |
