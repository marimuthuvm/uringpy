# Benchmark summary

- experiment: factorial   started (UTC): 2026-10-07T13:10:59+00:00
- repetitions per cell: 5   run length: 20 s   warm-up: 5 s   order: interleaved, shuffled (seed 1247964940)
- load: wrk -t8 -c400 --latency
- client: t2d-standard-8, 8 CPUs, kernel 7.0.0-1011-gcp
- server: t2d-standard-4, 4 CPUs, kernel 7.0.0-1011-gcp, interpreter 3.14.7 gil_OFF

Throughput is requests/second: mean of the repetitions, with the half-width of the 95% confidence interval (Student t). Scaling is the ratio to the 1-worker cell of the same engine and mode, with its 95% half-width. CPU columns are whole-machine busy %, averaged over runs. GIL is the state the server process reported at start-up. Proc CPU is the server processes' own user+system time per request (kernel network work done outside them is not included). GIL hold and wait are per handler call, where timing was enabled.

| engine | mode | workers | GIL | body B | batch cap | handler work | conns | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | proc CPU µs/req | GIL hold µs/req | GIL wait µs/req | GIL rel. or acq./req | vol. ctx sw./req | flags |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| uringpy | thread | 1 | off | 13 | none | 0 | 400 | 5 | 141,785 | 3,381 | 1.9 | 1.00× | 2.80 | 3.04 | 29.7 | 98.2 | 37.5 | 0.006 | 376.7 | 7.11 | - | - | - | 0.000 |  |
| uringpy | thread | 2 | off | 13 | none | 0 | 400 | 5 | 226,833 | 8,055 | 2.9 | 1.60× ± 0.07 | 1.70 | 2.12 | 59.1 | 98.1 | 54.7 | 0.012 | 168.8 | 8.85 | - | - | - | 0.001 |  |
| uringpy | thread | 4 | off | 13 | none | 0 | 400 | 5 | 326,564 | 1,624 | 0.4 | 2.30× ± 0.06 | 1.16 | 1.71 | 98.0 | 98.3 | 75.3 | 0.024 | 82.7 | 12.24 | - | - | - | 0.001 |  |
| c-epoll | thread | 1 | off | 13 | none | 0 | 400 | 5 | 123,941 | 2,731 | 1.8 | 1.00× | 3.15 | 6.29 | 29.2 | 98.0 | 35.5 | 2.004 | - | 8.09 | - | - | - | 0.000 |  |
| c-epoll | thread | 2 | off | 13 | none | 0 | 400 | 5 | 202,211 | 1,483 | 0.6 | 1.63× ± 0.04 | 1.90 | 3.94 | 58.7 | 98.3 | 56.5 | 2.007 | - | 9.91 | - | - | - | 0.001 |  |
| c-epoll | thread | 4 | off | 13 | none | 0 | 400 | 5 | 295,191 | 863 | 0.2 | 2.38× ± 0.05 | 1.23 | 2.75 | 97.9 | 98.3 | 75.2 | 2.014 | - | 13.50 | - | - | - | 0.001 |  |
| py-uring | thread | 1 | off | 13 | none | 0 | 400 | 5 | 130,002 | 1,505 | 0.9 | 1.00× | 3.06 | 3.30 | 29.2 | 97.8 | 34.9 | 0.010 | - | 7.73 | - | - | 0.010 | 0.000 |  |
| py-uring | thread | 2 | off | 13 | none | 0 | 400 | 5 | 208,337 | 4,446 | 1.7 | 1.60× ± 0.04 | 1.86 | 2.30 | 58.0 | 98.2 | 50.8 | 0.022 | - | 9.63 | - | - | 0.022 | 0.000 |  |
| py-uring | thread | 4 | off | 13 | none | 0 | 400 | 5 | 302,549 | 2,291 | 0.6 | 2.33× ± 0.03 | 1.27 | 1.81 | 98.1 | 98.4 | 71.6 | 0.045 | - | 13.22 | - | - | 0.045 | 0.001 |  |
| py-epoll | thread | 1 | off | 13 | none | 0 | 400 | 5 | 109,167 | 3,650 | 2.7 | 1.00× | 3.58 | 7.15 | 28.7 | 97.9 | 31.9 | 2.004 | - | 9.20 | - | - | 2.004 | 0.000 |  |
| py-epoll | thread | 2 | off | 13 | none | 0 | 400 | 5 | 176,229 | 4,077 | 1.9 | 1.61× ± 0.07 | 2.19 | 4.49 | 57.0 | 97.9 | 50.6 | 2.007 | - | 11.35 | - | - | 2.007 | 0.001 |  |
| py-epoll | thread | 4 | off | 13 | none | 0 | 400 | 5 | 261,801 | 1,302 | 0.4 | 2.40× ± 0.08 | 1.42 | 3.18 | 97.9 | 98.3 | 70.5 | 2.013 | - | 15.23 | - | - | 2.013 | 0.001 |  |
| py-epoll-batch | thread | 1 | off | 13 | none | 0 | 400 | 5 | 125,105 | 1,707 | 1.1 | 1.00× | 3.12 | 6.23 | 29.4 | 98.0 | 36.2 | 2.004 | - | 8.05 | - | - | 0.006 | 0.000 |  |
| py-epoll-batch | thread | 2 | off | 13 | none | 0 | 400 | 5 | 200,368 | 4,531 | 1.8 | 1.60× ± 0.04 | 1.89 | 4.00 | 58.6 | 98.2 | 57.5 | 2.007 | - | 10.01 | - | - | 0.013 | 0.001 |  |
| py-epoll-batch | thread | 4 | off | 13 | none | 0 | 400 | 5 | 291,749 | 886 | 0.2 | 2.33× ± 0.03 | 1.24 | 2.81 | 98.1 | 98.4 | 74.1 | 2.013 | - | 13.67 | - | - | 0.026 | 0.001 |  |
| py-uring-held | thread | 1 | off | 13 | none | 0 | 400 | 5 | 131,902 | 3,348 | 2.0 | 1.00× | 3.01 | 3.24 | 29.4 | 97.9 | 35.0 | 0.010 | - | 7.67 | - | - | 0.005 | 0.000 |  |
| py-uring-held | thread | 2 | off | 13 | none | 0 | 400 | 5 | 211,267 | 5,575 | 2.1 | 1.60× ± 0.06 | 1.86 | 2.15 | 58.7 | 98.1 | 50.8 | 0.022 | - | 9.51 | - | - | 0.011 | 0.000 |  |
| py-uring-held | thread | 4 | off | 13 | none | 0 | 400 | 5 | 303,015 | 1,234 | 0.3 | 2.30× ± 0.06 | 1.26 | 1.77 | 97.8 | 98.3 | 70.9 | 0.044 | - | 13.21 | - | - | 0.022 | 0.001 |  |
