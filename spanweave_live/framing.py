"""Framing: bytes in arbitrary chunks, complete records out (`SPEC.md` §3).

The first piece of the receiver, and the one with the least to do. It owns a
remainder buffer, splits on `\\n`, and hands **complete lines only** to
`spanweave.read_records`. It does not parse, does not classify, does not look
inside a line, and does not know what a trace id is (`SPEC.md` §1.1).

Why it exists at all: the reader neither buffers nor rejoins across calls
(`SPEC.md` §2.1), so an arbitrary chunk boundary handed over is half a
multi-byte character in each call -- decoded to U+FFFD, reported as
`undecodable_bytes`, and handed back as a record that is subtly not the one
that was sent. Framing is therefore the receiver's job, and getting it wrong
does not raise: it quietly changes the records. That is what makes it worth a
module and a corpus-wide test rather than three lines in an ingest loop.

The one policy it takes is `max_pending_bytes`, the cap on the remainder, and
that is the caller's number -- there is no default cap (`SPEC.md` §3.4). At the
cap the remainder is read as a line rather than kept, so the bytes come back as
a `malformed_record` and a `FramingEvent` says how many they were. Nothing is
dropped.

Nothing here reads the clock, sleeps, opens a socket or shuffles anything: a
`Framer` is a pure function of the bytes it has been handed, in the order it
was handed them.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from spanweave import Diagnostic, Records, read_records

#: The remainder outgrew the cap the caller set, so it was handed to the reader
#: as one line instead of being kept (`SPEC.md` §3.4). The bytes are reported,
#: never dropped: the reader answers with a `malformed_record` carrying their
#: text and a skipped record, and this event says how many bytes they were.
FRAGMENT_TOO_LONG: Final = "fragment_too_long"

#: The leading `line <n>` of a reader diagnostic about one line of input.
#:
#: The reader numbers lines **within the call it was given**, which for a push
#: is the chunk and not the stream, so the number has to be shifted by the
#: lines already handed over. It is read off the front of the message because
#: that is where the reader puts it and a `Diagnostic` carries no line field --
#: a limitation of this seam, named here rather than worked around silently.
#: Anchored at the start, so a message that merely mentions a line further in
#: (a JSON parse error quotes its own line 1) is not touched.
_LEADING_LINE = re.compile(r"\Aline (\d+)\b")

#: What a call that completed no line produced: no records, no diagnostics,
#: nothing skipped. Not an absence -- the bytes are in the remainder, and
#: `pending_bytes` is where that is visible (`SPEC.md` §1.5).
_NOTHING_YET = Records(records=(), diagnostics=(), skipped_records=0)


@dataclass(frozen=True, slots=True)
class FramingEvent:
    """One decision the framer made about bytes that a caller must know about.

    Today there is one code, `FRAGMENT_TOO_LONG`, and one decision to report:
    the caller's cap was reached (`SPEC.md` §1.5, §3.4).

    A type of its own rather than `spanweave_live.Event`, which the router
    emits, because the two layers have different facts to report and neither
    one's fields are honest for the other. A routing event names a record's
    arrival index, the trace id and the library's own refusal code; the framer
    has seen no record, knows no trace, and the library refused nothing -- what
    it has is a line and a length. Folding both into one dataclass would mean
    four fields that are `None` wherever they are not the emitter's, which is a
    shape neither caller can read.
    """

    code: str
    #: The fragment's 1-based line number in the stream. The line **the framer
    #: handed over**: once a line is cut into fragments the framer no longer
    #: knows where that line ended, and each fragment is numbered as a line of
    #: its own (`SPEC.md` §3.4).
    line: int
    #: How many bytes were handed over as that one line. The number the decision
    #: is about, kept as a field rather than folded into `detail` so a caller can
    #: act on it instead of parsing a sentence.
    length: int
    detail: str


def _merged(first: Records, second: Records) -> Records:
    """Two reads of one push, handed back as the one result the push owes.

    A push that both completes lines and then cuts an over-cap remainder loose
    (`SPEC.md` §3.4) is two calls to the reader, and its caller is owed one
    `Records`. The diagnostics of a collection are ordered by the library's own
    key (`spanweave` `SPEC.md` §5.2), so the two tuples are merged and
    **re-sorted** rather than concatenated -- the same reason `_with_offset`
    re-sorts after renumbering.
    """
    return Records(
        records=first.records + second.records,
        diagnostics=tuple(
            sorted(first.diagnostics + second.diagnostics, key=lambda d: d.sort_key)
        ),
        skipped_records=first.skipped_records + second.skipped_records,
    )


def _renumbered(diagnostic: Diagnostic, offset: int) -> Diagnostic:
    """One diagnostic, with its line number made absolute in the stream.

    A diagnostic that names no line -- a `duplicate_record`, or a container
    form's "the input ..." -- comes back untouched: there is no number to fix,
    and inventing one would be worse than leaving it.

    The chunk-local number is **replaced**, not kept alongside. How the bytes
    were chunked is the receiver's own doing and says nothing about the input;
    publishing it beside the real line number would make a reader wonder which
    of the two to act on.
    """
    match = _LEADING_LINE.match(diagnostic.message)
    if match is None:
        return diagnostic
    absolute = int(match.group(1)) + offset
    return Diagnostic(
        code=diagnostic.code,
        message=f"line {absolute}{diagnostic.message[match.end() :]}",
        level=diagnostic.level,
        node_id=diagnostic.node_id,
        source=diagnostic.source,
        adapter=diagnostic.adapter,
    )


def _with_offset(result: Records, offset: int) -> Records:
    """`result`, re-issued with `offset` lines already behind it."""
    if offset == 0 or not result.diagnostics:
        return result
    return Records(
        records=result.records,
        # Re-sorted, because the message is part of the order the library
        # states for a collection of diagnostics (`spanweave` `SPEC.md` §5.2)
        # and renumbering changes the message. Handing back a tuple that is
        # sorted by the *old* numbers would be this layer quietly breaking a
        # property its caller is entitled to.
        diagnostics=tuple(
            sorted(
                (_renumbered(d, offset) for d in result.diagnostics),
                key=lambda d: d.sort_key,
            )
        ),
        skipped_records=result.skipped_records,
    )


class Framer:
    """Where a record ends, when the bytes arrive in arbitrary chunks.

    One `Framer` per byte stream -- a tailed file, a connection, stdin -- and
    not shared between two, because the remainder and the line count are that
    stream's. It is deliberately not thread-safe and not re-entrant: there is
    no lock here and no module under `spanweave_live/` may import `threading`
    (`CLAUDE.md`, standing rules), so a caller that wants two streams makes two
    framers.

    The remainder's cap is `max_pending_bytes`, and it is the **caller's**
    number: `None`, the default, is no cap at all (`SPEC.md` §3.4). How many
    bytes of an unterminated line are too many is a policy, and the receiver
    carries no policy of its own -- a default here would be the receiver
    inventing one. What the receiver owns is the mechanism: at the cap the
    remainder is handed to the reader as one line rather than kept, so it comes
    back as a `malformed_record` with its text and a skipped record, and a
    `FramingEvent` says how long it was. Nothing is dropped (`SPEC.md` §1.5).

    `max_pending_bytes` is **keyword-only**: it is a policy the caller sets, not
    a reading order, and a positional slot would be a contract `SPEC.md` §3.1
    never offered (the same reason `Router`'s settings are keyword-only).
    """

    __slots__ = ("_counts", "_events", "_lines", "_max_pending_bytes", "_pending")

    def __init__(self, *, max_pending_bytes: int | None = None) -> None:
        if max_pending_bytes is not None and max_pending_bytes < 0:
            # `0` is legal and means every remainder is read the moment it
            # exists; a negative number is not a quantity of bytes at all.
            # Refused at construction rather than read as `0`, because
            # `len(pending) <= -1` is false for the **empty** remainder too, so
            # a negative cap would report a `fragment_too_long` of length 0 on
            # every push that ended on a line boundary and burn a line number
            # doing it -- which would make the framer's own line numbers wrong
            # for a reason no caller asked for (`SPEC.md` §3.4, §3.5). Nothing
            # about the stream causes it, so it is a `ValueError` and not an
            # event, as `Subscriptions.subscribe(every=0)` is.
            raise ValueError(
                f"max_pending_bytes is the most the framer will keep and is at "
                f"least 0 (0 reads every remainder at once, `SPEC.md` §3.4); "
                f"{max_pending_bytes!r} is not"
            )
        self._pending = bytearray()
        self._lines = 0
        self._max_pending_bytes = max_pending_bytes
        self._events: tuple[FramingEvent, ...] = ()
        self._counts: dict[str, int] = {}

    @property
    def max_pending_bytes(self) -> int | None:
        """The most the remainder may hold, or `None` for no cap.

        Read back as the caller set it, because a caller that hands a framer to
        another layer (R5's tail, R6's handler) is entitled to see the policy it
        is running under.
        """
        return self._max_pending_bytes

    @property
    def events(self) -> tuple[FramingEvent, ...]:
        """The events of the **most recent call**, and no further back.

        Reset by every `push`, `document` and `flush`, so it is always this
        call's answer and never a log that grows with the stream -- which is
        `SPEC.md` §2.3 and the same choice `Router` made (§4.6). It is a
        property rather than part of the return value because the return value
        is `spanweave.Records` and stays that way: a wrapper carrying both would
        be the second name for records, diagnostics and skips that §3.1 refuses.
        `counts` is the running total.
        """
        return self._events

    @property
    def counts(self) -> Mapping[str, int]:
        """How many of each event code, for the life of this framer.

        Bounded by the number of codes, not by the length of the stream.
        """
        return dict(self._counts)

    @property
    def pending_bytes(self) -> int:
        """How many bytes are held back as an incomplete final line.

        Zero after a `flush`. Non-zero is the ordinary state of a growing file
        read at an instant, and is **not** a malformed record: a tail that
        stops mid-record has not failed, it has not finished.
        """
        return len(self._pending)

    def push(self, chunk: bytes) -> Records:
        """Absorb a chunk of a line-delimited stream; read what it completed.

        Everything up to and including the last `\\n` goes to
        `spanweave.read_records` as one call; everything after it is kept for
        the next push. A chunk that completes no line reads nothing and reports
        nothing -- the bytes are in the remainder, not gone.

        The terminator travels with the lines rather than being stripped: the
        reader's own line splitting is then given exactly the input a file
        would have given it, and the final empty piece is a blank line, which
        it ignores.

        If this push leaves more than `max_pending_bytes` in the remainder, the
        remainder is not kept: it goes to the reader as one line too, in the
        same push, and `events` carries the `fragment_too_long` that says how
        long it was (`SPEC.md` §3.4).
        """
        self._events = ()
        self._pending += chunk
        end = self._pending.rfind(b"\n")
        if end < 0:
            return self._capped(_NOTHING_YET)
        complete = bytes(self._pending[: end + 1])
        del self._pending[: end + 1]
        offset = self._lines
        self._lines += complete.count(b"\n")
        return self._capped(_with_offset(read_records(complete), offset))

    def _capped(self, result: Records) -> Records:
        """`result`, plus the remainder read as a line if it outgrew the cap.

        The cap is the most the framer will **keep**, so it is `>` and not
        `>=`: a remainder exactly at the cap is a remainder the caller allowed.
        """
        cap = self._max_pending_bytes
        if cap is None or len(self._pending) <= cap:
            return result
        return _merged(result, self._cut_loose(cap))

    def _cut_loose(self, cap: int) -> Records:
        """Read the over-cap remainder as one line; report that it was.

        What the reader makes of it is the reader's: a fragment of a line is
        almost always a `malformed_record` carrying its text, which is the only
        place those bytes survive (`SPEC.md` §1.5), and if the fragment happens
        to be a whole record it is a record. Either way the framer is then
        holding nothing, so the next chunk starts clean rather than inheriting a
        buffer that can only grow -- a cap that wedged the stream it capped
        would be worse than no cap.

        The fragment is numbered as a line of its own, because the framer does
        not know where the line it came from ended: the rest of that line
        arrives later and is numbered as the next line (`SPEC.md` §3.4).
        """
        length = len(self._pending)
        fragment = bytes(self._pending)
        del self._pending[:]
        offset = self._lines
        self._lines += 1
        self._emit(
            FramingEvent(
                code=FRAGMENT_TOO_LONG,
                line=offset + 1,
                length=length,
                detail=(
                    f"{length} bytes were held with no newline, which is more "
                    f"than max_pending_bytes={cap}, so they were read as line "
                    f"{offset + 1} of the stream rather than kept"
                ),
            )
        )
        return _with_offset(read_records(fragment), offset)

    def _emit(self, event: FramingEvent) -> None:
        self._events += (event,)
        self._counts[event.code] = self._counts.get(event.code, 0) + 1

    def document(self, body: bytes) -> Records:
        """Read one whole body -- an OTLP/HTTP POST, a message off a queue.

        Handed over **unsplit**, which is the whole point: a JSON document is
        not a record until its closing brace, and the reader's container
        detection runs per call (`SPEC.md` §2.1), so a document split across
        two calls is two runs of lines that are not records. A separate method
        rather than a flag on `push`, because the caller knows which of the two
        it is holding and the bytes do not say.

        It carries no line offset: the body is the whole input as far as its
        own caller is concerned. It neither reads nor clears the remainder --
        a body and a tail are different transports, and neither may eat the
        other's bytes.

        `max_pending_bytes` does not apply: the cap bounds a **remainder**, and
        a body is not one. A body arrives whole or not at all, so there is
        nothing here for a cap to bound and capping it would be truncating an
        export the caller handed over complete.
        """
        self._events = ()
        return read_records(body)

    def flush(self) -> Records:
        """Read the remainder as a final line, and report what it was.

        For end of input: a file whose last line has no terminator, a
        connection that closed. A complete record simply missing its `\\n`
        becomes a record; a truncated one becomes the `malformed_record` that
        carries its text, which is the only place that text survives
        (`SPEC.md` §1.5). Either way the remainder is read exactly once and the
        framer is then holding nothing.

        An empty remainder reads nothing and reports nothing. There is no
        final line, so saying there was one would be inventing a fact.

        No cap applies: `flush` reads the remainder whatever its length, because
        that is what `flush` is for. A framer running under a cap has nothing
        over it to flush anyway -- `push` cut it loose when it crossed.
        """
        self._events = ()
        if not self._pending:
            return _NOTHING_YET
        remainder = bytes(self._pending)
        del self._pending[:]
        offset = self._lines
        self._lines += 1
        return _with_offset(read_records(remainder), offset)
