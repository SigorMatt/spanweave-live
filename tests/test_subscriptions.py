"""Subscriptions: the deltas go out, and nothing is concluded (`SPEC.md` §6).

The load-bearing claims of this file:

- **Folding every delta a subscriber received onto its first graph gives the
  final `graph()`, byte for byte** — at `every=1` after every record, and at
  `every=N` after the trace completes or is flushed. That is `spanweave`
  §10.6's promise read through the receiver: the corpus asserts it per
  *builder*, and here it is asserted per *subscriber*, over the deltas a
  fan-out actually chose to send. If this fails, the receiver is handing
  consumers a story that does not add up to the graph it holds. The `every=N`
  fold runs at `records=7, every=2` — **not** a multiple of `N` — because at
  `records=6` it was true of the fixture rather than of the mechanism
  (`patches/REVIEW-2026-10-06.md` §0(c)).
- **A coarse subscriber is handed the tail of its trace**, at completion and at
  `Router.flush`, instead of being told about it. The window it never asked for
  by the rule is one it is owed by the claim above, and reporting it as
  `delta_unsent` while delivering nothing was a dropped delta (`SPEC.md` §6.5,
  §6.6).
- **A raising subscriber never stalls another**, the record is still absorbed,
  and the failure is an `Event` with its code, the trace id and the version. A
  fan-out that stopped at the first failure is the mutation this file exists to
  catch; so is one that continued without saying anything.
- **Retention is the longest window a subscriber asked for, and no more** — and
  a builder nobody subscribed to is left at the library's own default, because
  `Routed.builder` is public (`SPEC.md` §6.4).

No clock, no socket, no unseeded randomness. Where completion is involved the
clock is the fake one the test owns, for `tests/test_completion.py`'s reason.
"""

from __future__ import annotations

import dataclasses

import pytest
import spanweave

from spanweave_live import (
    CONSUMER_ERROR,
    DELTA_UNAVAILABLE,
    DELTA_UNSENT,
    REFUSED,
    Cap,
    Completion,
    Router,
    Subscriptions,
    Update,
)

# --------------------------------------------------------------------------
# The records and the consumers. Hand-authored and small: the corpus is gate
# A's business, and these put a fan-out in states the corpus does not hold.
# --------------------------------------------------------------------------


def openinference(
    span_id: str, *, trace: str = "t1", parent: str | None = None
) -> dict:
    """One OpenInference span, claimed by exactly one adapter."""
    return {
        "trace_id": trace,
        "span_id": span_id,
        "parent_id": parent,
        "name": f"chain.{span_id}",
        "start_time": 1_000.0,
        "end_time": 1_001.0,
        "attributes": {"openinference.span.kind": "CHAIN"},
    }


def unclaimable(span_id: str, *, trace: str = "t1") -> dict:
    """A record no adapter claims, so the adapter surface says "no trace id"."""
    return {"trace_id": trace, "span_id": span_id, "name": f"mystery.{span_id}"}


def trace_of(count: int = 6, *, trace: str = "t1") -> list[dict]:
    """A root and `count - 1` children of it, in one trace.

    Children rather than a flat list so that each arrival adds an edge as well
    as a node: a delta that only ever added nodes would under-exercise the fold.
    """
    return [
        openinference("s0", trace=trace),
        *(
            openinference(f"s{index}", trace=trace, parent="s0")
            for index in range(1, count)
        ),
    ]


class Collector:
    """A consumer that keeps what it was handed and concludes nothing.

    It asks the builder for a graph on its **first** update only, which is the
    "first graph" the fold claim starts from (`SPEC.md` §6.6): there is no graph
    at version 0 to fold onto, because an empty builder refuses.
    """

    def __init__(self) -> None:
        self.updates: list[Update] = []
        self.first_graph: spanweave.Graph | None = None

    def __call__(self, update: Update) -> None:
        if not self.updates:
            self.first_graph = update.builder.graph()
        self.updates.append(update)


def route_all(router: Router, records: list[dict]) -> None:
    for record in records:
        router.route(record)


def final_graph(router: Router, trace_id: str = "t1") -> spanweave.Graph:
    builder = router.builder(trace_id)
    assert builder is not None
    return builder.graph()


