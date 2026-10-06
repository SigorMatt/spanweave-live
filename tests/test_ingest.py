"""Ingest: a growing file and a stdin pipe, on a clock the test owns
(`SPEC.md` §7.1).

Every test here drives the tail's whole loop on a **fake clock**, and the file
is written only when the tail sleeps. That is the point of the `sleep` seam and
not a convenience: a tail tested against the real clock and a real file would be
asserting "the writer got there before the next poll", which is a property of
the machine, and the test would be tuned until it asserted nothing. Here
"the bytes appended between these two polls" is a thing the test states.

The load-bearing claims of this file:

- **A corpus rendering appended in random chunks produces the graph gate A
  asserts.** Not a weaker comparison of this file's own: the rendering, the
  chunking and the byte-for-byte comparison are gate A's own helpers, imported
  (`tests/test_conformance.py`, `SPEC.md` §4.7). A tail that lost a byte, read
  one twice, or handed a partial line over would fail it.
- **Truncation and rotation are events**, counted, with the offset they
  happened at — and after each one the tail reads the *new* content from 0,
  which is the claim a tail that treated truncation as growth would fail by
  reading the middle of content nobody wrote there.
- **The bytes the framer was holding are reported, never joined** to the head of
  the new content (`SPEC.md` §1.5).
- **`sleep` is the caller's**, called with `poll_seconds`, and nothing here
  reads a clock of its own.
"""

from __future__ import annotations

import dataclasses
import random
from pathlib import Path

import pytest
import spanweave

from spanweave_live import (
    REOPEN_FAILED,
    ROTATED,
    TRUNCATED,
    VANISHED,
    Event,
    Framer,
    Router,
    stdin,
    tail,
)
from tests import gates

# Gate A's own corpus helpers and its comparison, imported rather than
# reimplemented: a second rendering loader or a second graph comparison would be
# a weaker gate wearing the same name (`SPEC.md` §4.7).
from tests.test_conformance import (
    SEEDS,
    chunked,
    loaded,
    rendering_id,
    renderings,
    undigested,
)

POLL_SECONDS = 0.25

#: The two renderings the two-content tests use: two different scenarios, so the
#: second can be relabelled onto `zz1` and the two are two traces. Named rather
#: than "the first two", so a corpus change moves the test rather than quietly
#: changing what it compares.
FIRST = "llm_tool_llm/openinference.jsonl"
SECOND = "single_tool_call/openinference.jsonl"


def jsonl() -> list[Path]:
    """Every line-delimited corpus rendering: what a tail or a pipe delivers."""
    return [path for path in renderings() if path.suffix == ".jsonl"]


def by_id(wanted: str) -> Path:
    for path in renderings():
        if rendering_id(path) == wanted:
            return path
    raise AssertionError(f"the corpus no longer holds {wanted}")


class Clock:
    """A clock the test owns, as `tests/test_completion.py`'s is.

    The start is an arbitrary non-zero reading, so an event measuring a duration
    against `0.0` by accident is visible.
    """

    def __init__(self, at: float = 1_000.0) -> None:
        self.reading = at
        self.reads = 0

    def __call__(self) -> float:
        self.reads += 1
        return self.reading

    def tick(self, seconds: float) -> None:
        self.reading += seconds


class Driver:
    """The world, which moves only when the tail sleeps.

    One scripted action per sleep — append these bytes, truncate the file,
    rotate it — so what the tail sees between two polls is written down in the
    test and not decided by the operating system. When the script is spent the
    driver counts quiet polls and `done` stops the tail, which is the `until`
    the tail takes rather than a timeout of its own.
    """

    def __init__(self, clock: Clock, actions, *, stop_after: int = 2) -> None:
        self.clock = clock
        self.actions = list(actions)
        self.stop_after = stop_after
        self.slept: list[float] = []
        self.quiet = 0

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.clock.tick(seconds)
        if self.actions:
            self.actions.pop(0)()
        else:
            self.quiet += 1

    def done(self) -> bool:
        return not self.actions and self.quiet >= self.stop_after


def appends(path: Path, data: bytes):
    def action() -> None:
        with path.open("ab") as handle:
            handle.write(data)

    return action


