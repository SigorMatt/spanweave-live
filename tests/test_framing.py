"""`Framer`: bytes in arbitrary chunks, complete records out (`SPEC.md` §3).

The central claim of this file is the first test: **how the bytes were chunked
cannot be seen in the records.** Everything else is a way that claim fails.

The corpus is the pinned `spanweave` repository's own
`fixtures/conformance/`, read through `corpus/` (`CLAUDE.md`). Its renderings
are the records the library itself is tested against, so "the framer agrees
with `read_records` of the whole input" is asserted over the same bytes that
define what the whole input means -- not over a stream this test wrote to suit
itself.

Every shuffle and every chunking here is **seeded, in the test**. `random` is
banned under `spanweave_live/` by the gate for exactly this reason: the
randomness belongs to the fixture, never to the library (`CLAUDE.md`,
standing rules).
"""

import json
import random
from pathlib import Path

import pytest
from spanweave import Diagnostic, Records, read_records

from spanweave_live import Framer

REPO = Path(__file__).resolve().parent.parent
CORPUS = REPO / "corpus" / "fixtures" / "conformance"

# Ten seeds, written down. A chunking that exists only in one run is a test
# that passes for a reason nobody can reproduce.
SEEDS = (0, 1, 2, 3, 7, 11, 13, 101, 1009, 20261004)

# What the corpus holds at the pinned sha, asserted below so that a sweep
# which silently stops covering something is a failure rather than a smaller
# number nobody reads. `tests/test_pins.py` is what keeps the sha still.
LINE_RENDERINGS_EXPECTED = 51
DOCUMENT_RENDERINGS_EXPECTED = 2


def line_renderings() -> list[Path]:
    """Every line-delimited rendering in the corpus. `push`'s input."""
    return sorted(CORPUS.glob("*/dialects/*.jsonl"))


def document_renderings() -> list[Path]:
    """Every whole-document rendering. `document`'s input -- never split."""
    return sorted(CORPUS.glob("*/dialects/*.json"))


def rendering_id(path: Path) -> str:
    return f"{path.parent.parent.name}/{path.name}"


def chunked(body: bytes, seed: int) -> list[bytes]:
    """`body` cut into seeded random chunks, one byte to the whole thing."""
    rng = random.Random(seed)
    chunks: list[bytes] = []
    offset = 0
    while offset < len(body):
        size = rng.randint(1, len(body))
        chunks.append(body[offset : offset + size])
        offset += size
    return chunks


def framed(chunks: list[bytes]) -> tuple[Records, ...]:
    """Push every chunk through one `Framer`, then flush it."""
    framer = Framer()
    results = [framer.push(chunk) for chunk in chunks]
    results.append(framer.flush())
    assert framer.pending_bytes == 0, "a flushed framer is holding nothing"
    return tuple(results)


def records_of(results: tuple[Records, ...]) -> tuple[object, ...]:
    return tuple(record for result in results for record in result.records)


def diagnostics_of(results: tuple[Records, ...]) -> list[Diagnostic]:
    """Every diagnostic the framing reported, in the library's own order."""
    collected = [d for result in results for d in result.diagnostics]
    return sorted(collected, key=lambda d: d.sort_key)


# --------------------------------------------------------------------------
# The corpus sweep: the chunking is invisible in the records.
# --------------------------------------------------------------------------


def test_the_sweep_covers_every_rendering_the_corpus_holds():
    """No rendering is skipped, and the counts are written down.

    A sweep over a glob is only as good as the glob: if a rendering were added
    in a form neither `*.jsonl` nor `*.json` matched, the sweep below would go
    on passing while covering less. So both counts are asserted, and their sum
    is checked against every file under a `dialects/` directory -- which is
    the thing that cannot be matched by a pattern that has gone stale.
    """
    lines = line_renderings()
    documents = document_renderings()
    everything = sorted(p for p in CORPUS.glob("*/dialects/*") if p.is_file())
    assert len(lines) == LINE_RENDERINGS_EXPECTED
    assert len(documents) == DOCUMENT_RENDERINGS_EXPECTED
    assert sorted(lines + documents) == everything