# --------------------------------------------------------------------------
# The surface `SPEC.md` §6.1 declares is the surface the code has.
# --------------------------------------------------------------------------


def test_an_update_carries_no_graph_and_nothing_about_meaning():
    """§6.1's field set, held as §5.6's `TraceState` field set is held.

    No graph (materializing one per record per subscriber is the cost §2.3 is
    about, and the builder is right there to ask), and nothing that says what
    the change *meant* — no severity, no role, no score. An `Update` that grew
    one would be the receiver evaluating on a consumer's behalf (`§1.2`).
    """
    assert [field.name for field in dataclasses.fields(Update)] == [
        "trace_id",
        "version",
        "since",
        "delta",
        "builder",
    ]


def test_a_subscription_narrows_by_trace_and_by_how_often_and_by_nothing_else():
    subscriptions = Subscriptions()
    first = subscriptions.subscribe(Collector())
    second = subscriptions.subscribe(Collector(), trace_id="t1", every=4)

    assert (first.trace_id, first.every, first.order) == (None, 1, 0)
    assert (second.trace_id, second.every, second.order) == ("t1", 4, 1)
    assert subscriptions.registered == (first, second)


@pytest.mark.parametrize("every", [0, -1, True, 1.5])
def test_every_is_a_count_of_versions_of_at_least_one(every):
    """`every=0` is not a frequency, and it is refused where it is written.

    A `ValueError` at registration rather than an event: nothing about the
    stream caused it, which is the same reason `spanweave`'s own `retain(-1)`
    raises (`SPEC.md` §6.1). `True` is 1 to Python and is not a frequency either.
    """
    with pytest.raises(ValueError, match="count of versions"):
        Subscriptions().subscribe(Collector(), every=every)


# --------------------------------------------------------------------------
# The claim (§6.6): the deltas a subscriber received add up to the graph.
# --------------------------------------------------------------------------


def test_folding_every_delta_a_per_record_subscriber_got_gives_the_final_graph():
    """The batch's central claim, at `every=1` (`SPEC.md` §6.6).

    Every delta the subscriber received is used: the first **is** the whole of
    the graph it produced (`since=0` has nothing beneath it, `spanweave` §10.5),
    and the rest fold onto that first graph in order. The result is compared to
    the router's own `graph()` byte for byte, which is the comparison this
    project makes everywhere else (`SPEC.md` §4.7).
    """
    records = trace_of(6)
    subscriptions = Subscriptions()
    collector = Collector()
    subscriptions.subscribe(collector)
    router = Router(subscriptions=subscriptions)

    route_all(router, records)

    assert [update.version for update in collector.updates] == [1, 2, 3, 4, 5, 6]
    assert [update.since for update in collector.updates] == [0, 1, 2, 3, 4, 5]
    assert all(update.trace_id == "t1" for update in collector.updates)

    first = collector.updates[0]
    opening = collector.first_graph
    assert opening is not None
    assert sorted(node.id for node in first.delta.nodes_added) == sorted(
        node.id for node in opening.nodes()
    )
    assert sorted(edge.identity for edge in first.delta.edges_added) == sorted(
        edge.identity for edge in opening.edges()
    )
    assert first.delta.nodes_removed == () and first.delta.edges_removed == ()

    folded = opening
    for update in collector.updates[1:]:
        folded = update.delta.fold(folded)
    assert spanweave.dumps(folded) == spanweave.dumps(final_graph(router))


