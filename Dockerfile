FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    liburing-dev \
    wrk \
    curl \
    strace \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir --upgrade pip setuptools wheel Cython pytest
RUN pip install --no-cache-dir -e . uvloop

CMD ["python3", "benchmarks/bench_throughput.py"]
