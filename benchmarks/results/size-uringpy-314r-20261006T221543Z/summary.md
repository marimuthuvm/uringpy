# Benchmark summary

- experiment: size   started (UTC): 2026-10-06T22:15:43+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 2101139516)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy | process | 4 | on | 64 | none | 0 | 5 | 327,875 | 901 | 0.2 | - | 1.17 | 1.65 | 97.6 | 98.2 | 75.6 | 0.023 | 85.7 | 12.19 | - | - |  |
| uringpy | process | 4 | on | 1024 | none | 0 | 5 | 320,988 | 1,641 | 0.4 | - | 1.19 | 1.76 | 98.0 | 98.3 | 75.4 | 0.024 | 84.8 | 12.42 | - | - |  |
| uringpy | process | 4 | on | 16384 | none | 0 | 5 | 119,330 | 474 | 0.3 | - | 3.17 | 7.89 | 83.0 | 85.4 | 60.4 | 0.638 | 3.1 | 22.21 | - | - |  |
| uringpy | process | 4 | on | 65536 | none | 0 | 5 | 30,022 | 121 | 0.3 | - | 12.93 | 68.39 | 36.2 | 37.6 | 33.2 | 0.737 | 2.7 | 31.09 | - | - |  |
| uringpy | process | 4 | on | 262144 | none | 0 | 5 | 7,489 | 44 | 0.5 | - | 50.03 | 333.83 | 32.2 | 34.1 | 31.6 | 1.229 | 1.6 | 85.10 | - | - |  |
| uringpy | process | 4 | on | 1048576 | none | 0 | 5 | 1,870 | 1 | 0.0 | - | 205.15 | 430.08 | 40.3 | 42.9 | 44.5 | 2.443 | 1.2 | 359.73 | - | - |  |
| asyncio-proto | process | 4 | on | 64 | none | 0 | 5 | 234,852 | 1,565 | 0.5 | - | 1.58 | 3.41 | 98.0 | 98.4 | 64.4 | - | - | - | - | - |  |
| asyncio-proto | process | 4 | on | 1024 | none | 0 | 5 | 230,688 | 1,469 | 0.5 | - | 1.59 | 3.54 | 97.8 | 98.3 | 65.0 | - | - | - | - | - |  |
| asyncio-proto | process | 4 | on | 16384 | none | 0 | 5 | 118,930 | 661 | 0.4 | - | 3.18 | 8.74 | 91.3 | 94.3 | 57.7 | - | - | - | - | - |  |
| asyncio-proto | process | 4 | on | 65536 | none | 0 | 5 | 30,045 | 114 | 0.3 | - | 13.16 | 32.97 | 38.6 | 40.5 | 36.5 | - | - | - | - | - |  |
| asyncio-proto | process | 4 | on | 262144 | none | 0 | 5 | 7,502 | 5 | 0.1 | - | 48.49 | 332.07 | 33.4 | 35.9 | 32.3 | - | - | - | - | - |  |
| asyncio-proto | process | 4 | on | 1048576 | none | 0 | 5 | 1,867 | 9 | 0.4 | - | 204.57 | 435.74 | 44.1 | 46.0 | 41.2 | - | - | - | - | - |  |
