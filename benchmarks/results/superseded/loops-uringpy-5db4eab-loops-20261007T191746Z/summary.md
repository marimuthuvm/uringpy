# Benchmark summary

- experiment: loops   started (UTC): 2026-10-07T19:17:46+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 1679897733)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | conns | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | GIL rel. or acq./req | vol. ctx sw./req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| asyncio | thread | 1 | on | 13 | none | 0 | 400 | 5 | 66,617 | 850 | 1.0 | 1.00× | 5.98 | 6.36 | 27.1 | 97.7 | 18.5 | - | - | - | - | - | - | - |  |
| asyncio | thread | 2 | on | 13 | none | 0 | 400 | 5 | 46,953 | 349 | 0.6 | 0.70× ± 0.01 | 8.48 | 10.15 | 38.8 | 60.2 | 16.4 | - | - | - | - | - | - | - |  |
| asyncio | thread | 4 | on | 13 | none | 0 | 400 | 5 | 33,937 | 302 | 0.7 | 0.51× ± 0.01 | 11.70 | 15.63 | 44.2 | 44.9 | 13.4 | - | - | - | - | - | - | - |  |
| asyncio | process | 1 | on | 13 | none | 0 | 400 | 5 | 67,726 | 1,364 | 1.6 | 1.00× | 5.88 | 6.27 | 27.1 | 97.9 | 19.0 | - | - | - | - | - | - | - |  |
| asyncio | process | 2 | on | 13 | none | 0 | 400 | 5 | 114,902 | 957 | 0.7 | 1.70× ± 0.04 | 3.46 | 3.84 | 54.0 | 97.8 | 33.0 | - | - | - | - | - | - | - |  |
| asyncio | process | 4 | on | 13 | none | 0 | 400 | 5 | 178,263 | 715 | 0.3 | 2.63× ± 0.05 | 2.17 | 2.69 | 98.0 | 98.4 | 50.9 | - | - | - | - | - | - | - |  |
| uvloop | thread | 1 | on | 13 | none | 0 | 400 | 5 | 71,135 | 1,229 | 1.4 | 1.00× | 5.51 | 114.23 | 27.3 | 97.6 | 20.7 | - | - | - | - | - | - | - |  |
| uvloop | thread | 2 | on | 13 | none | 0 | 400 | 5 | 67,600 | 899 | 1.1 | 0.95× ± 0.02 | 5.66 | 12.74 | 32.4 | 42.2 | 21.2 | - | - | - | - | - | - | - |  |
| uvloop | thread | 4 | on | 13 | none | 0 | 400 | 5 | 43,318 | 515 | 1.0 | 0.61× ± 0.01 | 8.49 | 19.46 | 42.5 | 43.5 | 14.5 | - | - | - | - | - | - | - |  |
| uvloop | process | 1 | on | 13 | none | 0 | 400 | 5 | 71,837 | 1,499 | 1.7 | 1.00× | 5.45 | 103.87 | 27.4 | 97.7 | 21.1 | - | - | - | - | - | - | - |  |
| uvloop | process | 2 | on | 13 | none | 0 | 400 | 5 | 123,994 | 2,379 | 1.5 | 1.73× ± 0.05 | 3.12 | 6.56 | 54.9 | 98.3 | 36.9 | - | - | - | - | - | - | - |  |
| uvloop | process | 4 | on | 13 | none | 0 | 400 | 5 | 193,510 | 2,102 | 0.9 | 2.69× ± 0.06 | 1.95 | 4.25 | 97.6 | 98.2 | 55.8 | - | - | - | - | - | - | - |  |
| uringcore | thread | 1 | - | 13 | none | 0 | 400 | 0 | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | 5 failed run(s); no successful run: unable to connect to 10.142.0.2:8080 Connection refused |
| uringcore | thread | 2 | - | 13 | none | 0 | 400 | 0 | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | 5 failed run(s); no successful run: unable to connect to 10.142.0.2:8080 Connection refused |
| uringcore | thread | 4 | - | 13 | none | 0 | 400 | 0 | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | 5 failed run(s); no successful run: unable to connect to 10.142.0.2:8080 Connection refused |
| uringcore | process | 1 | - | 13 | none | 0 | 400 | 0 | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | 5 failed run(s); no successful run: unable to connect to 10.142.0.2:8080 Connection refused |
| uringcore | process | 2 | - | 13 | none | 0 | 400 | 0 | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | 5 failed run(s); no successful run: unable to connect to 10.142.0.2:8080 Connection refused |
| uringcore | process | 4 | - | 13 | none | 0 | 400 | 0 | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | 5 failed run(s); no successful run: unable to connect to 10.142.0.2:8080 Connection refused |
