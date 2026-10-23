"""Pins: what the three completion policies do on the zoo's captures (V3).

The zoo's audit ran one policy, `--quiet 0`, and saw four traces complete once
per body (its `PROBES.md` L3); one more, Z5's, has no root and was never
completed by `RootEnded` (L4). This file runs each policy at values the audit
never ran, over the same captures (`SPEC.md` §4.8), on a fake clock, and pins
what it does. **These are pins, not fixes**: no policy changed for them, and
every assertion here holds on the parent of the batch that added it, except
one that reads a sentence that batch wrote into the documents. They are
readings of `SPEC.md` §5.3's definitions and §5.5's generations, held so that
a policy which starts firing at another instant fails here rather than in
somebody's stream.

The schedule is one for every policy (`SPEC.md` §5.3): body *k* of a capture,
counting from 0, is fed at `now = k`, and after it the router is ticked twice,
at `now = k` and at `now = k + 0.5`; *last* is the last body's *k*. A `Cap`
run also ticks after every record, at its body's instant, so that "at the
*N*-th record" is a thing a test can state.

What the file holds:

- On Z3, Z1, Z2 and Z6 (the real runs, whose root arrives last), `Quiet(0.5)`
  completes **once per body**, and every generation's written file is
  `spanweave.build` of **its own body**, byte for byte -- of the records since
  the previous generation fired, not of the stream's prefix, because
  generations are never merged. Every generation before the last carries
  `orphan_parent` because its parents are in a later one; the last holds the
  root; each after the first opens as `late_arrival` (`SPEC.md` §5.5).
- `Quiet(2.0)`, `RootEnded(1.0)` and `Cap(N)` each complete those four once,
  at the instant §5.3 states, with the end-of-input graph byte for byte.
- On Z5, real and recorded, `RootEnded` never completes the trace, at any
  grace and up to `now = 10^6`, because its graph has no root; `Quiet` and
  `Cap` do, and `Cap(5)` leaves it to end of input.
- On Z3 and Z1, `RootEnded` acts per generation (B5): body 0 re-fed after
  the trace completed opens generation 2, which `RootEnded` alone never
  completes on generation 1's root, up to `now = 10^6`, and end of input
  completes it beside generation 1.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from typing import NamedTuple

import pytest
import spanweave
from spanweave import EdgeKind

from spanweave_live import (
    COMPLETED,
    LATE_ARRIVAL,
    Cap,
    Completed,
    Completion,
    Event,
    Framer,
    Policy,
    Quiet,
    RootEnded,
    Router,
    root_ended,
)
from tests.test_zoo_gate import L3_CAPTURES, captures, json_bodies, zoo_records

REPO = Path(__file__).resolve().parent.parent
SPEC = REPO / "SPEC.md"
README = REPO / "README.md"

#: The second tick after each body, this far past the body's own instant.
#: Bodies are a second apart, so it falls between them.
HALF = 0.5
#: Fires at the second tick after every body: one generation per body.
PER_BODY = 0.5
#: Longer than the gap between bodies: fires only once the stream has stopped.
WHOLE = 2.0
#: `RootEnded`'s grace on the four captures whose root arrives last.
GRACE = 1.0
#: The graces and silences Z5 is run at.
ROOTLESS_SECONDS = (0.0, 1.0, 3600.0)
#: The furthest tick Z5 is run to.
HORIZON = 10.0**6
#: Z5, real and recorded: one body, four records, and no root.
ROOTLESS = ("z5/2026-10-13-real", "z5/2026-10-13-recorded")
#: The two captures a second generation is opened on, by re-feeding body 0.
REFED = ("z3/2026-10-13-real", "z1/2026-10-13-real")


class Tick(NamedTuple):
    now: float
    routed: int
    completed: tuple[Completed, ...]


class Run(NamedTuple):
    trace_id: str
    ticks: tuple[Tick, ...]
    late: tuple[Event, ...]
    written: dict[str, bytes]
    router: Router
    #: The fake clock `router`'s completion reads, for a test that goes on.
    clock: list[float]

    @property
    def completions(self) -> list[tuple[Tick, Completed]]:
        return [(tick, done) for tick in self.ticks for done in tick.completed]


def last(capture: str) -> float:
    """The instant the capture's last body is fed at: its index, from 0."""
    return float(len(json_bodies(capture)) - 1)


