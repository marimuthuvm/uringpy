# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: freethreading_compatible=True
"""Readiness-based twin of URingEngine's C reactor, for ablation.

EpollEngine.serve_forever_echo() serves the same canned response with the same
protocol behaviour as URingEngine.serve_forever_echo() -- one reply per recv(),
keep-alive, short sends resumed -- and likewise runs its whole loop in one
`nogil` region. The only thing that differs is the kernel interface: epoll
readiness plus one recv() and one send() system call per request, instead of
io_uring's batched submission and completion.

Comparing the two therefore isolates the system-call interface while holding
"C, GIL released" constant; comparing either against a Python-dispatch loop on
the same interface isolates the interpreter. It is a measurement baseline, not
a second product: there is no application-handler variant.
"""

import sys
from libc.stdlib cimport malloc, free, realloc
from libc.stdint cimport uint32_t, uint64_t
from libc.errno cimport errno, EINTR, EAGAIN
from cpython.exc cimport PyErr_CheckSignals

cdef extern from "sys/epoll.h" nogil:
    enum: EPOLLIN
    enum: EPOLLOUT
    enum: EPOLL_CTL_ADD
    enum: EPOLL_CTL_MOD
    enum: EPOLL_CLOEXEC
    ctypedef union epoll_data_t:
        void *ptr
        int fd
        uint32_t u32
        uint64_t u64
    struct epoll_event:
        uint32_t events
        epoll_data_t data
    int epoll_create1(int flags)
    int epoll_ctl(int epfd, int op, int fd, epoll_event *event)
    int epoll_wait(int epfd, epoll_event *events, int maxevents, int timeout)

cdef extern from "sys/socket.h" nogil:
    enum: SOCK_NONBLOCK
    enum: MSG_NOSIGNAL
    ssize_t recv(int sockfd, void *buf, size_t length, int flags)
    ssize_t send(int sockfd, const void *buf, size_t length, int flags)
    int accept4(int sockfd, void *addr, void *addrlen, int flags)

cdef extern from "fcntl.h" nogil:
    enum: F_GETFL
    enum: F_SETFL
    enum: O_NONBLOCK
    int fcntl(int fd, int cmd, ...)

cdef extern from "unistd.h" nogil:
    int close(int fd)

cdef enum:
    MAX_EVENTS = 1024
    RECV_BUF = 4096          # same size as the io_uring reactor's recv slot
    MAX_RESPONSE_LEN = 0xFFFFFF


