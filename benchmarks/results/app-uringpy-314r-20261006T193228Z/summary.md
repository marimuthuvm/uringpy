# Benchmark summary

- experiment: app   started (UTC): 2026-10-06T19:32:28+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 1353357894)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy-app | thread | 1 | on | 13 | none | 0 | 5 | 126,309 | 1,672 | 1.1 | 1.00× | 3.13 | 3.42 | 29.0 | 97.9 | 36.4 | 0.005 | 385.3 | 7.97 | - | - |  |
| uringpy-app | thread | 2 | on | 13 | none | 0 | 5 | 192,669 | 1,591 | 0.7 | 1.53× ± 0.02 | 2.03 | 2.55 | 56.5 | 94.9 | 47.5 | 0.011 | 181.6 | 10.20 | - | - |  |
| uringpy-app | thread | 4 | on | 13 | none | 0 | 5 | 196,290 | 4,547 | 1.9 | 1.55× ± 0.04 | 1.96 | 3.48 | 81.0 | 82.2 | 47.6 | 0.022 | 93.0 | 15.48 | - | - |  |
| uringpy-app | process | 1 | on | 13 | none | 0 | 5 | 125,757 | 1,807 | 1.2 | 1.00× | 3.15 | 3.43 | 29.0 | 98.1 | 35.1 | 0.005 | 382.1 | 8.00 | - | - |  |
| uringpy-app | process | 2 | on | 13 | none | 0 | 5 | 202,450 | 3,514 | 1.4 | 1.61× ± 0.04 | 1.92 | 2.36 | 58.0 | 98.2 | 52.5 | 0.011 | 184.2 | 9.92 | - | - |  |
| uringpy-app | process | 4 | on | 13 | none | 0 | 5 | 292,742 | 5,780 | 1.6 | 2.33× ± 0.06 | 1.29 | 1.91 | 97.4 | 98.0 | 70.3 | 0.025 | 80.8 | 13.59 | - | - |  |
| uringpy-app-batch | thread | 1 | on | 13 | none | 0 | 5 | 130,126 | 3,473 | 2.2 | 1.00× | 3.04 | 3.34 | 29.1 | 97.4 | 36.3 | 0.005 | 381.1 | 7.75 | - | - |  |
| uringpy-app-batch | thread | 2 | on | 13 | none | 0 | 5 | 204,064 | 2,588 | 1.0 | 1.57× ± 0.05 | 1.93 | 2.26 | 57.1 | 97.3 | 50.0 | 0.011 | 185.0 | 9.67 | - | - |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 0 | 5 | 275,578 | 5,592 | 1.6 | 2.12× ± 0.07 | 1.38 | 2.10 | 92.6 | 94.5 | 68.0 | 0.023 | 86.8 | 13.19 | - | - |  |
| uringpy-app-batch | process | 1 | on | 13 | none | 0 | 5 | 128,923 | 2,735 | 1.7 | 1.00× | 3.07 | 3.35 | 29.1 | 98.0 | 33.6 | 0.006 | 374.1 | 7.81 | - | - |  |
| uringpy-app-batch | process | 2 | on | 13 | none | 0 | 5 | 206,386 | 1,704 | 0.7 | 1.60× ± 0.04 | 1.87 | 2.37 | 58.2 | 98.2 | 55.8 | 0.011 | 177.5 | 9.73 | - | - |  |
| uringpy-app-batch | process | 4 | on | 13 | none | 0 | 5 | 297,365 | 797 | 0.2 | 2.31× ± 0.05 | 1.29 | 1.77 | 97.9 | 98.3 | 70.5 | 0.022 | 89.9 | 13.45 | - | - |  |
| asyncio-app | thread | 1 | on | 13 | none | 0 | 5 | 59,851 | 1,210 | 1.6 | 1.00× | 6.66 | 6.98 | 26.8 | 98.0 | 16.9 | - | - | - | - | - |  |
| asyncio-app | thread | 2 | on | 13 | none | 0 | 5 | 40,217 | 442 | 0.9 | 0.67× ± 0.02 | 9.91 | 11.47 | 37.2 | 60.5 | 16.3 | - | - | - | - | - |  |
| asyncio-app | thread | 4 | on | 13 | none | 0 | 5 | 31,150 | 535 | 1.4 | 0.52× ± 0.01 | 12.70 | 17.05 | 42.2 | 43.0 | 13.2 | - | - | - | - | - |  |
| asyncio-app | process | 1 | on | 13 | none | 0 | 5 | 60,195 | 1,775 | 2.4 | 1.00× | 6.62 | 6.92 | 26.8 | 98.3 | 17.3 | - | - | - | - | - |  |
| asyncio-app | process | 2 | on | 13 | none | 0 | 5 | 104,741 | 1,270 | 1.0 | 1.74× ± 0.06 | 3.81 | 4.13 | 53.7 | 98.3 | 32.7 | - | - | - | - | - |  |
| asyncio-app | process | 4 | on | 13 | none | 0 | 5 | 158,748 | 9,545 | 4.8 | 2.64× ± 0.18 | 2.45 | 3.39 | 98.2 | 98.5 | 45.4 | - | - | - | - | - |  |
| asyncio-proto-app | thread | 1 | on | 13 | none | 0 | 5 | 80,720 | 771 | 0.8 | 1.00× | 4.85 | 9.69 | 27.6 | 98.3 | 24.8 | - | - | - | - | - |  |
| asyncio-proto-app | thread | 2 | on | 13 | none | 0 | 5 | 64,075 | 949 | 1.2 | 0.79× ± 0.01 | 6.12 | 12.16 | 42.5 | 73.1 | 21.6 | - | - | - | - | - |  |
| asyncio-proto-app | thread | 4 | on | 13 | none | 0 | 5 | 38,584 | 353 | 0.7 | 0.48× ± 0.01 | 10.25 | 18.82 | 47.8 | 48.9 | 15.5 | - | - | - | - | - |  |
| asyncio-proto-app | process | 1 | on | 13 | none | 0 | 5 | 80,963 | 1,651 | 1.6 | 1.00× | 4.83 | 9.65 | 27.6 | 97.8 | 26.6 | - | - | - | - | - |  |
| asyncio-proto-app | process | 2 | on | 13 | none | 0 | 5 | 137,461 | 1,909 | 1.1 | 1.70× ± 0.04 | 2.80 | 5.82 | 55.3 | 98.3 | 42.5 | - | - | - | - | - |  |
| asyncio-proto-app | process | 4 | on | 13 | none | 0 | 5 | 187,087 | 20,970 | 9.0 | 2.31× ± 0.26 | 1.70 | 5.85 | 98.1 | 98.4 | 54.5 | - | - | - | - | - | CV > 5% |
| uvloop-proto-app | thread | 1 | on | 13 | none | 0 | 5 | 84,616 | 2,090 | 2.0 | 1.00× | 4.63 | 9.32 | 27.7 | 97.9 | 28.0 | - | - | - | - | - |  |
| uvloop-proto-app | thread | 2 | on | 13 | none | 0 | 5 | 68,851 | 697 | 0.8 | 0.81× ± 0.02 | 5.54 | 12.73 | 38.4 | 46.2 | 23.9 | - | - | - | - | - |  |
| uvloop-proto-app | thread | 4 | on | 13 | none | 0 | 5 | 29,924 | 258 | 0.7 | 0.35× ± 0.01 | 12.72 | 33.29 | 36.5 | 37.4 | 13.2 | - | - | - | - | - |  |
| uvloop-proto-app | process | 1 | on | 13 | none | 0 | 5 | 85,211 | 1,508 | 1.4 | 1.00× | 4.58 | 9.24 | 27.7 | 98.1 | 28.0 | - | - | - | - | - |  |
| uvloop-proto-app | process | 2 | on | 13 | none | 0 | 5 | 143,179 | 2,435 | 1.4 | 1.68× ± 0.04 | 2.65 | 5.53 | 55.5 | 98.2 | 48.3 | - | - | - | - | - |  |
| uvloop-proto-app | process | 4 | on | 13 | none | 0 | 5 | 219,929 | 1,549 | 0.6 | 2.58× ± 0.05 | 1.70 | 3.72 | 98.1 | 98.5 | 62.4 | - | - | - | - | - |  |
