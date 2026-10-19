"""The zoo gate (V0): a stranger's twelve captures, live and batch, byte for byte.

`corpus/fixtures/zoo/` is the twelve captures of `SigorMatt/spanweave-zoo` --
six agents, each run once against a real model and once against a recorded
one, under stock instrumentation into a stock Collector -- copied into the
pinned `spanweave` byte for byte and held there by its own `tests/test_zoo.py`.
They arrive here through the `corpus/` submodule, read in place, never copied
(`CLAUDE.md`). The zoo's audit observed that live, batch and incremental were
equal (`PROBES.md` L3); this file is that observation made a gate the receiver
runs on every `make conformance` (`SPEC.md` §4.8).

For each capture its JSON bodies -- the Collector's OTLP/JSON of what the
exporter sent, in the order the manifest lists them -- go through one
`Framer.document` each and one `Router`, and the input ends as the CLI ends it:
the completion is replaced by one whose only policy is `Cap(0)` and ticked once
(`SPEC.md` §8.5). The graph that tick **writes** is then compared with the
batch side, `spanweave.dumps` of `spanweave.build` of the same records.

The batch side is one input, built through the public `build` and nothing
internal: every zoo body is a single line, so the capture's bodies joined by
newlines are one line-delimited stream of OTLP exports, which is the shape a
Collector's file exporter writes. That the join adds and loses nothing is
asserted rather than assumed -- `read_records` of the joined stream yields
exactly the records of the bodies read one at a time, so the reader's
per-call deduplication (`SPEC.md` §2.2) cannot hide a difference -- and the
one field a builder cannot carry, `meta.source_digest`, is dropped from the
batch side and nothing else is normalized (`SPEC.md` §4.7).

**All twelve rows are equal, and two of them because V2 moved them.** Z4's
root span is claimed by no adapter (the zoo's `PROBES.md` S1). Until V2 the
receiver routed it to the no-trace builder and the trace's graph held four of
the capture's five records (L2); since V2 an unpacked record no adapter claims
is routed by its envelope's trace id, read through `spanweave.envelope`
(`SPEC.md` §4.2), and the trace holds all five. §4.8's table names L2 on those
two rows as the reason they moved, and this file is where they did.

Beside the gate, the measurement V2 stops on: over every unpacked record a
claimant claims, in the corpus and the zoo, the claimant's trace id equals
the envelope's. Were one ever to differ, which of the two routes would be a
rule nobody has stated (`SPEC.md` §4.2 cites the count; this file derives it).

**And every capture is replayed again from its raw bodies** (V1, the zoo's
L1): the exporter's own `application/x-protobuf` bodies, each through
`Endpoint.handle` as its manifest states it, then the same router and tick.
Each is answered `200` with the zoo's count for its JSON pair, and the graph
written is the JSON replay's byte for byte -- on all twelve, Z4's two included,
because what the protobuf path is held to is the JSON path.
"""

from __future__ import annotations

import dataclasses
import json
import re
from functools import cache
from pathlib import Path
from typing import NamedTuple

import pytest
import spanweave
from spanweave.adapters import classify, get
from spanweave.read import Unpacked

from spanweave_live import (
    COMPLETED,
    TRACES_TARGET,
    Cap,
    Completed,
    Completion,
    Endpoint,
    Framer,
    Request,
    Router,
)

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "corpus" / "fixtures"
ZOO = FIXTURES / "zoo"
SPEC = REPO / "SPEC.md"

JSON_BODY = "application/json"

#: The media type the exporter's own bodies were sent with, as each manifest
#: records it. Spelled here rather than imported, so that a receiver without
#: the constant fails on the status it answers and not on an import.
RAW_BODY = "application/x-protobuf"

#: What the corpus holds at the pin: six briefs, two runs each.
CAPTURES_EXPECTED = 12