def test_folding_every_delta_an_every_n_subscriber_got_gives_the_final_graph():
    """The same claim at `every=2`, at a record count that is **not** a multiple
    of `N` — and therefore only after a flush (`SPEC.md` §6.6).

    Seven records and `every=2`: the fan-out delivers at versions 2, 4 and 6,
    and version 7 is a residue no window covers. Without the trailing delta the
    fold is short by exactly that record, which is the state the run-2 review
    found this test hiding behind `records=6` (`patches/REVIEW-2026-10-06.md`
    §0(c), F2): the claim was true of the fixture rather than of the mechanism.
    So the count is odd on purpose, and `flush` is what makes the fold add up.

    The first delta is used by the claim too, as §6.6 says it is: what it adds
    **is** the whole of the graph it produced, asserted here as the `every=1`
    test asserts it (F3) — a mutation of the `since == 0` delta alone must not
    leave this test green.
    """
    subscriptions = Subscriptions()
    collector = Collector()
    subscriptions.subscribe(collector, every=2)
    router = Router(subscriptions=subscriptions)

    route_all(router, trace_of(7))

    assert [update.version for update in collector.updates] == [2, 4, 6]
    assert [update.since for update in collector.updates] == [0, 2, 4]

    assert router.flush("t1") == (), "a trailing delta is a delivery, not an event"

    assert [update.version for update in collector.updates] == [2, 4, 6, 7]
    assert [update.since for update in collector.updates] == [0, 2, 4, 6]

    first = collector.updates[0]
    opening = collector.first_graph
    assert opening is not None
    assert sorted(node.id for node in first.delta.nodes_added) == sorted(
        node.id for node in opening.nodes()
    )
    assert sorted(edge.identity for edge in first.delta.edges_added) == sorted(
        edge.identity for edge in opening.edges()
    )
    assert first.delta.nodes_removed == () and first.delta.edges_removed == ()

    folded = opening
    for update in collector.updates[1:]:
        folded = update.delta.fold(folded)
    assert spanweave.dumps(folded) == spanweave.dumps(final_graph(router))


def test_a_flush_hands_over_the_tail_once_and_then_has_nothing_to_hand():
    """`flush` is idempotent in the only sense that matters: the cursor moved.

    A second flush with no record in between delivers nothing, because the
    subscriber is no longer behind — the same rule `due` follows, read at the
    caller's moment instead of the record's (`SPEC.md` §6.2, §6.6).
    """
    subscriptions = Subscriptions()
    collector = Collector()
    subscriptions.subscribe(collector, every=5)
    router = Router(subscriptions=subscriptions)

    route_all(router, trace_of(3))
    assert collector.updates == []

    assert router.flush("t1") == ()
    assert [(update.since, update.version) for update in collector.updates] == [(0, 3)]

    assert router.flush("t1") == ()
    assert len(collector.updates) == 1, "nothing changed, so nothing was due"

    router.route(openinference("s9", parent="s0"))
    assert router.flush("t1") == ()
    assert [(update.since, update.version) for update in collector.updates] == [
        (0, 3),
        (3, 4),
    ]


def test_a_per_record_subscriber_has_no_tail_to_flush():
    """`every=1` is never behind, so a flush is a no-op for it (`SPEC.md` §6.6)."""
    subscriptions = Subscriptions()
    collector = Collector()
    subscriptions.subscribe(collector)
    router = Router(subscriptions=subscriptions)

    route_all(router, trace_of(4))
    assert len(collector.updates) == 4

    assert router.flush("t1") == ()
    assert len(collector.updates) == 4


def test_a_flush_of_a_trace_the_router_holds_no_builder_for_is_nothing():
    """Not an event: nothing was absorbed, so no window was dropped (§6.6)."""
    subscriptions = Subscriptions()
    collector = Collector()
    subscriptions.subscribe(collector, every=2)
    router = Router(subscriptions=subscriptions)

    assert router.flush("never-seen") == ()
    assert router.flush(None) == (), "the no-trace builder was never made"
    assert collector.updates == []
    assert router.counts == {}


def test_a_router_without_subscriptions_flushes_nothing():
    router = Router()
    route_all(router, trace_of(3))
    assert router.flush("t1") == ()
    assert router.counts == {}


def test_two_subscribers_at_one_window_are_handed_the_same_delta_object():
    """One fold per distinct `since`, shared because a `Delta` is a value (§6.2)."""
    subscriptions = Subscriptions()
    first, second = Collector(), Collector()
    subscriptions.subscribe(first)
    subscriptions.subscribe(second)
    router = Router(subscriptions=subscriptions)

    route_all(router, trace_of(3))

    assert len(first.updates) == len(second.updates) == 3
    for one, other in zip(first.updates, second.updates, strict=True):
        assert one.delta is other.delta


# --------------------------------------------------------------------------
# Isolation: a raising subscriber never stalls another (§6.5).
# --------------------------------------------------------------------------


class Exploding:
    """A consumer that raises every time, and counts how often it was called."""

    def __init__(self, message: str = "consumer blew up") -> None:
        self.message = message
        self.seen: list[int] = []

    def __call__(self, update: Update) -> None:
        self.seen.append(update.since)
        raise RuntimeError(self.message)


