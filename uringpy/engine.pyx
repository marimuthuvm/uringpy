# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: freethreading_compatible=True

import socket
import sys
import traceback
from libc.stdlib cimport malloc, free, realloc
from libc.stdint cimport uint8_t, uint16_t, uint32_t, uint64_t, int32_t, uintptr_t
from libc.string cimport memset, memcpy
from libc.errno cimport EINTR
from cpython.ref cimport PyObject
from cpython.exc cimport PyErr_CheckSignals
from posix.time cimport clock_gettime, timespec, CLOCK_MONOTONIC
from cpython.bytes cimport PyBytes_FromStringAndSize, PyBytes_AsStringAndSize
from cpython.buffer cimport PyObject_GetBuffer, PyBuffer_Release, PyBUF_SIMPLE

# A SEND completion carries the number of response bytes already sent in the low
# 24 bits of user_data, so a response must be shorter than 16 MiB.
cdef enum:
    MAX_RESPONSE_LEN = 0xFFFFFF


cdef class SlabView:
    # Zero-copy view over one slab slot. Exposes the received bytes to Python via
    # the buffer protocol (no bytes allocation) and returns the slot to the pool
    # when released, so the slot is pinned for the view's lifetime.
    cdef char *ptr
    cdef Py_ssize_t length
    cdef int slot_id
    cdef object engine
    cdef bint released
    cdef Py_ssize_t shape[1]

    def __cinit__(self, object engine, unsigned long long addr,
                  Py_ssize_t length, int slot_id):
        self.engine = engine
        self.ptr = <char*><uintptr_t>addr
        self.length = length
        self.slot_id = slot_id
        self.released = False

    def __getbuffer__(self, Py_buffer *buffer, int flags):
        self.shape[0] = self.length
        buffer.buf = self.ptr
        buffer.obj = self
        buffer.len = self.length
        buffer.itemsize = 1
        buffer.readonly = 1
        buffer.ndim = 1
        buffer.format = "B"
        buffer.shape = self.shape
        buffer.strides = NULL
        buffer.suboffsets = NULL
        buffer.internal = NULL

    def __releasebuffer__(self, Py_buffer *buffer):
        pass

    def release(self):
        if not self.released and self.slot_id >= 0 and self.engine is not None:
            self.engine._free_slot(self.slot_id)
            self.released = True

    def __dealloc__(self):
        self.release()


cdef extern from "liburing.h" nogil:
    struct io_uring_sqe:
        uint8_t opcode
        uint8_t flags
        uint16_t ioprio
        int32_t fd
        uint64_t off
        uint64_t addr
        uint32_t len
        uint32_t op_flags
        uint64_t user_data
        uint16_t buf_group

    struct io_uring_cqe:
        uint64_t user_data
        int32_t res
        uint32_t flags

    struct io_uring:
        pass

    struct io_uring_buf_ring:
        pass

    enum: IOSQE_BUFFER_SELECT
    enum: IORING_CQE_F_BUFFER
    enum: IORING_CQE_F_MORE
    enum: IORING_CQE_BUFFER_SHIFT

    int io_uring_queue_init(unsigned entries, io_uring *ring, unsigned flags)
    void io_uring_queue_exit(io_uring *ring)
    io_uring_sqe* io_uring_get_sqe(io_uring *ring)
    int io_uring_submit(io_uring *ring)
    int io_uring_submit_and_wait(io_uring *ring, unsigned wait_nr)
    int io_uring_peek_cqe(io_uring *ring, io_uring_cqe **cqe_ptr)
    int io_uring_wait_cqe(io_uring *ring, io_uring_cqe **cqe_ptr)
    void io_uring_cqe_seen(io_uring *ring, io_uring_cqe *cqe)
    void io_uring_prep_read(io_uring_sqe *sqe, int fd, void *buf, unsigned nbytes, uint64_t offset)
    void io_uring_prep_write(io_uring_sqe *sqe, int fd, const void *buf, unsigned nbytes, uint64_t offset)
    void io_uring_prep_accept(io_uring_sqe *sqe, int fd, void *addr, void *addrlen, int flags)
    void io_uring_prep_recv(io_uring_sqe *sqe, int fd, void *buf, size_t length, int flags)
    void io_uring_prep_send(io_uring_sqe *sqe, int fd, const void *buf, size_t length, int flags)
    void io_uring_prep_recv_multishot(io_uring_sqe *sqe, int fd, void *buf, size_t length, int flags)
    io_uring_buf_ring* io_uring_setup_buf_ring(io_uring *ring, unsigned nentries, int bgid, unsigned flags, int *ret)
    int io_uring_free_buf_ring(io_uring *ring, io_uring_buf_ring *br, unsigned nentries, int bgid)
    void io_uring_buf_ring_add(io_uring_buf_ring *br, void *addr, unsigned length, unsigned short bid, int mask, int buf_offset)
    void io_uring_buf_ring_advance(io_uring_buf_ring *br, int count)
    int io_uring_buf_ring_mask(unsigned ring_entries)

cdef extern from "slab.h" nogil:
    ctypedef struct slab_pool_t:
        void *raw_memory
        size_t slot_size
        size_t total_slots

    slab_pool_t* slab_pool_create(size_t total_slots, size_t slot_size)
    void* slab_alloc(slab_pool_t *pool, int32_t *slot_idx)
    void slab_free(slab_pool_t *pool, int32_t slot_idx)
    void slab_pool_destroy(slab_pool_t *pool)