#: The captures on which the zoo's audit saw a trace complete once per body
#: under `--quiet 0` (`PROBES.md` L3): Z3, Z1, Z2 and Z6, the real runs.
L3_CAPTURES = (
    "z3/2026-10-13-real",
    "z1/2026-10-13-real",
    "z2/2026-10-14-real",
    "z6/2026-10-14-real",
)

#: The rows a batch of this series moved to "equal", each with the zoo's probe
#: that says why; §4.8's table carries the probe beside the `yes`. V0 pinned
#: these two at 4 of 5 nodes as `no (L2)`, and V2 moved them.
MOVED = {
    "z4/2026-10-12-real": "L2",
    "z4/2026-10-12-recorded": "L2",
}


def captures() -> list[str]:
    """Every capture under the zoo, as `<brief>/<run-id>`, sorted."""
    return sorted(
        path.parent.relative_to(ZOO).as_posix()
        for path in ZOO.glob("*/*/MANIFEST.json")
    )


def json_bodies(capture: str) -> list[bytes]:
    """The capture's JSON bodies, in the order its manifest lists them.

    The manifest names each as `json/NNNN.json`; the copy keeps it as
    `NNNN.json` beside the manifest (the zoo README).
    """
    manifest = json.loads((ZOO / capture / "MANIFEST.json").read_text("utf-8"))
    return [
        (ZOO / capture / Path(body["file"]).name).read_bytes()
        for body in manifest["bodies"]
        if body["content_type"] == JSON_BODY
    ]


def raw_requests(capture: str) -> list[Request]:
    """The capture's raw bodies as the exporter POSTed them, in `forwards` order.

    Each is the exporter's own OTLP protobuf body (`raw/NNNN.body`), stated as
    a `Request` with the media type and content coding its manifest entry
    records -- the headers the exporter sent, not ones this test chose. The
    order is the manifest's `forwards` list, the order the bodies reached the
    Collector, and the `k`-th of them is the one the `k`-th JSON body
    re-encodes (the corpus README, "The pairs"); that each pair shares its
    `NNNN` is asserted here rather than assumed, as the pinned library's
    `tests/test_zoo.py` asserts it.
    """
    manifest = json.loads((ZOO / capture / "MANIFEST.json").read_text("utf-8"))
    listed = {body["file"]: body for body in manifest["bodies"]}
    forwarded = [listed[forward["file"]] for forward in manifest["forwards"]]
    json_names = [
        Path(body["file"]).stem
        for body in manifest["bodies"]
        if body["content_type"] == JSON_BODY
    ]
    assert [Path(body["file"]).stem for body in forwarded] == json_names, capture
    return [
        Request(
            method="POST",
            target=TRACES_TARGET,
            body=(ZOO / capture / body["file"]).read_bytes(),
            content_type=body["content_type"],
            content_encoding=body["content_encoding"],
        )
        for body in forwarded
    ]


@cache
def zoo_records() -> dict[str, tuple[int, ...]]:
    """The zoo README's `Bodies (records)` column: capture -> records per body.

    These are the zoo's `PROBES.md` "The captures", which the pinned
    library's `tests/test_zoo.py` re-counts against the bytes. Read from the
    README rather than counted here, so the number this gate holds the router
    to is the zoo's, and not one the receiver's own reading produced.
    """
    table: dict[str, tuple[int, ...]] = {}
    row = re.compile(r"^\| `([^`]+)` \|[^|]*\|[^|]*\| (\d+) \(([\d, ]+)\) \|", re.M)
    for capture, count, per_body in row.findall((ZOO / "README.md").read_text("utf-8")):
        records = tuple(int(n) for n in per_body.split(","))
        assert len(records) == int(count), capture
        table[capture] = records
    return table


def undigested(graph: spanweave.Graph) -> spanweave.Graph:
    """`graph` without `meta.source_digest`, as gate A drops it (`SPEC.md` §4.7)."""
    assert graph.meta is not None
    return dataclasses.replace(
        graph, meta=dataclasses.replace(graph.meta, source_digest=None)
    )