def drive(
    capture: str,
    policies: tuple[Policy, ...],
    out: Path,
    *,
    per_record: bool = False,
    at_body: bool = True,
    then: tuple[float, ...] = (),
) -> Run:
    """The capture through one `Framer` and one `Router` on §5.3's schedule.

    `at_body=False` drops the tick at the body's own instant and keeps the one
    half a second after it, which is the one variation of the schedule this
    file runs, and only to show where `RootEnded`'s grace runs from.

    Every tick is kept, with the clock reading it ran at and how many records
    had been routed, so a test can say at which instant something completed
    and that no other tick completed anything.
    """
    clock = [0.0]
    router = Router(
        completion=Completion(policies=policies, now=lambda: clock[0], out_dir=out)
    )
    framer = Framer()
    ticks: list[Tick] = []
    late: list[Event] = []
    trace_ids: set[str] = set()

    def tick(now: float) -> None:
        clock[0] = now
        ticks.append(Tick(now, router.routed, router.tick()))

    for k, body in enumerate(json_bodies(capture)):
        at = float(k)
        clock[0] = at
        for record in framer.document(body).records:
            routed = router.route(record)
            assert routed.trace_id is not None
            trace_ids.add(routed.trace_id)
            late.extend(e for e in routed.events if e.code == LATE_ARRIVAL)
            if per_record:
                tick(at)
        if at_body:
            tick(at)
        tick(at + HALF)
    for now in then:
        assert now > ticks[-1].now, "the clock only moves forward here"
        tick(now)
    (trace_id,) = trace_ids
    written = {path.name: path.read_bytes() for path in sorted(out.iterdir())}
    return Run(trace_id, tuple(ticks), tuple(late), written, router, clock)


def undigested(graph: spanweave.Graph) -> spanweave.Graph:
    """`graph` without the digest a `Builder` cannot carry (`SPEC.md` §4.7)."""
    assert graph.meta is not None
    return dataclasses.replace(
        graph, meta=dataclasses.replace(graph.meta, source_digest=None)
    )


def batch_of(*bodies: bytes) -> bytes:
    """`spanweave.build` of these bodies as one stream, as the zoo gate builds."""
    return spanweave.dumps(undigested(spanweave.build(b"\n".join(bodies) + b"\n")))


def orphans(graph: spanweave.Graph) -> int:
    return sum(1 for d in graph.diagnostics if d.code == "orphan_parent")


def end_of_input(run: Run, out: Path) -> tuple[Completed, ...]:
    """The CLI's end of input (`SPEC.md` §8.5): one `Cap(0)` tick."""
    clock = run.ticks[-1].now
    run.router.completion = Completion(
        policies=(Cap(0),), now=lambda: clock, out_dir=out
    )
    return run.router.tick()


# --------------------------------------------------------------------------
# What a generation is: Quiet(0.5) on the four captures whose root is last.
# --------------------------------------------------------------------------


class Generations(NamedTuple):
    bodies: int
    generations: int
    late_arrivals: int
    with_orphan_parent: int
    with_an_ended_root: int


def generation_name(trace_id: str, n: int) -> str:
    """`SPEC.md` §5.5: `<trace_id>.json`, then `<trace_id>.<n>.json`."""
    return f"{trace_id}.json" if n == 1 else f"{trace_id}.{n}.json"


