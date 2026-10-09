# Benchmark summary

- experiment: openloop   started (UTC): 2026-10-09T01:04:19+00:00
- repetitions per cell: 5   run length: 30 s   warm-up: 5 s   order: interleaved, shuffled (seed 1477241542)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1013-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1013-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | conns | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | GIL rel. or acq./req | GIL switches/req | vol. ctx sw./req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy-app | thread | 4 | on | 13 | none | 0 | 400 @10000/s | 5 | 9,942 | 25 | 0.2 | - | 0.94 | 2.02 | 7.9 | 8.2 | 5.4 | 1.143 | 1.8 | 26.62 | - | - | 1.000 | 0.552 | 0.861 |  |
| uringpy-app | thread | 4 | on | 13 | none | 0 | 400 @25000/s | 5 | 24,865 | 106 | 0.3 | - | 0.97 | 2.05 | 13.5 | 14.1 | 11.7 | 0.825 | 2.4 | 24.23 | - | - | 1.000 | 0.441 | 0.827 |  |
| uringpy-app | thread | 4 | on | 13 | none | 0 | 400 @50000/s | 5 | 49,652 | 191 | 0.3 | - | 1.20 | 2.66 | 29.5 | 30.1 | 16.6 | 0.292 | 6.9 | 22.16 | - | - | 1.000 | 0.255 | 0.792 |  |
| uringpy-app | thread | 4 | on | 13 | none | 0 | 400 @100000/s | 5 | 99,005 | 407 | 0.3 | - | 1.70 | 4.49 | 58.0 | 59.3 | 25.1 | 0.102 | 19.7 | 20.17 | - | - | 1.000 | 0.197 | 0.798 |  |
| uringpy-app | thread | 4 | on | 13 | none | 0 | 400 @150000/s | 5 | 148,942 | 306 | 0.2 | - | 2.19 | 5.51 | 75.4 | 76.8 | 38.4 | 0.044 | 45.4 | 18.16 | - | - | 1.000 | 0.146 | 0.602 |  |
| uringpy-app | thread | 4 | on | 13 | none | 0 | 400 @200000/s | 5 | 191,706 | 1,614 | 0.7 | - | 177.48 | 2,672.00 | 83.8 | 85.3 | 47.5 | 0.025 | 81.9 | 16.30 | - | - | 1.000 | 0.093 | 0.352 |  |
| uringpy-app | thread | 4 | on | 13 | none | 0 | 400 @250000/s | 5 | 202,488 | 2,163 | 0.9 | - | 3,478.00 | 7,520.00 | 85.7 | 86.6 | 49.8 | 0.021 | 94.2 | 15.96 | - | - | 1.000 | 0.083 | 0.304 | below the offered rate: saturated |
| uringpy-app | thread | 4 | on | 13 | none | 0 | 400 @300000/s | 5 | 202,513 | 4,689 | 1.9 | - | 5,942.00 | 11,340.00 | 85.4 | 86.2 | 50.0 | 0.021 | 94.7 | 15.91 | - | - | 1.000 | 0.083 | 0.305 | below the offered rate: saturated |
| uringpy-app | process | 4 | on | 13 | none | 0 | 400 @10000/s | 5 | 9,913 | 26 | 0.2 | - | 0.93 | 2.00 | 7.0 | 7.3 | 4.3 | 1.149 | 1.7 | 22.96 | - | - | 1.000 | 0.000 | 0.525 |  |
| uringpy-app | process | 4 | on | 13 | none | 0 | 400 @25000/s | 5 | 24,807 | 118 | 0.4 | - | 0.91 | 1.93 | 11.3 | 12.0 | 10.8 | 0.985 | 2.0 | 20.33 | - | - | 1.000 | 0.000 | 0.438 |  |
| uringpy-app | process | 4 | on | 13 | none | 0 | 400 @50000/s | 5 | 49,652 | 297 | 0.5 | - | 1.04 | 2.12 | 20.2 | 20.9 | 19.4 | 0.519 | 3.9 | 17.72 | - | - | 1.000 | 0.000 | 0.200 |  |
| uringpy-app | process | 4 | on | 13 | none | 0 | 400 @100000/s | 5 | 99,371 | 249 | 0.2 | - | 1.17 | 2.50 | 41.7 | 42.5 | 29.8 | 0.191 | 10.5 | 15.11 | - | - | 1.000 | 0.000 | 0.063 |  |
| uringpy-app | process | 4 | on | 13 | none | 0 | 400 @150000/s | 5 | 148,942 | 570 | 0.3 | - | 1.34 | 2.91 | 59.7 | 60.7 | 34.2 | 0.129 | 15.5 | 14.52 | - | - | 1.000 | 0.000 | 0.041 |  |
| uringpy-app | process | 4 | on | 13 | none | 0 | 400 @200000/s | 5 | 198,587 | 760 | 0.3 | - | 1.49 | 3.32 | 74.1 | 77.1 | 40.1 | 0.078 | 25.6 | 13.91 | - | - | 1.000 | 0.000 | 0.022 |  |
| uringpy-app | process | 4 | on | 13 | none | 0 | 400 @250000/s | 5 | 247,871 | 951 | 0.3 | - | 1.51 | 5.93 | 88.9 | 91.9 | 43.4 | 0.066 | 30.4 | 13.95 | - | - | 1.000 | 0.000 | 0.016 |  |
| uringpy-app | process | 4 | on | 13 | none | 0 | 400 @300000/s | 5 | 273,831 | 3,467 | 1.0 | - | 646.31 | 5,406.00 | 97.5 | 98.2 | 66.4 | 0.029 | 68.7 | 14.51 | - | - | 1.000 | 0.000 | 0.003 | below the offered rate: saturated |
| uringpy-app-batch | thread | 4 | on | 13 | none | 0 | 400 @10000/s | 5 | 9,935 | 20 | 0.2 | - | 0.92 | 1.99 | 7.8 | 8.2 | 4.5 | 1.182 | 1.7 | 26.30 | - | - | 0.650 | 0.569 | 0.787 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 0 | 400 @25000/s | 5 | 24,807 | 118 | 0.4 | - | 0.93 | 1.93 | 13.2 | 13.7 | 10.8 | 0.970 | 2.1 | 23.33 | - | - | 0.553 | 0.492 | 0.689 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 0 | 400 @50000/s | 5 | 49,578 | 191 | 0.3 | - | 1.05 | 2.16 | 23.7 | 24.3 | 17.9 | 0.464 | 4.3 | 19.66 | - | - | 0.300 | 0.274 | 0.396 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 0 | 400 @100000/s | 5 | 99,297 | 204 | 0.2 | - | 1.37 | 2.83 | 45.9 | 46.7 | 23.5 | 0.161 | 12.4 | 15.36 | - | - | 0.113 | 0.103 | 0.154 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 0 | 400 @150000/s | 5 | 148,833 | 682 | 0.4 | - | 1.50 | 3.29 | 61.9 | 63.1 | 30.6 | 0.093 | 21.6 | 14.41 | - | - | 0.068 | 0.061 | 0.084 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 0 | 400 @200000/s | 5 | 198,001 | 1,035 | 0.4 | - | 1.63 | 3.68 | 75.0 | 77.1 | 40.6 | 0.060 | 33.3 | 13.81 | - | - | 0.046 | 0.041 | 0.051 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 0 | 400 @250000/s | 5 | 247,012 | 3,139 | 1.0 | - | 36.16 | 399.32 | 89.0 | 91.5 | 50.0 | 0.053 | 38.2 | 13.78 | - | - | 0.040 | 0.035 | 0.035 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 0 | 400 @300000/s | 5 | 265,007 | 949 | 0.3 | - | 1,613.81 | 6,206.00 | 93.7 | 95.1 | 65.9 | 0.022 | 90.4 | 13.99 | - | - | 0.021 | 0.021 | 0.013 | below the offered rate: saturated |
| uringpy-app-batch | process | 4 | on | 13 | none | 0 | 400 @10000/s | 5 | 9,935 | 60 | 0.5 | - | 0.89 | 1.95 | 7.1 | 7.6 | 4.3 | 1.231 | 1.6 | 23.12 | - | - | 0.667 | 0.000 | 0.550 |  |
| uringpy-app-batch | process | 4 | on | 13 | none | 0 | 400 @25000/s | 5 | 24,807 | 118 | 0.4 | - | 0.92 | 1.89 | 11.5 | 12.1 | 10.5 | 1.030 | 1.9 | 20.46 | - | - | 0.576 | 0.000 | 0.442 |  |
| uringpy-app-batch | process | 4 | on | 13 | none | 0 | 400 @50000/s | 5 | 49,504 | 349 | 0.6 | - | 1.03 | 2.10 | 20.1 | 21.1 | 17.6 | 0.534 | 3.8 | 17.65 | - | - | 0.335 | 0.000 | 0.189 |  |
| uringpy-app-batch | process | 4 | on | 13 | none | 0 | 400 @100000/s | 5 | 99,298 | 204 | 0.2 | - | 1.14 | 2.37 | 40.6 | 41.8 | 30.6 | 0.213 | 9.4 | 15.11 | - | - | 0.147 | 0.000 | 0.062 |  |
| uringpy-app-batch | process | 4 | on | 13 | none | 0 | 400 @150000/s | 5 | 148,394 | 1,123 | 0.6 | - | 1.35 | 2.89 | 60.5 | 61.7 | 34.8 | 0.158 | 12.7 | 14.66 | - | - | 0.111 | 0.000 | 0.044 |  |
| uringpy-app-batch | process | 4 | on | 13 | none | 0 | 400 @200000/s | 5 | 198,733 | 500 | 0.2 | - | 1.47 | 3.30 | 73.9 | 75.6 | 40.4 | 0.090 | 22.4 | 13.86 | - | - | 0.065 | 0.000 | 0.022 |  |
| uringpy-app-batch | process | 4 | on | 13 | none | 0 | 400 @250000/s | 5 | 246,735 | 2,387 | 0.8 | - | 1.50 | 757.30 | 89.8 | 95.7 | 46.3 | 0.079 | 25.4 | 14.19 | - | - | 0.058 | 0.000 | 0.018 |  |
| uringpy-app-batch | process | 4 | on | 13 | none | 0 | 400 @300000/s | 5 | 272,861 | 3,487 | 1.0 | - | 1,043.77 | 5,770.00 | 97.6 | 98.5 | 62.8 | 0.034 | 58.3 | 14.49 | - | - | 0.030 | 0.000 | 0.003 | below the offered rate: saturated |
| uvloop-proto-app | process | 4 | on | 13 | none | 0 | 400 @10000/s | 5 | 9,935 | 39 | 0.3 | - | 0.91 | 1.96 | 7.1 | 7.6 | 4.3 | - | - | - | - | - | - | - | - |  |
| uvloop-proto-app | process | 4 | on | 13 | none | 0 | 400 @25000/s | 5 | 24,769 | 132 | 0.4 | - | 0.93 | 1.97 | 12.5 | 13.0 | 11.3 | - | - | - | - | - | - | - | - |  |
| uvloop-proto-app | process | 4 | on | 13 | none | 0 | 400 @50000/s | 5 | 49,468 | 191 | 0.3 | - | 1.03 | 2.08 | 21.4 | 22.2 | 17.6 | - | - | - | - | - | - | - | - |  |
| uvloop-proto-app | process | 4 | on | 13 | none | 0 | 400 @100000/s | 5 | 99,297 | 381 | 0.3 | - | 1.25 | 2.55 | 46.9 | 47.9 | 29.4 | - | - | - | - | - | - | - | - |  |
| uvloop-proto-app | process | 4 | on | 13 | none | 0 | 400 @150000/s | 5 | 148,834 | 482 | 0.3 | - | 1.36 | 2.97 | 67.8 | 69.2 | 39.1 | - | - | - | - | - | - | - | - |  |
| uvloop-proto-app | process | 4 | on | 13 | none | 0 | 400 @200000/s | 5 | 198,304 | 547 | 0.2 | - | 1.46 | 279.74 | 87.3 | 91.1 | 44.1 | - | - | - | - | - | - | - | - |  |
| uvloop-proto-app | process | 4 | on | 13 | none | 0 | 400 @250000/s | 5 | 209,927 | 3,419 | 1.3 | - | 2,560.00 | 7,420.00 | 97.6 | 98.3 | 62.3 | - | - | - | - | - | - | - | - | below the offered rate: saturated |
| uvloop-proto-app | process | 4 | on | 13 | none | 0 | 400 @300000/s | 5 | 210,008 | 2,613 | 1.0 | - | 5,342.00 | 11,206.00 | 98.0 | 98.5 | 62.3 | - | - | - | - | - | - | - | - | below the offered rate: saturated |