def test_a_raising_subscriber_never_stalls_another():
    """The mutation this test exists to catch is a fan-out that stops at the
    failure — and the one that continues in silence (`SPEC.md` §6.5).

    Three subscribers, the middle one raising. Both others are called, with the
    same update; the record stays absorbed; and the failure is an `Event` with
    the trace id and the version, counted on the router.
    """
    calls: list[tuple[str, int]] = []

    def first(update: Update) -> None:
        calls.append(("first", update.version))

    def last(update: Update) -> None:
        calls.append(("last", update.version))

    exploding = Exploding()
    subscriptions = Subscriptions()
    subscriptions.subscribe(first)
    subscriptions.subscribe(exploding)
    subscriptions.subscribe(last)
    router = Router(subscriptions=subscriptions)

    routed = router.route(openinference("s0"))

    assert calls == [("first", 1), ("last", 1)]
    assert exploding.seen == [0]

    errors = [event for event in routed.events if event.code == CONSUMER_ERROR]
    assert len(errors) == 1
    assert errors[0].trace_id == "t1"
    assert errors[0].version == 1
    assert "RuntimeError" in errors[0].detail
    assert "consumer blew up" in errors[0].detail
    assert router.counts[CONSUMER_ERROR] == 1

    # The record is still absorbed: a consumer's failure is not the record's.
    assert routed.version == 1
    builder = router.builder("t1")
    assert builder is not None and builder.version == 1
    assert len(builder.graph().nodes()) == 1

    # And the next record reaches all three again: nothing was unsubscribed.
    router.route(openinference("s1", parent="s0"))
    assert calls == [("first", 1), ("last", 1), ("first", 2), ("last", 2)]
    assert exploding.seen == [0, 1]
    assert router.counts[CONSUMER_ERROR] == 2


def test_a_subscriber_that_raised_is_not_re_sent_to():
    """Its cursor advanced with everybody else's (`SPEC.md` §6.2).

    `exploding.seen` is the `since` of each call: `[0, 1]` and not `[0, 0]`.
    Re-sending would let one consumer's failure change what it sees next, and a
    retry queue is a policy nobody asked the receiver for.
    """
    exploding = Exploding()
    subscriptions = Subscriptions()
    subscription = subscriptions.subscribe(exploding)
    router = Router(subscriptions=subscriptions)

    route_all(router, trace_of(3))

    assert exploding.seen == [0, 1, 2]
    assert subscriptions.seen(subscription, "t1") == 3


def test_a_consumer_error_does_not_stop_the_graphs_adding_up():
    """Isolation and §6.6's claim at once: the delta a raising consumer dropped
    on the floor is still the delta the other one folded."""
    subscriptions = Subscriptions()
    collector = Collector()
    subscriptions.subscribe(Exploding())
    subscriptions.subscribe(collector)
    router = Router(subscriptions=subscriptions)

    route_all(router, trace_of(5))

    opening = collector.first_graph
    assert opening is not None
    folded = opening
    for update in collector.updates[1:]:
        folded = update.delta.fold(folded)
    assert spanweave.dumps(folded) == spanweave.dumps(final_graph(router))
    assert router.counts[CONSUMER_ERROR] == 5


# --------------------------------------------------------------------------
# What fans out, and what does not (§6.2, §6.3).
# --------------------------------------------------------------------------


def test_a_refused_record_fans_nothing_out():
    """Only an **absorbed** record fans out (`SPEC.md` §6.2).

    A re-sent span is refused and the version does not move, so there is nothing
    that changed to report — and handing `delta(since=version - 1)` over anyway
    would deliver the previous record's difference a second time.
    """
    subscriptions = Subscriptions()
    collector = Collector()
    subscriptions.subscribe(collector)
    router = Router(subscriptions=subscriptions)

    router.route(openinference("s0"))
    routed = router.route(openinference("s0"))

    assert [event.code for event in routed.events] == [REFUSED]
    assert [update.version for update in collector.updates] == [1]