@pytest.mark.parametrize("capture", L3_CAPTURES)
def test_quiet_half_a_second_completes_once_per_body_and_merges_nothing(
    capture, tmp_path
):
    bodies = json_bodies(capture)
    run = drive(capture, (Quiet(PER_BODY),), tmp_path)
    completions = run.completions

    # Once per body, at the tick half a second after it, and at no other.
    assert [tick.now for tick, _ in completions] == [
        k + HALF for k in range(len(bodies))
    ]
    per_body = zoo_records()[capture]
    assert [done.version for _, done in completions] == list(per_body)
    assert sum(done.version for _, done in completions) == run.router.routed

    # Each generation is the batch graph of its own body -- not of the prefix.
    assert list(run.written) == sorted(
        generation_name(run.trace_id, n) for n in range(1, len(bodies) + 1)
    )
    for n, body in enumerate(bodies, start=1):
        assert run.written[generation_name(run.trace_id, n)] == batch_of(body), n

    # The ones before the last are missing parents a later one holds; the last
    # holds the root, and it has ended.
    graphs = [done.graph for _, done in completions]
    assert all(graph is not None for graph in graphs)
    *earlier, final = graphs
    assert final is not None
    assert all(g is not None and orphans(g) > 0 for g in earlier)
    assert all(g is not None and not root_ended(g) for g in earlier)
    assert root_ended(final)

    # Every generation after the first opens on its body's first record as a
    # late arrival, half a second after the previous one was completed.
    firsts = [sum(per_body[:k]) + 1 for k in range(1, len(bodies))]
    assert [event.index for event in run.late] == firsts
    assert [event.seconds for event in run.late] == [1.0 - HALF] * len(firsts)
    assert run.router.counts[COMPLETED] == len(bodies)
    assert run.router.counts.get(LATE_ARRIVAL, 0) == len(bodies) - 1


def measured_generations(capture: str, out: Path) -> Generations:
    run = drive(capture, (Quiet(PER_BODY),), out)
    graphs = [done.graph for _, done in run.completions]
    assert all(graph is not None for graph in graphs)
    return Generations(
        bodies=len(json_bodies(capture)),
        generations=len(graphs),
        late_arrivals=len(run.late),
        with_orphan_parent=sum(1 for g in graphs if g is not None and orphans(g)),
        with_an_ended_root=sum(1 for g in graphs if g is not None and root_ended(g)),
    )


def section(heading: str) -> str:
    spec = SPEC.read_text(encoding="utf-8")
    start = spec.index(f"### {heading} ")
    end = spec.index("\n### ", start + 1)
    return spec[start:end]


def test_section_5_5_s_generation_table_is_what_this_file_measures(tmp_path):
    """§5.5's table is a citation, and this re-derives every cell of it."""
    rows = re.findall(
        r"^\| `([^`]+)` \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|$",
        section("5.5"),
        re.M,
    )
    declared = {
        capture: Generations(*(int(n) for n in numbers)) for capture, *numbers in rows
    }
    measured = {
        capture: measured_generations(capture, tmp_path / capture.replace("/", "_"))
        for capture in L3_CAPTURES
    }
    assert declared == measured


# --------------------------------------------------------------------------
# The other three, on the same four: once, at §5.3's instant, the whole graph.
# --------------------------------------------------------------------------


def only_completion(run: Run) -> tuple[Tick, Completed]:
    (completion,) = run.completions
    return completion


@pytest.mark.parametrize("capture", L3_CAPTURES)
def test_quiet_two_seconds_completes_once_after_the_stream_stops(capture, tmp_path):
    end = last(capture) + WHOLE
    run = drive(capture, (Quiet(WHOLE),), tmp_path, then=(end - HALF, end))
    tick, done = only_completion(run)
    assert tick.now == end
    assert done.version == run.router.routed
    assert run.written == {f"{run.trace_id}.json": batch_of(*json_bodies(capture))}
    assert run.late == ()


@pytest.mark.parametrize("capture", L3_CAPTURES)
def test_root_ended_completes_once_a_grace_after_the_last_body(capture, tmp_path):
    bodies = json_bodies(capture)
    # The premise: no prefix before the last body has an ended root.
    for k in range(1, len(bodies)):
        assert not root_ended(spanweave.build(b"\n".join(bodies[:k]) + b"\n")), k
    end = last(capture) + GRACE
    run = drive(capture, (RootEnded(GRACE),), tmp_path, then=(end,))
    tick, done = only_completion(run)
    assert tick.now == end
    assert done.version == run.router.routed
    assert run.written == {f"{run.trace_id}.json": batch_of(*bodies)}
    assert run.late == ()


