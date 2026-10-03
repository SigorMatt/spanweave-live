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

Nothing here reads the clock, sleeps, opens a socket or shuffles anything: a
`Framer` is a pure function of the bytes it has been handed, in the order it
was handed them.
"""

from __future__ import annotations

import re

from spanweave import Diagnostic, Records, read_records

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

    There is **no cap** on the remainder, and that is a gap stated rather than
    a decision made. A stream that never sends a `\\n` grows this buffer, and
    `pending_bytes` is what makes that visible to a caller who wants to act on
    it. A cap would be a policy -- which bytes to refuse, and what to call the
    event -- and inventing one here is a halt point (`CONTRIBUTING.md`), so the
    receiver reports and does not decide.
    """

    __slots__ = ("_lines", "_pending")

    def __init__(self) -> None:
        self._pending = bytearray()
        self._lines = 0

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
        """
        self._pending += chunk
        end = self._pending.rfind(b"\n")
        if end < 0:
            return _NOTHING_YET
        complete = bytes(self._pending[: end + 1])
        del self._pending[: end + 1]
        offset = self._lines
        self._lines += complete.count(b"\n")
        return _with_offset(read_records(complete), offset)

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
        """
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
        """
        if not self._pending:
            return _NOTHING_YET
        remainder = bytes(self._pending)
        del self._pending[:]
        offset = self._lines
        self._lines += 1
        return _with_offset(read_records(remainder), offset)
