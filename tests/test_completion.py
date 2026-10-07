"""Completion: the caller's policy, on the caller's clock (`SPEC.md` §5).

Every test here runs on a **fake clock the test owns**. That is not a
convenience, it is the reason §1.4 makes the clock a seam and `tests/gates.py`
fails the build over a `time` import: a timeout policy tested against the real
clock passes on a fast machine, flakes on a loaded one, and then gets tuned
until it asserts nothing. The clock below moves only when a test says so, so
"fires at this instant and not the one before" is a thing a test can state.

The load-bearing claims of this file:

- **Each policy fires exactly when its definition says**, tested from both
  sides of its boundary — one tick before (it must not) and at it (it must).
  A `Quiet` that fired one tick early is the mutation this file exists to catch.
- **A late arrival is an event, never silence**, and **never a mutation of the
  graph already written**: the first generation's file is read before and after,
  byte for byte, and the second generation is written beside it.
- **A policy sees no meaning.** `TraceState` is an id, a clock reading and four
  numbers, and the test that holds its field set is what keeps a completion
  policy from growing into a detector with a timeout (`SPEC.md` §5.6).
- **Forgetting a completion is the caller's bound and an event.** At
  `max_completed=N` the oldest completions are evicted with one `forgotten`
  each, and a record for a forgotten id is a first sighting with **no**
  `late_arrival` — which is the consequence of the policy, so it is asserted
  here rather than discovered by somebody live (`SPEC.md` §5.5). With the
  default `None` nothing is ever forgotten, and a test reads the rest of the
  suite's source to keep that true of the whole suite.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib

import pytest
import spanweave

from spanweave_live import (
    CAP,
    COMPLETED,
    FORGOTTEN,
    LATE_ARRIVAL,
    NOT_WRITTEN,
    QUIET,
    RELEASED,
    ROOT_ENDED,
    WRITTEN,
    Cap,
    Completion,
    Quiet,
    RootEnded,
    Router,
    TraceState,
    root_ended,
)

# --------------------------------------------------------------------------
# The fake clock, and the records. Both small on purpose: the corpus is gate
# A's business, and these put the router in states the corpus does not hold.
# --------------------------------------------------------------------------


class Clock:
    """A clock the test owns. It moves when the test moves it, never otherwise.

    `Callable[[], float]`, which is the whole of what `Completion` asks for
    (`SPEC.md` §5.2). The start is an arbitrary non-zero reading so that a
    policy comparing against `0.0` by accident is visible.
    """

    def __init__(self, at: float = 1_000.0) -> None:
        self.reading = at
        self.reads = 0

    def __call__(self) -> float:
        self.reads += 1
        return self.reading

    def tick(self, seconds: float = 1.0) -> None:
        self.reading += seconds


def openinference(
    span_id: str,
    *,
    trace: str = "t1",
    parent: str | None = None,
    end: float | None = 1_001.0,
) -> dict:
    """One OpenInference span, claimed by exactly one adapter.

    `end=None` omits `end_time` altogether, which is how a span that has not
    reported an end is spelled — `ended_at` is then `None` and `RootEnded` has
    nothing to fire on (`SPEC.md` §5.6).
    """
    record: dict = {
        "trace_id": trace,
        "span_id": span_id,
        "parent_id": parent,
        "name": f"chain.{span_id}",
        "start_time": 1_000.0,
        "attributes": {"openinference.span.kind": "CHAIN"},
    }
    if end is not None:
        record["end_time"] = end
    return record


def unclaimable(span_id: str, *, trace: str = "t1") -> dict:
    """A record no adapter claims, so the adapter surface says "no trace id"."""
    return {"trace_id": trace, "span_id": span_id, "name": f"mystery.{span_id}"}


def graph_of(*records: dict) -> spanweave.Graph:
    builder = spanweave.Builder()
    for record in records:
        builder.feed(record)
    return builder.graph()


def undigested(graph: spanweave.Graph) -> spanweave.Graph:
    """`graph` without the digest a `Builder` cannot carry (`spanweave` §10.4)."""
    assert graph.meta is not None
    return dataclasses.replace(
        graph, meta=dataclasses.replace(graph.meta, source_digest=None)
    )


def batch(*records: dict) -> bytes:
    body = b"".join(json.dumps(record).encode("utf-8") + b"\n" for record in records)
    return spanweave.dumps(undigested(spanweave.build(body)))


def router_with(*policies, clock: Clock, out_dir=None, **settings) -> Router:
    return Router(
        completion=Completion(policies=policies, now=clock, out_dir=out_dir),
        **settings,
    )


def codes(events) -> list[str]:
    return [event.code for event in events]


# --------------------------------------------------------------------------
# The surface `SPEC.md` §5.1 declares is the surface the code has.
# --------------------------------------------------------------------------


def test_completions_settings_are_keyword_only_as_SPEC_declares():
    """§5.1 declares `__init__(self, *, policies, now, out_dir)`.

    Same reason as §4.1's: three independent settings with no reading order, and
    a positional order would be a contract the spec never offered.
    """
    with pytest.raises(TypeError):
        Completion((Quiet(1.0),), Clock())  # type: ignore[misc]


def test_now_has_no_default_because_no_module_here_holds_a_clock():
    """The argument is required, and that is the design (`SPEC.md` §5.2).

    A default would mean a module under `spanweave_live/` importing `time`,
    which would mean an entry in `tests/gates.py`'s seam allowlist. Requiring
    the argument costs the caller one line and keeps `completion.py` out of that
    allowlist, whose one entry is `real.py`, for `time` and `http.server`
    (`tests/gates.py:237`).
    """
    with pytest.raises(TypeError):
        Completion(policies=(Quiet(1.0),))  # type: ignore[call-arg]


def test_the_seam_allowlist_does_not_name_this_batchs_module():
    """R3 is the batch that was expected to need a seam, and it did not.

    `tests/test_gates.py` holds the allowlist's whole contents; this asserts the
    half of it that is §5's, from the side that could have changed it, so the
    fact is stated where a reader of §5 is looking. `Completion.now` has no
    default, so `completion.py` imports no clock and needs no entry -- and the
    one entry the allowlist does have, R7's `real.py`, is what hands `now` the
    real `time.monotonic` from outside the package (`SPEC.md` §5.2, §8.2).

    This test asserted `SEAMS == {}` until R7, which was true of every batch
    before the one that *is* a caller.
    """
    from tests import gates

    assert "completion.py" not in gates.SEAMS
    assert dict(gates.SEAMS) == {"real.py": frozenset({"time", "http.server"})}


def test_a_router_without_a_completion_policy_completes_nothing():
    """R2's router, unchanged: no clock to read, no tick, every builder held.

    `completion=None` is the default, which is why gate A — which builds routers
    exactly this way — is untouched by this batch and is not measuring a timeout.
    """
    router = Router()
    assert router.completion is None
    router.route(openinference("a"))
    assert router.tick() == ()
    assert router.trace_ids == ("t1",)


def test_the_clock_is_read_once_per_record_and_once_per_tick():
    """One reading per call, and one reading per tick (`SPEC.md` §5.2).

    A tick evaluating two traces against two readings could complete one and not
    the other for a reason no caller could see, so the count below is the rule
    rather than a trivia about calls: three traces, one tick, one read.
    """
    clock = Clock()
    router = router_with(Quiet(1.0), clock=clock)
    for trace in ("t1", "t2", "t3"):
        router.route(openinference("a", trace=trace))
    assert clock.reads == 3

    clock.tick(5.0)
    assert len(router.tick()) == 3
    assert clock.reads == 4


# --------------------------------------------------------------------------
# Each policy fires exactly when its definition says. Both sides of every
# boundary: the tick before must not fire, the tick at it must.
# --------------------------------------------------------------------------


def test_quiet_fires_at_the_tick_its_seconds_are_up_and_not_the_one_before():
    """`Quiet(5.0)`: `now - last_record_at >= 5.0` (`SPEC.md` §5.3).

    This is the boundary the batch's named mutation moves. A `Quiet` that fired
    one tick early completes this trace at 4.0 seconds of silence, and the
    first assertion below is what catches it.
    """
    clock = Clock()
    router = router_with(Quiet(5.0), clock=clock)
    router.route(openinference("a"))

    for elapsed in (1.0, 1.0, 1.0, 1.0):  # 1.0 .. 4.0 seconds of silence
        clock.tick(elapsed)
        assert router.tick() == (), f"fired early, at {clock.reading - 1_000.0}s"

    clock.tick(1.0)  # exactly 5.0
    completed = router.tick()
    assert [done.trace_id for done in completed] == ["t1"]
    assert completed[0].policy == Quiet(5.0)
    assert completed[0].policy.code == QUIET


def test_quiet_fires_at_its_boundary_and_not_a_hair_before_it():
    """The boundary is inclusive, to the float: 4.999 is not 5.0."""
    clock = Clock()
    router = router_with(Quiet(5.0), clock=clock)
    router.route(openinference("a"))

    clock.tick(4.999)
    assert router.tick() == ()
    clock.tick(0.001)
    assert len(router.tick()) == 1


def test_a_record_restarts_quiets_silence():
    """A record is activity, so the silence starts again from it (`§5.3`)."""
    clock = Clock()
    router = router_with(Quiet(5.0), clock=clock)
    router.route(openinference("a"))

    clock.tick(4.0)
    assert router.tick() == ()
    router.route(openinference("b"))  # activity at 4.0
    clock.tick(4.0)  # 4.0 of silence since then, not 8.0
    assert router.tick() == ()
    clock.tick(1.0)
    assert len(router.tick()) == 1


def test_a_refused_record_is_activity_and_not_silence():
    """A re-sent span is the exporter still talking about this trace (`§5.3`).

    The record is refused — it is a node-id collision — and the refusal is
    counted. Treating that as silence would complete a trace that is plainly
    still arriving.
    """
    clock = Clock()
    router = router_with(Quiet(5.0), clock=clock)
    router.route(openinference("a"))

    clock.tick(4.0)
    resent = router.route(openinference("a"))
    assert codes(resent.events) == ["refused"]

    clock.tick(4.0)
    assert router.tick() == (), "a refused record was read as silence"
    clock.tick(1.0)
    assert len(router.tick()) == 1


def test_quiet_zero_completes_on_the_first_tick_after_a_record():
    """`Quiet(0)` is legal: how quiet is too quiet is the caller's number."""
    clock = Clock()
    router = router_with(Quiet(0.0), clock=clock)
    router.route(openinference("a"))
    assert len(router.tick()) == 1


