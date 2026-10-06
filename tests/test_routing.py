"""`Router`: one `spanweave.Builder` per trace (`SPEC.md` §4).

Two claims are load-bearing here and the rest of the file supports them.

The first is `test_a_record_no_adapter_claims_is_not_routed_by_its_trace_id_key`:
**the trace id comes from the adapter surface and not from a key.** It is the
one test in the project that tells the two apart, and it exists because gate A
cannot (`SPEC.md` §4.7): `spanweave.read_records` normalizes an OTLP container's
`traceId` to `trace_id` while unpacking it, so every corpus rendering answers a
dialect read with exactly what the adapter surface would have said. A record
nobody claims that nonetheless carries a `trace_id` key is where the two
disagree.

The second is that **nothing is dropped silently**: a refusal and a cap hit are
each an event with a code, counted, and routing continues (`SPEC.md` §1.5, §4.4,
§4.5).

No clock, no socket, no unseeded randomness: a `Router` is a pure function of
the records handed to it, in the order they were handed over.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import pathlib

import pytest
import spanweave

from spanweave_live import (
    REFUSED,
    REFUSED_AT_CAP,
    Event,
    Framer,
    Routed,
    Router,
    trace_id_of,
)

# --------------------------------------------------------------------------
# Hand-authored records. Small on purpose: the corpus is gate A's business
# (`tests/test_conformance.py`), and these exist to put the router in states
# the corpus does not contain.
# --------------------------------------------------------------------------


def openinference(
    span_id: str, *, trace: str = "t1", parent: str | None = None
) -> dict:
    """One OpenInference span, claimed by exactly one adapter."""
    record: dict = {
        "trace_id": trace,
        "span_id": span_id,
        "parent_id": parent,
        "name": f"chain.{span_id}",
        "start_time": 1000.0,
        "end_time": 1001.0,
        "attributes": {"openinference.span.kind": "CHAIN"},
    }
    return record


def unclaimable(span_id: str, *, trace: str = "t1") -> dict:
    """A record no registered adapter recognizes -- **and it names a trace.**

    The whole point of this shape: `classify` returns nothing for it, so the
    adapter surface says "no trace id", while `record["trace_id"]` says `t1`.
    A dialect read therefore files it under a trace; the adapter surface files
    it under no trace. That is the difference, and it is the only place in this
    project the two differ (`SPEC.md` §4.7).
    """
    return {"trace_id": trace, "span_id": span_id, "name": f"mystery.{span_id}"}


def ambiguous(span_id: str, *, trace: str = "t1") -> dict:
    """A record both shipped adapters claim, which the library refuses."""
    return {
        "trace_id": trace,
        "span_id": span_id,
        "name": "both",
        "attributes": {
            "openinference.span.kind": "LLM",
            "llm.model_name": "demo-model",
            "gen_ai.operation.name": "chat",
            "gen_ai.system": "demo",
            "gen_ai.request.model": "demo-model",
        },
    }


def undigested(graph: spanweave.Graph) -> spanweave.Graph:
    """`graph` without the digest a `Builder` cannot carry (`§10.4` there)."""
    assert graph.meta is not None
    return dataclasses.replace(
        graph, meta=dataclasses.replace(graph.meta, source_digest=None)
    )


def batch(*records: dict) -> bytes:
    """`spanweave.build` of these records as a line-delimited input."""
    body = b"".join(json.dumps(record).encode("utf-8") + b"\n" for record in records)
    return spanweave.dumps(undigested(spanweave.build(body)))


def live(builder: spanweave.Builder) -> bytes:
    return spanweave.dumps(undigested(builder.graph()))


def codes_of(graph: spanweave.Graph) -> list[str]:
    return sorted(diagnostic.code for diagnostic in graph.diagnostics)


# --------------------------------------------------------------------------
# The surface `SPEC.md` §4.1 declares is the surface the code has.
# --------------------------------------------------------------------------


def test_the_routers_settings_are_keyword_only_as_SPEC_declares():
    """§4.1 declares `__init__(self, *, max_traces, adapter, temporal)`.

    The `*` was a sentence nothing held: the dataclass accepted
    `Router(1, 'openinference', False)`, so the three settings had a positional
    order the spec never promised and a caller could come to rely on
    (`reviews/2026-10-04-run1.md` R2-1). Pre-1.0, so the honest fix is the
    cheap one -- the code is keyword-only and the declared signature is now
    true. `routed`, likewise public and likewise undeclared, is in §4.1 too.
    """
    with pytest.raises(TypeError):
        Router(1)

    settings = Router(max_traces=1, adapter="openinference", temporal=False)
    assert (settings.max_traces, settings.adapter, settings.temporal) == (
        1,
        "openinference",
        False,
    )
    assert settings.routed == 0


def declared_fields(section: str, name: str) -> list[tuple[str, bool]]:
    """The fields of one dataclass as `SPEC.md` declares it, in order.

    The spec's own text, parsed rather than grepped: the `python` fence under
    the named section is a module, so `ast` says what is declared in it and a
    sentence in the prose cannot be mistaken for a field. Each field comes back
    as `(name, has_default)`.
    """
    spec = (pathlib.Path(__file__).resolve().parent.parent / "SPEC.md").read_text(
        encoding="utf-8"
    )
    heading = f"### {section} "
    start = spec.index(heading)
    # The next sibling `###`, or the next parent `##` for the last subsection
    # of a part -- which §7.2 is. Written as a minimum over both rather than as
    # one `index`, because the one that is absent must not end the search.
    end = min(
        (
            where
            for where in (spec.find("\n### ", start + 1), spec.find("\n## ", start + 1))
            if where != -1
        ),
        default=len(spec),
    )
    block = spec[start:end]
    fence = block.index("```python") + len("```python")
    source = block[fence : block.index("```", fence)]
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return [
                (field.target.id, field.value is not None)
                for field in node.body
                if isinstance(field, ast.AnnAssign)
                and isinstance(field.target, ast.Name)
            ]
    raise AssertionError(f"SPEC.md {section} declares no `class {name}`")


@pytest.mark.parametrize("name", ["Event", "Routed"])
def test_the_event_block_in_SPEC_is_the_dataclass_the_code_has(name):
    """§4.1 says it is declared **exactly** as the code accepts it. Held.

    R3 added `seconds` to that block with a paragraph and R4 added `version`
    with a paragraph; R5 added `Event.offset` to the code, cited §4.1 in its
    commit message and its CHANGELOG entry, and **did not add the field** —
    which nothing caught, because the only test on the block asserted the
    dataclass's own field order against itself
    (`reviews/2026-10-06-run2.md` F5). This is the cheap test that would have.

    Fields in declared order, with which of them carry a default, because an
    optional field moved in front of a required one is a signature change a
    name-set comparison would miss.
    """
    declared = declared_fields("4.1", name)
    actual = [
        (field.name, field.default is not dataclasses.MISSING)
        for field in dataclasses.fields({"Event": Event, "Routed": Routed}[name])
    ]
    assert declared == actual


# --------------------------------------------------------------------------
# The trace id comes from the adapter surface, never from a key (§4.2).
# --------------------------------------------------------------------------


def test_the_trace_id_is_what_the_claiming_adapter_parsed():
    assert trace_id_of(openinference("s0")) == "t1"
    assert trace_id_of(openinference("s0", trace="other")) == "other"


def test_a_record_nobody_claims_has_no_trace_id_however_it_is_keyed():
    """The claim, at the level of the one function that answers it.

    `unclaimable` carries `trace_id` and the dialect read would find it. The
    adapter surface is asked instead, nobody claims the record, and the answer
    is the absence `SPEC.md` §1.1 names rather than the key's value.
    """
    record = unclaimable("s9")
    assert record["trace_id"] == "t1"
    assert trace_id_of(record) is None


def test_a_record_more_than_one_adapter_claims_has_no_trace_id():
    """Nobody to ask: the library refuses an ambiguous record (§6.1 there)."""
    assert trace_id_of(ambiguous("sA")) is None


def test_a_record_that_is_not_an_object_has_no_trace_id():
    assert trace_id_of("not a record") is None
    assert trace_id_of(None) is None


def test_a_record_no_adapter_claims_is_not_routed_by_its_trace_id_key():
    """**The batch's load-bearing test** (`SPEC.md` §4.2, §4.7).

    Three records arrive: two OpenInference spans of `t1` and, between them,
    a record no adapter claims that also says `"trace_id": "t1"`.

    Through the adapter surface, `t1`'s graph is the graph of the two claimed
    spans and nothing else, and the unclaimed record is the no-trace builder's
    -- where `spanweave` itself reports it as an `unknown` node with an
    `unclaimed_record` diagnostic.

    A router keyed by `record["trace_id"]` puts all three in `t1`, so `t1`'s
    graph grows a third node and this comparison fails. That is the mutation
    this test exists to catch, and the reason it is hand-authored rather than
    drawn from the corpus is in `SPEC.md` §4.7.
    """
    first, mystery, second = (
        openinference("s0"),
        unclaimable("s9"),
        openinference("s1", parent="s0"),
    )
    router = Router()
    for record in (first, mystery, second):
        router.route(record)

    assert router.trace_ids == ("t1",)
    traced = router.builder("t1")
    assert traced is not None
    assert traced.version == 2, "the unclaimed record is not t1's"
    assert live(traced) == batch(first, second)

    # And the record is not lost: it was absorbed by the no-trace builder,
    # which holds nothing but unclaimed records and so refuses to produce a
    # graph at all -- `spanweave`'s own answer to an input nothing can read,
    # asserted on its own below.
    assert router.no_trace.version == 1


def test_the_no_trace_builder_says_what_a_batch_build_of_the_same_records_says():
    """`missing_trace_id` / `unclaimed_record` are carried, never invented.

    One claimed record with no trace id and one record nobody claims: the
    no-trace builder's graph is the batch graph of exactly those two, codes
    included. The receiver added no code of its own (`SPEC.md` §4.3).
    """
    nameless = openinference("s0")
    del nameless["trace_id"]
    mystery = unclaimable("s9")
    mystery.pop("trace_id")

    router = Router()
    for record in (nameless, mystery):
        routed = router.route(record)
        assert routed.trace_id is None
        assert routed.builder is router.no_trace

    assert router.trace_ids == ()
    assert live(router.no_trace) == batch(nameless, mystery)
    assert codes_of(router.no_trace.graph()) == [
        "missing_timestamp",
        "missing_trace_id",
        "unclaimed_record",
    ]


def test_a_no_trace_builder_holding_only_unclaimed_records_refuses_its_graph():
    """Inherited, not chosen (`SPEC.md` §4.3).

    `spanweave` refuses an input no adapter can read rather than handing back
    a graph of `unknown` nodes, and the receiver does not paper over it.
    """
    router = Router()
    router.route(unclaimable("s9"))
    with pytest.raises(spanweave.AdapterSelectionError) as refusal:
        router.no_trace.graph()
    assert refusal.value.code == "adapter_unconfident"


# --------------------------------------------------------------------------
# One builder per trace, created on first sight (§4.3).
# --------------------------------------------------------------------------


def test_two_traces_get_two_builders_and_each_is_its_own_batch_graph():
    a0, a1 = openinference("s0"), openinference("s1", parent="s0")
    b0 = openinference("s0", trace="t2")

    router = Router()
    for record in (a0, b0, a1):
        router.route(record)

    assert router.trace_ids == ("t1", "t2"), "first arrival order, not sorted"
    first, second = router.builder("t1"), router.builder("t2")
    assert first is not None and second is not None
    assert first is not second
    assert live(first) == batch(a0, a1)
    assert live(second) == batch(b0)


def test_every_record_of_one_trace_reaches_the_same_builder():
    router = Router()
    seen = {id(router.route(openinference(f"s{n}")).builder) for n in range(5)}
    assert len(seen) == 1
    assert router.routed == 5


def test_an_unknown_trace_has_no_builder_and_no_builder_is_made_by_asking():
    router = Router()
    assert router.builder("t1") is None
    assert router.trace_ids == ()


def test_routed_carries_the_arrival_index_and_the_version_it_produced():
    router = Router()
    first = router.route(openinference("s0"))
    second = router.route(openinference("s1", parent="s0"))
    assert (first.index, first.version) == (1, 1)
    assert (second.index, second.version) == (2, 2)
    assert first.events == () and second.events == ()


def test_adapter_and_temporal_reach_every_builder_the_router_makes():
    """Live and batch agree about the options too, not only the records."""
    a0, a1 = openinference("s0"), openinference("s1", parent="s0")
    router = Router(adapter="openinference", temporal=False)
    for record in (a0, a1):
        router.route(record)
    traced = router.builder("t1")
    assert traced is not None
    body = b"".join(json.dumps(r).encode() + b"\n" for r in (a0, a1))
    expected = spanweave.dumps(
        undigested(spanweave.build(body, adapter="openinference", temporal=False))
    )
    assert live(traced) == expected


# --------------------------------------------------------------------------
# A refusal is an event, and routing continues (§4.4).
# --------------------------------------------------------------------------


def test_a_resent_span_is_a_counted_refusal_and_the_next_record_still_routes():
    """At-least-once export, which is the ordinary case (`SPEC.md` §2.2)."""
    a0, a1 = openinference("s0"), openinference("s1", parent="s0")
    router = Router()
    router.route(a0)
    again = router.route(dict(a0))
    after = router.route(a1)

    (event,) = again.events
    assert event.code == REFUSED
    assert event.index == 2, "the record's arrival index, so it can be found"
    assert event.trace_id == "t1"
    assert event.spanweave_code == "duplicate_node_id"
    assert event.detail
    assert router.counts == {REFUSED: 1}

    assert again.version == 1, "a refused record is not absorbed (§10.5 there)"
    assert after.version == 2 and after.events == ()
    traced = router.builder("t1")
    assert traced is not None
    assert live(traced) == batch(a0, a1), "the resend changed nothing"


def test_an_ambiguous_record_is_refused_with_the_librarys_own_code():
    """No claimant means no trace id, and the no-trace builder refuses it."""
    router = Router()
    routed = router.route(ambiguous("sA"))
    (event,) = routed.events
    assert routed.trace_id is None
    assert event.code == REFUSED
    assert event.spanweave_code == "adapter_ambiguous"
    assert router.counts == {REFUSED: 1}


def test_routing_never_raises_for_anything_a_record_can_cause():
    router = Router()
    for record in (
        openinference("s0"),
        dict(openinference("s0")),
        unclaimable("s9"),
        ambiguous("sA"),
        "not a record",
        None,
        [1, 2, 3],
    ):
        router.route(record)
    assert router.routed == 7
    assert router.counts[REFUSED] == 2


# --------------------------------------------------------------------------
# `max_traces` is a cap, counted, never a silent drop (§4.5).
# --------------------------------------------------------------------------


def test_a_new_trace_at_the_cap_is_refused_in_the_open():
    a0 = openinference("s0")
    b0 = openinference("s0", trace="t2")
    router = Router(max_traces=1)
    router.route(a0)
    refused = router.route(b0)

    (event,) = refused.events
    assert event.code == REFUSED_AT_CAP
    assert (event.index, event.trace_id) == (2, "t2")
    assert event.spanweave_code is None
    assert "max_traces" in event.detail
    assert refused.builder is None and refused.version is None
    assert router.counts == {REFUSED_AT_CAP: 1}
    assert router.trace_ids == ("t1",), "no builder was made for the capped trace"


def test_at_the_cap_the_traces_already_held_keep_routing():
    a0, a1 = openinference("s0"), openinference("s1", parent="s0")
    router = Router(max_traces=1)
    router.route(a0)
    router.route(openinference("s0", trace="t2"))
    router.route(a1)
    traced = router.builder("t1")
    assert traced is not None
    assert live(traced) == batch(a0, a1)
    assert router.counts == {REFUSED_AT_CAP: 1}


def test_a_record_with_no_trace_id_is_never_refused_at_the_cap():
    """The no-trace builder is not a trace (`SPEC.md` §4.5).

    Counting it against the cap would make "no trace id" the thing that evicts
    real traces.
    """
    nameless = openinference("s0")
    del nameless["trace_id"]
    router = Router(max_traces=1)
    router.route(openinference("s0", trace="t1"))
    routed = router.route(nameless)
    assert routed.events == ()
    assert routed.builder is router.no_trace
    assert router.counts == {}


def test_no_cap_is_the_default():
    router = Router()
    for n in range(12):
        router.route(openinference("s0", trace=f"t{n}"))
    assert len(router.trace_ids) == 12
    assert router.counts == {}


# --------------------------------------------------------------------------
# The seam the ingest batches will use: a `Framer`'s records, routed.
# --------------------------------------------------------------------------


def test_framed_bytes_route_to_the_same_graph_as_build_of_those_bytes():
    """`Framer` + `Router`, in miniature. Gate A is this over the corpus."""
    a0, a1 = openinference("s0"), openinference("s1", parent="s0")
    body = b"".join(json.dumps(r).encode() + b"\n" for r in (a0, a1))

    framer, router = Framer(), Router()
    for index in range(0, len(body), 7):
        for record in framer.push(body[index : index + 7]).records:
            router.route(record)
    for record in framer.flush().records:
        router.route(record)

    traced = router.builder("t1")
    assert traced is not None
    assert live(traced) == batch(a0, a1)