def truncates(path: Path):
    def action() -> None:
        path.write_bytes(b"")

    return action


def rotates(path: Path, to: Path, *, wrote: bytes, then: bytes):
    """What a log rotator does: rename the file, then write a new one at the path.

    `wrote` is appended to the file **before** the rename, in the same action, so
    those bytes are in the old inode and unread when the path stops naming it: a
    tail that reopened before draining would lose them.
    """

    def action() -> None:
        with path.open("ab") as handle:
            handle.write(wrote)
        path.rename(to)
        path.write_bytes(then)

    return action


def unlinks(path: Path):
    def action() -> None:
        path.unlink()

    return action


def rotates_onto_something_unopenable(path: Path, to: Path, *, wrote: bytes):
    """A rotation whose replacement cannot be opened (`SPEC.md` §7.1).

    The path is renamed away and a **directory** takes its place, so
    `path.stat()` answers with a different `(st_dev, st_ino)` — the rotation is
    real — and `open("rb")` on it raises `IsADirectoryError`. A directory rather
    than a permission bit because a bit that root ignores would make the test a
    property of who runs it.
    """

    def action() -> None:
        with path.open("ab") as handle:
            handle.write(wrote)
        path.rename(to)
        path.mkdir()

    return action


def reverts(path: Path, held: Path):
    """The directory goes, and the file the tail still holds names the path again."""

    def action() -> None:
        path.rmdir()
        held.rename(path)

    return action


class Drain:
    """One tail, run to its stop, with every yield and its events kept.

    The events are read **between** yields, which is the protocol `SPEC.md` §7.1
    states: `events` is what happened since the previous yield, so a test that
    read them at the end would see only the last one's.
    """

    def __init__(self, source, *, router: Router | None = None) -> None:
        self.source = source
        self.router = Router() if router is None else router
        self.yields: list[spanweave.Records] = []
        self.events: list[tuple[Event, ...]] = []

    def run(self) -> Drain:
        for records in self.source:
            self.yields.append(records)
            self.events.append(getattr(self.source, "events", ()))
            for record in records.records:
                self.router.route(record)
        return self

    @property
    def flat(self) -> list[Event]:
        return [event for batch in self.events for event in batch]

    def absorb(self, framer: Framer) -> Drain:
        """What a caller whose own stop is end of input does (`SPEC.md` §7.1)."""
        for record in framer.flush().records:
            self.router.route(record)
        return self

    def graph(self, trace_id: str) -> str:
        builder = self.router.builder(trace_id)
        assert builder is not None, f"nothing routed to {trace_id}"
        return spanweave.dumps(undigested(builder.graph()))


def tailing(path: Path, driver: Driver, framer: Framer, **kwargs):
    return tail(
        path,
        now=driver.clock,
        sleep=driver.sleep,
        poll_seconds=POLL_SECONDS,
        framer=framer,
        until=driver.done,
        **kwargs,
    )


# --------------------------------------------------------------------------
# The claim: a file appended in random chunks is the graph gate A asserts.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_a_rendering_appended_in_random_chunks_is_the_graph_gate_a_asserts(
    tmp_path: Path, seed: int
) -> None:
    """Every line-delimited corpus rendering, written to a file the tail follows.

    The chunking is gate A's `chunked`, seeded, so the cuts land mid-line, mid
    token and mid multi-byte character; the comparison is gate A's, byte for
    byte against `spanweave.build` of the same rendering. What this adds to gate
    A is the **file**: the bytes arrive through `open`, `read` and a poll loop
    rather than from a `bytes` the test already held.
    """
    for path in jsonl():
        rendering = loaded(path, second=False)
        file = tmp_path / "trace.jsonl"
        file.write_bytes(b"")
        clock = Clock()
        pieces = chunked(rendering.data, random.Random(seed))
        driver = Driver(clock, [appends(file, piece) for piece in pieces])
        framer = Framer()
        source = tailing(file, driver, framer)
        drain = Drain(source).run().absorb(framer)

        where = f"{rendering_id(path)} @ seed {seed}"
        assert drain.flat == [], f"{where}: unexpected events {drain.flat}"
        assert source.counts == {}, where
        assert source.offset == len(rendering.data), where
        assert framer.pending_bytes == 0, where
        assert drain.graph(rendering.trace_id) == rendering.graph, (
            f"{where}: the tailed file does not produce spanweave.build's graph"
        )
        assert driver.slept == [POLL_SECONDS] * len(driver.slept), where
        assert clock.reading == 1_000.0 + POLL_SECONDS * len(driver.slept), where