cdef extern from "unistd.h" nogil:
    int close(int fd)


cdef inline unsigned long long _now_ns() noexcept nogil:
    cdef timespec ts
    clock_gettime(CLOCK_MONOTONIC, &ts)
    return <unsigned long long>ts.tv_sec * 1000000000ULL \
        + <unsigned long long>ts.tv_nsec


# --- nogil helpers shared by the C-side reactors -----------------------------
# Module-level inline functions (not methods) so the C compiler inlines them
# into the reactor loop.

cdef inline io_uring_sqe* _get_sqe(io_uring *ring,
                                   unsigned long long *enters) noexcept nogil:
    # If the submission queue is full, flush it once and retry instead of
    # silently dropping the operation. The flush is an io_uring_enter, so it is
    # counted in `enters`.
    cdef io_uring_sqe *sqe = io_uring_get_sqe(ring)
    if sqe == NULL:
        io_uring_submit(ring)
        enters[0] += 1
        sqe = io_uring_get_sqe(ring)
    return sqe


cdef inline void _arm_accept(io_uring *ring, int listen_fd,
                             unsigned long long *enters) noexcept nogil:
    cdef io_uring_sqe *sqe = _get_sqe(ring, enters)
    if sqe != NULL:
        io_uring_prep_accept(sqe, listen_fd, NULL, NULL, 0)
        sqe.user_data = (<uint64_t>1 << 56) | ((<uint64_t>(<uint32_t>listen_fd)) << 24)


cdef inline void _arm_recv(io_uring *ring, slab_pool_t *pool, int fd,
                           unsigned long long *enters) noexcept nogil:
    # Queue a recv into a fresh slab slot. If no slot or SQE is available the
    # connection is closed rather than left open with nothing armed on it.
    cdef int32_t slot = -1
    cdef void *buf = slab_alloc(pool, &slot)
    cdef io_uring_sqe *sqe
    if buf == NULL:
        close(fd)
        return
    sqe = _get_sqe(ring, enters)
    if sqe == NULL:
        slab_free(pool, slot)
        close(fd)
        return
    io_uring_prep_recv(sqe, fd, buf, pool.slot_size, 0)
    sqe.user_data = (<uint64_t>2 << 56) | ((<uint64_t>(<uint32_t>fd)) << 24) \
        | (<uint64_t>(slot & 0xFFFFFF))


cdef inline void _arm_send(io_uring *ring, int fd, const char *base,
                           size_t total, size_t off,
                           unsigned long long *enters) noexcept nogil:
    # Queue a send of base[off:total]. `base` must stay valid until the whole
    # response has been sent; `off` rides in user_data so a short send resumes
    # where it stopped.
    cdef io_uring_sqe *sqe = _get_sqe(ring, enters)
    if sqe == NULL:
        close(fd)
        return
    io_uring_prep_send(sqe, fd, base + off, total - off, 0)
    sqe.user_data = (<uint64_t>3 << 56) | ((<uint64_t>(<uint32_t>fd)) << 24) \
        | (<uint64_t>(off & 0xFFFFFF))


