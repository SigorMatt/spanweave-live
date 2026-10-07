"""Ingest: where the bytes come from (`SPEC.md` §7.1).

The fifth piece, and the first one that touches the outside world. It answers
one question -- **how do the bytes reach the framer?** -- for the two sources
that are files: a growing file followed by path, and stdin read to EOF. Neither
knows what a record is, what a trace is or what a graph is: each hands chunks to
`Framer.push` and hands the `spanweave.Records` that came back to its caller
(`SPEC.md` §1.1, §1.2).

**No clock here, and no sleeping of its own.** `now` and `sleep` are the
caller's callables, with no defaults, exactly as `Completion.now` is
(`SPEC.md` §5.2): this module imports no `time`, and the real `time.monotonic`
and `time.sleep` are bound by R7's CLI. The seam allowlist in `tests/gates.py`
has one entry -- `real.py`, for `time` and `http.server` (`SPEC.md` §8.2) -- and
this file is not it, which is the whole of what the no-default buys here. A tail
driven on a fake clock is a tail a test can state facts about -- "it read the
bytes appended between these two polls" -- which is not a thing a real `sleep`
lets anybody assert.

**No socket here either.** The HTTP endpoint is §7.2 and R6's, behind an
injected listener factory. This module opens files and reads a stream, which is
what `CLAUDE.md` says the receiver may do, and nothing else.

Three things can happen to a file that is not growth, and each is an **event
with a code**, counted, never a silent restart (`SPEC.md` §1.5): the file was
truncated, the path now names a different file, or the path names nothing. The
bytes the framer was still holding when one of those happened are flushed and
reported -- joining the tail of old content to the head of new content would
manufacture a record that was never written.
"""

from __future__ import annotations

import os
import pathlib
import sys
from collections.abc import Callable, Iterator, Mapping
from typing import BinaryIO, Final

from spanweave import Records

from spanweave_live.framing import Framer
from spanweave_live.routing import Event

#: The file is shorter than the offset the tail had reached, so the content it
#: was reading is gone: the tail restarts from 0 (`SPEC.md` §7.1). Reading on at
#: the old offset would be reading the middle of content nobody wrote there.
TRUNCATED: Final = "truncated"

#: The path now names a different file than the open handle -- a rotation. The
#: old handle is drained first, then the tail reopens **by path** at 0.
ROTATED: Final = "rotated"

#: The path names nothing. The open handle is kept and still read, because on a
#: POSIX system a renamed or unlinked file is still the file the tail holds, and
#: the bytes already written to it are still owed to the caller.
VANISHED: Final = "vanished"

#: A rotation was seen and the new path could not be opened. The tail keeps
#: following the old handle and retries; this is reported once per failure to
#: open, not once per poll.
REOPEN_FAILED: Final = "reopen_failed"

#: How much is asked of the stream per read. Not a policy about the content --
#: it bounds one `bytes` object and nothing else, and the framing is the
#: framer's (`SPEC.md` §3).
DEFAULT_CHUNK_BYTES: Final = 65_536

#: A yield that read nothing. Not an absence: it is how an event with no records
#: beside it reaches a caller that only looks between yields (`SPEC.md` §7.1).
_NOTHING = Records(records=(), diagnostics=(), skipped_records=0)

#: What the platform calls the identity of a file: the device and the inode.
#: Read, never defined here -- "the same file" is the operating system's answer
#: and not a policy the receiver invents (`SPEC.md` §7.1).
_Identity = tuple[int, int]


def _identity_of(handle: BinaryIO) -> _Identity:
    stat = os.fstat(handle.fileno())
    return (stat.st_dev, stat.st_ino)