@pytest.mark.parametrize("capture", L3_CAPTURES)
def test_root_ended_s_grace_runs_from_the_tick_that_first_saw_the_root(
    capture, tmp_path
):
    """Without the tick at `now = last`, the grace starts half a second later.

    The first tick to see the root ended is then `last + 0.5`, and the grace
    runs from there (`SPEC.md` §5.6) -- not from the last record's arrival,
    which is `last` either way -- so the tick at `last + 1.0` completes nothing
    and the one at `last + 1.5` completes the trace.
    """
    end = last(capture) + HALF + GRACE
    run = drive(
        capture,
        (RootEnded(GRACE),),
        tmp_path,
        at_body=False,
        then=(last(capture) + GRACE, end),
    )
    tick, done = only_completion(run)
    assert tick.now == end
    assert done.version == run.router.routed
    assert run.written == {f"{run.trace_id}.json": batch_of(*json_bodies(capture))}


# --------------------------------------------------------------------------
# RootEnded acts per generation: a later one is not completed on an earlier
# one's root (B5; the zoo's cold review, run 2, R-11 and R-15).
# --------------------------------------------------------------------------


def test_pin_the_refed_captures_are_z3_and_z1_whose_root_arrives_last():
    """A pin: the two captures named here are two of the four §5.3 runs."""
    assert L3_CAPTURES[:2] == REFED
    assert [c.split("/")[0] for c in REFED] == ["z3", "z1"]


def second_generation(capture: str, out: Path) -> tuple[Run, float, bytes]:
    """`RootEnded(1.0)` completes the trace once; then body 0 is fed again.

    The re-feed is a second after that completion, through a fresh `Framer`,
    and opens generation 2 as `late_arrival` (`SPEC.md` §5.5). Body 0 holds no
    root -- the root arrives in the last body -- so generation 2 has none.
    Returns the run, the re-feed's instant and body 0.
    """
    end = last(capture) + GRACE
    run = drive(capture, (RootEnded(GRACE),), out, then=(end,))
    tick, _ = only_completion(run)
    assert tick.now == end
    body = json_bodies(capture)[0]
    assert not root_ended(spanweave.build(body)), "the premise: body 0 has no root"
    at = end + 1.0
    run.clock[0] = at
    late = [
        event
        for record in Framer().document(body).records
        for event in run.router.route(record).events
        if event.code == LATE_ARRIVAL
    ]
    assert [event.seconds for event in late] == [1.0]
    return run, at, body


def ticked(run: Run, *instants: float) -> list[Completed]:
    done: list[Completed] = []
    for now in instants:
        run.clock[0] = now
        done.extend(run.router.tick())
    return done


@pytest.mark.parametrize("capture", REFED)
def test_pin_a_second_generation_does_not_complete_on_the_first_s_root(
    capture, tmp_path
):
    """A pin, green on the parent: `root_ended_at` is reset per generation.

    Generation 1 saw its root end at `now = last`. Were that reading kept, the
    first tick of generation 2 would already be a grace past it and complete
    the trace on a root generation 2 does not hold. It is not kept (`SPEC.md`
    §5.5, "this generation's records, this generation's silence"; §5.3).
    """
    run, at, _ = second_generation(capture, tmp_path)
    assert ticked(run, at, at + HALF, at + GRACE, at + HALF + GRACE) == []
    assert run.router.trace_ids == (run.trace_id,)


@pytest.mark.parametrize("capture", REFED)
def test_pin_root_ended_alone_never_completes_a_later_generation_and_end_does(
    capture, tmp_path
):
    """A pin, green on the parent: `RootEnded` acts per generation (§5.3).

    A later generation of a trace whose root arrived in an earlier one has no
    root of its own here, so `RootEnded` alone never completes it, up to
    `now = 10^6`; end of input (`Cap(0)`, `SPEC.md` §8.5) does, and writes it
    beside generation 1 as the batch graph of its own records.
    """
    run, at, body = second_generation(capture, tmp_path)
    assert (
        ticked(run, at, at + GRACE, *(at + s for s in ROOTLESS_SECONDS), HORIZON) == []
    )
    run.router.completion = Completion(
        policies=(Cap(0),), now=lambda: HORIZON, out_dir=tmp_path
    )
    (done,) = run.router.tick()
    assert (done.policy, done.version) == (Cap(0), len(Framer().document(body).records))
    second = tmp_path / generation_name(run.trace_id, 2)
    assert done.path == second
    assert second.read_bytes() == batch_of(body)
    assert (tmp_path / generation_name(run.trace_id, 1)).read_bytes() == batch_of(
        *json_bodies(capture)
    )


