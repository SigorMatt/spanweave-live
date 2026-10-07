"""Gate A: how two traces were interleaved cannot be seen in either graph.

This is the claim the project exists to make (`CLAUDE.md`, Architecture;
`SPEC.md` §4.7). For **every pair of renderings drawn from two different corpus
scenarios**, one of the two relabelled onto a second trace id, the pair's
arrivals are interleaved by a seeded shuffle that preserves each rendering's own
order, pushed through one `Framer` in seeded chunks, and routed through one
`Router`. Each trace's `graph()` must then serialize **byte for byte** to
`spanweave.dumps` of `spanweave.build` of that rendering alone.

The corpus is the pinned `spanweave` repository's own `fixtures/conformance/`,
read through `corpus/` (`CLAUDE.md`). Its renderings are the inputs that define
what those bytes mean, so the gate compares the receiver against the library
over the library's own fixtures rather than over a stream this test wrote to
suit itself.

Every shuffle and every chunking is **seeded, in the test**, and the ten seeds
are written down. `random` is banned under `spanweave_live/` by the gate for
exactly this reason: the randomness belongs to the fixture, never to the
library.

What this gate does **not** catch is stated in `SPEC.md` §4.7 and tested in
`tests/test_routing.py`: a router that read `record["trace_id"]` would pass
here, because `spanweave.read_records` normalizes an OTLP container's `traceId`
to `trace_id` while unpacking it, so by the time a router sees a record every
corpus rendering answers a dialect read with what the adapter surface would have
said. A green gate A is not evidence about §1.1; it is evidence about
interleaving.
"""

from __future__ import annotations

import dataclasses
import itertools
import random
import re
from pathlib import Path

import pytest
import spanweave

from spanweave_live import Framer, Router

REPO = Path(__file__).resolve().parent.parent
CORPUS = REPO / "corpus" / "fixtures" / "conformance"

# Ten seeds, written down literally. An interleaving that exists only in one run
# is a gate that passed for a reason nobody can reproduce.
SEEDS = (0, 1, 2, 3, 7, 11, 13, 101, 1009, 20261004)

# What the corpus holds at the pinned sha. Asserted below, so a sweep that
# silently stops covering something fails rather than quietly getting smaller.
# `tests/test_pins.py` is what keeps the sha still.
SCENARIOS_EXPECTED = 29
RENDERINGS_EXPECTED = 53
PAIRS_EXPECTED = 1354

#: The trace id every corpus rendering uses, and the id one side of each pair is
#: moved to so that the two are two traces rather than one.
CORPUS_TRACE_ID = b'"t1"'
SECOND_TRACE_ID = b'"zz1"'

#: A trace-id **value** of `t1`, in either spelling a rendering uses: the
#: line-delimited dialects write `trace_id`, an OTLP container writes `traceId`.
#: Used only to prove the relabelling below touches nothing else.
A_TRACE_ID_VALUE = re.compile(rb'"(?:trace_id|traceId)"\s*:\s*"t1"')


def scenarios() -> list[Path]:
    return sorted(path for path in CORPUS.iterdir() if path.is_dir())


def renderings() -> list[Path]:
    """Every rendering in the corpus: `.jsonl` lines and `.json` documents."""
    return sorted(
        path
        for path in CORPUS.glob("*/dialects/*")
        if path.suffix in (".jsonl", ".json")
    )


def rendering_id(path: Path) -> str:
    return f"{path.parent.parent.name}/{path.name}"


def pairs() -> list[tuple[Path, Path]]:
    """Every pair of renderings from **two different** scenarios.

    Two renderings of one scenario are two spellings of the same trace, and
    pairing them would compare the receiver against itself about one graph.
    """
    return [
        (first, second)
        for first, second in itertools.combinations(renderings(), 2)
        if first.parent.parent != second.parent.parent
    ]


def relabelled(data: bytes) -> bytes:
    """`data` moved onto a second trace id, and nothing else changed.

    Every corpus rendering identifies the one trace `t1`, so two renderings fed
    to one router would share a builder and the gate would assert nothing. The
    move is a byte substitution of the token `"t1"`, and the premise that every
    occurrence of that token in the corpus **is** a trace-id value is asserted
    here on every call: a corpus where that stops being true fails loudly
    instead of quietly rewriting something else (`SPEC.md` §4.7).
    """
    occurrences = data.count(CORPUS_TRACE_ID)
    as_a_trace_id = len(A_TRACE_ID_VALUE.findall(data))
    assert occurrences == as_a_trace_id, (
        f"{occurrences} occurrences of {CORPUS_TRACE_ID!r} but only "
        f"{as_a_trace_id} of them are trace-id values; relabelling would "
        f"change something that is not a trace id"
    )
    assert occurrences > 0, "nothing to relabel: this rendering does not use t1"
    assert SECOND_TRACE_ID not in data
    return data.replace(CORPUS_TRACE_ID, SECOND_TRACE_ID)


def undigested(graph: spanweave.Graph) -> spanweave.Graph:
    """`graph` without the one field a `Builder` cannot carry.

    `meta.source_digest` fingerprints the input **bytes**, and a builder fed
    records never saw them (`spanweave` `SPEC.md` §10.4). It is dropped from the
    batch side and nothing else is normalized, on either side.
    """
    assert graph.meta is not None
    return dataclasses.replace(
        graph, meta=dataclasses.replace(graph.meta, source_digest=None)
    )