class Replay(NamedTuple):
    per_body: tuple[int, ...]
    router: Router
    completed: tuple[Completed, ...]
    written: dict[str, bytes]
    batch: spanweave.Graph
    batch_bytes: bytes


@cache
def replay(capture: str, out: Path) -> Replay:
    """One capture through the receiver to end of input, and its batch side.

    `out` is a directory the caller made empty; the tick writes there. The
    clock is constant: nothing here is about time, and `Cap(0)` reads none.
    """
    framer = Framer()
    router = Router(completion=Completion(policies=(), now=lambda: 0.0, out_dir=out))
    per_body = []
    bodies = json_bodies(capture)
    for body in bodies:
        read = framer.document(body)
        per_body.append(len(read.records))
        for record in read.records:
            router.route(record)
    assert framer.pending_bytes == 0
    router.completion = Completion(policies=(Cap(0),), now=lambda: 0.0, out_dir=out)
    completed = router.tick()
    written = {path.name: path.read_bytes() for path in sorted(out.iterdir())}

    joined = b"\n".join(bodies) + b"\n"
    whole = spanweave.read_records(joined)
    one_at_a_time = [r for body in bodies for r in spanweave.read_records(body).records]
    assert list(whole.records) == one_at_a_time, f"{capture}: the join is not faithful"
    assert whole.skipped_records == 0
    batch = spanweave.build(joined)
    return Replay(
        tuple(per_body),
        router,
        completed,
        written,
        batch,
        spanweave.dumps(undigested(batch)),
    )


@pytest.fixture(scope="session")
def replayed(tmp_path_factory):
    def get(capture: str) -> Replay:
        out = tmp_path_factory.getbasetemp() / "zoo" / capture.replace("/", "_")
        out.mkdir(parents=True, exist_ok=True)
        return replay(capture, out)

    return get


class RawReplay(NamedTuple):
    statuses: tuple[int, ...]
    per_body: tuple[int, ...]
    endpoint: Endpoint
    router: Router
    completed: tuple[Completed, ...]
    written: dict[str, bytes]


@cache
def raw_replay(capture: str, out: Path) -> RawReplay:
    """The same capture again, from the bodies the exporter actually sent.

    Each raw body goes to `Endpoint.handle` as the `Request` its manifest
    states -- `application/x-protobuf`, the exporter's coding -- because the
    endpoint is the one path in the receiver that reads protobuf (`SPEC.md`
    §7.2). Everything after the endpoint is the JSON replay's: one `Router`,
    then the end-of-input `Cap(0)` tick, writing into `out`.
    """
    endpoint = Endpoint()
    router = Router(completion=Completion(policies=(), now=lambda: 0.0, out_dir=out))
    statuses, per_body = [], []
    for request in raw_requests(capture):
        exchange = endpoint.handle(request)
        statuses.append(exchange.response.status)
        per_body.append(len(exchange.records.records))
        for record in exchange.records.records:
            router.route(record)
    assert endpoint.framer.pending_bytes == 0
    router.completion = Completion(policies=(Cap(0),), now=lambda: 0.0, out_dir=out)
    completed = router.tick()
    written = {path.name: path.read_bytes() for path in sorted(out.iterdir())}
    return RawReplay(
        tuple(statuses), tuple(per_body), endpoint, router, completed, written
    )


@pytest.fixture(scope="session")
def raw_replayed(tmp_path_factory):
    def get(capture: str) -> RawReplay:
        out = tmp_path_factory.getbasetemp() / "zoo-raw" / capture.replace("/", "_")
        out.mkdir(parents=True, exist_ok=True)
        return raw_replay(capture, out)

    return get


# --------------------------------------------------------------------------
# What the gate covers, asserted rather than described.
# --------------------------------------------------------------------------