@pytest.mark.parametrize("capture", L3_CAPTURES)
def test_cap_at_the_record_count_completes_at_the_last_record(capture, tmp_path):
    count = sum(zoo_records()[capture])
    run = drive(capture, (Cap(count),), tmp_path, per_record=True)
    tick, done = only_completion(run)
    assert (tick.now, tick.routed) == (last(capture), count)
    (decision,) = [e for e in done.events if e.code == COMPLETED]
    assert decision.index == count
    assert run.written == {f"{run.trace_id}.json": batch_of(*json_bodies(capture))}


# --------------------------------------------------------------------------
# Z5: no root, so RootEnded alone never completes it (L4).
# --------------------------------------------------------------------------


def rootless_grid() -> tuple[float, ...]:
    """Ticks past the body's own two: either side of each S, then the horizon."""
    instants = {s - HALF for s in ROOTLESS_SECONDS} | set(ROOTLESS_SECONDS)
    return (*sorted(t for t in instants if t > HALF), HORIZON)


def test_pin_rootless_is_the_zoo_s_two_z5_captures():
    """A pin: `ROOTLESS` drives a third of this file, so it is not left empty.

    It is every capture the zoo files under Z5, and there are two of them, the
    real and the recorded run (B5; the zoo's cold review, run 2, R-14).
    """
    z5 = tuple(c for c in captures() if c.split("/")[0] == "z5")
    assert len(z5) == 2
    assert z5 == ROOTLESS


@pytest.mark.parametrize("capture", ROOTLESS)
def test_z5_s_graph_has_no_root(capture):
    """§5.6's root: no `parent` edge and no `orphan_parent`. Z5 has none."""
    (body,) = json_bodies(capture)
    graph = spanweave.build(body)
    named = {d.node_id for d in graph.diagnostics if d.code == "orphan_parent"}
    parentless = [
        n.id for n in graph.nodes() if not graph.parents(n.id, EdgeKind.PARENT)
    ]
    assert parentless, "the premise: there are nodes with no parent edge"
    assert set(parentless) <= named
    assert not root_ended(graph)


@pytest.mark.parametrize("capture", ROOTLESS)
@pytest.mark.parametrize("grace", ROOTLESS_SECONDS)
def test_root_ended_alone_never_completes_a_trace_whose_root_never_ends(
    capture, grace, tmp_path
):
    run = drive(
        capture, (RootEnded(grace),), tmp_path, per_record=True, then=rootless_grid()
    )
    assert run.ticks[-1].now == HORIZON
    assert run.completions == []
    assert run.written == {}
    # It is still held, and end of input completes it with the batch graph.
    (done,) = end_of_input(run, tmp_path)
    assert done.policy == Cap(0)
    assert (tmp_path / f"{run.trace_id}.json").read_bytes() == batch_of(
        *json_bodies(capture)
    )


@pytest.mark.parametrize("capture", ROOTLESS)
@pytest.mark.parametrize("seconds", ROOTLESS_SECONDS)
def test_quiet_completes_the_rootless_trace_once_at_last_plus_s(
    capture, seconds, tmp_path
):
    run = drive(capture, (Quiet(seconds),), tmp_path, then=rootless_grid())
    tick, done = only_completion(run)
    assert tick.now == last(capture) + seconds
    assert done.version == sum(zoo_records()[capture])
    assert run.written == {f"{run.trace_id}.json": batch_of(*json_bodies(capture))}


@pytest.mark.parametrize("capture", ROOTLESS)
def test_cap_four_completes_the_rootless_trace_at_the_fourth_record(capture, tmp_path):
    assert sum(zoo_records()[capture]) == 4
    run = drive(capture, (Cap(4),), tmp_path, per_record=True, then=rootless_grid())
    tick, done = only_completion(run)
    assert (tick.routed, done.version) == (4, 4)
    assert [t.routed for t in run.ticks if t.completed == ()][:3] == [1, 2, 3]
    assert run.written == {f"{run.trace_id}.json": batch_of(*json_bodies(capture))}


@pytest.mark.parametrize("capture", ROOTLESS)
def test_cap_five_never_completes_it_and_end_of_input_does(capture, tmp_path):
    run = drive(capture, (Cap(5),), tmp_path, per_record=True, then=rootless_grid())
    assert run.completions == []
    (done,) = end_of_input(run, tmp_path)
    assert done.version == 4
    assert (tmp_path / f"{run.trace_id}.json").read_bytes() == batch_of(
        *json_bodies(capture)
    )