def test_cap_fires_at_the_record_its_number_names_and_not_the_one_before():
    """`Cap(3)`: `records >= 3`, counting the builder's own version (`§5.3`)."""
    clock = Clock()
    router = router_with(Cap(3), clock=clock)

    router.route(openinference("a"))
    assert router.tick() == ()
    router.route(openinference("b"))
    assert router.tick() == (), "fired at two records, not three"
    router.route(openinference("c"))
    completed = router.tick()
    assert [done.trace_id for done in completed] == ["t1"]
    assert completed[0].policy == Cap(3)
    assert completed[0].policy.code == CAP
    assert completed[0].version == 3


def test_cap_counts_records_absorbed_and_not_records_offered():
    """A refused record was not absorbed, so it does not count (`§5.3`)."""
    clock = Clock()
    router = router_with(Cap(3), clock=clock)
    router.route(openinference("a"))
    router.route(openinference("b"))
    router.route(openinference("b"))  # refused: a node-id collision
    assert router.tick() == (), "a refused record was counted against the cap"
    router.route(openinference("c"))
    assert len(router.tick()) == 1


def test_root_ended_fires_when_the_grace_is_up_and_not_the_tick_before():
    """`RootEnded(2.0)`: an ended root seen, then 2.0 seconds (`§5.3`, `§5.6`).

    The grace runs from the tick that *saw* the ended root, which is the tick
    right after the root is absorbed here.
    """
    clock = Clock()
    router = router_with(RootEnded(2.0), clock=clock)
    router.route(openinference("root"))
    router.route(openinference("kid", parent="root"))

    clock.tick(1.0)
    assert router.tick() == (), "fired before the grace had even started"
    clock.tick(1.0)
    assert router.tick() == (), "fired one tick into a two-second grace"
    clock.tick(1.0)
    completed = router.tick()
    assert [done.trace_id for done in completed] == ["t1"]
    assert completed[0].policy == RootEnded(2.0)
    assert completed[0].policy.code == ROOT_ENDED