def test_the_zoo_is_the_twelve_captures_its_readme_counts():
    assert len(captures()) == CAPTURES_EXPECTED
    assert sorted(zoo_records()) == captures()
    assert set(L3_CAPTURES) <= set(captures())
    assert set(MOVED) <= set(captures())


@pytest.mark.parametrize("capture", captures())
def test_every_body_yields_the_records_the_zoo_counted_and_all_are_routed(
    capture, replayed
):
    run = replayed(capture)
    assert run.per_body == zoo_records()[capture]
    assert run.router.routed == sum(zoo_records()[capture])


# --------------------------------------------------------------------------
# The gate.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("capture", captures())
def test_end_of_input_completes_one_trace_and_writes_one_file(capture, replayed):
    run = replayed(capture)
    assert len(run.completed) == 1
    (done,) = run.completed
    assert done.policy == Cap(0)
    assert done.trace_id == run.batch.trace_id
    assert list(run.written) == [f"{done.trace_id}.json"]


@pytest.mark.parametrize("capture", captures())
def test_the_written_graph_is_the_batch_graph_byte_for_byte(capture, replayed):
    run = replayed(capture)
    (written,) = run.written.values()
    assert written == run.batch_bytes, capture
    assert run.router._no_trace is None, "nothing reached the no-trace builder"
    assert run.router.counts == {"completed": 1, "released": 1, "written": 1}


@pytest.mark.parametrize("capture", sorted(MOVED))
def test_z4_s_graph_holds_five_records_of_five_its_root_by_its_envelope(
    capture, replayed
):
    """The two rows V2 moved, and exactly what moved (L2).

    One record of five is claimed by no adapter. It was unpacked from an
    export, so the transport states its trace id, and the router reads that
    through `spanweave.envelope` (`SPEC.md` §4.2): all five reach the trace's
    builder, which is released at version 5. Its graph is five nodes -- the
    root an `unknown` node -- with four `parent` edges and no `orphan_parent`,
    which is the batch graph's account, byte for byte above. V0 pinned the same
    trace at four nodes, each of them an orphan.
    """
    run = replayed(capture)
    (done,) = run.completed
    assert done.graph is not None
    records = [
        r for body in json_bodies(capture) for r in spanweave.read_records(body).records
    ]
    unclaimed = [r for r in records if classify(r) == ()]
    assert (len(unclaimed), len(records)) == (1, 5)
    (root,) = unclaimed
    assert isinstance(root, Unpacked)
    assert spanweave.envelope(root).trace_id == done.trace_id

    assert done.version == 5
    assert run.router._no_trace is None
    graph = done.graph
    assert len(graph.nodes()) == 5
    assert [n.kind for n in graph.nodes()].count(spanweave.NodeKind.UNKNOWN) == 1
    assert len(graph.edges(spanweave.EdgeKind.PARENT)) == 4
    assert [d for d in graph.diagnostics if d.code == "orphan_parent"] == []


# --------------------------------------------------------------------------
# The raw replay: what a stock exporter sends is what the JSON replay wrote
# (V1, the zoo's L1).
# --------------------------------------------------------------------------


def test_the_zoo_s_raw_bodies_are_the_number_section_7_2_cites():
    """§7.2 cites how many raw bodies the zoo holds; this counts them."""
    spec = SPEC.read_text(encoding="utf-8")
    start = spec.index("### 7.2 ")
    end = spec.index("\n## ", start)
    (cited,) = set(re.findall(r"all (\d+) of the zoo's raw bodies", spec[start:end]))
    assert int(cited) == sum(len(raw_requests(c)) for c in captures())


