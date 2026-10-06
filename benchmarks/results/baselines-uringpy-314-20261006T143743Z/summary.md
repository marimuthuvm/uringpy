# Benchmark summary

- experiment: baselines   started (UTC): 2026-10-06T14:37:43+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 539189205)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up.

| engine | mode | workers | GIL | body B | batch cap | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uvloop | thread | 1 | on | 13 | none | 5 | 72,484 | 1,035 | 1.1 | 1.00× | 5.38 | 10.87 | 27.3 | 97.9 | 23.4 | - | - |  |
| uvloop | thread | 4 | on | 13 | none | 5 | 43,033 | 526 | 1.0 | 0.59× ± 0.01 | 8.42 | 19.88 | 42.2 | 43.0 | 15.9 | - | - |  |
| uvloop | process | 1 | on | 13 | none | 5 | 72,415 | 1,861 | 2.1 | 1.00× | 5.39 | 10.89 | 27.3 | 98.0 | 23.3 | - | - |  |
| uvloop | process | 4 | on | 13 | none | 5 | 193,582 | 1,865 | 0.8 | 2.67× ± 0.07 | 1.94 | 4.25 | 98.0 | 98.4 | 59.3 | - | - |  |
| uvloop-proto | thread | 1 | on | 13 | none | 5 | 97,954 | 2,300 | 1.9 | 1.00× | 3.98 | 8.01 | 28.3 | 97.9 | 32.6 | - | - |  |
| uvloop-proto | thread | 4 | on | 13 | none | 5 | 35,050 | 235 | 0.5 | 0.36× ± 0.01 | 10.93 | 26.61 | 39.7 | 40.6 | 16.0 | - | - |  |
| uvloop-proto | process | 1 | on | 13 | none | 5 | 96,495 | 1,775 | 1.5 | 1.00× | 4.05 | 8.15 | 28.1 | 97.8 | 32.8 | - | - |  |
| uvloop-proto | process | 4 | on | 13 | none | 5 | 247,042 | 598 | 0.2 | 2.56× ± 0.05 | 1.48 | 3.39 | 97.5 | 98.3 | 69.9 | - | - |  |