@pytest.mark.parametrize("rendering", line_renderings(), ids=rendering_id)
def test_seeded_chunkings_of_a_rendering_read_as_the_whole_input_does(rendering):
    """THE claim of §3: framing is invisible in the records.

    For every rendering of the corpus, and for each of ten seeded chunkings
    plus the two extremes a seed will not reliably produce -- one byte at a
    time, and the whole input in one chunk -- the records the `Framer` hands
    over are `read_records` of the whole input, exactly: same records, same
    order, same count, and the same diagnostics.

    This is the test the batch exists to pass. A framer that handed partial
    lines to the reader fails it with `malformed_record`s the whole read does
    not have.
    """
    body = rendering.read_bytes()
    whole = read_records(body)
    assert whole.records, f"{rendering_id(rendering)} holds no records to compare"

    chunkings: dict[str, list[bytes]] = {
        "one byte at a time": [body[i : i + 1] for i in range(len(body))],
        "one chunk": [body],
    }
    for seed in SEEDS:
        chunkings[f"seed {seed}"] = chunked(body, seed)

    for label, chunks in chunkings.items():
        results = framed(chunks)
        assert records_of(results) == whole.records, label
        assert diagnostics_of(results) == list(whole.diagnostics), label
        assert sum(r.skipped_records for r in results) == whole.skipped_records, label


# --------------------------------------------------------------------------
# A boundary inside a multi-byte character.
# --------------------------------------------------------------------------

# Two records carrying 2-, 3- and 4-byte UTF-8 sequences. Hand-authored, not
# captured: every rendering in the corpus is pure ASCII at the pinned sha, so
# there is nothing there a chunk boundary could cut in half, and a test that
# swept the corpus for this would pass by having nothing to find.
MULTI_BYTE_STREAM = (
    '{"trace_id":"t1","span_id":"s1","name":"llm","output":"café — 日本語 🙂"}\n'
    '{"trace_id":"t1","span_id":"s2","name":"tool","output":"naïve ✓ 🚀"}\n'
).encode()


def test_the_multi_byte_fixture_really_holds_multi_byte_characters():
    """The fixture above cannot quietly become ASCII.

    Without this, a later edit that dropped the non-ASCII characters would
    leave the next test green over bytes it was written to be the only test of.
    """
    widths = {
        len(character.encode()) for character in MULTI_BYTE_STREAM.decode("utf-8")
    }
    assert {2, 3, 4} <= widths


def test_a_boundary_inside_a_multi_byte_character_is_never_undecodable():
    """`undecodable_bytes` is what framing wrong looks like (`SPEC.md` §2.1).

    The reader neither buffers nor rejoins across calls: half a character
    handed over is decoded to U+FFFD and reported, and the record that comes
    back is subtly not the one that was sent. The `Framer`'s remainder is what
    prevents it, so this is asserted at **every** two-way split of the stream
    -- which includes every boundary inside every multi-byte sequence in it --
    and again one byte at a time, which splits all of them at once.
    """
    whole = read_records(MULTI_BYTE_STREAM)
    assert whole.diagnostics == (), "the fixture itself must read clean"

    chunkings = [
        [MULTI_BYTE_STREAM[:split], MULTI_BYTE_STREAM[split:]]
        for split in range(1, len(MULTI_BYTE_STREAM))
    ]
    chunkings.append([bytes([byte]) for byte in MULTI_BYTE_STREAM])

    for chunks in chunkings:
        results = framed(chunks)
        codes = [d.code for d in diagnostics_of(results)]
        assert "undecodable_bytes" not in codes, [len(c) for c in chunks]
        assert records_of(results) == whole.records, [len(c) for c in chunks]


# --------------------------------------------------------------------------
# A truncated final line.
# --------------------------------------------------------------------------

COMPLETE_LINES = b'{"trace_id":"t1","span_id":"s1"}\n{"trace_id":"t1","span_id":"s2"}\n'
TRUNCATED_TAIL = b'{"trace_id":"t1","span_i'