def test_a_record_refused_at_the_cap_fans_nothing_out():
    subscriptions = Subscriptions()
    collector = Collector()
    subscriptions.subscribe(collector)
    router = Router(max_traces=1, subscriptions=subscriptions)

    router.route(openinference("s0", trace="t1"))
    router.route(openinference("s0", trace="t2"))

    assert [update.trace_id for update in collector.updates] == ["t1"]


def test_all_traces_includes_the_no_trace_builder_and_a_named_one_does_not():
    """§6.3: `trace_id=None` is every builder the router feeds.

    Not §5.4's answer, deliberately, and the difference is that completing the
    no-trace builder would **throw away** the library's own account of those
    records while reporting on it throws away nothing. Leaving it out would mean
    a record was absorbed, the graph changed, and a consumer that asked for
    everything was told nothing — the silence §1.5 refuses.
    """
    subscriptions = Subscriptions()
    everything, just_t1 = Collector(), Collector()
    subscriptions.subscribe(everything)
    subscriptions.subscribe(just_t1, trace_id="t1")
    router = Router(subscriptions=subscriptions)

    router.route(openinference("s0", trace="t1"))
    router.route(openinference("s0", trace="t2"))
    router.route(unclaimable("mystery"))

    assert [update.trace_id for update in everything.updates] == ["t1", "t2", None]
    assert [update.trace_id for update in just_t1.updates] == ["t1"]


def test_the_fan_out_order_is_registration_order():
    """§6.2: the order the caller controls, for every record, in every process."""
    calls: list[int] = []
    subscriptions = Subscriptions()
    for order in range(5):
        subscriptions.subscribe(lambda _update, order=order: calls.append(order))
    router = Router(subscriptions=subscriptions)

    route_all(router, trace_of(2))

    assert calls == [0, 1, 2, 3, 4, 0, 1, 2, 3, 4]


def test_a_late_arrival_starts_the_windows_again_from_zero():
    """A new generation is a new builder at version 0, so every cursor is too
    (`SPEC.md` §5.5, §6.3)."""
    readings = [1_000.0]
    subscriptions = Subscriptions()
    collector = Collector()
    subscriptions.subscribe(collector)
    router = Router(
        completion=Completion(policies=(Cap(1),), now=lambda: readings[0]),
        subscriptions=subscriptions,
    )

    router.route(openinference("s0"))
    assert len(router.tick()) == 1
    readings[0] = 1_010.0
    router.route(openinference("s1"))

    assert [(update.since, update.version) for update in collector.updates] == [
        (0, 1),
        (0, 1),
    ]


# --------------------------------------------------------------------------
# Retention: the hungriest subscriber's window, and no more (§6.4).
# --------------------------------------------------------------------------


def test_retention_is_the_longest_window_any_subscriber_asked_for():
    """And **no more**: one version older than the longest window is refused.

    `every=1` alone would keep one version; the `every=3` subscriber is going to
    ask for three, so three are kept and the fourth is dropped.
    """
    subscriptions = Subscriptions()
    subscriptions.subscribe(Collector())
    subscriptions.subscribe(Collector(), every=3)
    assert subscriptions.window("t1") == 3
    router = Router(subscriptions=subscriptions)

    route_all(router, trace_of(6))
    builder = router.builder("t1")
    assert builder is not None and builder.version == 6

    assert builder.delta(since=3).since == 3
    with pytest.raises(spanweave.DeltaUnavailableError):
        builder.delta(since=2)


def test_a_builder_nobody_subscribed_to_keeps_the_librarys_own_default():
    """§6.4: `None` is not `0`.

    `Routed.builder` is public, so a caller may be folding its own deltas off a
    builder this router knows nothing about. Narrowing a journal the receiver
    never promised to narrow would break that caller silently.
    """
    for subscriptions in (None, Subscriptions()):
        if subscriptions is not None:
            subscriptions.subscribe(Collector(), trace_id="other")
            assert subscriptions.window("t1") is None
        router = Router(subscriptions=subscriptions)
        route_all(router, trace_of(6))
        builder = router.builder("t1")
        assert builder is not None
        assert builder.delta(since=0).changed, "retention was narrowed uninvited"


