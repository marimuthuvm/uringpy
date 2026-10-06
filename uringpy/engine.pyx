# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: freethreading_compatible=True

import socket
from libc.stdlib cimport malloc, free
from libc.stdint cimport uint8_t, uint16_t, uint32_t, uint64_t, int32_t, uintptr_t
from libc.string cimport memset
from cpython.buffer cimport PyObject_GetBuffer, PyBuffer_Release, PyBUF_SIMPLE
from cpython.bytes cimport PyBytes_FromStringAndSize


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
        self.initialized = True

    def __dealloc__(self):
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
        cdef double cpw = 0.0
        if self.stat_waits > 0:
            cpw = <double>self.stat_completions / <double>self.stat_waits
        return {"waits": self.stat_waits, "completions": self.stat_completions,
                "submits": self.stat_submits, "completions_per_wait": cpw}

    def _free_slot(self, int slot_idx):
        # Called by SlabView.release() to return a pinned slot to the pool.
        slab_free(self.pool, slot_idx)

    # --- GIL-aware C-side reactor -------------------------------------------
    # The novel path: instead of returning per-event Python objects (which force
    # the interpreter -- and the GIL -- onto the hot path of every completion),
    # serve_forever_echo drives the whole accept/recv/send protocol inside one
    # nogil region. Python is never touched per event, so N worker threads each
    # running this method scale across cores rather than serialising on the GIL.

    def set_response(self, bytes response):
        # Canned reply copied once into engine-owned C memory; the nogil loop
        # memcpys it into a fresh slab slot per send (send needs a live buffer
        # until completion).
        cdef size_t n = len(response)
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
        # Cooperative stop; the nogil loop checks this between waits.
        self._stop = 1

    def serve_forever_echo(self, int listen_fd):
        cdef io_uring_cqe *cqe
        cdef io_uring_sqe *sqe
        cdef int ret
        cdef uint64_t ud
        cdef int op, fd, res
        cdef int32_t slot_idx, new_slot
        cdef void *buf
        cdef char *dst
        cdef size_t j
        cdef char *resp = self._echo_resp
        cdef size_t resp_len = self._echo_resp_len

        if resp == NULL:
            raise RuntimeError("call set_response() before serve_forever_echo()")

        sqe = io_uring_get_sqe(&self.ring)
        if sqe == NULL:
            raise RuntimeError("Submission queue full at startup")
        io_uring_prep_accept(sqe, listen_fd, NULL, NULL, 0)
        sqe.user_data = (<uint64_t>1 << 56) | ((<uint64_t>(<uint32_t>listen_fd)) << 24)
        io_uring_submit(&self.ring)

        with nogil:
            while self._stop == 0:
                ret = io_uring_submit_and_wait(&self.ring, 1)
                if ret < 0:
                    break
                while True:
                    ret = io_uring_peek_cqe(&self.ring, &cqe)
                    if ret < 0 or cqe == NULL:
                        break
                    ud = cqe.user_data
                    op = <int>(ud >> 56)
                    fd = <int>((ud >> 24) & <uint64_t>0xFFFFFFFF)
                    slot_idx = <int32_t>(ud & <uint64_t>0xFFFFFF)
                    res = cqe.res
                    io_uring_cqe_seen(&self.ring, cqe)
                    self.stat_completions += 1

                    if op == 1:  # ACCEPT: re-arm, then start a recv on the new fd
                        sqe = io_uring_get_sqe(&self.ring)
                        if sqe != NULL:
                            io_uring_prep_accept(sqe, listen_fd, NULL, NULL, 0)
                            sqe.user_data = (<uint64_t>1 << 56) \
                                | ((<uint64_t>(<uint32_t>listen_fd)) << 24)
                        if res >= 0:
                            buf = slab_alloc(self.pool, &new_slot)
                            if buf != NULL:
                                sqe = io_uring_get_sqe(&self.ring)
                                if sqe != NULL:
                                    io_uring_prep_recv(sqe, res, buf,
                                                       self.pool.slot_size, 0)
                                    sqe.user_data = (<uint64_t>2 << 56) \
                                        | ((<uint64_t>(<uint32_t>res)) << 24) \
                                        | (<uint64_t>(new_slot & 0xFFFFFF))
                                else:
                                    slab_free(self.pool, new_slot)
                    elif op == 2:  # RECV: free the request slot, send the reply
                        if slot_idx >= 0:
                            slab_free(self.pool, slot_idx)
                        if res <= 0:
                            close(fd)
                        else:
                            buf = slab_alloc(self.pool, &new_slot)
                            if buf != NULL:
                                dst = <char*>buf
                                for j in range(resp_len):
                                    dst[j] = resp[j]
                                sqe = io_uring_get_sqe(&self.ring)
                                if sqe != NULL:
                                    io_uring_prep_send(sqe, fd, buf, resp_len, 0)
                                    sqe.user_data = (<uint64_t>3 << 56) \
                                        | ((<uint64_t>(<uint32_t>fd)) << 24) \
                                        | (<uint64_t>(new_slot & 0xFFFFFF))
                                else:
                                    slab_free(self.pool, new_slot)
                    elif op == 3:  # SEND: free the reply slot, re-arm keep-alive recv
                        if slot_idx >= 0:
                            slab_free(self.pool, slot_idx)
                        if res <= 0:
                            close(fd)
                        else:
                            buf = slab_alloc(self.pool, &new_slot)
                            if buf != NULL:
                                sqe = io_uring_get_sqe(&self.ring)
                                if sqe != NULL:
                                    io_uring_prep_recv(sqe, fd, buf,
                                                       self.pool.slot_size, 0)
                                    sqe.user_data = (<uint64_t>2 << 56) \
                                        | ((<uint64_t>(<uint32_t>fd)) << 24) \
                                        | (<uint64_t>(new_slot & 0xFFFFFF))
                                else:
                                    slab_free(self.pool, new_slot)
                self.stat_waits += 1
                io_uring_submit(&self.ring)

    def serve_forever_app(self, object handler, int listen_fd):
        # Realistic-workload variant: identical reactor, but each RECV crosses
        # into Python (`with gil`) to run `handler(request_bytes) -> response_bytes`
        # -- real per-request application work (parsing, logic). This deliberately
        # reintroduces the interpreter on the hot path, so it measures the BOUNDARY
        # of the C-reaping benefit: how much the advantage shrinks once genuine
        # Python work runs per request. Contrast with serve_forever_echo (all C).
        cdef io_uring_cqe *cqe
        cdef io_uring_sqe *sqe
        cdef int ret
        cdef uint64_t ud
        cdef int op, fd, res
        cdef int32_t slot_idx, new_slot
        cdef void *buf
        cdef char *reqptr
        cdef char *dst
        cdef Py_ssize_t rlen, k
        cdef object pydata, presp
        cdef const unsigned char[:] rview

        if handler is None:
            raise ValueError("serve_forever_app requires a handler")

        sqe = io_uring_get_sqe(&self.ring)
        if sqe == NULL:
            raise RuntimeError("Submission queue full at startup")
        io_uring_prep_accept(sqe, listen_fd, NULL, NULL, 0)
        sqe.user_data = (<uint64_t>1 << 56) | ((<uint64_t>(<uint32_t>listen_fd)) << 24)
        io_uring_submit(&self.ring)

        with nogil:
            while self._stop == 0:
                ret = io_uring_submit_and_wait(&self.ring, 1)
                if ret < 0:
                    break
                while True:
                    ret = io_uring_peek_cqe(&self.ring, &cqe)
                    if ret < 0 or cqe == NULL:
                        break
                    ud = cqe.user_data
                    op = <int>(ud >> 56)
                    fd = <int>((ud >> 24) & <uint64_t>0xFFFFFFFF)
                    slot_idx = <int32_t>(ud & <uint64_t>0xFFFFFF)
                    res = cqe.res
                    io_uring_cqe_seen(&self.ring, cqe)
                    self.stat_completions += 1

                    if op == 1:  # ACCEPT: re-arm, start a recv on the new fd
                        sqe = io_uring_get_sqe(&self.ring)
                        if sqe != NULL:
                            io_uring_prep_accept(sqe, listen_fd, NULL, NULL, 0)
                            sqe.user_data = (<uint64_t>1 << 56) \
                                | ((<uint64_t>(<uint32_t>listen_fd)) << 24)
                        if res >= 0:
                            buf = slab_alloc(self.pool, &new_slot)
                            if buf != NULL:
                                sqe = io_uring_get_sqe(&self.ring)
                                if sqe != NULL:
                                    io_uring_prep_recv(sqe, res, buf,
                                                       self.pool.slot_size, 0)
                                    sqe.user_data = (<uint64_t>2 << 56) \
                                        | ((<uint64_t>(<uint32_t>res)) << 24) \
                                        | (<uint64_t>(new_slot & 0xFFFFFF))
                                else:
                                    slab_free(self.pool, new_slot)
                    elif op == 2:  # RECV: run the Python handler, send its reply
                        if res <= 0:
                            if slot_idx >= 0:
                                slab_free(self.pool, slot_idx)
                            close(fd)
                        else:
                            reqptr = <char*>self.pool.raw_memory \
                                + slot_idx * self.pool.slot_size
                            with gil:
                                pydata = PyBytes_FromStringAndSize(reqptr, res)
                                slab_free(self.pool, slot_idx)
                                try:
                                    presp = handler(pydata)
                                except Exception:
                                    presp = None
                                if presp is None:
                                    close(fd)
                                else:
                                    rview = presp
                                    rlen = rview.shape[0]
                                    buf = slab_alloc(self.pool, &new_slot)
                                    if buf != NULL and rlen <= <Py_ssize_t>self.pool.slot_size:
                                        dst = <char*>buf
                                        for k in range(rlen):
                                            dst[k] = rview[k]
                                        sqe = io_uring_get_sqe(&self.ring)
                                        if sqe != NULL:
                                            io_uring_prep_send(sqe, fd, buf,
                                                               <size_t>rlen, 0)
                                            sqe.user_data = (<uint64_t>3 << 56) \
                                                | ((<uint64_t>(<uint32_t>fd)) << 24) \
                                                | (<uint64_t>(new_slot & 0xFFFFFF))
                                        else:
                                            slab_free(self.pool, new_slot)
                                            close(fd)
                                    elif buf != NULL:
                                        slab_free(self.pool, new_slot)
                                        close(fd)
                                    else:
                                        close(fd)
                    elif op == 3:  # SEND: re-arm keep-alive recv
                        if slot_idx >= 0:
                            slab_free(self.pool, slot_idx)
                        if res <= 0:
                            close(fd)
                        else:
                            buf = slab_alloc(self.pool, &new_slot)
                            if buf != NULL:
                                sqe = io_uring_get_sqe(&self.ring)
                                if sqe != NULL:
                                    io_uring_prep_recv(sqe, fd, buf,
                                                       self.pool.slot_size, 0)
                                    sqe.user_data = (<uint64_t>2 << 56) \
                                        | ((<uint64_t>(<uint32_t>fd)) << 24) \
                                        | (<uint64_t>(new_slot & 0xFFFFFF))
                                else:
                                    slab_free(self.pool, new_slot)
                self.stat_waits += 1
                io_uring_submit(&self.ring)

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