def test_the_tail_reads_in_chunk_bytes_and_yields_every_read(tmp_path: Path) -> None:
    """A read smaller than what is waiting is many reads, and every one yields.

    `chunk_bytes=7` makes the file's own writes and the tail's reads disagree,
    which is the ordinary case for a real file and the one a tail that assumed
    "one write, one read" would get wrong. A yield that completed no line is
    still a yield: "nothing arrived" and "nothing was completed" are different
    answers, and `pending_bytes` is where the second is visible.
    """
    rendering = loaded(by_id(FIRST), second=False)
    file = tmp_path / "trace.jsonl"
    file.write_bytes(b"")
    clock = Clock()
    driver = Driver(clock, [appends(file, rendering.data)])
    framer = Framer()
    source = tailing(file, driver, framer, chunk_bytes=7)
    drain = Drain(source).run().absorb(framer)

    assert source.reads == -(-len(rendering.data) // 7)
    assert len(drain.yields) == source.reads
    assert any(not records.records for records in drain.yields), (
        "a 7-byte read that completed no line must still be a yield"
    )
    assert drain.graph(rendering.trace_id) == rendering.graph


# --------------------------------------------------------------------------
# Truncation.
# --------------------------------------------------------------------------


def test_truncation_restarts_from_zero_and_is_an_event(tmp_path: Path) -> None:
    """The file is emptied, then holds a different trace, and both graphs are right.

    The second trace's graph is the assertion that matters: a tail that treated
    truncation as ordinary growth would keep reading at the old offset, so it
    would read either nothing at all or the middle of content nobody wrote
    there, and this trace's graph would not be `spanweave.build`'s.
    """
    first = loaded(by_id(FIRST), second=False)
    second = loaded(by_id(SECOND), second=True)
    file = tmp_path / "trace.jsonl"
    file.write_bytes(b"")
    clock = Clock()
    driver = Driver(
        clock,
        [
            appends(file, first.data),
            truncates(file),
            appends(file, second.data),
        ],
    )
    framer = Framer()
    source = tailing(file, driver, framer)
    drain = Drain(source).run().absorb(framer)

    assert source.counts == {TRUNCATED: 1}
    (event,) = drain.flat
    assert event.code == TRUNCATED
    assert event.offset == len(first.data), "the offset the content was lost at"
    assert event.index == 1, "one chunk had been handed over when it happened"
    assert event.trace_id is None and event.spanweave_code is None
    assert event.version is None
    # Two polls had gone by when the truncation was seen: one that found an
    # empty file, one that read it after the first append. Deterministic
    # because the clock moves only when the tail sleeps.
    assert event.seconds == pytest.approx(2 * POLL_SECONDS)
    assert str(file) in event.detail

    assert source.offset == len(second.data), "read from 0, not from the old offset"
    assert sorted(drain.router.trace_ids) == ["t1", "zz1"]
    assert drain.graph(first.trace_id) == first.graph
    assert drain.graph(second.trace_id) == second.graph


def test_the_remainder_at_a_truncation_is_reported_not_joined_to_the_new_content(
    tmp_path: Path,
) -> None:
    """A half-written line, then truncation: the bytes come back as themselves.

    The last line is cut mid-record, so the framer is holding a fragment when
    the file is emptied. It belongs to content that no longer exists, so it is
    **flushed** — one `malformed_record` carrying its text, counted in
    `skipped_records`, which is the only place those bytes survive — and the
    first line of the new content is read as its own line. A tail that kept the
    remainder would hand the reader one line made of two files, and the record
    it produced would be a record nobody wrote.
    """
    first = loaded(by_id(FIRST), second=False)
    second = loaded(by_id(SECOND), second=True)
    lines = first.data.splitlines(keepends=True)
    half = b"".join(lines[:-1]) + lines[-1][: len(lines[-1]) // 2]
    assert not half.endswith(b"\n"), "the framer must be left holding a fragment"
    file = tmp_path / "trace.jsonl"
    file.write_bytes(b"")
    clock = Clock()
    driver = Driver(
        clock,
        [appends(file, half), truncates(file), appends(file, second.data)],
    )
    framer = Framer()
    source = tailing(file, driver, framer)
    drain = Drain(source).run().absorb(framer)

    assert source.counts == {TRUNCATED: 1}
    at_truncation = [
        records
        for records, events in zip(drain.yields, drain.events, strict=True)
        if any(event.code == TRUNCATED for event in events)
    ]
    assert len(at_truncation) == 1
    assert at_truncation[0].skipped_records == 1, "the fragment, read as a line"
    assert [d.code for d in at_truncation[0].diagnostics] == ["malformed_record"]
    assert framer.pending_bytes == 0
    assert drain.graph(second.trace_id) == second.graph, (
        "the new content's first line was joined to the old content's last"
    )


# --------------------------------------------------------------------------
# Rotation.
# --------------------------------------------------------------------------


def test_rotation_reopens_by_path_and_loses_nothing_the_old_file_held(
    tmp_path: Path,
) -> None:
    """The path is renamed and a new file takes its place.

    The old file's bytes are written in the **same action** as the rename, so
    they are unread when the path stops naming that inode: the tail must drain
    the handle it holds before it reopens, or those records are gone. Both
    traces' graphs are then what `spanweave.build` says, which is the whole
    claim — and `rotated` says where.
    """
    first = loaded(by_id(FIRST), second=False)
    second = loaded(by_id(SECOND), second=True)
    file = tmp_path / "trace.jsonl"
    file.write_bytes(b"")
    clock = Clock()
    driver = Driver(
        clock,
        [
            rotates(
                file,
                tmp_path / "trace.jsonl.1",
                wrote=first.data,
                then=second.data,
            )
        ],
    )
    framer = Framer()
    source = tailing(file, driver, framer)
    drain = Drain(source).run().absorb(framer)

    assert source.counts == {ROTATED: 1}
    (event,) = drain.flat
    assert event.code == ROTATED
    assert event.offset == len(first.data)
    assert event.trace_id is None and event.spanweave_code is None
    assert source.offset == len(second.data)
    assert sorted(drain.router.trace_ids) == ["t1", "zz1"]
    assert drain.graph(first.trace_id) == first.graph, (
        "the bytes the old inode held when the path was renamed"
    )
    assert drain.graph(second.trace_id) == second.graph


def test_a_rotation_the_old_handle_still_owes_bytes_for_is_not_seen_yet(
    tmp_path: Path,
) -> None:
    """Rotation is detected on the first poll that reads nothing, and not before.

    Stated as a test because it is the mechanism that makes the previous test
    true, and because it costs one poll: the tail asks the path who it is only
    once the handle it holds has gone quiet.
    """
    first = loaded(by_id(FIRST), second=False)
    file = tmp_path / "trace.jsonl"
    file.write_bytes(b"")
    clock = Clock()
    driver = Driver(
        clock,
        [rotates(file, tmp_path / "trace.jsonl.1", wrote=first.data, then=b"")],
    )
    framer = Framer()
    source = tailing(file, driver, framer)
    before = []
    for records in source:
        before.append((len(records.records), source.counts.get(ROTATED, 0)))
    reads, seen = zip(*before, strict=True)
    assert sum(reads) > 0, "the old file's records were read"
    assert seen[: len(reads) - 1] == tuple([0] * (len(reads) - 1)), (
        "no rotation was claimed while the old handle still had bytes"
    )
    assert source.counts == {ROTATED: 1}


# --------------------------------------------------------------------------
# A path that names nothing.
# --------------------------------------------------------------------------


def test_a_rotation_that_cannot_be_reopened_keeps_the_handle_and_says_so(
    tmp_path: Path,
) -> None:
    """`reopen_failed`: specified, exported, and until now untested.

    Deleting the whole `except OSError` body left the suite green
    (`patches/REVIEW-2026-10-06.md` F10), so this is the test that holds the
    three things §7.1 promises about it: the replacement is opened **before**
    the old handle is closed, so a failure leaves the tail reading what it
    already had; the event carries the `offset` it had reached; and it is
    reported **once per failure** rather than once per poll.

    The rendering is split across the rotation on purpose: the first half is in
    the old inode when the path stops naming it and the second half is appended
    to that same inode afterwards. Both halves reach the graph only if the tail
    is still reading the handle it holds, so `first.graph` is the assertion that
    "keeps reading what it had" is true rather than merely said.
    """
    first = loaded(by_id(FIRST), second=False)
    cut = len(first.data) // 2
    file = tmp_path / "trace.jsonl"
    held = tmp_path / "trace.jsonl.1"
    file.write_bytes(b"")
    clock = Clock()
    driver = Driver(
        clock,
        [
            rotates_onto_something_unopenable(file, held, wrote=first.data[:cut]),
            appends(held, first.data[cut:]),
        ],
        stop_after=4,
    )
    framer = Framer()
    source = tailing(file, driver, framer)
    drain = Drain(source).run().absorb(framer)

    assert source.counts == {REOPEN_FAILED: 1}, "once per failure, not once per poll"
    (event,) = drain.flat
    assert event.code == REOPEN_FAILED
    assert event.offset == cut, "where in the old content the tail had read to"
    assert event.trace_id is None and event.spanweave_code is None
    assert "keeps reading the handle it has" in event.detail
    assert driver.quiet >= 4, "many polls found it unopenable, and said so once"
    assert source.offset == len(first.data), "the old handle was read to its end"
    assert drain.graph(first.trace_id) == first.graph


def test_a_second_distinct_reopen_failure_is_reported_again(tmp_path: Path) -> None:
    """Once per failure is once per **rotation**, as `vanished`'s is once per
    vanishing (`SPEC.md` §7.1).

    The streak flag was cleared only on a successful reopen, so a path that
    reverted to the file the tail still holds left it set forever and the next
    genuinely distinct rotation failure was silent — a dropped report, which
    §1.5 does not allow (`patches/REVIEW-2026-10-06.md` F10). Here the path is
    rotated onto a directory, reverted to the held file, and rotated onto a
    directory again: two rotations, two failures, two events.
    """
    file = tmp_path / "trace.jsonl"
    held = tmp_path / "trace.jsonl.1"
    file.write_bytes(b"")
    clock = Clock()
    driver = Driver(
        clock,
        [
            rotates_onto_something_unopenable(file, held, wrote=b""),
            reverts(file, held),
            rotates_onto_something_unopenable(file, held, wrote=b""),
        ],
        stop_after=3,
    )
    framer = Framer()
    source = tailing(file, driver, framer)
    drain = Drain(source).run()

    assert source.counts == {REOPEN_FAILED: 2}
    assert [event.code for event in drain.flat] == [REOPEN_FAILED, REOPEN_FAILED]
    assert all(event.offset == 0 for event in drain.flat)


def test_a_vanished_path_is_one_event_and_the_open_handle_is_still_read(
    tmp_path: Path,
) -> None:
    """`rm` on a tailed file: the handle is still the file, and silence is no answer.

    Reported **once per vanishing**, not once per poll: how many times the path
    disappeared is a fact about the file, and how many polls found it gone is a
    fact about the caller's `poll_seconds`. The second number would grow without
    bound and say nothing (`SPEC.md` §4.6, §7.1).
    """
    first = loaded(by_id(FIRST), second=False)
    file = tmp_path / "trace.jsonl"
    file.write_bytes(b"")
    clock = Clock()
    driver = Driver(
        clock,
        [appends(file, first.data), unlinks(file)],
        stop_after=5,
    )
    framer = Framer()
    source = tailing(file, driver, framer)
    drain = Drain(source).run().absorb(framer)

    assert source.counts == {VANISHED: 1}, "once per vanishing, not once per poll"
    (event,) = drain.flat
    assert event.code == VANISHED
    assert event.offset is None, "there is no offset in the path's absence"
    assert driver.quiet >= 5, "many polls found it gone, and said so once"
    assert drain.graph(first.trace_id) == first.graph


# --------------------------------------------------------------------------
# stdin.
# --------------------------------------------------------------------------


class Pieces:
    """A binary stream that hands over exactly these chunks, then EOF.

    `read(n)` is allowed to return fewer than `n` bytes, which is what a pipe
    does, so the chunking stays the test's seeded business and `chunk_bytes`
    cannot quietly become what the test is measuring.
    """

    def __init__(self, pieces) -> None:
        self.pieces = list(pieces)
        self.reads = 0

    def read(self, size: int = -1) -> bytes:
        self.reads += 1
        return self.pieces.pop(0) if self.pieces else b""


@pytest.mark.parametrize("seed", SEEDS)
def test_stdin_reads_to_eof_and_is_the_graph_gate_a_asserts(seed: int) -> None:
    """Every line-delimited rendering through a pipe, in seeded chunks."""
    for path in jsonl():
        rendering = loaded(path, second=False)
        pieces = chunked(rendering.data, random.Random(seed))
        stream = Pieces(pieces)
        framer = Framer()
        drain = Drain(stdin(stream, framer=framer)).run()

        where = f"{rendering_id(path)} @ seed {seed}"
        assert len(drain.yields) == len(pieces) + 1, f"{where}: one yield per read"
        assert framer.pending_bytes == 0, where
        assert drain.graph(rendering.trace_id) == rendering.graph, where


def test_stdin_flushes_at_eof_because_eof_is_end_of_input() -> None:
    """A last line with no `\\n` is a record, and it arrives in the final yield.

    A tail's stop is the caller's `until` and is **not** end of input, so a tail
    does not flush. EOF is, so `stdin` does — and the record that only the flush
    can produce is the proof.
    """
    rendering = loaded(by_id(FIRST), second=False)
    assert rendering.data.endswith(b"\n")
    stream = Pieces([rendering.data.rstrip(b"\n")])
    framer = Framer()
    drain = Drain(stdin(stream, framer=framer)).run()

    assert len(drain.yields) == 2
    assert drain.yields[0].records and drain.yields[1].records, (
        "the last line had no terminator, so only the flush could read it"
    )
    assert framer.pending_bytes == 0
    assert drain.graph(rendering.trace_id) == rendering.graph


def test_stdin_yields_the_flush_even_when_the_remainder_was_empty() -> None:
    """The stream ended, which is the one thing a caller cannot read off a chunk."""
    rendering = loaded(by_id(FIRST), second=False)
    stream = Pieces([rendering.data])
    drain = Drain(stdin(stream)).run()

    assert len(drain.yields) == 2
    assert drain.yields[1] == spanweave.Records(
        records=(), diagnostics=(), skipped_records=0
    )


# --------------------------------------------------------------------------
# The seams, and the surface.
# --------------------------------------------------------------------------


def test_the_tail_sleeps_only_through_the_injected_seam(tmp_path: Path) -> None:
    """Every wait is the caller's `sleep`, called with the caller's `poll_seconds`.

    The clock is read, never advanced, by anything in the package: the driver is
    what moves it, and the only reason it moves at all in these tests is that
    the driver's `sleep` says so.
    """
    file = tmp_path / "trace.jsonl"
    file.write_bytes(b"")
    clock = Clock()
    driver = Driver(clock, [], stop_after=3)
    source = tail(
        file,
        now=clock,
        sleep=driver.sleep,
        poll_seconds=1.5,
        until=driver.done,
    )
    assert list(source) == []
    assert driver.slept == [1.5, 1.5, 1.5]
    assert clock.reading == 1_000.0 + 4.5
    assert source.polls == 3


def test_the_tail_settings_are_keyword_only(tmp_path: Path) -> None:
    """`now`, `sleep` and `poll_seconds` are seams, not a reading order."""
    file = tmp_path / "trace.jsonl"
    file.write_bytes(b"")
    clock = Clock()
    with pytest.raises(TypeError):
        tail(file, clock, lambda _seconds: None, 1.0)  # type: ignore[misc]


def test_an_unopenable_path_is_the_callers_error_and_not_an_event(
    tmp_path: Path,
) -> None:
    """Waiting for a file to appear is a retry policy, and the receiver has none.

    The first open is the caller's claim that there is a file there. Everything
    that happens to it **after** that is an event (`SPEC.md` §7.1, §1.2).
    """
    clock = Clock()
    driver = Driver(clock, [])
    source = tail(
        tmp_path / "nothing.jsonl",
        now=clock,
        sleep=driver.sleep,
        poll_seconds=1.0,
        until=driver.done,
    )
    with pytest.raises(FileNotFoundError):
        next(iter(source))


def test_the_ingest_events_are_routings_event_and_carry_no_new_field() -> None:
    """One `Event` type for the layers above framing (`SPEC.md` §3.1, §7.1).

    R2b split `FramingEvent` off because a framing event has a length and none
    of a routing event's facts. Ingest is **above** routing, so there is no
    upward import to avoid and the facts do fit — and `offset` is the one field
    it needed, added as R3 added `seconds` and R4 added `version`.

    The list is the whole of `Event`, so a field another section adds shows up
    here too: `at` is R3a's, the clock reading a `forgotten` is about
    (`SPEC.md` §5.5), and it is `None` on every ingest code. Ingest still added
    exactly one field, which is what this test is named for.
    """
    assert [field.name for field in dataclasses.fields(Event)] == [
        "code",
        "index",
        "trace_id",
        "spanweave_code",
        "detail",
        "seconds",
        "version",
        "offset",
        "at",
    ]


def test_ingest_needs_no_entry_in_the_seam_allowlist() -> None:
    """R5's seam question, asserted rather than asserted-about.

    `sleep` and `now` have **no defaults**, so no module under
    `spanweave_live/` imports `time` and the allowlist stays empty after this
    batch, as it did after R3 and R4 (`SPEC.md` §1.4, §5.2, §7.1). The real
    `time.sleep` is bound by R7's CLI.
    """
    source = gates.PACKAGE_ROOT / "ingest.py"
    assert source.exists()
    assert (
        gates.check_source(
            f"spanweave_live/{source.name}",
            source.read_text(encoding="utf-8"),
            gates.ALL_RULES,
        )
        == []
    )
    assert "ingest.py" not in gates.SEAMS, (
        "R5 added no seam entry: the caller supplies `sleep`. R7's `real.py` is "
        "the allowlist's one entry and this file is not it (SPEC.md 8.2)"
    )


def test_these_tests_run_on_both_platforms_the_section_claims() -> None:
    """Rotation and truncation are platform facts, so CI has to read them twice.

    `(st_dev, st_ino)` and `os.fstat(...).st_size` are the operating system's
    answers, not the receiver's (`SPEC.md` §7.1) — which is exactly why "the
    code is portable" is not a claim a one-OS test run can make. Until R5a the
    only macOS job ran `make conformance`, i.e. `tests/test_conformance.py`
    alone, so **this file had never run on macOS** while `WORKPLAN.md` §4 cited
    macOS for it (`patches/REVIEW-2026-10-06.md` F6, `WORKPLAN.md` §3,
    2026-10-06). CI gains a `check` job on `macos-latest`, which runs the whole
    suite including this file.

    Asserted here rather than in a CI-shaped test file because this is the
    section whose claim needs it, and a workflow that quietly loses the job
    should fail the test that depends on it.
    """
    workflow = (
        Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci.yml"
    ).read_text(encoding="utf-8")
    check = workflow[workflow.index("  check:") : workflow.index("  conformance:")]
    assert "macos-latest" in check, (
        "no macOS job runs `make check`, so tests/test_ingest.py runs on one OS"
    )
    assert "make check" in check


def test_a_tail_is_iterated_once(tmp_path: Path) -> None:
    """A second iteration would resume the first one's stream, looking like a start.

    The framer, the offset and the line count are the stream's, so there is no
    honest "again" to offer: one `Tail` per file, as one `Framer` per byte stream
    (`SPEC.md` §3.1, §7.1).
    """
    file = tmp_path / "trace.jsonl"
    file.write_bytes(b"")
    clock = Clock()
    driver = Driver(clock, [], stop_after=1)
    source = tail(
        file,
        now=clock,
        sleep=driver.sleep,
        poll_seconds=POLL_SECONDS,
        until=driver.done,
    )
    assert list(source) == []
    with pytest.raises(RuntimeError, match="already been iterated"):
        list(source)