@pytest.mark.parametrize("capture", captures())
def test_every_raw_body_is_served_and_routes_the_records_its_json_body_does(
    capture, replayed, raw_replayed
):
    """Each protobuf body is a `200` and yields the zoo's count for its pair.

    The count is the zoo's own (`zoo_records`), the same one the JSON replay
    is held to, so a raw body that is answered `200` and routed nothing -- or
    routed through the JSON reader, which reads protobuf as nothing but
    skipped lines -- fails here on the number and not only on a graph.
    """
    raw = raw_replayed(capture)
    assert raw.statuses == (200,) * len(zoo_records()[capture])
    assert raw.per_body == zoo_records()[capture] == replayed(capture).per_body
    assert raw.router.routed == replayed(capture).router.routed
    assert raw.endpoint.counts == {}


@pytest.mark.parametrize("capture", captures())
def test_the_raw_replay_writes_the_json_replay_s_graph_byte_for_byte(
    capture, replayed, raw_replayed
):
    """Raw replay equals JSON replay, on all twelve, Z4's two included.

    The comparison is with what the JSON replay **wrote**, whatever that is:
    on ten captures it is the batch graph, and on Z4's two it is the short
    graph §4.8 pins (L2). So this holds the protobuf path to the JSON path
    and nothing else, and V2's move of Z4 moves both sides together.
    """
    raw = raw_replayed(capture)
    assert len(raw.completed) == 1
    assert raw.written == replayed(capture).written


@pytest.mark.parametrize("capture", L3_CAPTURES)
def test_the_l3_captures_complete_once_at_the_last_index_and_orphan_nothing(
    capture, replayed
):
    """The audit's observation, now asserted (`PROBES.md` L3).

    Fed whole and completed at end of input, each of the four traces the audit
    saw complete once per body under `--quiet 0` completes **once**, at the
    tick after its last record, and its graph carries no `orphan_parent`: the
    early generations were the policy firing early, not the receiver losing
    parents (`SPEC.md` §5.5 reads that further).
    """
    run = replayed(capture)
    (done,) = run.completed
    assert done.graph is not None
    (decision,) = [event for event in done.events if event.code == COMPLETED]
    assert decision.index == run.router.routed == sum(zoo_records()[capture])
    assert done.version == run.router.routed
    assert not [d for d in done.graph.diagnostics if d.code == "orphan_parent"]


# --------------------------------------------------------------------------
# §4.8's table is this file's measurement, read rather than paraphrased.
# --------------------------------------------------------------------------


def declared_rows() -> dict[str, tuple[int, int, int, str]]:
    """§4.8's table: capture -> (bodies, routed, in the graph, batch-equal)."""
    spec = SPEC.read_text(encoding="utf-8")
    start = spec.index("### 4.8 ")
    end = spec.index("\n## ", start)
    rows: dict[str, tuple[int, int, int, str]] = {}
    for capture, bodies, routed, held, equal in re.findall(
        r"^\| `([^`]+)` \| (\d+) \| (\d+) \| (\d+) \| ([^|]+?) \|$",
        spec[start:end],
        re.M,
    ):
        rows[capture] = (int(bodies), int(routed), int(held), equal)
    return rows


def test_the_spec_s_zoo_gate_table_is_what_the_gate_measures(replayed):
    measured: dict[str, tuple[int, int, int, str]] = {}
    for capture in captures():
        run = replayed(capture)
        (done,) = run.completed
        (written,) = run.written.values()
        equal = "yes" if written == run.batch_bytes else "no"
        if capture in MOVED:
            equal = f"{equal} ({MOVED[capture]})"
        measured[capture] = (
            len(run.per_body),
            run.router.routed,
            done.version,
            equal,
        )
    assert declared_rows() == measured


def test_the_readme_s_zoo_sentence_is_what_the_gate_measures(replayed):
    """README says how many of the twelve are equal; this counts them."""
    words = {"two": 2, "ten": 10, "eleven": 11, "twelve": 12}
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    stated = re.search(r"All (\w+) are equal, Z4's (\w+) included", readme)
    assert stated is not None
    total, moved = stated.groups()
    measured = [
        next(iter(replayed(capture).written.values())) == replayed(capture).batch_bytes
        for capture in captures()
    ]
    assert words[total] == len(measured) == sum(measured)
    assert words[moved] == len(MOVED)


