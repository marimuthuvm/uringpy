# Benchmark summary

- experiment: app   started (UTC): 2026-10-08T22:58:56+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 21894301)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1013-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1013-gcp, interpreter 3.14.7 gil_on

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | conns | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | GIL rel. or acq./req | GIL switches/req | vol. ctx sw./req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy | thread | 1 | on | 13 | none | 0 | 400 | 5 | 131,267 | 3,769 | 2.3 | 1.00× | 3.03 | 3.27 | 29.6 | 97.1 | 35.4 | 0.006 | 365.2 | 7.70 | - | - | - | 0.000 | 0.000 |  |
| uringpy | thread | 4 | on | 13 | none | 0 | 400 | 5 | 302,251 | 2,417 | 0.6 | 2.30× ± 0.07 | 1.26 | 2.03 | 95.3 | 95.5 | 72.6 | 0.022 | 93.0 | 12.94 | - | - | - | 0.000 | 0.001 |  |
| uringpy | process | 4 | on | 13 | none | 0 | 400 | 5 | 301,232 | 4,421 | 1.2 | - | 1.27 | 1.85 | 97.0 | 97.4 | 73.0 | 0.023 | 88.7 | 13.25 | - | - | - | 0.000 | 0.001 |  |
| py-epoll | thread | 1 | on | 13 | none | 0 | 400 | 5 | 98,790 | 2,934 | 2.4 | 1.00× | 3.97 | 7.88 | 28.3 | 96.7 | 28.0 | 2.004 | - | 10.15 | - | - | 2.004 | 0.000 | 0.000 |  |
| py-epoll | thread | 4 | on | 13 | none | 0 | 400 | 5 | 65,903 | 7,652 | 9.4 | 0.67× ± 0.08 | 5.96 | 11.50 | 62.0 | 63.3 | 19.5 | 2.012 | - | 33.59 | - | - | 2.012 | 1.452 | 2.002 | CV > 5% |
| py-epoll | process | 4 | on | 13 | none | 0 | 400 | 5 | 245,546 | 1,667 | 0.5 | - | 1.53 | 3.38 | 96.8 | 97.2 | 68.5 | 2.014 | - | 16.24 | - | - | 2.014 | 0.000 | 0.001 |  |
| uringpy-app | thread | 1 | on | 13 | none | 0 | 400 | 5 | 113,339 | 1,943 | 1.4 | 1.00× | 3.51 | 3.85 | 28.9 | 97.1 | 30.8 | 0.005 | 385.5 | 8.86 | - | - | 1.000 | 0.000 | 0.000 |  |
| uringpy-app | thread | 4 | on | 13 | none | 0 | 400 | 5 | 201,450 | 3,167 | 1.3 | 1.78× ± 0.04 | 1.90 | 3.39 | 84.4 | 85.1 | 49.5 | 0.022 | 92.6 | 16.04 | - | - | 1.000 | 0.082 | 0.301 |  |
| uringpy-app | process | 4 | on | 13 | none | 0 | 400 | 5 | 273,434 | 3,005 | 0.9 | - | 1.41 | 1.95 | 96.5 | 97.1 | 66.8 | 0.022 | 89.7 | 14.64 | - | - | 1.000 | 0.000 | 0.001 |  |
| uringpy-app-batch | thread | 1 | on | 13 | none | 0 | 400 | 5 | 117,281 | 3,293 | 2.3 | 1.00× | 3.38 | 3.71 | 28.8 | 96.8 | 31.8 | 0.006 | 370.3 | 8.61 | - | - | 0.005 | 0.000 | 0.000 |  |
| uringpy-app-batch | thread | 4 | on | 13 | none | 0 | 400 | 5 | 264,941 | 1,066 | 0.3 | 2.26× ± 0.06 | 1.47 | 2.05 | 93.0 | 94.4 | 65.6 | 0.022 | 92.6 | 14.02 | - | - | 0.021 | 0.021 | 0.012 |  |
| uringpy-app-batch | process | 4 | on | 13 | none | 0 | 400 | 5 | 277,070 | 1,523 | 0.4 | - | 1.41 | 1.88 | 97.0 | 97.3 | 67.4 | 0.022 | 89.6 | 14.42 | - | - | 0.022 | 0.000 | 0.001 |  |
| c-epoll-app | thread | 1 | on | 13 | none | 0 | 400 | 5 | 95,424 | 2,715 | 2.3 | 1.00× | 4.12 | 8.17 | 28.3 | 96.9 | 26.5 | 2.004 | - | 10.52 | - | - | 1.000 | 0.000 | 0.000 |  |
| c-epoll-app | thread | 4 | on | 13 | none | 0 | 400 | 5 | 74,568 | 3,785 | 4.1 | 0.78× ± 0.05 | 5.22 | 10.63 | 60.6 | 61.8 | 24.4 | 2.013 | - | 28.52 | - | - | 1.000 | 0.911 | 1.403 |  |
| c-epoll-app | process | 4 | on | 13 | none | 0 | 400 | 5 | 240,342 | 1,034 | 0.3 | - | 1.54 | 3.50 | 96.7 | 97.2 | 67.7 | 2.013 | - | 16.58 | - | - | 1.000 | 0.000 | 0.001 |  |
| c-epoll-app-batch | thread | 1 | on | 13 | none | 0 | 400 | 5 | 108,052 | 3,218 | 2.4 | 1.00× | 3.61 | 7.19 | 28.9 | 96.9 | 29.8 | 2.004 | - | 9.27 | - | - | 0.003 | 0.000 | 0.000 |  |
| c-epoll-app-batch | thread | 4 | on | 13 | none | 0 | 400 | 5 | 256,053 | 2,799 | 0.9 | 2.37× ± 0.08 | 1.39 | 3.21 | 93.9 | 94.6 | 67.6 | 2.013 | - | 15.04 | - | - | 0.013 | 0.013 | 0.007 |  |
| c-epoll-app-batch | process | 4 | on | 13 | none | 0 | 400 | 5 | 264,192 | 8,013 | 2.4 | - | 1.35 | 3.02 | 96.9 | 97.4 | 68.0 | 2.014 | - | 15.08 | - | - | 0.013 | 0.000 | 0.001 |  |