# --------------------------------------------------------------------------
# The documents cite this file's numbers; these re-derive them.
# --------------------------------------------------------------------------


def number(text: str) -> float:
    return float(text.replace("10^6", str(10**6)))


def test_section_5_3_states_the_values_this_file_runs():
    text = " ".join(section("5.3").split())
    assert "`now = k + 0.5`" in text and HALF == 0.5
    assert number(re.findall(r"`Quiet\(([\d.]+)\)` completes the trace", text)[0]) == (
        PER_BODY
    )
    assert (
        number(re.findall(r"`Quiet\(([\d.]+)\)` completes nothing", text)[0]) == WHOLE
    )
    assert f"`now = last + {WHOLE}`" in text
    assert number(re.findall(r"`RootEnded\(([\d.]+)\)` completes", text)[0]) == GRACE
    assert f"`now = last + {GRACE}`" in text
    assert f"`now = last + {HALF + GRACE}`" in text
    (graces,) = re.findall(r"`RootEnded\(S\)` for S in \{([\d, ]+)\}", text)
    assert tuple(number(s) for s in graces.split(",")) == ROOTLESS_SECONDS
    (horizon,) = re.findall(r"up to `now = (10\^6)`", text)
    assert number(horizon) == HORIZON
    assert "`Cap(4)` at the fourth record" in text
    assert "`Cap(5)` never" in text
    # Where `RootEnded`'s grace runs from, at the instants
    # `test_root_ended_s_grace_runs_from_the_tick_that_first_saw_the_root` runs.
    assert f"the first to see it is `last + {HALF}`" in text
    assert f"the tick at `last + {GRACE}` completes nothing" in text
    # The record `test_cap_at_the_record_count_completes_at_the_last_record`
    # completes at, with `count` as its *N*.
    assert (
        "`Cap(N)`, with *N* the capture's record count and a tick after every "
        "record, completes at the *N*-th record"
    ) in text


def offset(text: str | None) -> float:
    """`None` for `now = k` itself, else the `+ x` after it."""
    return 0.0 if text is None else float(text.removeprefix(" + "))


def test_section_5_3_s_schedule_is_the_one_this_file_drives(tmp_path):
    """A pin, green on the parent: §5.3's `now = k` and its two ticks, measured.

    The tick instants are read off the run, and the instant each body was fed
    at off its generation's `completed` event, whose `seconds` runs from the
    generation's first record (§5.4), so neither is this file's constant
    compared with itself.
    """
    text = " ".join(section("5.3").split())
    (schedule,) = re.findall(
        r"is fed at `now = k( \+ [\d.]+)?`, and after it the router is ticked "
        r"twice, at `now = k( \+ [\d.]+)?` and at `now = k( \+ [\d.]+)?`",
        text,
    )
    fed, *ticks = (offset(group or None) for group in schedule)
    capture = L3_CAPTURES[0]
    bodies = len(json_bodies(capture))
    run = drive(capture, (Quiet(PER_BODY),), tmp_path)
    assert [tick.now for tick in run.ticks] == [
        k + after for k in range(bodies) for after in ticks
    ]
    assert len(run.completions) == bodies
    for k, (tick, done) in enumerate(run.completions):
        (decision,) = [e for e in done.events if e.code == COMPLETED]
        assert decision.seconds is not None
        assert tick.now - decision.seconds == k + fed, k


def test_the_readme_s_traps_are_the_number_it_says_and_the_third_is_this_one():
    words = {"two": 2, "three": 3, "four": 4}
    readme = README.read_text(encoding="utf-8")
    stated = re.search(r"the first two of the (\w+) traps worth knowing", readme)
    assert stated is not None
    start = readme.index(stated.group(0))
    end = readme.index("\n\nExit codes", start)
    bullets = re.split(r"^- ", readme[start:end], flags=re.M)[1:]
    assert len(bullets) == words[stated.group(1)]
    third = " ".join(bullets[2].split())
    for cited in ("orphan_parent", "late_arrival", "never merged", "--root-grace"):
        assert cited in third
    assert "§5.3, §5.5" in third