class Rendering:
    """One rendering's bytes, its trace id, and the graph it must produce."""

    __slots__ = ("arrivals", "data", "graph", "path", "trace_id")

    def __init__(self, path: Path, data: bytes) -> None:
        self.path = path
        self.data = data
        batch = spanweave.build(data)
        self.trace_id = batch.trace_id
        self.graph = spanweave.dumps(undigested(batch))
        self.arrivals = arrivals(path, data)


def arrivals(path: Path, data: bytes) -> tuple[tuple[str, bytes], ...]:
    """What reaches the receiver, in the order the exporter sent it.

    A `.jsonl` rendering arrives one line at a time, as a tail or a stdin pipe
    would deliver it; a `.json` rendering is one OTLP document and arrives
    whole, through `Framer.document`, because a document split across calls is
    lost (`SPEC.md` §3.3).
    """
    if path.suffix == ".json":
        return (("document", data),)
    return tuple(("line", line) for line in data.splitlines(keepends=True))


_LOADED: dict[tuple[Path, bool], Rendering] = {}


def loaded(path: Path, *, second: bool) -> Rendering:
    """One rendering, read and built once per session rather than per pair."""
    key = (path, second)
    if key not in _LOADED:
        data = path.read_bytes()
        _LOADED[key] = Rendering(path, relabelled(data) if second else data)
    return _LOADED[key]


def interleave(
    first: tuple[tuple[str, bytes], ...],
    second: tuple[tuple[str, bytes], ...],
    rng: random.Random,
) -> list[tuple[str, bytes]]:
    """Two arrival streams, shuffled together, each keeping its own order.

    Which is what interleaving is: two exporters writing to one transport can
    land in any relative order, and neither can reorder itself. Shuffling
    *within* a stream would be testing `spanweave`'s order-independence, which
    is `spanweave`'s own test and not this one.
    """
    picks = [0] * len(first) + [1] * len(second)
    rng.shuffle(picks)
    streams = (iter(first), iter(second))
    return [next(streams[pick]) for pick in picks]


def chunked(body: bytes, rng: random.Random) -> list[bytes]:
    """`body` cut into seeded chunks, one byte to the whole thing."""
    pieces: list[bytes] = []
    offset = 0
    while offset < len(body):
        size = rng.randint(1, len(body))
        pieces.append(body[offset : offset + size])
        offset += size
    return pieces


def replay(items: list[tuple[str, bytes]], rng: random.Random) -> Router:
    """One `Framer`, one `Router`, and the arrivals in the order given."""
    framer, router = Framer(), Router()
    for kind, body in items:
        if kind == "document":
            for record in framer.document(body).records:
                router.route(record)
            continue
        for chunk in chunked(body, rng):
            for record in framer.push(chunk).records:
                router.route(record)
    for record in framer.flush().records:
        router.route(record)
    assert framer.pending_bytes == 0
    return router


# --------------------------------------------------------------------------
# What the sweep covers, asserted rather than described.
# --------------------------------------------------------------------------


def test_the_corpus_is_the_size_the_sweep_claims():
    assert len(scenarios()) == SCENARIOS_EXPECTED
    assert len(renderings()) == RENDERINGS_EXPECTED
    assert len(pairs()) == PAIRS_EXPECTED
    documents = [path for path in renderings() if path.suffix == ".json"]
    assert len(documents) == 2, "the OTLP container renderings, framed whole"


def test_every_corpus_rendering_identifies_the_one_trace_the_relabelling_assumes():
    """The premise of the relabelling, swept over the whole corpus."""
    for path in renderings():
        rendering = loaded(path, second=False)
        assert rendering.trace_id == "t1", rendering_id(path)
        assert loaded(path, second=True).trace_id == "zz1", rendering_id(path)


def test_the_interleaving_actually_interleaves():
    """A helper that returned one stream then the other would assert nothing."""
    first = tuple(("line", bytes([n])) for n in range(10))
    second = tuple(("line", bytes([n])) for n in range(100, 110))
    mixed = 0
    for seed in SEEDS:
        items = interleave(first, second, random.Random(seed))
        assert len(items) == 20
        assert [item for item in items if item in first] == list(first)
        assert [item for item in items if item in second] == list(second)
        switches = sum(
            1
            for before, after in itertools.pairwise(items)
            if (before in first) != (after in first)
        )
        assert switches >= 2, f"seed {seed} barely interleaved"
        mixed += switches
    assert mixed >= 10 * len(SEEDS)


# --------------------------------------------------------------------------
# Gate A itself.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_interleaved_traces_produce_each_traces_own_batch_graph(seed: int) -> None:
    """Gate A, over every cross-scenario pair, at one seed.

    Parametrized by seed and not by pair: one test per pair would be more than
    thirteen thousand test ids for the same assertion, and a failure names its
    pair in the message either way.
    """
    checked = 0
    for first, second in pairs():
        a = loaded(first, second=False)
        b = loaded(second, second=True)
        rng = random.Random(seed)
        router = replay(interleave(a.arrivals, b.arrivals, rng), rng)

        where = f"{rendering_id(first)} + {rendering_id(second)} @ seed {seed}"
        assert router.counts == {}, f"{where}: unexpected events {router.counts}"
        assert sorted(router.trace_ids) == sorted({a.trace_id, b.trace_id}), (
            f"{where}: routed to {router.trace_ids}"
        )

        for rendering in (a, b):
            builder = router.builder(rendering.trace_id)
            assert builder is not None, f"{where}: no builder for {rendering.trace_id}"
            assert spanweave.dumps(undigested(builder.graph())) == rendering.graph, (
                f"{where}: trace {rendering.trace_id} does not match "
                f"spanweave.build of {rendering_id(rendering.path)}"
            )
            checked += 1
    assert checked == 2 * PAIRS_EXPECTED
