# Benchmark summary

- experiment: scaling   started (UTC): 2026-10-07T12:16:46+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 1737078742)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_OFF

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | conns | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | GIL rel. or acq./req | vol. ctx sw./req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy | thread | 1 | off | 13 | none | 0 | 400 | 5 | 143,356 | 3,347 | 1.9 | 1.00× | 2.77 | 2.97 | 29.8 | 97.7 | 36.3 | 0.006 | 340.3 | 7.01 | - | - | - | 0.000 |  |
| uringpy | thread | 2 | off | 13 | none | 0 | 400 | 5 | 230,531 | 4,392 | 1.5 | 1.61× ± 0.05 | 1.68 | 2.14 | 59.7 | 98.3 | 55.7 | 0.011 | 182.1 | 8.72 | - | - | - | 0.000 |  |
| uringpy | thread | 3 | off | 13 | none | 0 | 400 | 5 | 284,851 | 3,865 | 1.1 | 1.99× ± 0.05 | 1.35 | 1.80 | 82.1 | 98.1 | 66.4 | 0.017 | 117.7 | 10.55 | - | - | - | 0.001 |  |
| uringpy | thread | 4 | off | 13 | none | 0 | 400 | 5 | 326,569 | 1,477 | 0.4 | 2.28× ± 0.05 | 1.16 | 1.72 | 97.8 | 98.2 | 74.7 | 0.023 | 87.5 | 12.24 | - | - | - | 0.001 |  |
| uringpy | process | 1 | off | 13 | none | 0 | 400 | 5 | 143,943 | 6,139 | 3.4 | 1.00× | 2.76 | 2.95 | 29.9 | 97.9 | 36.0 | 0.006 | 344.3 | 6.99 | - | - | - | 0.000 |  |
| uringpy | process | 2 | off | 13 | none | 0 | 400 | 5 | 227,119 | 10,732 | 3.8 | 1.58× ± 0.10 | 1.73 | 2.07 | 59.3 | 98.3 | 53.7 | 0.012 | 170.5 | 8.82 | - | - | - | 0.000 |  |
| uringpy | process | 3 | off | 13 | none | 0 | 400 | 5 | 285,507 | 4,267 | 1.2 | 1.98× ± 0.09 | 1.34 | 1.90 | 82.4 | 98.0 | 69.0 | 0.018 | 112.6 | 10.53 | - | - | - | 0.001 |  |
| uringpy | process | 4 | off | 13 | none | 0 | 400 | 5 | 325,618 | 2,224 | 0.6 | 2.26× ± 0.10 | 1.14 | 1.83 | 97.9 | 98.2 | 75.7 | 0.024 | 82.0 | 12.24 | - | - | - | 0.001 |  |
| asyncio | thread | 1 | off | 13 | none | 0 | 400 | 5 | 63,645 | 1,868 | 2.4 | 1.00× | 6.26 | 6.64 | 26.9 | 98.1 | 18.2 | - | - | - | - | - | - | - |  |
| asyncio | thread | 2 | off | 13 | none | 0 | 400 | 5 | 107,299 | 1,092 | 0.8 | 1.69× ± 0.05 | 3.68 | 4.12 | 53.5 | 97.9 | 29.6 | - | - | - | - | - | - | - |  |
| asyncio | thread | 3 | off | 13 | none | 0 | 400 | 5 | 140,895 | 1,236 | 0.7 | 2.21× ± 0.07 | 2.81 | 3.20 | 78.0 | 98.4 | 40.0 | - | - | - | - | - | - | - |  |
| asyncio | thread | 4 | off | 13 | none | 0 | 400 | 5 | 168,129 | 2,453 | 1.2 | 2.64× ± 0.09 | 2.32 | 2.91 | 98.2 | 98.5 | 49.5 | - | - | - | - | - | - | - |  |
| asyncio | process | 1 | off | 13 | none | 0 | 400 | 5 | 64,429 | 1,140 | 1.4 | 1.00× | 6.18 | 6.56 | 26.9 | 98.0 | 17.7 | - | - | - | - | - | - | - |  |
| asyncio | process | 2 | off | 13 | none | 0 | 400 | 5 | 110,007 | 2,184 | 1.6 | 1.71× ± 0.05 | 3.60 | 3.98 | 53.8 | 98.1 | 31.8 | - | - | - | - | - | - | - |  |
| asyncio | process | 3 | off | 13 | none | 0 | 400 | 5 | 145,345 | 2,002 | 1.1 | 2.26× ± 0.05 | 2.71 | 3.14 | 78.2 | 98.5 | 40.3 | - | - | - | - | - | - | - |  |
| asyncio | process | 4 | off | 13 | none | 0 | 400 | 5 | 173,155 | 1,410 | 0.7 | 2.69× ± 0.05 | 2.26 | 2.81 | 97.7 | 98.3 | 50.3 | - | - | - | - | - | - | - |  |
| asyncio-proto | thread | 1 | off | 13 | none | 0 | 400 | 5 | 90,249 | 1,828 | 1.6 | 1.00× | 4.34 | 8.65 | 28.0 | 98.0 | 24.8 | - | - | - | - | - | - | - |  |
| asyncio-proto | thread | 2 | off | 13 | none | 0 | 400 | 5 | 149,890 | 3,666 | 2.0 | 1.66× ± 0.05 | 2.58 | 5.36 | 56.2 | 98.1 | 46.6 | - | - | - | - | - | - | - |  |
| asyncio-proto | thread | 3 | off | 13 | none | 0 | 400 | 5 | 191,913 | 1,785 | 0.7 | 2.13× ± 0.05 | 1.95 | 4.23 | 79.8 | 98.3 | 56.8 | - | - | - | - | - | - | - |  |
| asyncio-proto | thread | 4 | off | 13 | none | 0 | 400 | 5 | 223,484 | 831 | 0.3 | 2.48× ± 0.05 | 1.65 | 3.78 | 98.0 | 98.4 | 63.6 | - | - | - | - | - | - | - |  |
| asyncio-proto | process | 1 | off | 13 | none | 0 | 400 | 5 | 90,851 | 1,038 | 0.9 | 1.00× | 4.31 | 8.59 | 28.0 | 97.8 | 25.4 | - | - | - | - | - | - | - |  |
| asyncio-proto | process | 2 | off | 13 | none | 0 | 400 | 5 | 150,507 | 2,556 | 1.4 | 1.66× ± 0.03 | 2.56 | 5.37 | 55.7 | 98.2 | 45.0 | - | - | - | - | - | - | - |  |
| asyncio-proto | process | 3 | off | 13 | none | 0 | 400 | 5 | 196,161 | 3,679 | 1.5 | 2.16× ± 0.05 | 1.94 | 4.16 | 79.8 | 97.9 | 58.3 | - | - | - | - | - | - | - |  |
| asyncio-proto | process | 4 | off | 13 | none | 0 | 400 | 5 | 229,197 | 1,025 | 0.4 | 2.52× ± 0.03 | 1.64 | 3.56 | 98.2 | 98.5 | 63.5 | - | - | - | - | - | - | - |  |
