# Benchmark summary

- experiment: openloop   started (UTC): 2026-10-08T18:19:24+00:00
- repetitions per cell: 5   run length: 30 s   warm-up: 5 s   order: interleaved, shuffled (seed 198216527)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1013-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1013-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | conns | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | GIL rel. or acq./req | GIL switches/req | vol. ctx sw./req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy-app | thread | 4 | on | 13 | none | 0 | 400 @50000/s | 5 | 49,505 | 125 | 0.2 | - | 1.22 | 2.70 | 30.2 | 30.9 | 17.3 | 0.314 | 6.4 | 22.52 | - | - | 1.000 | 0.264 | 0.789 |  |
| uringpy-app | thread | 4 | on | 13 | none | 0 | 400 @100000/s | 5 | 99,220 | 454 | 0.4 | - | 1.80 | 4.74 | 58.7 | 59.9 | 28.0 | 0.089 | 22.4 | 20.33 | - | - | 1.000 | 0.192 | 0.797 |  |
| uringpy-app | thread | 4 | on | 13 | none | 0 | 400 @150000/s | 5 | 148,608 | 374 | 0.2 | - | 2.27 | 5.66 | 75.5 | 76.3 | 40.4 | 0.044 | 45.8 | 18.30 | - | - | 1.000 | 0.144 | 0.600 |  |
| uringpy-app | thread | 4 | on | 13 | none | 0 | 400 @200000/s | 5 | 192,472 | 1,422 | 0.6 | - | 460.68 | 2,296.00 | 84.0 | 85.3 | 49.1 | 0.024 | 82.5 | 16.39 | - | - | 1.000 | 0.088 | 0.333 |  |
| uringpy-app | thread | 4 | on | 13 | none | 0 | 400 @300000/s | 5 | 200,504 | 4,023 | 1.6 | - | 6,136.00 | 11,278.00 | 85.3 | 86.4 | 50.0 | 0.021 | 94.8 | 16.06 | - | - | 1.000 | 0.083 | 0.306 | below the offered rate: saturated |
| uringpy-app | thread | 4 | on | 13 | none | 0 | 400 @400000/s | 5 | 203,022 | 3,309 | 1.3 | - | 9,588.00 | 15,492.00 | 85.8 | 86.4 | 51.1 | 0.021 | 94.6 | 15.92 | - | - | 1.000 | 0.081 | 0.293 | below the offered rate: saturated |
| uringpy-app-batch | thread | 4 | on | 13 | none | 0 | 400 @50000/s | 5 | 49,578 | 191 | 0.3 | - | 1.08 | 2.20 | 23.9 | 24.8 | 18.8 | 0.487 | 4.1 | 20.02 | - | - | 0.315 | 0.287 | 0.409 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 0 | 400 @100000/s | 5 | 99,297 | 203 | 0.2 | - | 1.35 | 2.83 | 46.6 | 47.3 | 25.3 | 0.182 | 11.0 | 16.07 | - | - | 0.127 | 0.116 | 0.171 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 0 | 400 @150000/s | 5 | 149,052 | 375 | 0.2 | - | 1.50 | 3.30 | 62.5 | 64.1 | 32.7 | 0.098 | 20.4 | 14.62 | - | - | 0.072 | 0.064 | 0.088 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 0 | 400 @200000/s | 5 | 198,002 | 1,037 | 0.4 | - | 1.62 | 3.67 | 75.8 | 77.7 | 42.9 | 0.061 | 32.7 | 13.98 | - | - | 0.047 | 0.042 | 0.051 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 0 | 400 @300000/s | 5 | 259,676 | 4,014 | 1.2 | - | 2,286.00 | 5,664.00 | 94.3 | 95.7 | 66.1 | 0.022 | 89.7 | 14.30 | - | - | 0.022 | 0.021 | 0.012 | below the offered rate: saturated |
| uringpy-app-batch | thread | 4 | on | 13 | none | 0 | 400 @400000/s | 5 | 264,493 | 1,820 | 0.6 | - | 6,428.00 | 11,262.00 | 94.2 | 95.6 | 67.0 | 0.021 | 94.0 | 14.06 | - | - | 0.021 | 0.021 | 0.012 | below the offered rate: saturated |
| uringpy-app-batch | process | 4 | on | 13 | none | 0 | 400 @50000/s | 5 | 49,652 | 191 | 0.3 | - | 1.05 | 2.14 | 20.3 | 21.0 | 19.1 | 0.567 | 3.5 | 18.09 | - | - | 0.354 | 0.000 | 0.203 |  |
| uringpy-app-batch | process | 4 | on | 13 | none | 0 | 400 @100000/s | 5 | 99,077 | 518 | 0.4 | - | 1.18 | 2.50 | 43.5 | 44.7 | 29.1 | 0.256 | 7.8 | 15.64 | - | - | 0.174 | 0.000 | 0.076 |  |
| uringpy-app-batch | process | 4 | on | 13 | none | 0 | 400 @150000/s | 5 | 148,723 | 570 | 0.3 | - | 1.34 | 2.93 | 61.7 | 63.0 | 37.0 | 0.166 | 12.1 | 15.11 | - | - | 0.116 | 0.000 | 0.046 |  |
| uringpy-app-batch | process | 4 | on | 13 | none | 0 | 400 @200000/s | 5 | 198,734 | 810 | 0.3 | - | 1.48 | 3.32 | 74.9 | 77.5 | 42.5 | 0.094 | 21.3 | 14.10 | - | - | 0.068 | 0.000 | 0.023 |  |
| uringpy-app-batch | process | 4 | on | 13 | none | 0 | 400 @300000/s | 5 | 275,015 | 2,602 | 0.8 | - | 1,254.69 | 4,484.00 | 98.2 | 98.6 | 65.9 | 0.031 | 65.1 | 14.45 | - | - | 0.027 | 0.000 | 0.002 | below the offered rate: saturated |
| uringpy-app-batch | process | 4 | on | 13 | none | 0 | 400 @400000/s | 5 | 277,490 | 1,256 | 0.4 | - | 5,574.00 | 11,034.00 | 98.3 | 98.7 | 69.0 | 0.022 | 91.5 | 14.40 | - | - | 0.021 | 0.000 | 0.001 | below the offered rate: saturated |
| uvloop-proto-app | process | 4 | on | 13 | none | 0 | 400 @50000/s | 5 | 49,652 | 191 | 0.3 | - | 1.02 | 2.10 | 21.0 | 22.1 | 19.3 | - | - | - | - | - | - | - | - |  |
| uvloop-proto-app | process | 4 | on | 13 | none | 0 | 400 @100000/s | 5 | 99,149 | 380 | 0.3 | - | 1.22 | 2.53 | 48.1 | 49.1 | 29.7 | - | - | - | - | - | - | - | - |  |
| uvloop-proto-app | process | 4 | on | 13 | none | 0 | 400 @150000/s | 5 | 149,163 | 375 | 0.2 | - | 1.33 | 2.97 | 69.1 | 70.7 | 41.1 | - | - | - | - | - | - | - | - |  |
| uvloop-proto-app | process | 4 | on | 13 | none | 0 | 400 @200000/s | 5 | 197,772 | 1,251 | 0.5 | - | 1.45 | 207.60 | 87.9 | 92.1 | 44.6 | - | - | - | - | - | - | - | - |  |
| uvloop-proto-app | process | 4 | on | 13 | none | 0 | 400 @300000/s | 5 | 209,694 | 2,639 | 1.0 | - | 5,498.00 | 10,880.00 | 98.2 | 98.6 | 62.5 | - | - | - | - | - | - | - | - | below the offered rate: saturated |
| uvloop-proto-app | process | 4 | on | 13 | none | 0 | 400 @400000/s | 5 | 208,754 | 2,024 | 0.8 | - | 8,978.00 | 16,390.00 | 98.2 | 98.7 | 62.1 | - | - | - | - | - | - | - | - | below the offered rate: saturated |