class Tail:
    """One growing file, followed by path, chunk by chunk into one `Framer`.

    Iterating a `Tail` yields one `spanweave.Records` per read -- including a
    read that completed no line, because "nothing arrived" and "nothing was
    completed" are different answers and `Framer.pending_bytes` is where the
    second one is visible. Between reads it calls the caller's `sleep`, so a
    test on a fake clock drives the whole loop and a real tail costs one poll
    per `poll_seconds`.

    It is **iterated once**: the handle, the offset and the framer are this
    tail's state, and a second iteration would resume the first one's stream
    rather than start a new one. One `Tail` per file, as one `Framer` per byte
    stream (`SPEC.md` §3.1).

    Events ride **beside** the yields, as the framer's do and for the same
    reason (`SPEC.md` §3.1): the yielded value is `spanweave.Records` and stays
    that way. `events` is what happened since the previous yield; `counts` is
    the running total per code and is bounded by the number of codes.
    """

    __slots__ = (
        "_chunk_bytes",
        "_counts",
        "_events",
        "_framer",
        "_handle",
        "_identity",
        "_missing",
        "_now",
        "_offset",
        "_opened_at",
        "_poll_seconds",
        "_polls",
        "_reads",
        "_reopen_pending",
        "_sleep",
        "_start",
        "_started",
        "_until",
        "path",
    )

    def __init__(
        self,
        path: str | os.PathLike[str],
        *,
        now: Callable[[], float],
        sleep: Callable[[float], None],
        poll_seconds: float,
        start: int = 0,
        framer: Framer | None = None,
        chunk_bytes: int = DEFAULT_CHUNK_BYTES,
        until: Callable[[], bool] | None = None,
    ) -> None:
        self.path = pathlib.Path(path)
        self._now = now
        self._sleep = sleep
        self._poll_seconds = poll_seconds
        self._start = start
        self._framer = Framer() if framer is None else framer
        self._chunk_bytes = chunk_bytes
        self._until = until
        self._handle: BinaryIO | None = None
        self._identity: _Identity | None = None
        self._offset = start
        self._opened_at = 0.0
        self._polls = 0
        self._reads = 0
        self._missing = False
        self._reopen_pending = False
        self._started = False
        self._events: tuple[Event, ...] = ()
        self._counts: dict[str, int] = {}

    # -- what a caller may ask -------------------------------------------

    @property
    def framer(self) -> Framer:
        """The framer the bytes went through -- the caller's, if it gave one.

        Public because the remainder is the caller's to settle: a tail that
        stops following has not reached end of input, so it does **not** flush
        (`SPEC.md` §7.1), and `pending_bytes` plus `flush()` are how a caller
        whose own stop *is* end of input gets the last line.
        """
        return self._framer

    @property
    def offset(self) -> int:
        """How far into the current content the tail has read.

        Back to 0 after a truncation or a rotation, which is the whole of what
        those two words mean here.
        """
        return self._offset

    @property
    def polls(self) -> int:
        """How many times the tail has looked at the file."""
        return self._polls

    @property
    def reads(self) -> int:
        """How many chunks the tail has handed to the framer."""
        return self._reads

    @property
    def events(self) -> tuple[Event, ...]:
        """What happened since the previous yield, and no further back.

        The framer's rule (`SPEC.md` §3.1) with "call" read as "yield". A poll
        with an event to report yields even when it read nothing, so an event is
        never invisible to a caller that looks between yields.
        """
        return self._events

    @property
    def counts(self) -> Mapping[str, int]:
        """How many of each event code, for the life of this tail."""
        return dict(self._counts)

    # -- the loop --------------------------------------------------------

    def __iter__(self) -> Iterator[Records]:
        """Follow the file: read what is there, sleep, look again.

        The initial open is **not** caught: a path the caller named that cannot
        be opened at all is the caller's error, and waiting for a file to appear
        is a retry policy the receiver does not carry (`SPEC.md` §1.2, §7.1).
        Everything that happens to the file *after* that is an event.

        Iterated **once**: a second iteration would resume the first one's
        stream -- the same framer, the same offset, the same line count -- while
        looking like a fresh start, so it raises instead. One `Tail` per file,
        as one `Framer` per byte stream (`SPEC.md` §3.1, §7.1).
        """
        if self._started:
            raise RuntimeError(f"this tail of {self.path} has already been iterated")
        self._started = True
        self._handle = self.path.open("rb")
        self._handle.seek(self._start)
        self._identity = _identity_of(self._handle)
        self._opened_at = self._now()
        try:
            while self._until is None or not self._until():
                for records in self._poll():
                    yield records
                    self._events = ()
        finally:
            self._close()

    def _poll(self) -> Iterator[Records]:
        """One look at the file: at most one restart, every byte available."""
        self._polls += 1
        progress = False
        if self._shrank():
            yield self._restart_truncated()
            progress = True
        handle = self._handle_now()
        while True:
            chunk = handle.read(self._chunk_bytes)
            if not chunk:
                break
            self._offset += len(chunk)
            self._reads += 1
            progress = True
            yield self._framer.push(chunk)
        if not progress:
            # Only now: the old handle is drained, so a rotation seen here
            # cannot cost a byte that was written to the old file before the
            # rename. That honesty costs one poll (`SPEC.md` §7.1).
            records, restarted = self._inspect_path()
            if records is not None:
                yield records
            progress = restarted
        if not progress:
            self._sleep(self._poll_seconds)

    def _handle_now(self) -> BinaryIO:
        """The open handle, as a type that is not `None`.

        A tail follows a file for as long as it is iterated and closes it on the
        way out, so every caller of this is inside that window. It raises rather
        than asserts because an assertion is not a contract a `-O` run keeps.
        """
        handle = self._handle
        if handle is None:
            raise RuntimeError(f"{self.path} is not open: iterate the tail")
        return handle

    def _shrank(self) -> bool:
        """Is the file shorter than the offset the tail has reached?

        `os.fstat` of the **open handle**, so the question is about the file the
        tail is reading and not about whatever the path names now -- those are
        two different questions and the second one is `_inspect_path`'s.
        """
        return os.fstat(self._handle_now().fileno()).st_size < self._offset

    def _inspect_path(self) -> tuple[Records | None, bool]:
        """Does the path still name the file the tail holds open?

        Answers with what to yield -- so that an event reaches a caller that
        only looks between yields -- and whether the tail has content to read
        right away rather than a poll to wait out.
        """
        try:
            stat = self.path.stat()
        except OSError as error:
            if self._missing:
                return (None, False)
            self._missing = True
            self._emit(
                VANISHED,
                detail=(
                    f"{self.path} names nothing ({error}); the open handle is "
                    f"kept and still read, because the bytes already written to "
                    f"it are still owed"
                ),
            )
            return (_NOTHING, False)
        self._missing = False
        if (stat.st_dev, stat.st_ino) == self._identity:
            # The path names the file the tail holds, so any earlier reopen
            # failure is over: the **next** failure is a different rotation and
            # is reported again. Cleared here and not only on a successful
            # reopen, because a path that reverted to the held inode otherwise
            # left the flag set forever and the next genuinely distinct failure
            # was silent -- "once per failure" read as "once per tail"
            # (`SPEC.md` §7.1, `reviews/2026-10-06-run2.md` F10).
            self._reopen_pending = False
            return (None, False)
        return self._restart_rotated()

    # -- the two restarts ------------------------------------------------

    def _restart_truncated(self) -> Records:
        """Back to 0 in the same file, and say so.

        The same inode, so there is nothing to reopen: the content was replaced
        under the tail. What the framer was holding belonged to the old content,
        so it is **flushed** -- reported as the malformed line it now is, which
        is the only place those bytes survive (`SPEC.md` §1.5, §3.4) -- and
        never joined to the head of the new content.
        """
        stale = self._framer.flush()
        handle = self._handle_now()
        size = os.fstat(handle.fileno()).st_size
        self._emit(
            TRUNCATED,
            detail=(
                f"{self.path} is {size} bytes, which is shorter than the "
                f"{self._offset} the tail had read, so it is read again from 0"
            ),
            offset=self._offset,
        )
        handle.seek(0)
        self._offset = 0
        self._opened_at = self._now()
        return stale

    def _restart_rotated(self) -> tuple[Records | None, bool]:
        """Reopen **by path**, at 0, and say so.

        The new file is opened **before** the old handle is closed and before
        the framer is flushed, so a reopen that fails leaves the tail following
        what it already had rather than following nothing. A failure is its own
        event, once, and the next poll tries again.
        """
        try:
            replacement = self.path.open("rb")
        except OSError as error:
            if self._reopen_pending:
                return (None, False)
            self._reopen_pending = True
            self._emit(
                REOPEN_FAILED,
                detail=(
                    f"{self.path} names a different file than the open handle, "
                    f"and opening it failed ({error}); the tail keeps reading "
                    f"the handle it has"
                ),
                offset=self._offset,
            )
            return (_NOTHING, False)
        stale = self._framer.flush()
        self._emit(
            ROTATED,
            detail=(
                f"{self.path} names a different file than the handle the tail "
                f"had read {self._offset} bytes of, so it is reopened by path "
                f"and read from 0"
            ),
            offset=self._offset,
        )
        self._close()
        self._handle = replacement
        self._identity = _identity_of(replacement)
        self._offset = 0
        self._opened_at = self._now()
        self._reopen_pending = False
        return (stale, True)

    # -- bookkeeping -----------------------------------------------------

    def _emit(self, code: str, *, detail: str, offset: int | None = None) -> None:
        """One `routing.Event`, counted.

        Routing's `Event` and not a type of this module's own: ingest sits
        **above** routing, so there is no upward import to avoid, and the facts
        fit -- `index` is what the tail had handed over, `seconds` is how long
        it had been reading the content it is leaving, `offset` is where in that
        content it was. `FramingEvent` stays the framer's for the reason
        `SPEC.md` §3.1 gives (R2b), which is about §3's layer and not this one.
        """
        event = Event(
            code=code,
            index=self._reads,
            trace_id=None,
            spanweave_code=None,
            detail=detail,
            seconds=self._now() - self._opened_at,
            offset=offset,
        )
        self._events += (event,)
        self._counts[code] = self._counts.get(code, 0) + 1

    def _close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None