def test_a_truncated_final_line_is_pending_and_not_yet_malformed():
    """A line that has not arrived is pending, not broken (`SPEC.md` §3).

    The distinction is the whole point of the remainder. A tail that stops
    mid-record is the ordinary state of a growing file read at any instant;
    calling it `malformed_record` would make a `malformed_record` per poll out
    of a file that is merely still being written.
    """
    framer = Framer()
    result = framer.push(COMPLETE_LINES + TRUNCATED_TAIL)

    assert len(result.records) == 2
    assert [d.code for d in result.diagnostics] == []
    assert result.skipped_records == 0
    assert framer.pending_bytes == len(TRUNCATED_TAIL)

    # And it stays pending across a push that adds no terminator.
    again = framer.push(b"d")
    assert again.records == ()
    assert again.diagnostics == ()
    assert framer.pending_bytes == len(TRUNCATED_TAIL) + 1


def test_flush_reports_the_remainder_rather_than_dropping_it():
    """Nothing is dropped silently (`SPEC.md` §1.5): flush reads the remainder.

    The truncated tail is not a record, so what flush produces is the
    `malformed_record` that carries its text -- the only place that text
    survives -- and the framer is then holding nothing.
    """
    framer = Framer()
    framer.push(COMPLETE_LINES + TRUNCATED_TAIL)

    flushed = framer.flush()
    assert flushed.records == ()
    assert [d.code for d in flushed.diagnostics] == ["malformed_record"]
    assert flushed.skipped_records == 1
    assert flushed.diagnostics[0].source == TRUNCATED_TAIL.decode()
    assert framer.pending_bytes == 0

    # Flushing an empty framer reports nothing, because there is nothing.
    assert framer.flush() == Records(records=(), diagnostics=(), skipped_records=0)


def test_flush_reads_a_complete_final_line_that_had_no_terminator():
    """A file whose last line has no `\\n` loses nothing.

    The remainder is read as a final line, so a complete record that simply
    arrived without a terminator becomes a record -- which is also what
    `read_records` of the whole input does with it.
    """
    body = COMPLETE_LINES + b'{"trace_id":"t1","span_id":"s3"}'
    framer = Framer()
    pushed = framer.push(body)
    flushed = framer.flush()

    assert framer.pending_bytes == 0
    assert pushed.records + flushed.records == read_records(body).records
    assert flushed.diagnostics == ()


# --------------------------------------------------------------------------
# Absolute line numbers.
# --------------------------------------------------------------------------


def stream_of_records(total: int, *, malformed: int = 0) -> bytes:
    """`total` distinct line-delimited records, terminated.

    Where `malformed` names a 1-based line, that line is not JSON. Distinct
    records on purpose: two identical lines would be a `duplicate_record`,
    which is a per-call collapse (`SPEC.md` §2.2) and a different test's
    subject.
    """
    lines = []
    for number in range(1, total + 1):
        if number == malformed:
            lines.append(b'{"oops')
        else:
            record = {"trace_id": "t1", "span_id": f"s{number}"}
            lines.append(json.dumps(record, sort_keys=True).encode())
    return b"\n".join(lines) + b"\n"


@pytest.mark.parametrize("position", [1, 2, 7, 12])
def test_a_diagnostic_numbers_the_line_in_the_stream_not_in_the_chunk(position):
    """The line number is the line's position in the whole stream.

    Asserted by comparing against `read_records` of the whole input rather
    than against a sentence written here: the reader's own message for the
    same line is the expectation, so this test states the rule -- the number
    is absolute -- without restating the library's prose, which is not this
    project's to fix.

    The `startswith` assertions are what catch a framer that renumbers
    nothing: within its own chunk, a malformed line is often line 1.
    """
    body = stream_of_records(12, malformed=position)
    whole = read_records(body)
    assert [d.code for d in whole.diagnostics] == ["malformed_record"]
    # `startswith`, not `in`: the parser's own message quotes a line 1 of its
    # own further along, and the number this test is about is the leading one.
    assert whole.diagnostics[0].message.startswith(f"line {position} ")

    for seed in SEEDS:
        results = framed(chunked(body, seed))
        assert records_of(results) == whole.records, seed
        assert diagnostics_of(results) == list(whole.diagnostics), seed

    # One byte at a time puts the malformed line alone in its own call, which
    # is where a chunk-local number is most obviously wrong.
    results = framed([body[i : i + 1] for i in range(len(body))])
    reported = diagnostics_of(results)
    assert [d.code for d in reported] == ["malformed_record"]
    assert reported[0].message.startswith(f"line {position} ")


