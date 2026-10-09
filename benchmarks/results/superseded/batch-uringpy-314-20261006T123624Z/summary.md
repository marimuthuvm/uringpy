# Benchmark summary

- experiment: batch   started (UTC): 2026-10-06T12:36:24+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 1111285435)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up.

| engine | mode | workers | GIL | body B | batch cap | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy | thread | 1 | on | 13 | 1 | 5 | 115,289 | 3,385 | 2.4 | 1.00× | 3.46 | 3.65 | 28.7 | 97.9 | 33.4 | 2.001 | 1.0 |  |
| uringpy | thread | 1 | on | 13 | 4 | 5 | 134,161 | 4,368 | 2.6 | 1.00× | 2.96 | 3.21 | 29.6 | 98.2 | 42.2 | 0.501 | 4.0 |  |
| uringpy | thread | 1 | on | 13 | 16 | 5 | 143,350 | 2,452 | 1.4 | 1.00× | 2.77 | 2.99 | 30.0 | 97.9 | 41.6 | 0.126 | 15.9 |  |
| uringpy | thread | 1 | on | 13 | 64 | 5 | 141,411 | 4,489 | 2.6 | 1.00× | 2.81 | 3.02 | 29.7 | 98.0 | 38.3 | 0.032 | 63.0 |  |
| uringpy | thread | 1 | on | 13 | 256 | 5 | 142,717 | 2,268 | 1.3 | 1.00× | 2.78 | 3.00 | 29.7 | 98.1 | 39.7 | 0.008 | 241.9 |  |
| uringpy | thread | 1 | on | 13 | none | 5 | 144,039 | 4,509 | 2.5 | 1.00× | 2.76 | 2.96 | 29.9 | 98.3 | 38.9 | 0.006 | 356.1 |  |
