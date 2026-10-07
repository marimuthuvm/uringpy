# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: freethreading_compatible=True
"""Readiness-based twins of URingEngine's C reactor, for ablation.

EpollEngine runs the same loop as URingEngine's reactor on epoll: readiness
notification plus one recv() and one send() system call per request, instead
of io_uring's batched submission and completion. Like the io_uring reactor it
has two entry points, both inside one `nogil` region:

    serve_forever_echo(listen_fd)          a fixed response, no Python at all
    serve_forever_app(listen_fd, handler)  a Python handler per request, with
                                           the GIL taken once per request or,
                                           after set_gil_batching(True), once
                                           for all requests found in one pass
                                           over the ready list

Comparing an EpollEngine entry point with the URingEngine one of the same name
changes the kernel interface and nothing else. In particular the handler
variant shows whether taking the GIL once per batch of requests depends on
io_uring at all: an epoll_wait() result is a batch too.

BatchIO is a helper for a loop written in Python: it does the recv() and
send() of every socket queued to it inside one GIL release. A Python epoll
loop built on it makes the same two system calls per request as a plain one,
but gives up the GIL twice per pass over the ready list instead of twice per
request.

These are measurement baselines, not a second product.
"""

import sys
import traceback
from libc.stdlib cimport malloc, free, realloc
from libc.string cimport memcpy
from libc.stdint cimport uint32_t, uint64_t
from libc.errno cimport errno, EINTR, EAGAIN
from cpython.ref cimport PyObject
from cpython.exc cimport PyErr_CheckSignals
from cpython.bytes cimport PyBytes_FromStringAndSize, PyBytes_AsStringAndSize
from posix.time cimport clock_gettime, timespec, CLOCK_MONOTONIC

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
    # Requests collected before the GIL is taken once for all of them. One
    # epoll_wait() returns at most MAX_EVENTS events, so a pass always fits.
    PEND_CAP = 1024


cdef inline unsigned long long _now_ns() noexcept nogil:
    cdef timespec ts
    clock_gettime(CLOCK_MONOTONIC, &ts)
    return <unsigned long long>ts.tv_sec * 1000000000ULL + <unsigned long long>ts.tv_nsec