def test_root_ended_with_no_grace_fires_on_the_tick_that_sees_the_end():
    clock = Clock()
    router = router_with(RootEnded(0.0), clock=clock)
    router.route(openinference("root"))
    assert len(router.tick()) == 1


def test_root_ended_runs_its_grace_from_when_the_receiver_saw_it():
    """Not from the span's own `ended_at` (`SPEC.md` §5.2).

    This root ended at Unix second 1, decades before the receiver's clock
    reading of 1000. A policy that compared `ended_at` against `now` would see a
    grace of thirty-odd years already elapsed and complete the trace at once;
    the receiver waits its two seconds from the tick that saw the end, because
    the only clock it can reason about is its own.
    """
    clock = Clock(at=1_000.0)
    router = router_with(RootEnded(2.0), clock=clock)
    router.route(openinference("root", end=1.0))

    clock.tick(1.0)
    assert router.tick() == (), "the span's clock was compared against ours"
    clock.tick(1.0)
    assert router.tick() == (), "one second into a two-second grace"
    clock.tick(1.0)  # two seconds since the tick at 1001.0 that saw the end
    assert len(router.tick()) == 1


def test_root_ended_does_not_fire_while_the_root_has_not_ended():
    """A root with no `end_time` reported never satisfies it (`§5.6`)."""
    clock = Clock()
    router = router_with(RootEnded(0.0), clock=clock)
    router.route(openinference("root", end=None))
    router.route(openinference("kid", parent="root"))

    for _ in range(5):
        clock.tick(10.0)
        assert router.tick() == ()
    assert router.trace_ids == ("t1",)


def test_a_trace_of_nothing_but_orphans_has_no_root():
    """A child whose parent has not arrived is not a root (`§5.6`).

    Live, a trace's root arriving after its children is the ordinary case
    (`spanweave` §10.6), and this is the case that makes reading "no parent
    edge" alone wrong: the child has no `parent` edge either, and completing
    here would complete a trace whose real root is still in flight.
    """
    orphan = graph_of(openinference("kid", parent="root"))
    assert [d.code for d in orphan.diagnostics] == ["orphan_parent"]
    assert root_ended(orphan) is False

    clock = Clock()
    router = router_with(RootEnded(0.0), clock=clock)
    router.route(openinference("kid", parent="root"))
    clock.tick(10.0)
    assert router.tick() == (), "an orphan was read as a root"

    # And when the root does arrive, the same policy completes the trace.
    router.route(openinference("root"))
    clock.tick(1.0)
    assert len(router.tick()) == 1