def test_retention_is_per_trace_and_not_per_router():
    """`and no more` is half the claim: a subscriber for `t1` is not `t2`'s."""
    subscriptions = Subscriptions()
    subscriptions.subscribe(Collector(), trace_id="t1", every=2)
    router = Router(subscriptions=subscriptions)

    route_all(router, trace_of(6, trace="t1"))
    route_all(router, trace_of(6, trace="t2"))

    watched, unwatched = router.builder("t1"), router.builder("t2")
    assert watched is not None and unwatched is not None
    with pytest.raises(spanweave.DeltaUnavailableError):
        watched.delta(since=3)
    assert unwatched.delta(since=0).changed


def test_a_router_without_subscriptions_fans_nothing_out_and_reads_nothing():
    """R2's and R3's behaviour, unchanged — which is why gate A is untouched."""
    router = Router()
    route_all(router, trace_of(4))

    assert router.counts == {}
    builder = router.builder("t1")
    assert builder is not None and builder.version == 4


def test_a_caller_that_narrows_a_builders_retention_gets_an_event_not_a_traceback():
    """§6.5's `delta_unavailable`, and the only way to reach it.

    Retention is the router's or the caller's and not both. A caller is entitled
    to narrow a `Routed.builder`'s journal, and then the honest answer is this
    event — carrying the library's own code — rather than a traceback that would
    lose every other subscriber and every later record.
    """
    subscriptions = Subscriptions()
    collector = Collector()
    subscriptions.subscribe(collector, every=2)
    router = Router(subscriptions=subscriptions)

    router.route(openinference("s0"))
    builder = router.builder("t1")
    assert builder is not None
    builder.retain(0)
    routed = router.route(openinference("s1", parent="s0"))

    unavailable = [event for event in routed.events if event.code == DELTA_UNAVAILABLE]
    assert len(unavailable) == 1
    assert unavailable[0].spanweave_code == "delta_unavailable"
    assert unavailable[0].trace_id == "t1"
    assert unavailable[0].version == 2
    assert router.counts[DELTA_UNAVAILABLE] == 1
    # Nothing approximate was handed over in its place, and the record is in.
    assert collector.updates == []
    assert routed.version == 2


def test_a_consumer_joining_mid_stream_with_a_coarser_window_is_the_other_way():
    """The second way to `delta_unavailable`, which touches no caller's
    retention (`SPEC.md` §6.5, `patches/REVIEW-2026-10-06.md` F4).

    §6.1 makes `Subscriptions` mutable on purpose — "something consumers join" —
    so a consumer may join a trace already in flight and ask for a window
    *wider* than the one the journal is currently kept at. The first such window
    is the one that cannot be produced: retention is widened **after** a
    fan-out (§6.4), so the widening arrives one delivery too late for the
    joiner's own first window. The behaviour is the right one and it is this
    event: one code, the other subscriber untouched, no traceback, and every
    later window served.
    """
    subscriptions = Subscriptions()
    fine, coarse = Collector(), Collector()
    subscriptions.subscribe(fine)
    router = Router(subscriptions=subscriptions)

    route_all(router, trace_of(5))
    assert subscriptions.window("t1") == 1

    subscriptions.subscribe(coarse, every=4)
    routed = router.route(openinference("s5", parent="s0"))

    unavailable = [event for event in routed.events if event.code == DELTA_UNAVAILABLE]
    assert len(unavailable) == 1
    assert unavailable[0].spanweave_code == "delta_unavailable"
    assert unavailable[0].version == 6
    assert coarse.updates == [], "nothing approximate was handed over"
    assert [update.version for update in fine.updates] == [1, 2, 3, 4, 5, 6]

    # Widened afterwards, so the joiner's next window is served and no later
    # record repeats the refusal.
    assert subscriptions.window("t1") == 4
    route_all(
        router,
        [openinference(f"s{index}", parent="s0") for index in range(6, 11)],
    )
    assert [(update.since, update.version) for update in coarse.updates] == [(6, 10)]
    assert router.counts[DELTA_UNAVAILABLE] == 1


# --------------------------------------------------------------------------
# A released builder takes its journal with it (§6.5).
# --------------------------------------------------------------------------