def tail(
    path: str | os.PathLike[str],
    *,
    now: Callable[[], float],
    sleep: Callable[[float], None],
    poll_seconds: float,
    start: int = 0,
    framer: Framer | None = None,
    chunk_bytes: int = DEFAULT_CHUNK_BYTES,
    until: Callable[[], bool] | None = None,
) -> Tail:
    """Follow a growing file: `for records in tail(path, now=..., sleep=...)`.

    A `Tail`: **a single-use iterable of `spanweave.Records`, not an iterator**
    -- `iter(t)` is a fresh generator and `next(t)` is a `TypeError`, and a
    second iteration raises rather than resuming the first one's stream. An
    object rather than a bare generator because the events have to ride beside
    the yields and a generator has nowhere to put them (`SPEC.md` §3.1, §7.1).
    """
    return Tail(
        path,
        now=now,
        sleep=sleep,
        poll_seconds=poll_seconds,
        start=start,
        framer=framer,
        chunk_bytes=chunk_bytes,
        until=until,
    )


def stdin(
    stream: BinaryIO | None = None,
    *,
    framer: Framer | None = None,
    chunk_bytes: int = DEFAULT_CHUNK_BYTES,
) -> Iterator[Records]:
    """Read a binary stream to EOF, chunk by chunk; `None` is `sys.stdin.buffer`.

    No `sleep` and no `now`: a blocking read **is** the wait, and a `sleep` here
    would be a seam that never fires (`SPEC.md` §7.1). No events either -- a
    pipe cannot be truncated or rotated, and inventing a code for a short read
    would be a code per poll on a stream that is merely still open.

    EOF **is** end of input, unlike a tail's stop, so the remainder is flushed:
    a last line with no `\\n` comes back as the record it is, and a half-written
    one as the `malformed_record` carrying its text (`SPEC.md` §3.4). That final
    yield is always made, even when the remainder was empty, because "the stream
    ended" is the one thing a caller cannot read off the chunks.
    """
    source = sys.stdin.buffer if stream is None else stream
    framing = Framer() if framer is None else framer
    while True:
        chunk = source.read(chunk_bytes)
        if not chunk:
            break
        yield framing.push(chunk)
    yield framing.flush()
