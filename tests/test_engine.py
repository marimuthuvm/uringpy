import os
import pytest
from uringpy import URingEngine

def test_engine_init():
    try:
        engine = URingEngine(entries=64, slot_size=1024, total_slots=64)
        assert engine is not None
    except OSError as e:
        pytest.skip(f"Kernel does not support io_uring or permission denied: {e}")

def test_slab_read_cycle():
    try:
        engine = URingEngine(entries=64, slot_size=1024, total_slots=64)
    except OSError:
        pytest.skip("io_uring unavailable")

    r, w = os.pipe()
    os.write(w, b"hello uringpy")
    
    slot = engine.submit_read(r)
    assert slot >= 0

    res = None
    for _ in range(100):
        res = engine.poll_completion()
        if res is not None:
            break

    assert res is not None
    bytes_read, data = res
    assert bytes_read == 13
    assert data == b"hello uringpy"

    os.close(r)
    os.close(w)
