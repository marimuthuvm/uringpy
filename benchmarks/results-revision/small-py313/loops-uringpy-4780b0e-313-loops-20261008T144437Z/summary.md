# Benchmark summary

- experiment: loops   started (UTC): 2026-10-08T14:44:37+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 1307436009)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1013-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1013-gcp, interpreter 3.13.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | conns | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | GIL rel. or acq./req | GIL switches/req | vol. ctx sw./req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| asyncio | thread | 1 | on | 13 | none | 0 | 400 | 5 | 61,327 | 833 | 1.1 | 1.00× | 6.50 | 6.84 | 27.1 | 98.3 | 17.7 | - | - | - | - | - | - | - | - |  |
| asyncio | thread | 2 | on | 13 | none | 0 | 400 | 5 | 43,592 | 1,327 | 2.5 | 0.71× ± 0.02 | 9.04 | 12.62 | 38.9 | 59.1 | 16.2 | - | - | - | - | - | - | - | - |  |
| asyncio | thread | 4 | on | 13 | none | 0 | 400 | 5 | 31,878 | 1,298 | 3.3 | 0.52× ± 0.02 | 12.35 | 17.24 | 44.5 | 45.4 | 12.9 | - | - | - | - | - | - | - | - |  |
| asyncio | process | 1 | on | 13 | none | 0 | 400 | 5 | 62,009 | 1,509 | 2.0 | 1.00× | 6.42 | 6.73 | 27.2 | 98.1 | 18.1 | - | - | - | - | - | - | - | - |  |
| asyncio | process | 2 | on | 13 | none | 0 | 400 | 5 | 107,316 | 1,934 | 1.5 | 1.73× ± 0.05 | 3.62 | 4.27 | 54.2 | 98.0 | 33.3 | - | - | - | - | - | - | - | - |  |
| asyncio | process | 4 | on | 13 | none | 0 | 400 | 5 | 169,335 | 862 | 0.4 | 2.73× ± 0.07 | 2.35 | 2.86 | 97.9 | 98.4 | 51.0 | - | - | - | - | - | - | - | - |  |
| asyncio-proto | thread | 1 | on | 13 | none | 0 | 400 | 5 | 85,260 | 1,287 | 1.2 | 1.00× | 4.59 | 9.13 | 28.2 | 98.0 | 24.8 | - | - | - | - | - | - | - | - |  |
| asyncio-proto | thread | 2 | on | 13 | none | 0 | 400 | 5 | 86,783 | 1,254 | 1.2 | 1.02× ± 0.02 | 4.46 | 9.03 | 46.3 | 64.7 | 27.1 | - | - | - | - | - | - | - | - |  |
| asyncio-proto | thread | 4 | on | 13 | none | 0 | 400 | 5 | 44,290 | 1,601 | 2.9 | 0.52× ± 0.02 | 8.87 | 16.75 | 56.3 | 57.0 | 16.7 | - | - | - | - | - | - | - | - |  |
| asyncio-proto | process | 1 | on | 13 | none | 0 | 400 | 5 | 86,135 | 1,842 | 1.7 | 1.00× | 4.55 | 9.05 | 28.3 | 98.0 | 24.5 | - | - | - | - | - | - | - | - |  |
| asyncio-proto | process | 2 | on | 13 | none | 0 | 400 | 5 | 144,266 | 2,911 | 1.6 | 1.67× ± 0.05 | 2.69 | 5.55 | 56.7 | 97.9 | 44.1 | - | - | - | - | - | - | - | - |  |
| asyncio-proto | process | 4 | on | 13 | none | 0 | 400 | 5 | 218,295 | 927 | 0.3 | 2.53× ± 0.06 | 1.73 | 3.70 | 98.0 | 98.4 | 63.7 | - | - | - | - | - | - | - | - |  |
| uvloop | thread | 1 | on | 13 | none | 0 | 400 | 5 | 69,837 | 878 | 1.0 | 1.00× | 5.59 | 132.00 | 27.6 | 98.3 | 21.2 | - | - | - | - | - | - | - | - |  |
| uvloop | thread | 2 | on | 13 | none | 0 | 400 | 5 | 63,723 | 1,326 | 1.7 | 0.91× ± 0.02 | 5.92 | 13.86 | 32.5 | 46.8 | 20.6 | - | - | - | - | - | - | - | - |  |
| uvloop | thread | 4 | on | 13 | none | 0 | 400 | 5 | 42,609 | 989 | 1.9 | 0.61× ± 0.02 | 8.56 | 20.92 | 43.1 | 43.7 | 15.2 | - | - | - | - | - | - | - | - |  |
| uvloop | process | 1 | on | 13 | none | 0 | 400 | 5 | 69,865 | 976 | 1.1 | 1.00× | 5.60 | 124.44 | 27.6 | 97.5 | 21.3 | - | - | - | - | - | - | - | - |  |
| uvloop | process | 2 | on | 13 | none | 0 | 400 | 5 | 119,444 | 1,480 | 1.0 | 1.71× ± 0.03 | 3.26 | 6.81 | 54.9 | 98.2 | 36.3 | - | - | - | - | - | - | - | - |  |
| uvloop | process | 4 | on | 13 | none | 0 | 400 | 5 | 188,542 | 4,207 | 1.8 | 2.70× ± 0.07 | 2.03 | 4.48 | 98.2 | 98.5 | 56.6 | - | - | - | - | - | - | - | - |  |
| uvloop-proto | thread | 1 | on | 13 | none | 0 | 400 | 5 | 90,465 | 1,667 | 1.5 | 1.00× | 4.33 | 26.00 | 28.4 | 98.3 | 26.9 | - | - | - | - | - | - | - | - |  |
| uvloop-proto | thread | 2 | on | 13 | none | 0 | 400 | 5 | 74,961 | 1,249 | 1.3 | 0.83× ± 0.02 | 5.12 | 11.80 | 40.3 | 59.7 | 24.2 | - | - | - | - | - | - | - | - |  |
| uvloop-proto | thread | 4 | on | 13 | none | 0 | 400 | 5 | 34,026 | 858 | 2.0 | 0.38× ± 0.01 | 11.12 | 32.96 | 40.9 | 41.9 | 13.6 | - | - | - | - | - | - | - | - |  |
| uvloop-proto | process | 1 | on | 13 | none | 0 | 400 | 5 | 91,206 | 1,507 | 1.3 | 1.00× | 4.28 | 17.59 | 28.4 | 98.1 | 27.4 | - | - | - | - | - | - | - | - |  |
| uvloop-proto | process | 2 | on | 13 | none | 0 | 400 | 5 | 154,233 | 2,930 | 1.5 | 1.69× ± 0.04 | 2.50 | 5.18 | 56.8 | 98.0 | 46.8 | - | - | - | - | - | - | - | - |  |
| uvloop-proto | process | 4 | on | 13 | none | 0 | 400 | 5 | 233,978 | 1,446 | 0.5 | 2.57× ± 0.05 | 1.57 | 3.66 | 98.1 | 98.4 | 67.0 | - | - | - | - | - | - | - | - |  |
| uringpy | thread | 1 | on | 13 | none | 0 | 400 | 5 | 133,392 | 2,892 | 1.7 | 1.00× | 2.96 | 3.32 | 30.1 | 97.9 | 37.1 | 0.006 | 329.8 | 7.59 | - | - | - | 0.000 | 0.000 |  |
| uringpy | thread | 2 | on | 13 | none | 0 | 400 | 5 | 206,668 | 5,174 | 2.0 | 1.55× ± 0.05 | 1.83 | 2.40 | 58.9 | 98.2 | 55.5 | 0.012 | 175.2 | 9.72 | - | - | - | 0.000 | 0.000 |  |
| uringpy | thread | 4 | on | 13 | none | 0 | 400 | 5 | 303,824 | 2,106 | 0.6 | 2.28× ± 0.05 | 1.25 | 1.80 | 97.9 | 98.4 | 75.1 | 0.021 | 93.9 | 12.85 | - | - | - | 0.000 | 0.001 |  |
| uringpy | process | 1 | on | 13 | none | 0 | 400 | 5 | 129,055 | 2,147 | 1.3 | 1.00× | 3.07 | 3.38 | 29.9 | 98.2 | 34.6 | 0.006 | 356.4 | 7.74 | - | - | - | 0.000 | 0.000 |  |
| uringpy | process | 2 | on | 13 | none | 0 | 400 | 5 | 211,929 | 5,349 | 2.0 | 1.64× ± 0.05 | 1.86 | 2.21 | 59.8 | 98.3 | 55.2 | 0.012 | 176.1 | 9.45 | - | - | - | 0.000 | 0.000 |  |
| uringpy | process | 4 | on | 13 | none | 0 | 400 | 5 | 301,848 | 1,971 | 0.5 | 2.34× ± 0.04 | 1.24 | 1.93 | 98.1 | 98.4 | 74.9 | 0.023 | 87.5 | 13.24 | - | - | - | 0.000 | 0.001 |  |