cdef class URingEngine:
    cdef io_uring ring
    cdef slab_pool_t *pool
    cdef bint initialized
    cdef io_uring_buf_ring *buf_ring
    cdef void *buf_base
    cdef unsigned buf_count
    cdef unsigned buf_size
    cdef int buf_gid
    cdef int buf_mask
    cdef unsigned long long stat_waits
    cdef unsigned long long stat_completions
    cdef unsigned long long stat_submits
    cdef char *_echo_resp
    cdef size_t _echo_resp_len
    cdef int _stop
    cdef int _serving
    cdef object _pending_exc
    # Per-connection response buffers for serve_forever_app, indexed by fd.
    # Owned by this engine (one engine per worker), so never shared.
    cdef char **_conn_buf
    cdef size_t *_conn_cap
    cdef size_t *_conn_len
    cdef int _conn_n
    cdef unsigned long long stat_handler_calls
    cdef unsigned long long stat_handler_errors
    # Reactor-only counters: io_uring_enter calls, responses fully sent, and
    # close() calls made by the loop.
    cdef unsigned long long stat_enters
    cdef unsigned long long stat_requests
    cdef unsigned long long stat_closes
    cdef unsigned _max_batch
    # Optional timing of the GIL-held section of serve_forever_app.
    cdef bint _gil_timing
    cdef unsigned long long stat_gil_hold_ns
    cdef unsigned long long stat_gil_wait_ns
    def __cinit__(self, unsigned int entries=1024, size_t slot_size=4096, size_t total_slots=1024):
        cdef int ret = io_uring_queue_init(entries, &self.ring, 0)
        if ret < 0:
            raise OSError(-ret, "Failed to initialize io_uring queue")
        
        self.pool = slab_pool_create(total_slots, slot_size)
        if self.pool == NULL:
            io_uring_queue_exit(&self.ring)
            raise MemoryError("Failed to allocate slab pool")

        self.buf_ring = NULL
        self.buf_base = NULL
        self.buf_count = 0
        self.stat_waits = 0
        self.stat_completions = 0
        self.stat_submits = 0
        self._echo_resp = NULL
        self._echo_resp_len = 0
        self._stop = 0
        self._serving = 0
        self._pending_exc = None
        self._conn_buf = NULL
        self._conn_cap = NULL
        self._conn_len = NULL
        self._conn_n = 0
        self.stat_handler_calls = 0
        self.stat_handler_errors = 0
        self.stat_enters = 0
        self.stat_requests = 0
        self.stat_closes = 0
        self._max_batch = 0
        self._gil_timing = False
        self.stat_gil_hold_ns = 0
        self.stat_gil_wait_ns = 0
        self.initialized = True

    def __dealloc__(self):
        cdef int i
        if self._conn_buf != NULL:
            for i in range(self._conn_n):
                if self._conn_buf[i] != NULL:
                    free(self._conn_buf[i])
            free(self._conn_buf)
        if self._conn_cap != NULL:
            free(self._conn_cap)
        if self._conn_len != NULL:
            free(self._conn_len)
        if self.initialized:
            if self.buf_ring != NULL and self.buf_count > 0:
                io_uring_free_buf_ring(&self.ring, self.buf_ring, self.buf_count, self.buf_gid)
            if self.buf_base != NULL:
                free(self.buf_base)
            io_uring_queue_exit(&self.ring)
            if self.pool != NULL:
                slab_pool_destroy(self.pool)
            if self._echo_resp != NULL:
                free(self._echo_resp)

    def submit_read(self, int fd):
        cdef int32_t slot_idx = -1
        cdef void *buf = slab_alloc(self.pool, &slot_idx)
        if buf == NULL:
            raise MemoryError("Slab pool exhausted")

        cdef io_uring_sqe *sqe = io_uring_get_sqe(&self.ring)
        if sqe == NULL:
            slab_free(self.pool, slot_idx)
            raise RuntimeError("Submission queue full")

        io_uring_prep_read(sqe, fd, buf, <unsigned int>self.pool.slot_size, 0)
        sqe.user_data = <uint64_t>slot_idx
        io_uring_submit(&self.ring)
        return slot_idx

    def poll_completion(self):
        cdef io_uring_cqe *cqe = NULL
        cdef int ret = io_uring_peek_cqe(&self.ring, &cqe)
        if ret < 0 or cqe == NULL:
            return None

        cdef int32_t slot_idx = <int32_t>cqe.user_data
        cdef int res = cqe.res
        io_uring_cqe_seen(&self.ring, cqe)

        cdef bytes data = None
        if res > 0 and slot_idx >= 0:
            data = (<char*>self.pool.raw_memory + (slot_idx * self.pool.slot_size))[:res]
        
        if slot_idx >= 0:
            slab_free(self.pool, slot_idx)

        return res, data

    cdef object _consume(self, io_uring_cqe *cqe):
        # Shared reap path: identical slab + zero-copy slice handling used by
        # the non-blocking poll and the blocking wait entry points.
        cdef int32_t slot_idx = <int32_t>cqe.user_data
        cdef int res = cqe.res
        io_uring_cqe_seen(&self.ring, cqe)

        cdef bytes data = None
        if res > 0 and slot_idx >= 0:
            data = (<char*>self.pool.raw_memory + (slot_idx * self.pool.slot_size))[:res]

        if slot_idx >= 0:
            slab_free(self.pool, slot_idx)

        return res, data

    def wait_completion(self):
        # Blocking analogue of poll_completion: parks in-kernel until a
        # completion is ready (like epoll_wait) instead of busy-polling.
        cdef io_uring_cqe *cqe = NULL
        cdef int ret
        with nogil:
            ret = io_uring_wait_cqe(&self.ring, &cqe)
        if ret < 0:
            raise OSError(-ret, "io_uring_wait_cqe failed")
        if cqe == NULL:
            return None
        return self._consume(cqe)

    def submit_read_and_wait(self, int fd):
        # Submit one read and block for its completion in a single io_uring_enter
        # syscall, versus submit_read + poll (two syscalls / busy-poll spin).
        cdef int32_t slot_idx = -1
        cdef void *buf = slab_alloc(self.pool, &slot_idx)
        if buf == NULL:
            raise MemoryError("Slab pool exhausted")

        cdef io_uring_sqe *sqe = io_uring_get_sqe(&self.ring)
        if sqe == NULL:
            slab_free(self.pool, slot_idx)
            raise RuntimeError("Submission queue full")

        io_uring_prep_read(sqe, fd, buf, <unsigned int>self.pool.slot_size, 0)
        sqe.user_data = <uint64_t>slot_idx

        cdef io_uring_cqe *cqe = NULL
        cdef int ret
        with nogil:
            ret = io_uring_submit_and_wait(&self.ring, 1)
        if ret < 0:
            slab_free(self.pool, slot_idx)
            raise OSError(-ret, "io_uring_submit_and_wait failed")

        ret = io_uring_peek_cqe(&self.ring, &cqe)
        if ret < 0 or cqe == NULL:
            slab_free(self.pool, slot_idx)
            return None
        return self._consume(cqe)

    def submit_read_batch_and_wait(self, int fd, int count):
        # Queue `count` reads into the SQ ring, then submit them all and block
        # for every completion in a SINGLE io_uring_enter syscall. This is the
        # amortization epoll cannot express: one syscall drives `count` reads
        # and `count` reaps, instead of a syscall per operation.
        cdef int32_t *slots
        cdef int i
        cdef int prepared = 0
        cdef int reaped = 0
        cdef int ret = 0
        cdef int32_t slot_idx
        cdef void *buf
        cdef io_uring_sqe *sqe
        cdef io_uring_cqe *cqe = NULL

        if count <= 0:
            return []

        slots = <int32_t*>malloc(count * sizeof(int32_t))
        if slots == NULL:
            raise MemoryError("Failed to allocate batch slot table")

        try:
            # Prep phase: on any failure here nothing has been submitted, so we
            # free exactly the slots prepared so far.
            try:
                for i in range(count):
                    buf = slab_alloc(self.pool, &slot_idx)
                    if buf == NULL:
                        raise MemoryError("Slab pool exhausted mid-batch")
                    sqe = io_uring_get_sqe(&self.ring)
                    if sqe == NULL:
                        slab_free(self.pool, slot_idx)
                        raise RuntimeError("Submission queue full mid-batch")
                    io_uring_prep_read(sqe, fd, buf, <unsigned int>self.pool.slot_size, 0)
                    sqe.user_data = <uint64_t>slot_idx
                    slots[prepared] = slot_idx
                    prepared += 1
            except:
                for i in range(prepared):
                    slab_free(self.pool, slots[i])
                raise

            with nogil:
                ret = io_uring_submit_and_wait(&self.ring, count)
            if ret < 0:
                # Kernel accepted no completions; slots are still ours to free.
                for i in range(prepared):
                    slab_free(self.pool, slots[i])
                raise OSError(-ret, "io_uring_submit_and_wait failed")

            # Reap phase: _consume frees each slot as its completion is seen.
            results = []
            while reaped < count:
                ret = io_uring_peek_cqe(&self.ring, &cqe)
                if ret < 0 or cqe == NULL:
                    break
                results.append(self._consume(cqe))
                reaped += 1
            return results
        finally:
            free(slots)

    # --- Server-oriented API (accept / recv / send) --------------------------
    # user_data packs (op, fd, slot): op in bits 56..63, fd in bits 24..55,
    # slot in bits 0..23. This lets a single completion queue multiplex accepts,
    # receives, and sends across many connections without a Python-side map.
    # op codes: 1=ACCEPT, 2=RECV, 3=SEND.

    def submit_accept(self, int listen_fd):
        cdef io_uring_sqe *sqe = io_uring_get_sqe(&self.ring)
        if sqe == NULL:
            raise RuntimeError("Submission queue full")
        io_uring_prep_accept(sqe, listen_fd, NULL, NULL, 0)
        sqe.user_data = (<uint64_t>1 << 56) | ((<uint64_t>(<uint32_t>listen_fd)) << 24)

    def submit_recv(self, int fd):
        cdef int32_t slot_idx = -1
        cdef void *buf = slab_alloc(self.pool, &slot_idx)
        if buf == NULL:
            raise MemoryError("Slab pool exhausted")
        cdef io_uring_sqe *sqe = io_uring_get_sqe(&self.ring)
        if sqe == NULL:
            slab_free(self.pool, slot_idx)
            raise RuntimeError("Submission queue full")
        io_uring_prep_recv(sqe, fd, buf, self.pool.slot_size, 0)
        sqe.user_data = (<uint64_t>2 << 56) | ((<uint64_t>(<uint32_t>fd)) << 24) \
            | (<uint64_t>(slot_idx & 0xFFFFFF))

    def submit_send(self, int fd, bytes payload):
        cdef size_t n = len(payload)
        if n > self.pool.slot_size:
            raise ValueError("Payload exceeds slab slot size")
        cdef int32_t slot_idx = -1
        cdef char *buf = <char*>slab_alloc(self.pool, &slot_idx)
        if buf == NULL:
            raise MemoryError("Slab pool exhausted")
        # Copy the response into a slab slot so it stays valid until completion.
        cdef const unsigned char[:] src = payload
        cdef size_t i
        for i in range(n):
            buf[i] = src[i]
        cdef io_uring_sqe *sqe = io_uring_get_sqe(&self.ring)
        if sqe == NULL:
            slab_free(self.pool, slot_idx)
            raise RuntimeError("Submission queue full")
        io_uring_prep_send(sqe, fd, buf, n, 0)
        sqe.user_data = (<uint64_t>3 << 56) | ((<uint64_t>(<uint32_t>fd)) << 24) \
            | (<uint64_t>(slot_idx & 0xFFFFFF))

    def flush(self):
        cdef int ret = io_uring_submit(&self.ring)
        if ret < 0:
            raise OSError(-ret, "io_uring_submit failed")
        self.stat_submits += 1
        return ret

    def get_stats(self):
        # Completion-batching evidence. completions_per_wait is a conservative
        # lower bound on the amortization factor: each blocking get_*events call
        # issues at most one io_uring_enter (and skips it when completions are
        # already ready), yet reaps this many completions on average.
        #
        # The C reactors (serve_forever_*) additionally count exactly:
        #   enters   : io_uring_enter system calls issued by the loop
        #   requests : responses sent in full
        #   syscalls : enters + close() calls, i.e. every system call the loop
        #              made (for comparison with EpollEngine's count)
        cdef double cpw = 0.0
        cdef double cpe = 0.0
        cdef double spr = 0.0
        cdef unsigned long long syscalls = self.stat_enters + self.stat_closes
        if self.stat_waits > 0:
            cpw = <double>self.stat_completions / <double>self.stat_waits
        if self.stat_enters > 0:
            cpe = <double>self.stat_completions / <double>self.stat_enters
        if self.stat_requests > 0:
            spr = <double>syscalls / <double>self.stat_requests
        return {"waits": self.stat_waits, "completions": self.stat_completions,
                "submits": self.stat_submits, "completions_per_wait": cpw,
                "enters": self.stat_enters, "requests": self.stat_requests,
                "syscalls": syscalls, "completions_per_enter": cpe,
                "syscalls_per_request": spr,
                "handler_calls": self.stat_handler_calls,
                "handler_errors": self.stat_handler_errors,
                "gil_hold_ns": self.stat_gil_hold_ns,
                "gil_wait_ns": self.stat_gil_wait_ns}

    def set_gil_timing(self, bint enabled):
        # serve_forever_app only. When enabled, every request records how long
        # the worker waited to get the GIL (gil_wait_ns) and how long it then
        # held it (gil_hold_ns: building the request bytes, the handler call,
        # copying the response out). Costs three clock reads per request, so it
        # is off by default.
        if self._serving:
            raise RuntimeError("set_gil_timing() cannot be called while serving")
        self._gil_timing = enabled

    def set_max_batch(self, unsigned int n):
        # Ablation knob for the C reactors: process at most `n` completions per
        # io_uring_enter (0 = no limit, the default). n=1 forces one system
        # call per completion, removing syscall amortization while leaving
        # everything else unchanged.
        if self._serving:
            raise RuntimeError("set_max_batch() cannot be called while serving")
        self._max_batch = n

    def _free_slot(self, int slot_idx):
        # Called by SlabView.release() to return a pinned slot to the pool.
        slab_free(self.pool, slot_idx)

    # --- GIL-aware C-side reactors ------------------------------------------
    # Instead of returning per-event Python objects (which force the interpreter
    # -- and the GIL -- onto the hot path of every completion), _serve drives the
    # whole accept/recv/send protocol inside one nogil region.
    #
    #   serve_forever_echo : every request gets the canned set_response() bytes.
    #                        Python is never touched per event, so N worker
    #                        threads scale across cores instead of serialising
    #                        on the GIL.
    #   serve_forever_app  : every request is passed to a Python handler inside a
    #                        `with gil` block. Transport stays in C; only the
    #                        handler call holds the GIL. This is the boundary
    #                        case: per-request Python work re-serialises workers.
    #
    # Both reply once per recv() and do not parse request framing, so pipelined
    # or fragmented requests are not handled. Responses of any size below 16 MiB
    # are sent in full: a short send is resumed from the offset in user_data.

    def set_response(self, bytes response):
        # Canned reply copied once into engine-owned C memory. The nogil loop
        # sends straight from this buffer, so it must not change while serving.
        cdef size_t n = len(response)
        if self._serving:
            raise RuntimeError("set_response() cannot be called while serving")
        if n == 0 or n > MAX_RESPONSE_LEN:
            raise ValueError("response must be 1..16777215 bytes")
        if self._echo_resp != NULL:
            free(self._echo_resp)
            self._echo_resp = NULL
        self._echo_resp = <char*>malloc(n)
        if self._echo_resp == NULL:
            raise MemoryError("Failed to allocate response buffer")
        cdef const unsigned char[:] src = response
        cdef size_t i
        for i in range(n):
            self._echo_resp[i] = src[i]
        self._echo_resp_len = n

    def stop(self):
        # Cooperative stop; the nogil loop checks this between waits, so it
        # takes effect at the next completion.
        self._stop = 1

    cdef int _ensure_conn(self, int fd) noexcept nogil:
        # Grow the per-connection response table to cover `fd`. 0 on success.
        cdef int new_n, i
        cdef char **nb
        cdef size_t *nc
        cdef size_t *nl
        if fd < 0:
            return -1
        if fd < self._conn_n:
            return 0
        new_n = self._conn_n * 2 if self._conn_n > 0 else 1024
        while new_n <= fd:
            new_n *= 2
        nb = <char**>realloc(self._conn_buf, new_n * sizeof(char*))
        if nb == NULL:
            return -1
        self._conn_buf = nb
        nc = <size_t*>realloc(self._conn_cap, new_n * sizeof(size_t))
        if nc == NULL:
            return -1
        self._conn_cap = nc
        nl = <size_t*>realloc(self._conn_len, new_n * sizeof(size_t))
        if nl == NULL:
            return -1
        self._conn_len = nl
        for i in range(self._conn_n, new_n):
            self._conn_buf[i] = NULL
            self._conn_cap[i] = 0
            self._conn_len[i] = 0
        self._conn_n = new_n
        return 0

    cdef int _run_handler(self, PyObject *handler, int fd, const char *req,
                          int n, unsigned long long t_req) noexcept with gil:
        # Entry point from the nogil loop: acquires the GIL (that is what
        # `with gil` does), runs the handler, releases it on return. `t_req` is
        # the time just before the acquisition was requested, or 0 when timing
        # is off.
        cdef unsigned long long t_in
        cdef int rc
        if t_req == 0:
            return self._handle_locked(handler, fd, req, n)
        t_in = _now_ns()
        self.stat_gil_wait_ns += t_in - t_req
        rc = self._handle_locked(handler, fd, req, n)
        self.stat_gil_hold_ns += _now_ns() - t_in
        return rc

    cdef int _handle_locked(self, PyObject *handler, int fd,
                            const char *req, int n) noexcept:
        # The only GIL-held step of serve_forever_app: build the request bytes,
        # call the handler, and copy its response into this connection's C
        # buffer so the send can proceed with the GIL released. Returns 0 on
        # success, -1 if the connection should be closed.
        cdef char *src = NULL
        cdef Py_ssize_t rlen = 0
        cdef char *nb
        self.stat_handler_calls += 1
        try:
            out = (<object>handler)(PyBytes_FromStringAndSize(req, n))
            if not isinstance(out, bytes):
                raise TypeError("handler must return bytes, got %s"
                                % type(out).__name__)
            PyBytes_AsStringAndSize(out, &src, &rlen)
            if rlen <= 0 or rlen > MAX_RESPONSE_LEN:
                raise ValueError("handler response must be 1..16777215 bytes")
            if self._ensure_conn(fd) < 0:
                raise MemoryError("connection table")
            if <size_t>rlen > self._conn_cap[fd]:
                nb = <char*>realloc(self._conn_buf[fd], rlen)
                if nb == NULL:
                    raise MemoryError("response buffer")
                self._conn_buf[fd] = nb
                self._conn_cap[fd] = rlen
            memcpy(self._conn_buf[fd], src, rlen)
            self._conn_len[fd] = rlen
            return 0
        except Exception:
            # A failing handler closes that connection only. Report the first
            # failure in full and count the rest (see get_stats()).
            self.stat_handler_errors += 1
            if self.stat_handler_errors == 1:
                traceback.print_exc(file=sys.stderr)
            return -1

    cdef int _check_signals(self) noexcept with gil:
        # The wait was interrupted by a signal. Python-level signal handlers
        # only run when the interpreter gets control, so give it control here
        # (this is a no-op off the main thread). Returns 0 to keep serving, -1
        # if a handler raised (e.g. KeyboardInterrupt); _run() re-raises it.
        try:
            PyErr_CheckSignals()
            return 0
        except BaseException as exc:
            self._pending_exc = exc
            return -1

    cdef int _serve(self, int listen_fd, PyObject *handler) noexcept nogil:
        # Shared reactor loop. handler == NULL selects the canned-echo path.
        # Returns 0 after stop() or when a signal handler raised, or a negative
        # errno if the ring failed.
        cdef io_uring_cqe *cqe
        cdef int ret, rc
        cdef uint64_t ud
        cdef int op, fd, res
        cdef size_t low, off, total
        cdef bint timing = self._gil_timing
        cdef unsigned long long t_req
        cdef const char *base
        cdef bint app = handler != NULL
        cdef const char *resp = self._echo_resp
        cdef size_t resp_len = self._echo_resp_len
        cdef size_t slot_size = self.pool.slot_size
        cdef unsigned max_batch = self._max_batch
        cdef unsigned batch
        cdef unsigned long long *enters = &self.stat_enters

        while self._stop == 0:
            # The only system call of an iteration: submits everything queued
            # while draining the previous batch, then waits for >= 1 completion.
            ret = io_uring_submit_and_wait(&self.ring, 1)
            self.stat_enters += 1
            if ret < 0:
                if ret == -EINTR:
                    if self._check_signals() < 0:
                        return 0
                    continue
                return ret
            self.stat_waits += 1
            batch = 0
            while True:
                if max_batch != 0 and batch >= max_batch:
                    break  # batch cap reached: go back through io_uring_enter
                ret = io_uring_peek_cqe(&self.ring, &cqe)
                if ret < 0 or cqe == NULL:
                    break
                batch += 1
                ud = cqe.user_data
                op = <int>(ud >> 56)
                fd = <int>((ud >> 24) & <uint64_t>0xFFFFFFFF)
                low = <size_t>(ud & <uint64_t>0xFFFFFF)
                res = cqe.res
                io_uring_cqe_seen(&self.ring, cqe)
                self.stat_completions += 1

                if op == 1:  # ACCEPT: re-arm, then start a recv on the new fd
                    _arm_accept(&self.ring, listen_fd, enters)
                    if res >= 0:
                        _arm_recv(&self.ring, self.pool, res, enters)
                elif op == 2:  # RECV: `low` is the slab slot holding the request
                    if res <= 0:
                        slab_free(self.pool, <int32_t>low)
                        close(fd)
                        self.stat_closes += 1
                    elif app:
                        t_req = 0
                        if timing:
                            t_req = _now_ns()
                        rc = self._run_handler(
                            handler, fd,
                            <const char*>self.pool.raw_memory + low * slot_size,
                            res, t_req)
                        slab_free(self.pool, <int32_t>low)
                        if rc < 0:
                            close(fd)
                            self.stat_closes += 1
                        else:
                            _arm_send(&self.ring, fd, self._conn_buf[fd],
                                      self._conn_len[fd], 0, enters)
                    else:
                        slab_free(self.pool, <int32_t>low)
                        _arm_send(&self.ring, fd, resp, resp_len, 0, enters)
                elif op == 3:  # SEND: `low` is the offset this send started at
                    if res <= 0:
                        close(fd)
                        self.stat_closes += 1
                    else:
                        off = low + <size_t>res
                        if app:
                            base = self._conn_buf[fd]
                            total = self._conn_len[fd]
                        else:
                            base = resp
                            total = resp_len
                        if off < total:   # short send: resume
                            _arm_send(&self.ring, fd, base, total, off, enters)
                        else:             # done: re-arm keep-alive recv
                            self.stat_requests += 1
                            _arm_recv(&self.ring, self.pool, fd, enters)
        return 0

    cdef _run(self, int listen_fd, PyObject *handler):
        cdef int ret
        if self._serving:
            raise RuntimeError("engine is already serving")
        cdef io_uring_sqe *sqe = io_uring_get_sqe(&self.ring)
        if sqe == NULL:
            raise RuntimeError("Submission queue full at startup")
        io_uring_prep_accept(sqe, listen_fd, NULL, NULL, 0)
        sqe.user_data = (<uint64_t>1 << 56) | ((<uint64_t>(<uint32_t>listen_fd)) << 24)
        io_uring_submit(&self.ring)

        self._serving = 1
        try:
            with nogil:
                ret = self._serve(listen_fd, handler)
        finally:
            self._serving = 0
        if self._pending_exc is not None:
            exc = self._pending_exc
            self._pending_exc = None
            raise exc
        if ret < 0:
            raise OSError(-ret, "io_uring_submit_and_wait failed")

    def serve_forever_echo(self, int listen_fd):
        # Serve the set_response() bytes to every request, entirely in C.
        if self._echo_resp == NULL:
            raise RuntimeError("call set_response() before serve_forever_echo()")
        self._run(listen_fd, NULL)

    def serve_forever_app(self, int listen_fd, handler):
        # Serve handler(request_bytes) -> response_bytes. Accept/recv/send run
        # in C with the GIL released; only the handler call itself holds it.
        if not callable(handler):
            raise TypeError("handler must be callable")
        # `handler` is kept alive by this frame for the whole serve call.
        self._run(listen_fd, <PyObject*>handler)

    def get_events(self, int max_events=256, bint wait=True, bint copy_data=True,
                   bint as_view=False):
        # Drain up to max_events completions. If wait and none are ready, block
        # in-kernel for at least one (epoll_wait-style). Returns a list of
        # (op, fd, res, data) where data is the received payload for RECV else None.
        # copy_data=False skips the RECV bytes allocation (slot is still freed)
        # for servers that ignore the request body — a true zero-copy fast path.
        # as_view=True instead returns a SlabView (buffer-protocol memoryview
        # source) that owns the slot until released — zero-copy WITH data access.
        cdef io_uring_cqe *cqe = NULL
        cdef int ret
        cdef list events = []
        cdef int drained = 0

        if wait:
            with nogil:
                ret = io_uring_wait_cqe(&self.ring, &cqe)
            if ret < 0:
                raise OSError(-ret, "io_uring_wait_cqe failed")
            if cqe != NULL:
                events.append(self._decode_event(cqe, copy_data, as_view))
                io_uring_cqe_seen(&self.ring, cqe)
                drained += 1

        while drained < max_events:
            ret = io_uring_peek_cqe(&self.ring, &cqe)
            if ret < 0 or cqe == NULL:
                break
            events.append(self._decode_event(cqe, copy_data, as_view))
            io_uring_cqe_seen(&self.ring, cqe)
            drained += 1
        if wait:
            self.stat_waits += 1
            self.stat_completions += drained
        return events

    cdef object _decode_event(self, io_uring_cqe *cqe, bint copy_data, bint as_view):
        cdef uint64_t ud = cqe.user_data
        cdef int op = <int>(ud >> 56)
        cdef int fd = <int>((ud >> 24) & 0xFFFFFFFF)
        cdef int32_t slot_idx = <int32_t>(ud & 0xFFFFFF)
        cdef int res = cqe.res
        cdef bytes data = None
        cdef unsigned long long addr
        if op == 2:  # RECV
            if res > 0 and as_view:
                # Transfer slot ownership to the view; do NOT free here.
                addr = <unsigned long long><uintptr_t>(
                    <char*>self.pool.raw_memory + (slot_idx * self.pool.slot_size))
                return (op, fd, res, SlabView(self, addr, res, slot_idx))
            if res > 0 and copy_data:
                data = (<char*>self.pool.raw_memory + (slot_idx * self.pool.slot_size))[:res]
            slab_free(self.pool, slot_idx)
        elif op == 3:  # SEND: response buffer no longer needed
            slab_free(self.pool, slot_idx)
        return (op, fd, res, data)

    # --- Provided buffer rings + multishot receive ---------------------------
    # The kernel selects a buffer from a pre-registered ring on each recv, so one
    # multishot submission yields many completions, each tagged with the chosen
    # buffer id. The ring is a genuine kernel-producer / user-consumer structure.

    def setup_provided_buffers(self, unsigned nentries, unsigned buf_size, int bgid=1):
        # nentries must be a power of two. Allocates the backing region and
        # publishes every buffer into the ring.
        if nentries == 0 or (nentries & (nentries - 1)) != 0:
            raise ValueError("nentries must be a power of two")
        cdef int ret = 0
        self.buf_ring = io_uring_setup_buf_ring(&self.ring, nentries, bgid, 0, &ret)
        if self.buf_ring == NULL:
            raise OSError(-ret if ret < 0 else 1, "io_uring_setup_buf_ring failed")

        cdef size_t total = <size_t>nentries * buf_size
        self.buf_base = malloc(total)
        if self.buf_base == NULL:
            io_uring_free_buf_ring(&self.ring, self.buf_ring, nentries, bgid)
            self.buf_ring = NULL
            raise MemoryError("Failed to allocate provided-buffer region")

        self.buf_count = nentries
        self.buf_size = buf_size
        self.buf_gid = bgid
        self.buf_mask = io_uring_buf_ring_mask(nentries)

        cdef unsigned i
        for i in range(nentries):
            io_uring_buf_ring_add(self.buf_ring,
                                  <char*>self.buf_base + <size_t>i * buf_size,
                                  buf_size, <unsigned short>i, self.buf_mask, <int>i)
        io_uring_buf_ring_advance(self.buf_ring, <int>nentries)

    def arm_multishot_recv(self, int fd):
        if self.buf_ring == NULL:
            raise RuntimeError("call setup_provided_buffers() first")
        cdef io_uring_sqe *sqe = io_uring_get_sqe(&self.ring)
        if sqe == NULL:
            raise RuntimeError("Submission queue full")
        io_uring_prep_recv_multishot(sqe, fd, NULL, 0, 0)
        sqe.flags = sqe.flags | <uint8_t>IOSQE_BUFFER_SELECT
        sqe.buf_group = <uint16_t>self.buf_gid
        sqe.user_data = (<uint64_t>2 << 56) | ((<uint64_t>(<uint32_t>fd)) << 24)
        io_uring_submit(&self.ring)

    def get_buf_events(self, int max_events=256, bint wait=True, bint copy_data=True):
        # Returns list of (fd, res, data, more). data is the received bytes when
        # copy_data else None; more indicates the multishot recv is still armed.
        # Each consumed buffer is recycled back into the ring.
        cdef io_uring_cqe *cqe = NULL
        cdef int ret
        cdef list events = []
        cdef int drained = 0

        if wait:
            with nogil:
                ret = io_uring_wait_cqe(&self.ring, &cqe)
            if ret < 0:
                raise OSError(-ret, "io_uring_wait_cqe failed")
            if cqe != NULL:
                events.append(self._decode_buf_event(cqe, copy_data))
                io_uring_cqe_seen(&self.ring, cqe)
                drained += 1

        while drained < max_events:
            ret = io_uring_peek_cqe(&self.ring, &cqe)
            if ret < 0 or cqe == NULL:
                break
            events.append(self._decode_buf_event(cqe, copy_data))
            io_uring_cqe_seen(&self.ring, cqe)
            drained += 1
        return events

    cdef object _decode_buf_event(self, io_uring_cqe *cqe, bint copy_data):
        cdef uint64_t ud = cqe.user_data
        cdef int fd = <int>((ud >> 24) & 0xFFFFFFFF)
        cdef int res = cqe.res
        cdef uint32_t flags = cqe.flags
        cdef bint more = (flags & <uint32_t>IORING_CQE_F_MORE) != 0
        cdef bytes data = None
        cdef unsigned bid
        cdef char *addr
        if (flags & <uint32_t>IORING_CQE_F_BUFFER) != 0 and res > 0:
            bid = flags >> <uint32_t>IORING_CQE_BUFFER_SHIFT
            addr = <char*>self.buf_base + <size_t>bid * self.buf_size
            if copy_data:
                data = addr[:res]
            # Recycle the buffer back into the ring for kernel reuse.
            io_uring_buf_ring_add(self.buf_ring, addr, self.buf_size,
                                  <unsigned short>bid, self.buf_mask, 0)
            io_uring_buf_ring_advance(self.buf_ring, 1)
        return (fd, res, data, more)

    def get_server_events(self, int max_events=1024, bint wait=True, bint copy_data=False):
        # Unified drain for a multishot + provided-buffer server: decodes accept,
        # multishot-recv (with kernel buffer selection + recycle), and send
        # completions from one queue. Returns (op, fd, res, data, more).
        cdef io_uring_cqe *cqe = NULL
        cdef int ret
        cdef list events = []
        cdef int drained = 0

        if wait:
            with nogil:
                ret = io_uring_wait_cqe(&self.ring, &cqe)
            if ret < 0:
                raise OSError(-ret, "io_uring_wait_cqe failed")
            if cqe != NULL:
                events.append(self._decode_server_event(cqe, copy_data))
                io_uring_cqe_seen(&self.ring, cqe)
                drained += 1

        while drained < max_events:
            ret = io_uring_peek_cqe(&self.ring, &cqe)
            if ret < 0 or cqe == NULL:
                break
            events.append(self._decode_server_event(cqe, copy_data))
            io_uring_cqe_seen(&self.ring, cqe)
            drained += 1
        if wait:
            self.stat_waits += 1
            self.stat_completions += drained
        return events

    cdef object _decode_server_event(self, io_uring_cqe *cqe, bint copy_data):
        cdef uint64_t ud = cqe.user_data
        cdef int op = <int>(ud >> 56)
        cdef int fd = <int>((ud >> 24) & 0xFFFFFFFF)
        cdef int32_t slot_idx = <int32_t>(ud & 0xFFFFFF)
        cdef int res = cqe.res
        cdef uint32_t flags = cqe.flags
        cdef bint more = (flags & <uint32_t>IORING_CQE_F_MORE) != 0
        cdef bytes data = None
        cdef unsigned bid
        cdef char *addr
        if op == 2:  # multishot RECV with kernel-selected buffer
            if (flags & <uint32_t>IORING_CQE_F_BUFFER) != 0 and res > 0:
                bid = flags >> <uint32_t>IORING_CQE_BUFFER_SHIFT
                addr = <char*>self.buf_base + <size_t>bid * self.buf_size
                if copy_data:
                    data = addr[:res]
                io_uring_buf_ring_add(self.buf_ring, addr, self.buf_size,
                                      <unsigned short>bid, self.buf_mask, 0)
                io_uring_buf_ring_advance(self.buf_ring, 1)
            return (op, fd, res, data, more)
        elif op == 3:  # SEND: release the slab slot used for the response
            slab_free(self.pool, slot_idx)
            return (op, fd, res, None, False)
        # ACCEPT (op == 1) or anything else
        return (op, fd, res, None, False)