# --------------------------------------------------------------------------
# The measurement V2 stops on: the claimant and the envelope agree.
# --------------------------------------------------------------------------


class Agreement(NamedTuple):
    compared: int
    equal: int
    differing: int
    one_side_none: int
    conformance: int
    zoo_json: int
    zoo_raw: int


def claimed_unpacked(records: spanweave.Records) -> list[object]:
    """The records the reader unpacked from an export that one adapter claims."""
    return [
        r for r in records.records if isinstance(r, Unpacked) and len(classify(r)) == 1
    ]


@cache
def agreement() -> Agreement:
    """Every claimed unpacked record in the corpus and the zoo, asked two ways.

    The corpus is every rendering of `fixtures/conformance/` and every file of
    `fixtures/captured/`; the zoo is every capture's JSON bodies through
    `read_records` and its raw bodies through `read_protobuf`, so a record of
    the zoo is counted once per encoding. For each, the claimant's `parse`
    states one trace id or does not, and `spanweave.envelope` states one or
    refuses. The receiver's own `trace_id_of` is not asked: this measures the
    library's two answers, which is what the stop condition is about.
    """
    sources: list[tuple[str, spanweave.Records]] = []
    for path in sorted(FIXTURES.glob("conformance/*/dialects/*")):
        sources.append(("conformance", spanweave.read_records(path.read_bytes())))
    for path in sorted(FIXTURES.glob("captured/*.jsonl")):
        sources.append(("conformance", spanweave.read_records(path.read_bytes())))
    for capture in captures():
        for body in json_bodies(capture):
            sources.append(("zoo_json", spanweave.read_records(body)))
        for request in raw_requests(capture):
            sources.append(("zoo_raw", spanweave.read_protobuf(request.body)))
    tally = dict.fromkeys(Agreement._fields, 0)
    for where, records in sources:
        for record in claimed_unpacked(records):
            (claimant,) = classify(record)
            parsed = {s.trace_id for s in get(claimant).parse([record]) if s.trace_id}
            by_claimant = next(iter(parsed)) if len(parsed) == 1 else None
            try:
                by_envelope: str | None = spanweave.envelope(record).trace_id
            except spanweave.EnvelopeError:
                by_envelope = None
            tally["compared"] += 1
            tally[where] += 1
            if by_claimant is None or by_envelope is None:
                tally["one_side_none"] += 1
            elif by_claimant == by_envelope:
                tally["equal"] += 1
            else:
                tally["differing"] += 1
    return Agreement(**tally)


def test_every_claimant_s_trace_id_is_its_envelope_s():
    """V2's stop condition, measured: not one record where the two differ."""
    measured = agreement()
    assert measured.differing == 0
    assert measured.one_side_none == 0
    assert measured.equal == measured.compared > 0


def test_section_4_2_cites_the_agreement_this_file_measures():
    """§4.2 states the count; this re-derives every number in the sentence."""
    spec = SPEC.read_text(encoding="utf-8")
    start = spec.index("### 4.2 ")
    end = spec.index("\n### ", start + 1)
    stated = re.search(
        r"compared on \*\*(\d+)\*\* records \N{EM DASH} (\d+) from the corpus' "
        r"renderings, (\d+) from the zoo's JSON bodies and (\d+) from its raw "
        r"bodies \N{EM DASH} and are equal on (\d+), differ on (\d+), and on "
        r"(\d+) one side states no id",
        " ".join(spec[start:end].split()),
    )
    assert stated is not None
    measured = agreement()
    assert tuple(int(n) for n in stated.groups()) == (
        measured.compared,
        measured.conformance,
        measured.zoo_json,
        measured.zoo_raw,
        measured.equal,
        measured.differing,
        measured.one_side_none,
    )
