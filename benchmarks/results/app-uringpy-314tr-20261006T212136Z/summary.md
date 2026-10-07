# Benchmark summary

- experiment: app   started (UTC): 2026-10-06T21:21:36+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 1345264894)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_OFF

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy-app | thread | 1 | off | 13 | none | 0 | 5 | 125,277 | 1,507 | 1.0 | 1.00× | 3.16 | 3.47 | 29.0 | 98.2 | 34.0 | 0.005 | 386.0 | 8.08 | - | - |  |
| uringpy-app | thread | 2 | off | 13 | none | 0 | 5 | 199,215 | 6,367 | 2.6 | 1.59× ± 0.05 | 1.97 | 2.31 | 57.8 | 98.2 | 49.4 | 0.011 | 176.7 | 10.07 | - | - |  |
| uringpy-app | thread | 4 | off | 13 | none | 0 | 5 | 290,538 | 2,278 | 0.6 | 2.32× ± 0.03 | 1.30 | 1.88 | 97.7 | 98.2 | 66.5 | 0.022 | 90.2 | 13.75 | - | - |  |
| uringpy-app | process | 1 | off | 13 | none | 0 | 5 | 125,775 | 1,787 | 1.1 | 1.00× | 3.16 | 3.40 | 29.0 | 98.0 | 33.0 | 0.005 | 383.2 | 8.02 | - | - |  |
| uringpy-app | process | 2 | off | 13 | none | 0 | 5 | 202,368 | 2,461 | 1.0 | 1.61× ± 0.03 | 1.92 | 2.36 | 58.0 | 98.3 | 49.8 | 0.011 | 185.2 | 9.92 | - | - |  |
| uringpy-app | process | 4 | off | 13 | none | 0 | 5 | 293,788 | 1,886 | 0.5 | 2.34× ± 0.04 | 1.33 | 1.78 | 97.7 | 98.2 | 67.1 | 0.022 | 90.7 | 13.62 | - | - |  |
| uringpy-app-batch | thread | 1 | off | 13 | none | 0 | 5 | 127,088 | 3,100 | 2.0 | 1.00× | 3.13 | 3.37 | 28.9 | 97.5 | 32.6 | 0.005 | 387.3 | 7.92 | - | - |  |
| uringpy-app-batch | thread | 2 | off | 13 | none | 0 | 5 | 204,134 | 7,855 | 3.1 | 1.61× ± 0.07 | 1.92 | 2.34 | 58.1 | 98.3 | 50.7 | 0.012 | 174.5 | 9.82 | - | - |  |
| uringpy-app-batch | thread | 4 | off | 13 | none | 0 | 5 | 290,904 | 6,795 | 1.9 | 2.29× ± 0.08 | 1.31 | 1.97 | 97.6 | 98.1 | 69.2 | 0.026 | 76.9 | 13.69 | - | - |  |
| uringpy-app-batch | process | 1 | off | 13 | none | 0 | 5 | 129,639 | 4,354 | 2.7 | 1.00× | 3.06 | 3.30 | 29.1 | 98.2 | 32.0 | 0.006 | 379.2 | 7.77 | - | - |  |
| uringpy-app-batch | process | 2 | off | 13 | none | 0 | 5 | 208,582 | 3,555 | 1.4 | 1.61× ± 0.06 | 1.82 | 2.31 | 58.3 | 98.0 | 49.7 | 0.012 | 173.4 | 9.65 | - | - |  |
| uringpy-app-batch | process | 4 | off | 13 | none | 0 | 5 | 296,360 | 1,576 | 0.4 | 2.29× ± 0.08 | 1.29 | 1.83 | 97.7 | 98.2 | 68.0 | 0.022 | 89.9 | 13.49 | - | - |  |
| asyncio-app | thread | 1 | off | 13 | none | 0 | 5 | 56,471 | 759 | 1.1 | 1.00× | 7.03 | 7.54 | 26.7 | 98.4 | 15.5 | - | - | - | - | - |  |
| asyncio-app | thread | 2 | off | 13 | none | 0 | 5 | 96,767 | 606 | 0.5 | 1.71× ± 0.03 | 4.11 | 4.59 | 53.4 | 98.2 | 28.5 | - | - | - | - | - |  |
| asyncio-app | thread | 4 | off | 13 | none | 0 | 5 | 151,070 | 2,267 | 1.2 | 2.68× ± 0.05 | 2.60 | 3.24 | 98.2 | 98.5 | 43.0 | - | - | - | - | - |  |
| asyncio-app | process | 1 | off | 13 | none | 0 | 5 | 56,884 | 550 | 0.8 | 1.00× | 7.00 | 7.34 | 26.7 | 98.0 | 15.6 | - | - | - | - | - |  |
| asyncio-app | process | 2 | off | 13 | none | 0 | 5 | 98,836 | 2,879 | 2.3 | 1.74× ± 0.05 | 4.09 | 4.59 | 53.4 | 98.3 | 30.0 | - | - | - | - | - |  |
| asyncio-app | process | 4 | off | 13 | none | 0 | 5 | 155,165 | 2,157 | 1.1 | 2.73× ± 0.05 | 2.53 | 3.15 | 97.9 | 98.3 | 46.1 | - | - | - | - | - |  |
| asyncio-proto-app | thread | 1 | off | 13 | none | 0 | 5 | 78,600 | 1,021 | 1.0 | 1.00× | 4.99 | 9.96 | 27.5 | 97.9 | 21.7 | - | - | - | - | - |  |
| asyncio-proto-app | thread | 2 | off | 13 | none | 0 | 5 | 129,230 | 381 | 0.2 | 1.64× ± 0.02 | 3.00 | 6.14 | 54.7 | 98.0 | 38.8 | - | - | - | - | - |  |
| asyncio-proto-app | thread | 4 | off | 13 | none | 0 | 5 | 198,329 | 1,152 | 0.5 | 2.52× ± 0.04 | 1.92 | 4.21 | 98.0 | 98.4 | 55.9 | - | - | - | - | - |  |
| asyncio-proto-app | process | 1 | off | 13 | none | 0 | 5 | 79,423 | 1,728 | 1.8 | 1.00× | 4.93 | 9.85 | 27.5 | 97.9 | 22.9 | - | - | - | - | - |  |
| asyncio-proto-app | process | 2 | off | 13 | none | 0 | 5 | 134,196 | 1,783 | 1.1 | 1.69× ± 0.04 | 2.87 | 5.85 | 55.4 | 98.4 | 40.2 | - | - | - | - | - |  |
| asyncio-proto-app | process | 4 | off | 13 | none | 0 | 5 | 204,524 | 3,220 | 1.3 | 2.58× ± 0.07 | 1.83 | 3.95 | 97.6 | 98.3 | 58.9 | - | - | - | - | - |  |