def test_every_root_must_have_ended_and_not_merely_one_of_them():
    """Every root, not any one of them (`SPEC.md` §5.6).

    Two nodes with no parent are siblings at trace root (`spanweave` §4.3). With
    "any", one finished sibling would complete a trace whose other top-level
    operation was still running.
    """
    both = graph_of(openinference("a"), openinference("b"))
    assert root_ended(both) is True
    one_open = graph_of(openinference("a"), openinference("b", end=None))
    assert root_ended(one_open) is False

    clock = Clock()
    router = router_with(RootEnded(0.0), clock=clock)
    router.route(openinference("a"))
    router.route(openinference("b", end=None))
    clock.tick(10.0)
    assert router.tick() == (), "one ended root completed a trace with two"


def test_an_ended_root_is_recorded_once_and_the_grace_does_not_restart():
    """`root_ended_at` is the first sighting, not the latest (`§5.6`)."""
    clock = Clock()
    router = router_with(RootEnded(3.0), clock=clock)
    router.route(openinference("root"))

    clock.tick(1.0)
    assert router.tick() == ()  # sees the ended root here
    clock.tick(1.0)
    assert router.tick() == ()  # would restart a grace that restarted
    clock.tick(1.0)
    assert router.tick() == ()
    clock.tick(1.0)
    assert len(router.tick()) == 1


def test_the_policies_compose_as_any_of_in_the_callers_order():
    """First in the caller's tuple that fires is the one reported (`§5.4`)."""
    clock = Clock()
    router = router_with(Cap(2), Quiet(1.0), clock=clock)
    router.route(openinference("a"))
    clock.tick(5.0)
    completed = router.tick()
    assert completed[0].policy == Quiet(1.0), "the quiet one was second but fired"

    clock = Clock()
    router = router_with(Quiet(100.0), Cap(2), clock=clock)
    router.route(openinference("a"))
    router.route(openinference("b"))
    completed = router.tick()
    assert completed[0].policy == Cap(2)


def test_an_empty_policy_tuple_never_completes_anything():
    clock = Clock()
    router = router_with(clock=clock)
    router.route(openinference("a"))
    clock.tick(10_000.0)
    assert router.tick() == ()


# --------------------------------------------------------------------------
# What completing does: say so, materialize, write, release — each an event.
# --------------------------------------------------------------------------


def test_completing_releases_the_builder_and_the_trace_leaves_trace_ids():
    """The point of the section: a finished trace stops costing (`§2.3`)."""
    clock = Clock()
    router = router_with(Cap(1), clock=clock)
    router.route(openinference("a"))
    held = router.builder("t1")
    assert held is not None

    completed = router.tick()
    assert completed[0].version == 1
    assert router.builder("t1") is None
    assert router.trace_ids == ()


def test_each_step_of_completing_is_an_event_with_a_code(tmp_path):
    """Say so, write, release — in that order, counted (`§1.5`, `§5.4`)."""
    clock = Clock()
    router = router_with(Cap(1), clock=clock, out_dir=tmp_path)
    router.route(openinference("a"))
    clock.tick(4.0)

    completed = router.tick()
    assert codes(completed[0].events) == [COMPLETED, WRITTEN, RELEASED]
    assert router.counts == {COMPLETED: 1, WRITTEN: 1, RELEASED: 1}

    done, written, released = completed[0].events
    # The trace was open for four seconds of the receiver's clock.
    assert done.seconds == 4.0
    assert done.trace_id == "t1"
    assert "Cap(records=1)" in done.detail
    # A tick is not caused by a record, so the index is the arrival count.
    assert (done.index, written.index, released.index) == (1, 1, 1)
    assert written.detail == str(completed[0].path)
    assert released.seconds is None


def test_the_written_file_is_the_batch_graph_of_the_records_absorbed(tmp_path):
    """`spanweave.dump` of the final graph, which is `build` of the same records.

    The claim the project exists to make, at the one place R3 adds: a trace
    completed live and written out is the batch graph of its records, byte for
    byte (`SPEC.md` §4.7's comparison, minus the digest a `Builder` cannot
    carry).
    """
    records = (openinference("root"), openinference("kid", parent="root"))
    clock = Clock()
    router = router_with(Cap(2), clock=clock, out_dir=tmp_path)
    for record in records:
        router.route(record)

    completed = router.tick()
    path = completed[0].path
    assert path == tmp_path / "t1.json"
    assert path.read_bytes() == spanweave.dumps(completed[0].graph)
    assert path.read_bytes() == batch(*records)


def test_nothing_is_written_when_the_caller_named_no_directory():
    """No `out_dir` is not a failure and not an event: it is the default."""
    clock = Clock()
    router = router_with(Cap(1), clock=clock)
    router.route(openinference("a"))
    completed = router.tick()
    assert completed[0].path is None
    assert completed[0].graph is not None
    assert codes(completed[0].events) == [COMPLETED, RELEASED]


def test_a_trace_id_that_is_not_one_path_component_is_not_written(tmp_path):
    """A trace id is untrusted input, so no file is named from this one (`§5.4`).

    The trace id here is a relative path out of the directory the caller named.
    The receiver writes nothing, says `not_written` with the reason, and the
    directory stays empty — the record is still absorbed and the trace still
    completes, because refusing to write is not refusing telemetry (`§1.3`).
    """
    out = tmp_path / "out"
    out.mkdir()
    clock = Clock()
    router = router_with(Cap(1), clock=clock, out_dir=out)
    router.route(openinference("a", trace="../escaped"))

    completed = router.tick()
    assert completed[0].trace_id == "../escaped"
    assert completed[0].path is None
    assert completed[0].graph is not None, "the graph was still materialized"
    assert codes(completed[0].events) == [COMPLETED, NOT_WRITTEN, RELEASED]
    assert "not usable as one path component" in completed[0].events[1].detail
    assert list(out.iterdir()) == []
    assert list(tmp_path.iterdir()) == [out], "a file was written outside out_dir"