def test_a_remainder_read_by_flush_is_numbered_as_the_final_line():
    """The line flush reads is the one after every line push handed over."""
    body = stream_of_records(5, malformed=5).rstrip(b"\n")
    whole = read_records(body)

    framer = Framer()
    framer.push(body)
    flushed = framer.flush()

    assert [d.code for d in flushed.diagnostics] == ["malformed_record"]
    assert flushed.diagnostics == whole.diagnostics
    assert flushed.diagnostics[0].message.startswith("line 5 ")


def test_diagnostics_come_back_in_the_librarys_own_order():
    """Renumbering does not leave them unsorted (`spanweave` `SPEC.md` §5.2).

    Two malformed lines in one chunk, read as lines 10 and 11 of the stream
    and as lines 1 and 2 of the call -- so the tuple is sorted by the numbers
    the receiver hands over, not by the ones the reader used.
    """
    good = stream_of_records(9)
    body = good + b'{"oops\n{"nope\n'

    framer = Framer()
    framer.push(good)
    result = framer.push(b'{"oops\n{"nope\n')

    messages = [d.message for d in result.diagnostics]
    assert len(messages) == 2
    assert messages == sorted(messages)
    assert messages[0].startswith("line 10 ")
    assert messages[1].startswith("line 11 ")
    # And they are the reader's own diagnostics for those lines of this stream.
    assert result.diagnostics == read_records(body).diagnostics


# --------------------------------------------------------------------------
# A whole document, handed over unsplit.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("rendering", document_renderings(), ids=rendering_id)
def test_document_reads_a_whole_body_exactly_as_read_records_does(rendering):
    """`document` is `read_records` of the body, and nothing else (`SPEC.md` §3).

    An OTLP JSON document must not be split, so it is a different method
    rather than a flag on `push` (`SPEC.md` §2.1). It carries no offset,
    because the body is the whole input as far as its caller is concerned.
    """
    body = rendering.read_bytes()
    framer = Framer()
    result = framer.document(body)

    assert result == read_records(body)
    assert len(result.records) > 1, "an export unpacks to one record per span"
    assert framer.pending_bytes == 0


@pytest.mark.parametrize("rendering", document_renderings(), ids=rendering_id)
def test_a_document_pushed_in_chunks_is_lost_which_is_why_document_exists(rendering):
    """Why `document` is a method and not a flag (`SPEC.md` §3).

    The reader's container detection is **per call** (`SPEC.md` §2.1, §2.2), so
    a pretty-printed document survives `push` only where it happens to arrive
    whole: push it in two chunks and each call sees a run of lines that are not
    records, and says so with a `malformed_record` apiece. The framer does not
    rejoin them -- a framer that buffered until something parsed would be the
    library's own rule reimplemented here, differently, and it would hold a
    tail forever on the ordinary input it was given.

    `document` is immune because it never splits: the same bytes, one call.
    """
    body = rendering.read_bytes()
    assert body.count(b"\n") > 1, "a pretty-printed document, not one line"

    chunks = chunked(body, seed=SEEDS[0])
    assert len(chunks) > 1, "a one-chunk framing would prove nothing here"
    chunked_results = framed(chunks)
    assert records_of(chunked_results) == ()
    assert {d.code for d in diagnostics_of(chunked_results)} == {"malformed_record"}

    assert Framer().document(body).records == read_records(body).records


def test_document_leaves_the_line_remainder_alone():
    """`document` neither touches the remainder nor is confused by it.

    The two are different transports (`SPEC.md` §3): a body is whole when it
    arrives, a tail is not. Mixing them on one framer is a caller error, and
    the honest behaviour is that neither silently eats the other's bytes.
    """
    framer = Framer()
    framer.push(COMPLETE_LINES + TRUNCATED_TAIL)
    assert framer.pending_bytes == len(TRUNCATED_TAIL)

    body = b'{"resourceSpans":[{"scopeSpans":[{"spans":[{"traceId":"t1"}]}]}]}'
    assert framer.document(body) == read_records(body)
    assert framer.pending_bytes == len(TRUNCATED_TAIL)