cdef class EpollEngine:
    cdef int ep
    cdef char *_resp
    cdef size_t _resp_len
    cdef char *_rbuf
    cdef int _stop
    cdef int _serving
    cdef object _pending_exc
    # Per-connection state, indexed by fd: bytes of the current response
    # already sent, whether the fd is currently registered for EPOLLOUT, and
    # (handler mode) the response the handler returned for it.
    cdef size_t *_off
    cdef unsigned char *_wout
    cdef char **_conn_buf
    cdef size_t *_conn_cap
    cdef size_t *_conn_len
    cdef int _conn_n
    cdef unsigned long long stat_waits
    cdef unsigned long long stat_events
    cdef unsigned long long stat_requests
    cdef unsigned long long stat_syscalls
    # Handler mode.
    cdef bint _gil_timing
    cdef bint _gil_batch
    cdef int _pend_cap
    cdef char *_bat_buf       # PEND_CAP receive buffers, one per pending request
    cdef int *_pend_fd
    cdef int *_pend_len       # request length; after the handlers ran, 0 or -1
    cdef int _pend_n
    cdef unsigned long long stat_handler_calls
    cdef unsigned long long stat_handler_errors
    cdef unsigned long long stat_gil_hold_ns
    cdef unsigned long long stat_gil_wait_ns
    cdef unsigned long long stat_gil_acquires

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
        self._conn_buf = NULL
        self._conn_cap = NULL
        self._conn_len = NULL
        self._conn_n = 0
        self.stat_waits = 0
        self.stat_events = 0
        self.stat_requests = 0
        self.stat_syscalls = 0
        self._gil_timing = False
        self._gil_batch = False
        self._pend_cap = PEND_CAP
        self._bat_buf = NULL
        self._pend_fd = NULL
        self._pend_len = NULL
        self._pend_n = 0
        self.stat_handler_calls = 0
        self.stat_handler_errors = 0
        self.stat_gil_hold_ns = 0
        self.stat_gil_wait_ns = 0
        self.stat_gil_acquires = 0
        self._rbuf = <char*>malloc(RECV_BUF)
        if self._rbuf == NULL:
            raise MemoryError("Failed to allocate receive buffer")
        self.ep = epoll_create1(EPOLL_CLOEXEC)
        if self.ep < 0:
            raise OSError(errno, "epoll_create1 failed")

    def __dealloc__(self):
        cdef int i
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
        if self._conn_buf != NULL:
            for i in range(self._conn_n):
                if self._conn_buf[i] != NULL:
                    free(self._conn_buf[i])
            free(self._conn_buf)
        if self._conn_cap != NULL:
            free(self._conn_cap)
        if self._conn_len != NULL:
            free(self._conn_len)
        if self._bat_buf != NULL:
            free(self._bat_buf)
        if self._pend_fd != NULL:
            free(self._pend_fd)
        if self._pend_len != NULL:
            free(self._pend_len)

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

    def set_gil_timing(self, bint enabled):
        # serve_forever_app only: record, per handler call, how long the worker
        # waited for the GIL and how long it held it (see URingEngine).
        if self._serving:
            raise RuntimeError("set_gil_timing() cannot be called while serving")
        self._gil_timing = enabled

    def set_gil_batching(self, bint enabled, unsigned int max_requests=0):
        # serve_forever_app only: take the GIL once for all requests found in
        # one pass over the ready list, instead of once per request. Same
        # contract as URingEngine.set_gil_batching().
        if self._serving:
            raise RuntimeError("set_gil_batching() cannot be called while serving")
        if enabled and self._bat_buf == NULL:
            self._bat_buf = <char*>malloc(<size_t>PEND_CAP * RECV_BUF)
            self._pend_fd = <int*>malloc(PEND_CAP * sizeof(int))
            self._pend_len = <int*>malloc(PEND_CAP * sizeof(int))
            if self._bat_buf == NULL or self._pend_fd == NULL or self._pend_len == NULL:
                raise MemoryError("Failed to allocate the request batch")
        self._pend_cap = PEND_CAP if max_requests == 0 or max_requests > PEND_CAP else <int>max_requests
        self._gil_batch = enabled

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
                "events_per_wait": epw, "syscalls_per_request": spr,
                "handler_calls": self.stat_handler_calls,
                "handler_errors": self.stat_handler_errors,
                "gil_hold_ns": self.stat_gil_hold_ns,
                "gil_wait_ns": self.stat_gil_wait_ns,
                "gil_acquires": self.stat_gil_acquires}

    cdef int _ensure_conn(self, int fd) noexcept nogil:
        cdef int new_n, i
        cdef size_t *no
        cdef unsigned char *nw
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
        no = <size_t*>realloc(self._off, new_n * sizeof(size_t))
        if no == NULL:
            return -1
        self._off = no
        nw = <unsigned char*>realloc(self._wout, new_n)
        if nw == NULL:
            return -1
        self._wout = nw
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
            self._off[i] = 0
            self._wout[i] = 0
            self._conn_buf[i] = NULL
            self._conn_cap[i] = 0
            self._conn_len[i] = 0
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

    cdef void _send_some(self, int fd, const char *base, size_t total) noexcept nogil:
        # Send as much of the response as the socket takes. If it is not all
        # gone, wait for EPOLLOUT and resume; once it is, go back to EPOLLIN.
        cdef epoll_event ev
        cdef size_t off = self._off[fd]
        cdef ssize_t s = send(fd, base + off, total - off, MSG_NOSIGNAL)
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
        if off >= total:
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
            # A failing handler closes that connection only.
            self.stat_handler_errors += 1
            if self.stat_handler_errors == 1:
                traceback.print_exc(file=sys.stderr)
            return -1
        except BaseException as exc:
            # KeyboardInterrupt, SystemExit: stop the reactor and let
            # serve_forever_app() re-raise (see URingEngine._handle_locked).
            if self._pending_exc is None:
                self._pending_exc = exc
            self._stop = 1
            return -1

    cdef int _run_handler(self, PyObject *handler, int fd, const char *req,
                          int n, unsigned long long t_req) noexcept with gil:
        # One GIL acquisition for one request. t_req is the time just before
        # the acquisition was requested, or 0 when timing is off.
        cdef unsigned long long t_in
        cdef int rc
        self.stat_gil_acquires += 1
        if t_req == 0:
            return self._handle_locked(handler, fd, req, n)
        t_in = _now_ns()
        self.stat_gil_wait_ns += t_in - t_req
        rc = self._handle_locked(handler, fd, req, n)
        self.stat_gil_hold_ns += _now_ns() - t_in
        return rc

    cdef int _run_batch(self, PyObject *handler, int count,
                        unsigned long long t_req) noexcept with gil:
        # One GIL acquisition for `count` pending requests. Each request's
        # result (0 or -1) replaces its length in _pend_len.
        cdef int i
        cdef unsigned long long t_in = 0
        self.stat_gil_acquires += 1
        if t_req != 0:
            t_in = _now_ns()
            self.stat_gil_wait_ns += t_in - t_req
        for i in range(count):
            if self._stop:
                self._pend_len[i] = -1
                continue
            self._pend_len[i] = self._handle_locked(
                handler, self._pend_fd[i],
                self._bat_buf + <size_t>i * RECV_BUF, self._pend_len[i])
        if t_req != 0:
            self.stat_gil_hold_ns += _now_ns() - t_in
        return 0

    cdef void _flush_pending(self, PyObject *handler, bint timing) noexcept nogil:
        # Run the handlers of the collected requests under one GIL acquisition,
        # then, with the GIL released again, send the responses.
        cdef int i, fd
        cdef int count = self._pend_n
        cdef unsigned long long t_req = 0
        if count == 0:
            return
        if timing:
            t_req = _now_ns()
        self._run_batch(handler, count, t_req)
        for i in range(count):
            fd = self._pend_fd[i]
            if self._pend_len[i] < 0:
                close(fd)
                self.stat_syscalls += 1
            else:
                self._off[fd] = 0
                self._send_some(fd, self._conn_buf[fd], self._conn_len[fd])
        self._pend_n = 0

    cdef int _serve(self, int listen_fd, PyObject *handler) noexcept nogil:
        # Shared loop. handler == NULL selects the fixed-response path.
        cdef epoll_event evs[MAX_EVENTS]
        cdef epoll_event ev
        cdef int n, i, fd, c, rc
        cdef uint32_t what
        cdef ssize_t r
        cdef bint app = handler != NULL
        cdef bint gil_batch = app and self._gil_batch
        cdef bint timing = self._gil_timing
        cdef unsigned long long t_req
        cdef char *buf

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
                if self._stop != 0:
                    break
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
                elif what & EPOLLOUT:  # resuming a short send
                    if app:
                        self._send_some(fd, self._conn_buf[fd], self._conn_len[fd])
                    else:
                        self._send_some(fd, self._resp, self._resp_len)
                else:  # readable, hung up, or in error: recv() tells us which
                    buf = self._rbuf
                    if gil_batch:
                        buf = self._bat_buf + <size_t>self._pend_n * RECV_BUF
                    r = recv(fd, buf, RECV_BUF, 0)
                    self.stat_syscalls += 1
                    if r <= 0:
                        if r < 0 and errno == EAGAIN:
                            continue
                        close(fd)  # also removes it from the epoll set
                        self.stat_syscalls += 1
                    elif not app:
                        self._off[fd] = 0
                        self._send_some(fd, self._resp, self._resp_len)
                    elif gil_batch:
                        # Defer: the handler runs with the rest of this pass.
                        self._pend_fd[self._pend_n] = fd
                        self._pend_len[self._pend_n] = <int>r
                        self._pend_n += 1
                        if self._pend_n >= self._pend_cap:
                            self._flush_pending(handler, timing)
                    else:
                        t_req = 0
                        if timing:
                            t_req = _now_ns()
                        rc = self._run_handler(handler, fd, buf, <int>r, t_req)
                        if rc < 0:
                            close(fd)
                            self.stat_syscalls += 1
                        else:
                            self._off[fd] = 0
                            self._send_some(fd, self._conn_buf[fd], self._conn_len[fd])
            if gil_batch:
                self._flush_pending(handler, timing)
        return 0

    cdef _run(self, int listen_fd, PyObject *handler):
        # Note: puts `listen_fd` into non-blocking mode.
        cdef int ret, fl
        if self._serving:
            raise RuntimeError("engine is already serving")
        fl = fcntl(listen_fd, F_GETFL, 0)
        if fl < 0 or fcntl(listen_fd, F_SETFL, fl | O_NONBLOCK) < 0:
            raise OSError(errno, "fcntl(O_NONBLOCK) failed on the listener")
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
            raise OSError(-ret, "epoll reactor failed")

    def serve_forever_echo(self, int listen_fd):
        # Serve the set_response() bytes to every request, entirely in C.
        if self._resp == NULL:
            raise RuntimeError("call set_response() before serve_forever_echo()")
        self._run(listen_fd, NULL)

    def serve_forever_app(self, int listen_fd, handler):
        # Serve handler(request_bytes) -> response_bytes. accept/recv/send run
        # in C with the GIL released; only the handler call itself holds it
        # (once per request, or once per pass after set_gil_batching(True)).
        if not callable(handler):
            raise TypeError("handler must be callable")
        self._run(listen_fd, <PyObject*>handler)


