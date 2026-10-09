# Benchmark summary

- experiment: app   started (UTC): 2026-10-07T13:51:43+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 894237396)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_OFF

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | conns | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | GIL rel. or acq./req | vol. ctx sw./req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy-app | thread | 1 | off | 13 | none | 0 | 400 | 5 | 122,737 | 2,065 | 1.4 | 1.00× | 3.23 | 3.51 | 28.9 | 97.7 | 34.5 | 0.006 | 378.9 | 8.18 | - | - | 1.000 | 0.000 |  |
| uringpy-app | thread | 2 | off | 13 | none | 0 | 400 | 5 | 200,918 | 4,641 | 1.9 | 1.64× ± 0.05 | 1.95 | 2.31 | 58.0 | 98.4 | 51.6 | 0.011 | 182.5 | 10.02 | - | - | 1.000 | 0.000 |  |
| uringpy-app | thread | 4 | off | 13 | none | 0 | 400 | 5 | 290,285 | 1,050 | 0.3 | 2.37× ± 0.04 | 1.32 | 1.86 | 98.0 | 98.4 | 67.6 | 0.022 | 91.8 | 13.80 | - | - | 1.000 | 0.001 |  |
| uringpy-app | process | 1 | off | 13 | none | 0 | 400 | 5 | 121,700 | 3,819 | 2.5 | 1.00× | 3.26 | 3.52 | 28.8 | 98.1 | 34.2 | 0.005 | 385.8 | 8.24 | - | - | 1.000 | 0.000 |  |
| uringpy-app | process | 2 | off | 13 | none | 0 | 400 | 5 | 200,319 | 5,603 | 2.3 | 1.65× ± 0.07 | 1.95 | 2.32 | 57.9 | 97.9 | 50.8 | 0.011 | 184.2 | 10.03 | - | - | 1.000 | 0.000 |  |
| uringpy-app | process | 4 | off | 13 | none | 0 | 400 | 5 | 289,577 | 4,692 | 1.3 | 2.38× ± 0.08 | 1.31 | 2.00 | 97.5 | 97.9 | 71.8 | 0.026 | 78.7 | 13.72 | - | - | 1.000 | 0.002 |  |
| uringpy-app-batch | thread | 1 | off | 13 | none | 0 | 400 | 5 | 126,934 | 2,572 | 1.6 | 1.00× | 3.12 | 3.39 | 29.0 | 97.9 | 33.9 | 0.006 | 371.7 | 7.94 | - | - | 0.005 | 0.000 |  |
| uringpy-app-batch | thread | 2 | off | 13 | none | 0 | 400 | 5 | 202,579 | 2,659 | 1.1 | 1.60× ± 0.04 | 1.94 | 2.30 | 57.8 | 98.4 | 51.1 | 0.011 | 181.1 | 9.89 | - | - | 0.011 | 0.000 |  |
| uringpy-app-batch | thread | 4 | off | 13 | none | 0 | 400 | 5 | 291,394 | 4,779 | 1.3 | 2.30× ± 0.06 | 1.30 | 1.91 | 97.9 | 98.4 | 71.5 | 0.024 | 82.4 | 13.73 | - | - | 0.023 | 0.001 |  |
| uringpy-app-batch | process | 1 | off | 13 | none | 0 | 400 | 5 | 125,746 | 2,749 | 1.8 | 1.00× | 3.15 | 3.48 | 28.8 | 98.0 | 35.6 | 0.006 | 378.2 | 7.96 | - | - | 0.005 | 0.000 |  |
| uringpy-app-batch | process | 2 | off | 13 | none | 0 | 400 | 5 | 204,984 | 6,805 | 2.7 | 1.63× ± 0.06 | 1.91 | 2.30 | 58.3 | 98.2 | 52.1 | 0.011 | 177.2 | 9.79 | - | - | 0.011 | 0.000 |  |
| uringpy-app-batch | process | 4 | off | 13 | none | 0 | 400 | 5 | 294,235 | 1,825 | 0.5 | 2.34× ± 0.05 | 1.29 | 1.84 | 97.7 | 98.2 | 70.5 | 0.023 | 89.1 | 13.57 | - | - | 0.022 | 0.001 |  |
| c-epoll-app | thread | 1 | off | 13 | none | 0 | 400 | 5 | 102,113 | 2,027 | 1.6 | 1.00× | 3.82 | 7.64 | 28.4 | 98.3 | 34.5 | 2.004 | - | 9.81 | - | - | 1.000 | 0.000 |  |
| c-epoll-app | thread | 2 | off | 13 | none | 0 | 400 | 5 | 164,219 | 3,192 | 1.6 | 1.61× ± 0.04 | 2.33 | 4.79 | 56.4 | 98.1 | 50.5 | 2.008 | - | 12.18 | - | - | 1.000 | 0.001 |  |
| c-epoll-app | thread | 4 | off | 13 | none | 0 | 400 | 5 | 248,082 | 1,149 | 0.4 | 2.43× ± 0.05 | 1.48 | 3.28 | 98.1 | 98.4 | 69.5 | 2.013 | - | 16.07 | - | - | 1.000 | 0.001 |  |
| c-epoll-app | process | 1 | off | 13 | none | 0 | 400 | 5 | 102,778 | 2,312 | 1.8 | 1.00× | 3.80 | 7.59 | 28.5 | 97.9 | 30.7 | 2.004 | - | 9.73 | - | - | 1.000 | 0.000 |  |
| c-epoll-app | process | 2 | off | 13 | none | 0 | 400 | 5 | 167,254 | 3,768 | 1.8 | 1.63× ± 0.05 | 2.28 | 4.93 | 56.6 | 98.1 | 52.6 | 2.008 | - | 11.94 | - | - | 1.000 | 0.001 |  |
| c-epoll-app | process | 4 | off | 13 | none | 0 | 400 | 5 | 253,635 | 786 | 0.2 | 2.47× ± 0.06 | 1.47 | 3.31 | 97.9 | 98.4 | 70.8 | 2.014 | - | 15.72 | - | - | 1.000 | 0.001 |  |
| c-epoll-app-batch | thread | 1 | off | 13 | none | 0 | 400 | 5 | 114,275 | 2,256 | 1.6 | 1.00× | 3.40 | 6.80 | 28.9 | 98.2 | 33.1 | 2.004 | - | 8.76 | - | - | 0.003 | 0.000 |  |
| c-epoll-app-batch | thread | 2 | off | 13 | none | 0 | 400 | 5 | 187,871 | 2,201 | 0.9 | 1.64× ± 0.04 | 2.00 | 4.23 | 57.5 | 98.1 | 52.5 | 2.007 | - | 10.64 | - | - | 0.007 | 0.001 |  |
| c-epoll-app-batch | thread | 4 | off | 13 | none | 0 | 400 | 5 | 275,866 | 624 | 0.2 | 2.41× ± 0.05 | 1.29 | 2.82 | 97.9 | 98.3 | 70.4 | 2.015 | - | 14.45 | - | - | 0.015 | 0.001 |  |
| c-epoll-app-batch | process | 1 | off | 13 | none | 0 | 400 | 5 | 114,607 | 2,299 | 1.6 | 1.00× | 3.38 | 6.77 | 28.8 | 98.0 | 33.8 | 2.004 | - | 8.72 | - | - | 0.003 | 0.000 |  |
| c-epoll-app-batch | process | 2 | off | 13 | none | 0 | 400 | 5 | 188,937 | 1,545 | 0.7 | 1.65× ± 0.04 | 1.99 | 4.15 | 57.5 | 98.3 | 52.6 | 2.007 | - | 10.58 | - | - | 0.006 | 0.000 |  |
| c-epoll-app-batch | process | 4 | off | 13 | none | 0 | 400 | 5 | 279,133 | 623 | 0.2 | 2.44× ± 0.05 | 1.26 | 2.89 | 97.7 | 98.3 | 71.1 | 2.015 | - | 14.28 | - | - | 0.014 | 0.001 |  |
| asyncio-app | thread | 1 | off | 13 | none | 0 | 400 | 5 | 56,847 | 1,073 | 1.5 | 1.00× | 6.99 | 7.52 | 26.8 | 98.1 | 18.3 | - | - | - | - | - | - | - |  |
| asyncio-app | thread | 2 | off | 13 | none | 0 | 400 | 5 | 95,472 | 2,008 | 1.7 | 1.68× ± 0.05 | 4.12 | 4.73 | 53.3 | 98.2 | 32.5 | - | - | - | - | - | - | - |  |
| asyncio-app | thread | 4 | off | 13 | none | 0 | 400 | 5 | 150,635 | 966 | 0.5 | 2.65× ± 0.05 | 2.65 | 3.05 | 97.9 | 98.3 | 48.7 | - | - | - | - | - | - | - |  |
| asyncio-app | process | 1 | off | 13 | none | 0 | 400 | 5 | 57,400 | 964 | 1.4 | 1.00× | 6.94 | 7.37 | 26.8 | 98.3 | 18.5 | - | - | - | - | - | - | - |  |
| asyncio-app | process | 2 | off | 13 | none | 0 | 400 | 5 | 98,832 | 1,218 | 1.0 | 1.72× ± 0.04 | 4.03 | 4.44 | 53.5 | 98.4 | 34.3 | - | - | - | - | - | - | - |  |
| asyncio-app | process | 4 | off | 13 | none | 0 | 400 | 5 | 156,056 | 994 | 0.5 | 2.72× ± 0.05 | 2.55 | 2.97 | 97.6 | 98.4 | 50.7 | - | - | - | - | - | - | - |  |
| asyncio-proto-app | thread | 1 | off | 13 | none | 0 | 400 | 5 | 78,483 | 1,075 | 1.1 | 1.00× | 4.99 | 9.95 | 27.6 | 98.2 | 24.6 | - | - | - | - | - | - | - |  |
| asyncio-proto-app | thread | 2 | off | 13 | none | 0 | 400 | 5 | 128,235 | 2,146 | 1.3 | 1.63× ± 0.04 | 3.03 | 6.23 | 54.9 | 98.3 | 41.2 | - | - | - | - | - | - | - |  |
| asyncio-proto-app | thread | 4 | off | 13 | none | 0 | 400 | 5 | 197,285 | 1,411 | 0.6 | 2.51× ± 0.04 | 1.91 | 4.15 | 98.2 | 98.5 | 60.8 | - | - | - | - | - | - | - |  |
| asyncio-proto-app | process | 1 | off | 13 | none | 0 | 400 | 5 | 78,499 | 1,757 | 1.8 | 1.00× | 4.99 | 9.95 | 27.6 | 98.2 | 24.2 | - | - | - | - | - | - | - |  |
| asyncio-proto-app | process | 2 | off | 13 | none | 0 | 400 | 5 | 133,988 | 3,036 | 1.8 | 1.71× ± 0.05 | 2.94 | 6.08 | 55.2 | 98.2 | 42.2 | - | - | - | - | - | - | - |  |
| asyncio-proto-app | process | 4 | off | 13 | none | 0 | 400 | 5 | 203,169 | 1,715 | 0.7 | 2.59× ± 0.06 | 1.88 | 4.05 | 98.0 | 98.5 | 62.2 | - | - | - | - | - | - | - |  |
