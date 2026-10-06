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

from spanweave_live import FRAGMENT_TOO_LONG, Framer

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


# Every line rendering in the corpus reads **clean** at the pinned sha: not one
# of the 51 produces a diagnostic or skips a record. So a sweep over the corpus
# as captured compares two empty sequences twice, and a `push` that swallowed
# every diagnostic, or that reported `skipped_records=0` unconditionally, would
# pass it -- which is what `patches/REVIEW-2026-10-04.md` found (R1-1, R1-2).
#
# So every rendering is swept in two forms: as captured, and with one line
# corrupted. The corrupted form is **derived from the corpus bytes**, by the
# function below, and is never a hand-copied fixture: a second copy of a
# rendering checked into this repo is a copy nothing holds at the pin, and it
# would go on reading the way the corpus read on the day it was copied.
CORRUPTED_LINE = b'{"oops'


def corrupted(body: bytes) -> bytes:
    """`body` with one line replaced by one that is not JSON.

    Deterministic, and a function of the bytes alone: the line replaced is the
    middle one, so the same rendering always corrupts to the same stream and
    the corruption is never at an edge the framer treats specially. The line
    count is unchanged, so the diagnostic the reader issues names a line in the
    middle of the stream -- which is also where a chunk-local number would be
    most obviously wrong (§3.5).
    """
    lines = body.split(b"\n")
    assert lines[-1] == b"", "a corpus rendering is newline-terminated"
    content = lines[:-1]
    assert content, "a rendering holds at least one line"
    content[len(content) // 2] = CORRUPTED_LINE
    return b"\n".join(content) + b"\n"


#: The two forms every line rendering is swept in. The second is what makes the
#: sweep's `diagnostics` and `skipped_records` assertions compare something.
FORMS = ("as captured", "one line corrupted")


def form_of(rendering: Path, form: str) -> bytes:
    body = rendering.read_bytes()
    return body if form == "as captured" else corrupted(body)


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


def framing_of(chunks: list[bytes], framer: Framer) -> tuple[Records, ...]:
    """Push every chunk through `framer`, then flush it."""
    results = [framer.push(chunk) for chunk in chunks]
    results.append(framer.flush())
    assert framer.pending_bytes == 0, "a flushed framer is holding nothing"
    return tuple(results)


def framed(chunks: list[bytes]) -> tuple[Records, ...]:
    """Push every chunk through one default `Framer`, then flush it."""
    return framing_of(chunks, Framer())


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
def test_a_corrupted_rendering_carries_a_diagnostic_and_a_skipped_record(rendering):
    """What the second form of the sweep is for, asserted before it is used.

    The sweep below compares the framer's diagnostics and its `skipped_records`
    against the whole read's. Over the corpus as captured both sides are empty,
    so without this form the comparison is vacuous. This test is what keeps the
    corruption real: one `malformed_record` and exactly one skipped record, for
    every rendering, so a corruption that stopped corrupting (a corpus whose
    middle line is already unreadable, a `CORRUPTED_LINE` that became valid
    JSON) is a failure here rather than a quietly empty assertion below.
    """
    whole = read_records(corrupted(rendering.read_bytes()))
    assert [d.code for d in whole.diagnostics] == ["malformed_record"]
    assert whole.skipped_records == 1


@pytest.mark.parametrize("form", FORMS)
@pytest.mark.parametrize("rendering", line_renderings(), ids=rendering_id)
def test_seeded_chunkings_of_a_rendering_read_as_the_whole_input_does(rendering, form):
    """THE claim of §3: framing is invisible in the records.

    For every rendering of the corpus, in both forms, and for each of ten
    seeded chunkings plus the two extremes a seed will not reliably produce --
    one byte at a time, and the whole input in one chunk -- the records the
    `Framer` hands over are `read_records` of the whole input, exactly: same
    records, same order, same count, the same diagnostics, and the same
    `skipped_records`.

    This is the test the batch exists to pass. A framer that handed partial
    lines to the reader fails it with `malformed_record`s the whole read does
    not have; a framer that swallowed a diagnostic, or that reported
    `skipped_records=0`, fails it on the corrupted form -- and on the corrupted
    form only, which is why the form exists.
    """
    body = form_of(rendering, form)
    whole = read_records(body)
    if form == "as captured":
        assert whole.records, f"{rendering_id(rendering)} holds no records to compare"
    else:
        # Non-empty on both counts, or this parametrization proves nothing.
        assert whole.diagnostics and whole.skipped_records == 1

    chunkings: dict[str, list[bytes]] = {
        "one byte at a time": [body[i : i + 1] for i in range(len(body))],
        "one chunk": [body],
    }
    for seed in SEEDS:
        chunkings[f"seed {seed}"] = chunked(body, seed)

    for label, chunks in chunkings.items():
        results = framed(chunks)
        assert records_of(results) == whole.records, f"{form}, {label}"
        assert diagnostics_of(results) == list(whole.diagnostics), f"{form}, {label}"
        assert sum(r.skipped_records for r in results) == whole.skipped_records, (
            f"{form}, {label}"
        )


@pytest.mark.parametrize("form", FORMS)
@pytest.mark.parametrize("rendering", line_renderings(), ids=rendering_id)
def test_a_cap_of_none_is_r1s_behaviour_over_the_whole_sweep(rendering, form):
    """`max_pending_bytes=None` is unbounded, exactly as R1 shipped (§3.4).

    The default is `None` because a default cap would be the receiver inventing
    a policy, so the no-cap path is the one almost every caller runs and the
    claim that the cap changed nothing about it has to be held over the whole
    sweep rather than a sample of it: the same 51 renderings x 2 forms x 12
    framings = 1224 framings the test above runs, re-run against a framer
    constructed with the cap spelled out.

    Two things are asserted, and the second is the one a sampled test would
    miss: the records, diagnostics and `skipped_records` are `read_records` of
    the whole input, and **no event is emitted and no count is kept** anywhere
    in the sweep. An over-eager cap -- one that fired on a `>=`, or that capped
    `None` to some number of its own -- would cut corpus lines loose and show up
    as a `fragment_too_long` here even where the records still happened to
    match.
    """
    body = form_of(rendering, form)
    whole = read_records(body)

    chunkings: dict[str, list[bytes]] = {
        "one byte at a time": [body[i : i + 1] for i in range(len(body))],
        "one chunk": [body],
    }
    for seed in SEEDS:
        chunkings[f"seed {seed}"] = chunked(body, seed)

    for label, chunks in chunkings.items():
        framer = Framer(max_pending_bytes=None)
        assert framer.max_pending_bytes is None
        results = framing_of(chunks, framer)
        assert records_of(results) == whole.records, f"{form}, {label}"
        assert diagnostics_of(results) == list(whole.diagnostics), f"{form}, {label}"
        assert sum(r.skipped_records for r in results) == whole.skipped_records, (
            f"{form}, {label}"
        )
        assert framer.events == (), f"{form}, {label}"
        assert framer.counts == {}, f"{form}, {label}"


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
# What a push did not hand over: `skipped_records`, counted per chunk.
# --------------------------------------------------------------------------


def test_push_reports_a_skipped_record_for_a_complete_line_it_could_not_read():
    """`skipped_records` is a count, not a field that happens to be zero.

    `SPEC.md` §1.5 and `CLAUDE.md` standing rule 5 rest on this number: a line
    the reader could not read is a `malformed_record` **and** a skip, and the
    skip is what the caller adds up. Asserted here on `push` directly, and not
    only through the corpus sweep, because a `push` that returned
    `skipped_records=0` unconditionally passed the whole suite before this test
    existed (`patches/REVIEW-2026-10-04.md` R1-2).
    """
    framer = Framer()
    result = framer.push(b'{"trace_id":"t1","span_id":"s1"}\n' + CORRUPTED_LINE + b"\n")

    assert len(result.records) == 1
    assert [d.code for d in result.diagnostics] == ["malformed_record"]
    assert result.skipped_records == 1
    assert framer.pending_bytes == 0

    # And the next chunk's count is its own: the framer accumulates no total.
    assert framer.push(b'{"trace_id":"t1","span_id":"s2"}\n').skipped_records == 0


# --------------------------------------------------------------------------
# No dedup cache of its own (`SPEC.md` §3.2, §2.2).
# --------------------------------------------------------------------------


def test_the_framer_grows_no_dedup_cache_of_its_own():
    """Deduplication is the reader's, per call, and the framer adds none.

    Both halves matter and they are each other's control. In **one** chunk two
    identical lines are one call, so they are one record and one
    `duplicate_record` -- the reader's collapse, which the framer must not
    anticipate. Across **two** chunks they are two calls, so they are two
    records and no diagnostic, and the second is the `Builder`'s refusal (§4),
    not the framer's problem.

    A `self._seen` set inside `Framer` would pass the second half by passing
    nothing on: it returns one record both ways and makes the
    `duplicate_record` disappear -- a diagnostic lost, which is standing rule 5
    and not only spec prose. Nothing in the suite caught that before this test
    (`patches/REVIEW-2026-10-04.md` R1-4), because no corpus rendering holds a
    byte-identical duplicate line and every hand-authored fixture here uses
    distinct records.
    """
    line = b'{"trace_id":"t1","span_id":"s1"}\n'

    one_chunk = Framer().push(line + line)
    assert len(one_chunk.records) == 1
    assert [d.code for d in one_chunk.diagnostics] == ["duplicate_record"]

    framer = Framer()
    first, second = framer.push(line), framer.push(line)
    assert len(first.records) == 1
    assert len(second.records) == 1
    assert second.records == first.records
    assert first.diagnostics == ()
    assert second.diagnostics == ()


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

    Two malformed lines in one chunk, read as lines **9 and 10** of the stream
    and as lines 1 and 2 of the call -- so the tuple is sorted by the numbers
    the receiver hands over, not by the ones the reader used.

    Crossing the 9 -> 10 digit boundary is the whole point of the fixture, and
    it is why there are eight good lines and not nine. The order is by message,
    and `"line 10 ..."` sorts **before** `"line 9 ..."`, so the sorted tuple is
    the reverse of the order the lines arrived in: a framer that renumbered and
    handed the tuple back unsorted fails here. With nine good lines the two
    malformed ones are 10 and 11, whose order is the same either way, and the
    test passed with the sort removed (`patches/REVIEW-2026-10-04.md` R1-3).
    """
    good = stream_of_records(8)
    body = good + b'{"oops\n{"nope\n'

    framer = Framer()
    framer.push(good)
    result = framer.push(b'{"oops\n{"nope\n')

    messages = [d.message for d in result.diagnostics]
    assert len(messages) == 2
    assert messages == sorted(messages)
    assert messages[0].startswith("line 10 ")
    assert messages[1].startswith("line 9 ")
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
    """Why `document` is a method and not a flag -- the trap (`SPEC.md` §3.3).

    The reader's container detection is **per call** (`SPEC.md` §2.1, §2.2), so
    both halves of this are true at once, and together they are a trap rather
    than a rule:

    - a body that happens to arrive **whole** reads exactly as `document` reads
      it -- same records, no diagnostic -- so a caller who pushes bodies is
      green on every body small enough to arrive in one piece;
    - the same body pushed in **chunks** is gone: each call sees a run of lines
      that are not records and says so with a `malformed_record` apiece.

    The framer does not rejoin them. A framer that buffered until something
    parsed would be the library's own §2.1 rule reimplemented here,
    differently, and it would hold a tail forever on the ordinary line-delimited
    input it was given. `document` is immune because it never splits: the same
    bytes, one call. R6 hands POST bodies to `document`, never to `push`.
    """
    body = rendering.read_bytes()
    assert body.count(b"\n") > 1, "a pretty-printed document, not one line"

    # The half that makes it a trap: whole, it reads, and it reads identically.
    whole = read_records(body)
    arrived_whole = framed([body])
    assert records_of(arrived_whole) == whole.records
    assert diagnostics_of(arrived_whole) == []
    assert Framer().document(body) == whole

    chunks = chunked(body, seed=SEEDS[0])
    assert len(chunks) > 1, "a one-chunk framing would prove nothing here"
    chunked_results = framed(chunks)
    assert records_of(chunked_results) == ()
    assert {d.code for d in diagnostics_of(chunked_results)} == {"malformed_record"}

    assert Framer().document(body).records == whole.records


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


# --------------------------------------------------------------------------
# The remainder's cap is the caller's number (`SPEC.md` §3.4).
# --------------------------------------------------------------------------

# Small on purpose: the cap is a policy, and a test that needed a megabyte to
# cross it would be asserting the policy rather than the mechanism.
CAP = 64

# A fragment of a line, with no `\n` anywhere in it, longer than CAP.
OVERSIZE = b'{"trace_id":"t1","span_id":"' + b"s" * CAP
GOOD_LINE = b'{"trace_id":"t1","span_id":"s1"}\n'


def test_the_cap_is_a_keyword_the_caller_sets_and_defaults_to_no_cap():
    """`None` by default, and never positional (`SPEC.md` §3.1, §3.4).

    The default is the whole of the receiver's position on it: how many bytes of
    an unterminated line are too many is the caller's policy, and a number
    chosen here would be the receiver carrying one of its own (`CLAUDE.md`
    standing rule 2). Keyword-only for the reason `Router`'s settings are: a
    positional slot is a reading order, and `SPEC.md` never offered one.
    """
    assert Framer().max_pending_bytes is None
    assert Framer(max_pending_bytes=CAP).max_pending_bytes == CAP
    with pytest.raises(TypeError):
        Framer(CAP)  # type: ignore[misc]


def test_a_cap_of_zero_reads_every_remainder_the_moment_it_exists():
    """§3.4's stated boundary, which nothing held (`REVIEW-2026-10-06.md` F9).

    `0` is legal — the spec and the CHANGELOG both say so — and it is the one
    cap value where `>` and `>=` differ in their *consequence* rather than by a
    byte: at `0` every remainder is over the cap, so a push that completes no
    line hands its bytes to the reader immediately rather than keeping them.
    The framer is then holding nothing, and the next chunk is a line of its own
    rather than the tail of that one.
    """
    framer = Framer(max_pending_bytes=0)
    assert framer.max_pending_bytes == 0

    result = framer.push(b"ab")

    assert result.records == ()
    assert [d.code for d in result.diagnostics] == ["malformed_record"]
    assert [d.source for d in result.diagnostics] == ["ab"]
    assert result.skipped_records == 1
    (event,) = framer.events
    assert (event.code, event.line, event.length) == (FRAGMENT_TOO_LONG, 1, 2)
    assert framer.pending_bytes == 0

    # And an empty remainder is not a fragment: a complete line leaves nothing
    # behind, so there is nothing for the cap to be about and no event.
    framer = Framer(max_pending_bytes=0)
    assert framer.push(GOOD_LINE).skipped_records == 0
    assert framer.events == ()
    assert framer.counts == {}


@pytest.mark.parametrize("cap", [-1, -64])
def test_a_negative_cap_is_refused_rather_than_read_as_zero(cap):
    """A cap below zero is a `ValueError` at construction (`SPEC.md` §3.4).

    The run-2 review recorded it as "spec-silent and behaves as `0`"; it does
    not. `len(pending) <= -1` is false for the **empty** remainder too, so a
    negative cap reports a `fragment_too_long` of length 0 on every push that
    ends on a line boundary and burns a line number doing it — which would make
    the framer's own line numbers wrong for a reason no caller asked for
    (§3.4's cost, §3.5's agreement). There is no reading of "the most the
    framer will keep" under which a negative number is a quantity, so it is
    refused where `Subscriptions.subscribe(every=0)` is refused and for the
    same reason: nothing about the stream caused it.
    """
    with pytest.raises(ValueError, match="max_pending_bytes"):
        Framer(max_pending_bytes=cap)


def test_the_cap_is_the_most_the_framer_will_keep_so_the_boundary_is_strict():
    """A remainder exactly at the cap is one the caller allowed.

    `>` and not `>=`, asserted at the byte: at `CAP` bytes nothing has happened
    and the remainder is still pending, and the `CAP + 1`th byte is what trips
    it. A cap that fired one byte early would refuse a line the caller's own
    number permits, and nothing else in this file would notice.
    """
    framer = Framer(max_pending_bytes=CAP)

    assert framer.push(b"x" * CAP) == Records(
        records=(), diagnostics=(), skipped_records=0
    )
    assert framer.pending_bytes == CAP
    assert framer.events == ()
    assert framer.counts == {}

    tripped = framer.push(b"x")
    assert [d.code for d in tripped.diagnostics] == ["malformed_record"]
    (event,) = framer.events
    assert event.length == CAP + 1
    assert framer.pending_bytes == 0


def test_a_fragment_past_the_cap_is_read_as_a_line_and_the_framer_continues():
    """At the cap the bytes are reported, and the stream goes on (§1.5, §3.4).

    The decision the receiver is allowed to make is *when to stop keeping*
    bytes, never whether to keep them at all. So the over-cap remainder goes to
    the reader as one line: it comes back as the `malformed_record` carrying its
    text -- the only place those bytes survive -- it is counted in
    `skipped_records`, and the `fragment_too_long` event says how long it was.

    The last two assertions are the ones that make it a cap rather than a wall.
    The framer is holding nothing afterwards, so the **next** chunk reads as an
    ordinary line: a cap that wedged the stream it capped, or that went on
    reporting the fragment it already reported, would be worse than no cap.
    """
    framer = Framer(max_pending_bytes=CAP)

    # Nothing yet: under the cap, an unterminated line is merely pending.
    assert framer.push(OVERSIZE[:CAP]) == Records(
        records=(), diagnostics=(), skipped_records=0
    )
    assert framer.events == ()

    result = framer.push(OVERSIZE[CAP:])

    assert result.records == ()
    assert [d.code for d in result.diagnostics] == ["malformed_record"]
    assert result.skipped_records == 1
    # Verbatim, which is what "never dropped" has to mean to mean anything.
    assert result.diagnostics[0].source == OVERSIZE.decode()
    assert result.diagnostics[0].message.startswith("line 1 ")

    (event,) = framer.events
    assert event.code == FRAGMENT_TOO_LONG == "fragment_too_long"
    assert event.length == len(OVERSIZE)
    assert event.line == 1
    assert str(CAP) in event.detail
    assert framer.counts == {FRAGMENT_TOO_LONG: 1}
    assert framer.pending_bytes == 0

    # And the framer continues: the next chunk is an ordinary line.
    carried_on = framer.push(GOOD_LINE)
    assert carried_on.records == read_records(GOOD_LINE).records
    assert carried_on.diagnostics == ()
    assert carried_on.skipped_records == 0
    assert framer.events == (), "events are the last call's, not a log"
    assert framer.counts == {FRAGMENT_TOO_LONG: 1}, "counts are the stream's"


def test_a_chunk_hands_over_its_complete_lines_before_its_over_cap_tail():
    """One push, two reads, one result -- and the records are not lost.

    A chunk can both complete lines and leave an over-cap tail. The lines are
    the reader's as usual and the tail is cut loose in the same push, so the
    caller gets one `Records` carrying both: the record, the fragment's
    `malformed_record`, and the skip. A framer that cut the tail loose *instead*
    of reading the chunk would lose a record it had whole.
    """
    framer = Framer(max_pending_bytes=CAP)
    result = framer.push(GOOD_LINE + OVERSIZE)

    assert result.records == read_records(GOOD_LINE).records
    assert [d.code for d in result.diagnostics] == ["malformed_record"]
    assert result.skipped_records == 1
    assert result.diagnostics[0].source == OVERSIZE.decode()

    (event,) = framer.events
    assert event.length == len(OVERSIZE)
    # Line 1 was the good line, so the fragment is line 2 of the stream.
    assert event.line == 2
    assert result.diagnostics[0].message.startswith("line 2 ")
    assert framer.pending_bytes == 0


def test_every_byte_of_an_endless_line_is_accounted_for_and_none_is_dropped():
    """The cap never loses a byte, however long the line that hit it.

    A stream that sends no `\\n` at all, in chunks that each cross the cap: the
    fragments come back one per crossing, and **concatenating the text of every
    `malformed_record` reproduces the input exactly**. That is the assertion the
    whole design of §3.4 exists to make true -- a framer that truncated, or that
    dropped the oversize remainder and carried on, keeps the records and the
    diagnostics it would have had and fails here on the bytes.

    `skipped_records` is summed as well, because it is the number a caller adds
    up (standing rule 5): one skip per fragment, never a silent zero.
    """
    stream = b"x" * (CAP * 5 + 7)
    chunks = [stream[i : i + CAP + 1] for i in range(0, len(stream), CAP + 1)]
    assert len(chunks) > 1, "a one-chunk stream would not test the carry-over"

    framer = Framer(max_pending_bytes=CAP)
    results = []
    events = []
    for chunk in chunks:
        results.append(framer.push(chunk))
        events.extend(framer.events)
    results.append(framer.flush())

    diagnostics = [d for result in results for d in result.diagnostics]
    assert {d.code for d in diagnostics} == {"malformed_record"}
    assert "".join(d.source or "" for d in diagnostics).encode() == stream
    assert sum(r.skipped_records for r in results) == len(diagnostics)
    assert all(r.records == () for r in results)
    assert framer.pending_bytes == 0

    # One event per crossing, every fragment but the flushed tail, and the
    # lengths they report are the bytes that were handed over -- all of them.
    assert len(events) == len(diagnostics) - 1 == framer.counts[FRAGMENT_TOO_LONG]
    assert [e.code for e in events] == [FRAGMENT_TOO_LONG] * len(events)
    assert [e.line for e in events] == list(range(1, len(events) + 1))
    flushed_tail = len(results[-1].diagnostics[0].source or "")
    assert sum(e.length for e in events) == len(stream) - flushed_tail


def test_the_cap_does_not_reach_a_document_or_the_flush_of_a_short_remainder():
    """The cap bounds a remainder, and a body is not one (`SPEC.md` §3.3).

    A body arrives whole or not at all, so there is nothing for a cap to bound
    and capping it would truncate an export the caller handed over complete. And
    `flush` reads whatever is left whatever its length, because that is what
    `flush` is for -- under a cap there is never more than the cap left to read,
    since `push` cut anything longer loose when it crossed.
    """
    body = b'{"resourceSpans":[{"scopeSpans":[{"spans":[{"traceId":"t1"}]}]}]}'
    assert len(body) > CAP
    framer = Framer(max_pending_bytes=CAP)
    assert framer.document(body) == read_records(body)
    assert framer.events == ()
    assert framer.counts == {}

    framer.push(TRUNCATED_TAIL)
    assert framer.pending_bytes == len(TRUNCATED_TAIL)
    flushed = framer.flush()
    assert [d.code for d in flushed.diagnostics] == ["malformed_record"]
    assert flushed.diagnostics[0].source == TRUNCATED_TAIL.decode()
    assert framer.events == ()