@pytest.mark.parametrize("trace_id", ["", ".", "..", "a/b", "a\\b", "a\0b"])
def test_the_ids_no_file_is_named_from(trace_id, tmp_path):
    from spanweave_live.completion import usable_as_one_path_component

    assert usable_as_one_path_component(trace_id) is False
    assert usable_as_one_path_component("t1") is True


def test_a_write_that_fails_is_an_event_and_not_a_crash(tmp_path):
    """A receiver that died on one unwritable file would lose the rest (`§5.4`)."""
    blocked = tmp_path / "a-file"
    blocked.write_bytes(b"not a directory")
    clock = Clock()
    router = router_with(Cap(1), clock=clock, out_dir=blocked / "out")
    router.route(openinference("a"))

    completed = router.tick()
    assert codes(completed[0].events) == [COMPLETED, NOT_WRITTEN, RELEASED]
    assert "failed" in completed[0].events[1].detail
    assert completed[0].path is None
    # And the router is still usable afterwards.
    router.route(openinference("b", trace="t2"))
    assert router.trace_ids == ("t2",)


def test_the_no_trace_builder_is_never_completed():
    """It is not a trace, so no timeout is about it (`§4.5`, `§5.4`)."""
    clock = Clock()
    router = router_with(Quiet(1.0), clock=clock)
    router.route(unclaimable("a"))
    clock.tick(1_000.0)

    assert router.tick() == ()
    assert router.no_trace.version == 1


def test_completing_frees_a_slot_at_the_cap():
    """Completion releases; the cap then has room (`§4.5`'s one direction)."""
    clock = Clock()
    router = router_with(Cap(1), clock=clock, max_traces=1)
    router.route(openinference("a", trace="t1"))
    refused = router.route(openinference("b", trace="t2"))
    assert codes(refused.events) == ["refused_at_cap"]

    assert len(router.tick()) == 1
    admitted = router.route(openinference("b", trace="t2"))
    assert admitted.events == ()
    assert router.trace_ids == ("t2",)


def test_ticks_complete_in_trace_ids_order():
    """One clock reading, and a deterministic order over it (`§5.4`)."""
    clock = Clock()
    router = router_with(Quiet(1.0), clock=clock)
    for trace in ("t3", "t1", "t2"):
        router.route(openinference("a", trace=trace))
    assert router.trace_ids == ("t3", "t1", "t2")

    clock.tick(5.0)
    completed = router.tick()
    assert [done.trace_id for done in completed] == ["t3", "t1", "t2"]


# --------------------------------------------------------------------------
# A late arrival: an event, a new builder, and never a rewritten file.
# --------------------------------------------------------------------------


def test_a_late_record_opens_a_new_builder_and_says_so_with_the_gap():
    """`late_arrival` with the trace id and the gap (`SPEC.md` §5.5)."""
    clock = Clock()
    router = router_with(Cap(1), clock=clock)
    router.route(openinference("a"))
    assert len(router.tick()) == 1

    clock.tick(7.5)
    late = router.route(openinference("b"))
    assert codes(late.events) == [LATE_ARRIVAL]
    event = late.events[0]
    assert event.trace_id == "t1"
    assert event.seconds == 7.5
    assert router.counts[LATE_ARRIVAL] == 1

    # Not refused, not dropped, not held: absorbed, into a builder of its own.
    assert late.version == 1
    assert late.builder is not None
    assert late.builder.version == 1
    assert router.builder("t1") is late.builder


def test_a_late_arrival_is_never_silent():
    """The event is the whole point: a vanished builder with nothing said about
    it is the silence this project does not do (`§1.5`)."""
    clock = Clock()
    router = router_with(Cap(1), clock=clock)
    router.route(openinference("a"))
    router.tick()
    clock.tick(1.0)
    assert router.route(openinference("b")).events != ()


def test_a_re_opened_trace_rejoins_trace_ids_at_the_end():
    """Arrival order of builders, which is what the router has (`§4.3`)."""
    clock = Clock()
    router = router_with(Cap(1), clock=clock)
    router.route(openinference("a", trace="t1"))
    assert len(router.tick()) == 1
    router.route(openinference("a", trace="t2"))
    assert router.trace_ids == ("t2",)

    router.route(openinference("b", trace="t1"))
    assert router.trace_ids == ("t2", "t1")


def test_the_second_generations_policies_are_its_own():
    """This generation's records, this generation's silence (`§5.5`)."""
    clock = Clock()
    router = router_with(Cap(2), clock=clock)
    router.route(openinference("a"))
    router.route(openinference("b"))
    assert len(router.tick()) == 1

    clock.tick(1.0)
    router.route(openinference("c"))
    assert router.tick() == (), "the new builder inherited the old count"
    router.route(openinference("d"))
    completed = router.tick()
    assert completed[0].version == 2


