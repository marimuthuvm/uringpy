# Cross-runtime benchmark image: builds on the uringpy image and adds the
# competing Python io_uring event loops that install in this environment.
# Note: talyn requires Python >= 3.13 and is therefore excluded from this
# 3.11-based image; it must be benchmarked separately on a 3.13+ host.
FROM uringpy:latest

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    cargo \
    rustc \
    && rm -rf /var/lib/apt/lists/*

# uringloop (Cython, proactor over io_uring). Depends on the liburing wheel.
RUN pip install --no-cache-dir liburing \
    && git clone --depth 1 https://github.com/thearchitector/uringloop /opt/uringloop \
    && pip install --no-cache-dir /opt/uringloop || echo "[warn] uringloop build failed"

# uringcore (Rust/PyO3). Builds from source via the system Rust toolchain.
RUN pip install --no-cache-dir uringcore || echo "[warn] uringcore build failed"

WORKDIR /app