cdef class EpollEngine:
    cdef int ep
    cdef char *_resp
    cdef size_t _resp_len
    cdef char *_rbuf
    cdef int _stop
    cdef int _serving
    cdef object _pending_exc
    # Per-connection send state, indexed by fd: bytes of the current response
    # already sent, and whether the fd is currently registered for EPOLLOUT.
    cdef size_t *_off
    cdef unsigned char *_wout
    cdef int _conn_n
    cdef unsigned long long stat_waits
    cdef unsigned long long stat_events
    cdef unsigned long long stat_requests
    cdef unsigned long long stat_syscalls

    def __cinit__(self):
        self.ep = -1
        self._resp = NULL
        self._resp_len = 0
        self._rbuf = NULL
        self._stop = 0
        self._serving = 0
        self._pending_exc = None
        self._off = NULL
        self._wout = NULL
        self._conn_n = 0
        self.stat_waits = 0
        self.stat_events = 0
        self.stat_requests = 0
        self.stat_syscalls = 0
        self._rbuf = <char*>malloc(RECV_BUF)
        if self._rbuf == NULL:
            raise MemoryError("Failed to allocate receive buffer")
        self.ep = epoll_create1(EPOLL_CLOEXEC)
        if self.ep < 0:
            raise OSError(errno, "epoll_create1 failed")

    def __dealloc__(self):
        if self.ep >= 0:
            close(self.ep)
        if self._resp != NULL:
            free(self._resp)
        if self._rbuf != NULL:
            free(self._rbuf)
        if self._off != NULL:
            free(self._off)
        if self._wout != NULL:
            free(self._wout)

    def set_response(self, bytes response):
        cdef size_t n = len(response)
        if self._serving:
            raise RuntimeError("set_response() cannot be called while serving")
        if n == 0 or n > MAX_RESPONSE_LEN:
            raise ValueError("response must be 1..16777215 bytes")
        if self._resp != NULL:
            free(self._resp)
            self._resp = NULL
        self._resp = <char*>malloc(n)
        if self._resp == NULL:
            raise MemoryError("Failed to allocate response buffer")
        cdef const unsigned char[:] src = response
        cdef size_t i
        for i in range(n):
            self._resp[i] = src[i]
        self._resp_len = n

    def stop(self):
        # Cooperative stop; takes effect at the next event.
        self._stop = 1

    def get_stats(self):
        # syscalls counts every system call the loop made: epoll_wait,
        # accept4, epoll_ctl, recv, send and close.
        cdef double epw = 0.0
        cdef double spr = 0.0
        if self.stat_waits > 0:
            epw = <double>self.stat_events / <double>self.stat_waits
        if self.stat_requests > 0:
            spr = <double>self.stat_syscalls / <double>self.stat_requests
        return {"waits": self.stat_waits, "events": self.stat_events,
                "requests": self.stat_requests, "syscalls": self.stat_syscalls,
                "events_per_wait": epw, "syscalls_per_request": spr}

    cdef int _ensure_conn(self, int fd) noexcept nogil:
        cdef int new_n, i
        cdef size_t *no
        cdef unsigned char *nw
        if fd < 0:
            return -1
        if fd < self._conn_n:
            return 0
        new_n = self._conn_n * 2 if self._conn_n > 0 else 1024
        while new_n <= fd:
            new_n *= 2
        no = <size_t*>realloc(self._off, new_n * sizeof(size_t))
        if no == NULL:
            return -1
        self._off = no
        nw = <unsigned char*>realloc(self._wout, new_n)
        if nw == NULL:
            return -1
        self._wout = nw
        for i in range(self._conn_n, new_n):
            self._off[i] = 0
            self._wout[i] = 0
        self._conn_n = new_n
        return 0

    cdef int _check_signals(self) noexcept with gil:
        # Same contract as URingEngine._check_signals.
        try:
            PyErr_CheckSignals()
            return 0
        except BaseException as exc:
            self._pending_exc = exc
            return -1

    cdef void _send_some(self, int fd) noexcept nogil:
        # Send as much of the response as the socket takes. If it is not all
        # gone, wait for EPOLLOUT and resume; once it is, go back to EPOLLIN.
        cdef epoll_event ev
        cdef size_t off = self._off[fd]
        cdef ssize_t s = send(fd, self._resp + off, self._resp_len - off, MSG_NOSIGNAL)
        self.stat_syscalls += 1
        if s < 0:
            if errno != EAGAIN:
                close(fd)
                self.stat_syscalls += 1
                return
            s = 0
        off += <size_t>s
        ev.data.u64 = 0
        ev.data.fd = fd
        if off >= self._resp_len:
            self._off[fd] = 0
            self.stat_requests += 1
            if self._wout[fd]:
                self._wout[fd] = 0
                ev.events = EPOLLIN
                epoll_ctl(self.ep, EPOLL_CTL_MOD, fd, &ev)
                self.stat_syscalls += 1
        else:
            self._off[fd] = off
            if not self._wout[fd]:
                self._wout[fd] = 1
                ev.events = EPOLLOUT
                epoll_ctl(self.ep, EPOLL_CTL_MOD, fd, &ev)
                self.stat_syscalls += 1

    cdef int _serve(self, int listen_fd) noexcept nogil:
        cdef epoll_event evs[MAX_EVENTS]
        cdef epoll_event ev
        cdef int n, i, fd, c
        cdef uint32_t what
        cdef ssize_t r

        ev.data.u64 = 0
        ev.data.fd = listen_fd
        ev.events = EPOLLIN
        if epoll_ctl(self.ep, EPOLL_CTL_ADD, listen_fd, &ev) < 0:
            return -errno
        self.stat_syscalls += 1

        while self._stop == 0:
            n = epoll_wait(self.ep, evs, MAX_EVENTS, -1)
            self.stat_syscalls += 1
            if n < 0:
                if errno == EINTR:
                    if self._check_signals() < 0:
                        return 0
                    continue
                return -errno
            self.stat_waits += 1
            self.stat_events += <unsigned long long>n
            for i in range(n):
                fd = evs[i].data.fd
                what = evs[i].events
                if fd == listen_fd:
                    while True:  # accept everything that is ready
                        c = accept4(listen_fd, NULL, NULL, SOCK_NONBLOCK)
                        self.stat_syscalls += 1
                        if c < 0:
                            break
                        if self._ensure_conn(c) < 0:
                            close(c)
                            self.stat_syscalls += 1
                            continue
                        self._off[c] = 0
                        self._wout[c] = 0
                        ev.data.u64 = 0
                        ev.data.fd = c
                        ev.events = EPOLLIN
                        epoll_ctl(self.ep, EPOLL_CTL_ADD, c, &ev)
                        self.stat_syscalls += 1
                elif what & EPOLLOUT:
                    self._send_some(fd)  # resuming a short send
                else:  # readable, hung up, or in error: recv() tells us which
                    r = recv(fd, self._rbuf, RECV_BUF, 0)
                    self.stat_syscalls += 1
                    if r <= 0:
                        if r < 0 and errno == EAGAIN:
                            continue
                        close(fd)  # also removes it from the epoll set
                        self.stat_syscalls += 1
                    else:
                        self._off[fd] = 0
                        self._send_some(fd)
        return 0

    def serve_forever_echo(self, int listen_fd):
        # Serve the set_response() bytes to every request, entirely in C.
        # Note: puts `listen_fd` into non-blocking mode.
        cdef int ret, fl
        if self._resp == NULL:
            raise RuntimeError("call set_response() before serve_forever_echo()")
        if self._serving:
            raise RuntimeError("engine is already serving")
        fl = fcntl(listen_fd, F_GETFL, 0)
        if fl < 0 or fcntl(listen_fd, F_SETFL, fl | O_NONBLOCK) < 0:
            raise OSError(errno, "fcntl(O_NONBLOCK) failed on the listener")
        self._serving = 1
        try:
            with nogil:
                ret = self._serve(listen_fd)
        finally:
            self._serving = 0
        if self._pending_exc is not None:
            exc = self._pending_exc
            self._pending_exc = None
            raise exc
        if ret < 0:
            raise OSError(-ret, "epoll reactor failed")