def test_a_late_arrival_never_rewrites_the_graph_already_written(tmp_path):
    """The file the receiver already wrote is not rewritten or appended to.

    `SPEC.md` §5.5 read as a test: the first generation's bytes are taken before
    the late record arrives and again after the second generation completes, and
    they are the same bytes. The second generation is written **beside** the
    first, under its generation's name. Two files are two honest statements; one
    overwritten file is a lost one.
    """
    clock = Clock()
    router = router_with(Cap(1), clock=clock, out_dir=tmp_path)
    router.route(openinference("a"))
    first = router.tick()[0]
    assert first.path == tmp_path / "t1.json"
    before = first.path.read_bytes()

    clock.tick(3.0)
    late = router.route(openinference("b"))
    assert codes(late.events) == [LATE_ARRIVAL]
    assert first.path.read_bytes() == before, "the written file changed on arrival"

    second = router.tick()[0]
    assert second.path == tmp_path / "t1.2.json"
    assert first.path.read_bytes() == before, "the first file was rewritten"
    assert second.path.read_bytes() != before
    assert sorted(path.name for path in tmp_path.iterdir()) == ["t1.2.json", "t1.json"]

    # Each file is the batch graph of the records of its own generation.
    assert before == batch(openinference("a"))
    assert second.path.read_bytes() == batch(openinference("b"))


def test_a_third_generation_is_written_beside_the_first_two(tmp_path):
    clock = Clock()
    router = router_with(Cap(1), clock=clock, out_dir=tmp_path)
    for span in ("a", "b", "c"):
        router.route(openinference(span))
        assert len(router.tick()) == 1
        clock.tick(1.0)
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "t1.2.json",
        "t1.3.json",
        "t1.json",
    ]


# --------------------------------------------------------------------------
# The book is bounded by the caller's `max_completed`, and forgetting is an
# event (`SPEC.md` §5.5, `TASKS.md`'s decision of 2026-10-06).
# --------------------------------------------------------------------------


def completed_ids(router: Router) -> list[str]:
    """The trace ids this router still remembers a completion for.

    The private book, read deliberately: `SPEC.md` §5.5 is a claim about memory,
    and a test that only read the public surface could not tell a bound that
    evicted from one that emitted an event and kept the entry.
    """
    return [
        trace_id
        for trace_id, book in router._books.items()
        if book.completed_at is not None
    ]


def test_the_oldest_completion_is_forgotten_at_the_bound_and_says_so():
    """`max_completed=2`, three completions: one `forgotten`, the oldest (§5.5).

    The event carries the trace id and, in `at`, the clock reading at which that
    trace was completed -- a field and not a sentence, for §4.1's reason. It
    rides on the `Completed` of the trace whose completion pushed the book over,
    because a tick that completes nothing has no `Completed` to report on.
    """
    clock = Clock()
    router = router_with(Cap(1), clock=clock, max_completed=2)

    completions = {}
    for trace in ("t1", "t2", "t3"):
        clock.tick(1.0)
        router.route(openinference("a", trace=trace))
        done = router.tick()
        assert len(done) == 1
        completions[trace] = clock.reading

    assert completed_ids(router) == ["t2", "t3"], "the bound did not evict"
    assert router.counts[FORGOTTEN] == 1

    # One event, on the completion that pushed the book past the bound.
    forgotten = [event for event in done[0].events if event.code == FORGOTTEN]
    assert len(forgotten) == 1
    assert forgotten[0].trace_id == "t1"
    assert forgotten[0].at == completions["t1"]
    assert forgotten[0].seconds is None, "a completion instant is not a duration"
    # Bookkeeping after the decision: `released` stays §5.4's fourth event.
    assert codes(done[0].events) == [COMPLETED, RELEASED, FORGOTTEN]


def test_a_record_for_a_forgotten_trace_is_a_first_sighting(tmp_path):
    """Generation 1, and **no `late_arrival`** -- the trade the bound buys.

    The gap a late arrival would carry is the fact that was evicted, so there is
    nothing to report and the receiver does not invent one (`SPEC.md` §5.5). The
    file name is the proof it is generation 1: `t1.json`, not `t1.2.json` -- and
    that is the second half of the trade, asserted here because it is the one
    place the bound costs more than memory. §5.5's "the file already written is
    not rewritten" holds while the completion is **remembered**; a generation the
    receiver cannot number is written over the first one's file, and the
    alternative is remembering the number the caller asked it to forget.
    """
    clock = Clock()
    router = router_with(Cap(1), clock=clock, max_completed=1, out_dir=tmp_path)
    router.route(openinference("a", trace="t1"))
    first = router.tick()[0]
    assert first.path == tmp_path / "t1.json"
    before = first.path.read_bytes()

    clock.tick(1.0)
    router.route(openinference("a", trace="t2"))
    assert codes(router.tick()[0].events) == [COMPLETED, WRITTEN, RELEASED, FORGOTTEN]
    assert completed_ids(router) == ["t2"]

    clock.tick(9.0)
    again = router.route(openinference("b", trace="t1"))
    assert again.events == (), "a forgotten trace was reported as a late arrival"
    assert LATE_ARRIVAL not in router.counts
    # Absorbed, into a trace this router has no memory of.
    assert again.version == 1
    # Generation 1 again, so this is written OVER the first generation's file.
    assert router.tick()[0].path == tmp_path / "t1.json"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["t1.json", "t2.json"]
    assert (tmp_path / "t1.json").read_bytes() == batch(openinference("b", trace="t1"))
    assert (tmp_path / "t1.json").read_bytes() != before