def test_a_completing_trace_hands_the_tail_over_before_it_releases():
    """The trailing delta, at completion (`SPEC.md` §5.4 step five, §6.5, §6.6).

    The `every=4` subscriber was last handed version 4 and the trace completes
    at version 6, so versions 5 and 6 are its tail. Until the run-2 review they
    were a `delta_unsent` *report* and nothing else, which meant a coarse
    subscriber silently never saw the end of any trace whose length was not a
    multiple of its window — a dropped delta, which §1.5 does not allow
    (`WORKPLAN.md` §3, 2026-10-06). It is handed over instead, and the report
    is kept for the one case where it cannot be.

    The builder has already left `trace_ids` when this delivery is made, and
    `update.builder` is that released builder: its `graph()` is the final graph,
    which is the one `Completed.graph` carries.
    """
    subscriptions = Subscriptions()
    coarse, per_record = Collector(), Collector()
    subscriptions.subscribe(coarse, every=4)
    subscriptions.subscribe(per_record)
    router = Router(
        completion=Completion(policies=(Cap(6),), now=lambda: 1_000.0),
        subscriptions=subscriptions,
    )

    route_all(router, trace_of(6))
    completed = router.tick()

    assert len(completed) == 1
    assert not [event for event in completed[0].events if event.code == DELTA_UNSENT]
    assert DELTA_UNSENT not in router.counts
    assert [(update.since, update.version) for update in coarse.updates] == [
        (0, 4),
        (4, 6),
    ]
    assert [update.version for update in per_record.updates] == [1, 2, 3, 4, 5, 6]

    tail = coarse.updates[-1]
    assert router.builder("t1") is None, "the tail is handed over at release"
    graph = completed[0].graph
    assert graph is not None
    assert spanweave.dumps(tail.builder.graph()) == spanweave.dumps(graph)

    opening = coarse.first_graph
    assert opening is not None
    folded = opening
    for update in coarse.updates[1:]:
        folded = update.delta.fold(folded)
    assert spanweave.dumps(folded) == spanweave.dumps(graph), (
        "the deltas a coarse subscriber got do not add up to the completed graph"
    )


def test_a_trailing_window_the_journal_cannot_produce_is_still_delta_unsent():
    """The one case the flush cannot serve, and it is not silent (§6.5).

    A caller that narrowed a `Routed.builder`'s own journal (§6.4) has taken
    retention over, so the tail is a window the library refuses to produce.
    `delta_unsent` is then what it was before the trailing delta existed — a
    report, carrying the library's own code, on the same `Completed`.
    """
    subscriptions = Subscriptions()
    coarse = Collector()
    subscriptions.subscribe(coarse, every=4)
    router = Router(
        completion=Completion(policies=(Cap(6),), now=lambda: 1_000.0),
        subscriptions=subscriptions,
    )

    route_all(router, trace_of(6))
    builder = router.builder("t1")
    assert builder is not None
    builder.retain(1)
    completed = router.tick()

    assert len(completed) == 1
    unsent = [event for event in completed[0].events if event.code == DELTA_UNSENT]
    assert len(unsent) == 1
    assert unsent[0].trace_id == "t1"
    assert unsent[0].version == 6
    assert unsent[0].spanweave_code == "delta_unavailable"
    assert "4" in unsent[0].detail
    assert router.counts[DELTA_UNSENT] == 1
    assert [update.version for update in coarse.updates] == [4]


def test_a_completion_nobody_is_behind_on_reports_no_unsent_window():
    subscriptions = Subscriptions()
    subscriptions.subscribe(Collector())
    router = Router(
        completion=Completion(policies=(Cap(2),), now=lambda: 1_000.0),
        subscriptions=subscriptions,
    )

    route_all(router, trace_of(2))
    completed = router.tick()

    assert len(completed) == 1
    assert not [event for event in completed[0].events if event.code == DELTA_UNSENT]
    assert DELTA_UNSENT not in router.counts


def test_released_forgets_the_cursors_so_they_are_bounded_by_the_builders():
    """§6.4's second half: the cursors are one `int` per subscription per trace
    the router **currently holds**, which `max_traces` bounds."""
    subscriptions = Subscriptions()
    subscription = subscriptions.subscribe(Collector())
    router = Router(
        completion=Completion(policies=(Cap(1),), now=lambda: 1_000.0),
        subscriptions=subscriptions,
    )

    router.route(openinference("s0"))
    assert subscriptions.seen(subscription, "t1") == 1
    router.tick()
    assert subscriptions.seen(subscription, "t1") == 0