cdef class BatchIO:
    """recv() + send() for many sockets inside one GIL release.

    For a readiness loop written in Python: queue(fd) each socket the loop
    found readable (no system call, GIL held), then run() once. run() releases
    the GIL, and for every queued socket reads a request and sends the
    set_response() bytes, exactly one recv() and one send() each. Sockets must
    be non-blocking. A socket whose peer has closed is closed here, which also
    removes it from any epoll set. As with the other Python-loop baselines the
    response goes out in a single send(), so it is for small responses only.
    """
    cdef char *_resp
    cdef size_t _resp_len
    cdef char *_rbuf
    cdef int *_fds
    cdef int _n
    cdef int _cap
    cdef unsigned long long stat_requests
    cdef unsigned long long stat_syscalls
    cdef unsigned long long stat_runs

    def __cinit__(self):
        self._resp = NULL
        self._resp_len = 0
        self._n = 0
        self._cap = 1024
        self.stat_requests = 0
        self.stat_syscalls = 0
        self.stat_runs = 0
        self._rbuf = <char*>malloc(RECV_BUF)
        self._fds = <int*>malloc(self._cap * sizeof(int))
        if self._rbuf == NULL or self._fds == NULL:
            raise MemoryError("Failed to allocate BatchIO buffers")

    def __dealloc__(self):
        if self._resp != NULL:
            free(self._resp)
        if self._rbuf != NULL:
            free(self._rbuf)
        if self._fds != NULL:
            free(self._fds)

    def set_response(self, bytes response):
        cdef size_t n = len(response)
        if n == 0 or n > MAX_RESPONSE_LEN:
            raise ValueError("response must be 1..16777215 bytes")
        if self._resp != NULL:
            free(self._resp)
            self._resp = NULL
        self._resp = <char*>malloc(n)
        if self._resp == NULL:
            raise MemoryError("Failed to allocate response buffer")
        memcpy(self._resp, <const char*>response, n)
        self._resp_len = n

    def queue(self, int fd):
        cdef int *nf
        if self._n == self._cap:
            nf = <int*>realloc(self._fds, self._cap * 2 * sizeof(int))
            if nf == NULL:
                raise MemoryError("BatchIO queue")
            self._fds = nf
            self._cap *= 2
        self._fds[self._n] = fd
        self._n += 1

    def run(self):
        # Returns the number of requests answered.
        cdef int i, fd
        cdef int n = self._n
        cdef unsigned long long done = 0
        cdef unsigned long long calls = 0
        cdef ssize_t r
        if self._resp == NULL:
            raise RuntimeError("call set_response() before run()")
        with nogil:
            for i in range(n):
                fd = self._fds[i]
                r = recv(fd, self._rbuf, RECV_BUF, 0)
                calls += 1
                if r <= 0:
                    if r < 0 and errno == EAGAIN:
                        continue
                    close(fd)
                    calls += 1
                else:
                    send(fd, self._resp, self._resp_len, MSG_NOSIGNAL)
                    calls += 1
                    done += 1
        self._n = 0
        self.stat_requests += done
        self.stat_syscalls += calls
        self.stat_runs += 1
        return done

    def get_stats(self):
        # runs is the number of GIL releases made by this object.
        return {"requests": self.stat_requests, "syscalls": self.stat_syscalls,
                "runs": self.stat_runs}