def test_a_record_for_a_remembered_trace_is_still_a_late_arrival_with_the_gap():
    """The bound changes nothing for a completion still in the book (§5.5)."""
    clock = Clock()
    router = router_with(Cap(1), clock=clock, max_completed=2)
    router.route(openinference("a", trace="t1"))
    assert len(router.tick()) == 1
    clock.tick(1.0)
    router.route(openinference("a", trace="t2"))
    assert len(router.tick()) == 1
    assert completed_ids(router) == ["t1", "t2"]

    clock.tick(4.5)
    late = router.route(openinference("b", trace="t1"))
    assert codes(late.events) == [LATE_ARRIVAL]
    assert late.events[0].trace_id == "t1"
    assert late.events[0].seconds == 5.5, "the gap is from t1's own completion"
    assert late.events[0].at is None


def test_the_evictions_of_one_tick_are_oldest_first_and_one_event_each():
    """Three traces completing in one tick at `max_completed=1` (§5.5).

    Oldest completion first, ties broken by first-arrival order, so what a bound
    throws away is a function of the stream and the clock -- never of a dict's
    hashing (`CLAUDE.md` 8). Here the three complete against **one** clock
    reading, so every `completed_at` is equal and only the tie-break orders
    them: `t3` arrived first, so `t3` is forgotten first.
    """
    clock = Clock()
    router = router_with(Quiet(1.0), clock=clock, max_completed=1)
    for trace in ("t3", "t1", "t2"):
        router.route(openinference("a", trace=trace))
    clock.tick(5.0)

    completed = router.tick()
    assert [done.trace_id for done in completed] == ["t3", "t1", "t2"]
    forgotten = [
        (event.trace_id, event.at)
        for done in completed
        for event in done.events
        if event.code == FORGOTTEN
    ]
    assert forgotten == [("t3", clock.reading), ("t1", clock.reading)]
    assert completed_ids(router) == ["t2"]
    assert router.counts[FORGOTTEN] == 2


def test_oldest_means_oldest_completion_and_not_oldest_arrival():
    """A trace that arrived first and completed last is forgotten last (§5.5).

    The two orders differ here on purpose: `t1` arrives first and runs long,
    `t2` and `t3` arrive later and end at once. "Oldest" is about the
    completion, because the book is a record *of a completion* and the bound is
    on how many of those are remembered.
    """
    clock = Clock()
    router = router_with(Cap(2), clock=clock, max_completed=2)
    router.route(openinference("a", trace="t1"))
    for trace in ("t2", "t3"):
        clock.tick(1.0)
        router.route(openinference("a", trace=trace))
        router.route(openinference("b", trace=trace))
        assert len(router.tick()) == 1
    assert completed_ids(router) == ["t2", "t3"]

    # t1 ends last, so t2 -- the first *completion* -- is what goes.
    clock.tick(1.0)
    router.route(openinference("b", trace="t1"))
    done = router.tick()[0]
    assert [event.trace_id for event in done.events if event.code == FORGOTTEN] == [
        "t2"
    ]
    assert completed_ids(router) == ["t3", "t1"]


def test_the_remembered_completions_are_counted_and_not_recounted():
    """The count is `len(_books) - len(_builders)`, and that identity holds.

    `_forget` reads how many completions are remembered as a subtraction, so a
    bound of `N` costs nothing per completion (`SPEC.md` §5.5, §2.3). What the
    subtraction rests on is that every builder has a book, which this drives
    from every side the router has: an open trace, a completion, a late arrival
    that re-opens one, a record the cap refused, and a record with no trace id
    at all.
    """
    clock = Clock()
    router = router_with(Cap(1), clock=clock, max_traces=2)

    def identity() -> None:
        assert len(router._books) - len(router._builders) == len(completed_ids(router))

    identity()
    router.route(unclaimable("u"))
    identity()
    router.route(openinference("a", trace="t1"))
    router.route(openinference("a", trace="t2"))
    identity()
    refused = router.route(openinference("a", trace="t3"))
    assert codes(refused.events) == ["refused_at_cap"]
    identity()
    assert len(router.tick()) == 2
    identity()

    clock.tick(1.0)
    late = router.route(openinference("b", trace="t1"))
    assert codes(late.events) == [LATE_ARRIVAL]
    identity()
    assert len(router.tick()) == 1
    identity()


def test_an_open_trace_is_never_forgotten_however_small_the_bound():
    """The bound is on **completed** ids, and an open book is live state (§5.5).

    `Quiet` reads `last_record_at` off the book of a trace whose builder the
    router still holds, so evicting one would complete a trace early for a
    reason no caller could see. Those are bounded by `max_traces` instead.
    """
    clock = Clock()
    router = router_with(Quiet(10.0), Cap(2), clock=clock, max_completed=0)
    # t1 completes on `Cap(2)`; t2 and t3 stay open on `Quiet(10.0)`.
    router.route(openinference("a", trace="t1"))
    router.route(openinference("b", trace="t1"))
    router.route(openinference("a", trace="t2"))
    router.route(openinference("a", trace="t3"))
    assert [done.trace_id for done in router.tick()] == ["t1"]
    assert router.trace_ids == ("t2", "t3")
    assert completed_ids(router) == []
    assert sorted(router._books) == ["t2", "t3"], "an open trace was forgotten"

    # And their silence is still measured from their own last record.
    clock.tick(9.0)
    assert router.tick() == ()
    clock.tick(1.0)
    assert [done.trace_id for done in router.tick()] == ["t2", "t3"]


@pytest.mark.parametrize("bound", [0, -1])
def test_a_bound_of_zero_forgets_in_the_tick_that_completed(bound):
    """Legal, and the number is the caller's (`SPEC.md` §5.5, §1.2).

    A completion is reported and then immediately forgotten, so the next record
    for that trace is a first sighting. A negative bound reads as zero, as a
    `max_traces` below zero does, and neither is validated: no record can cause
    the number.
    """
    clock = Clock()
    router = router_with(Cap(1), clock=clock, max_completed=bound)
    router.route(openinference("a"))
    done = router.tick()[0]
    assert codes(done.events) == [COMPLETED, RELEASED, FORGOTTEN]
    assert router._books == {}

    clock.tick(3.0)
    assert router.route(openinference("b")).events == ()


def test_nothing_is_ever_forgotten_without_a_bound():
    """`None` is the default and forgets nothing: R3's behaviour, unchanged.

    The upgrade adds no silence a caller did not ask for, which is why the
    default is the shipped one and not a number somebody guessed.
    """
    clock = Clock()
    router = router_with(Cap(1), clock=clock)
    assert router.max_completed is None
    assert Router().max_completed is None

    for index in range(200):
        clock.tick(1.0)
        router.route(openinference("a", trace=f"t{index}"))
        assert codes(router.tick()[0].events) == [COMPLETED, RELEASED]
    assert len(completed_ids(router)) == 200
    assert FORGOTTEN not in router.counts


def test_no_other_test_in_the_suite_sets_a_bound():
    """With `None`, nothing is ever forgotten **across the whole suite**.

    The claim is about every other test file, gate A included, so it is read off
    the suite's own source rather than asserted one router at a time: if no test
    outside this file constructs a `max_completed`, every router the rest of the
    suite builds has the default and forgets nothing. A test that adds a bound
    elsewhere has to come and say so here.
    """
    here = pathlib.Path(__file__).resolve()
    elsewhere = sorted(
        path.name
        for path in here.parent.glob("*.py")
        if path != here and "max_completed" in path.read_text(encoding="utf-8")
    )
    # R7's `tests/test_cli.py` is the one exception and it is named here rather
    # than quietly allowed: `--max-completed` is how this batch's own
    # consequence -- a forgotten id writing its graph OVER the earlier file --
    # is proved from the outside (`SPEC.md` §8.5). It sets the bound in the
    # processes it runs, never in a router of this suite's, which is what the
    # second assertion holds: so every router the rest of the suite builds,
    # gate A's included, still has the default and forgets nothing.
    assert elsewhere == ["test_cli.py"]
    assert "max_completed=" not in (here.parent / "test_cli.py").read_text(
        encoding="utf-8"
    )


# --------------------------------------------------------------------------
# What a policy may not look at (`SPEC.md` §5.6).
# --------------------------------------------------------------------------


def test_a_policy_sees_an_id_a_clock_and_four_numbers_and_no_meaning():
    """`TraceState`'s field set, held exactly (`SPEC.md` §5.6).

    No span, no node, no name, no kind. A completion policy that could fire on
    `name == "final_answer"` would be a detector with a timeout, and the
    receiver carries no rules (`SPEC.md` §1.2). This test is what makes adding
    such a field a deliberate act with a spec change attached.
    """
    assert [field.name for field in dataclasses.fields(TraceState)] == [
        "trace_id",
        "now",
        "records",
        "first_record_at",
        "last_record_at",
        "root_ended_at",
    ]


def test_root_ended_reads_the_graph_and_never_a_record():
    """`root_ended` takes a `spanweave.Graph` and nothing else (`§1.1`, `§5.6`).

    Its parameter is the library's own type, so the only thing it can read is
    what the graph states. A dialect read would need a record, and it has none.
    """
    signature = root_ended.__annotations__
    assert signature["graph"] == "Graph"
    assert signature["return"] == "bool"
    with pytest.raises(AttributeError):
        root_ended(openinference("a"))  # type: ignore[arg-type]


def test_completion_holds_no_opinion_about_a_graph_it_completed():
    """It hands the graph over; it computes nothing about it (`§1.2`).

    `Completed` carries the trace id, the policy, the version, the graph, the
    path and the events. No score, no severity, no verdict, no "ok".
    """
    from spanweave_live.routing import Completed

    assert [field.name for field in dataclasses.fields(Completed)] == [
        "trace_id",
        "policy",
        "version",
        "graph",
        "path",
        "events",
    ]
