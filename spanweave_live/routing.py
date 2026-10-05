"""Routing: one `spanweave.Builder` per trace (`SPEC.md` §4).

The second piece of the receiver, and the one with the sharpest invariant. It
answers "which builder does this record belong to?" and holds a `Builder` per
trace id, created the first time that trace is seen. It does not evaluate a
record, score it, hold it, or read what the graph came to say: it partitions,
and the graphs are the caller's (`SPEC.md` §1.2, §1.3).

**It never reads a dialect.** A record's trace id comes from
`spanweave.adapters.classify` and the claiming adapter's `parse`, and from
nowhere else -- no key table, no `record["trace_id"]`, no container walk
(`SPEC.md` §1.1, §4.2). The cheap-looking alternative works on every fixture
anyone would write and is a second dialect reader that can disagree with the
library about the same bytes, for reasons no fixture of the receiver's own can
pin. The cost of doing it properly is a second parse per record, measured at
15.5-17.1% of per-record routing: it is paid deliberately and registered as a
thread in `SPEC.md` §4.2 -- which is where the number is, and which outlives
the plan -- not worked around.

Nothing here reads the clock, sleeps, opens a socket or shuffles anything. The
clock `tick` evaluates completion against is the caller's `now`, handed to the
`Completion` it was given (`SPEC.md` §5.2); a router without a completion policy
never reads one at all.
"""

from __future__ import annotations

import pathlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from spanweave import Builder, Graph, SpanweaveError
from spanweave.adapters import classify, get

from spanweave_live.completion import (
    COMPLETED,
    LATE_ARRIVAL,
    NOT_WRITTEN,
    RELEASED,
    WRITTEN,
    Completion,
    Policy,
    TraceState,
    root_ended,
    write,
)

#: One record, as `spanweave.read_records` yielded it.
#:
#: `Any` on purpose, and deliberately not a JSON type of the receiver's own:
#: `spanweave`'s `JsonValue` *is* `Any` and is not exported, so a narrower
#: alias here would be a shape the library never promised and that the next
#: adapter could falsify.
Record = Any

#: A `spanweave.Builder` refused the record -- most often a span re-sent under
#: at-least-once export, which is a node-id collision and costs nothing else
#: (`SPEC.md` §2.2). Routine, and loud: counted, and routing continues.
REFUSED: Final = "refused"

#: A record named a trace the router has no room for (`SPEC.md` §4.5). Refused
#: in the open rather than dropped: silence was the alternative.
REFUSED_AT_CAP: Final = "refused_at_cap"


@dataclass(frozen=True, slots=True)
class Event:
    """One decision the router made that a caller is entitled to know about.

    Every refusal, cap hit and anything else the receiver did not handle is one
    of these, with a code (`SPEC.md` §1.5). `spanweave_code` is the library's
    own code where the library is what refused, kept as a field rather than
    folded into `detail` so a caller can match on it instead of on a sentence.
    """

    code: str
    #: The record's 1-based arrival index in this router. Arrival order, not a
    #: line number: the router never saw the bytes. On an event a **tick**
    #: emitted (`SPEC.md` §5.4) there is no record to index, so it is the
    #: router's arrival count when the tick ran -- the honest nearest thing, and
    #: what places the tick in the stream.
    index: int
    trace_id: str | None
    spanweave_code: str | None
    detail: str
    #: The duration this event is about, where it is about one: the gap for a
    #: `late_arrival`, the trace's open lifetime for a `completed`. `None` for
    #: `refused` and `refused_at_cap`, which are about no duration. A field
    #: rather than a sentence because `SPEC.md` §1.5 is only true if a caller
    #: can match on the number (`SPEC.md` §4.1, §5.1).
    seconds: float | None = None


@dataclass(frozen=True, slots=True)
class Routed:
    """Where one record went, and what that cost.

    `builder` is `None` only when nothing absorbed the record, which today is
    the cap and nothing else. `version` is the builder's version **after** the
    attempt: a refused record is not absorbed and the builder is left exactly
    as it was (`spanweave` `SPEC.md` §10.5), so this is the unchanged version
    rather than the one the record would have produced.
    """

    index: int
    trace_id: str | None
    builder: Builder | None
    version: int | None
    events: tuple[Event, ...] = ()


@dataclass(frozen=True, slots=True)
class Completed:
    """One trace a `tick` completed, and what completing it did (`§5.4`).

    Here beside `Routed` rather than in `completion.py` for one reason, and it
    is layering rather than taste: this carries routing `Event`s, so declaring
    it over there would make completion import routing while routing imports
    completion. `completion.py` is the lower layer and holds values and pure
    functions only (`SPEC.md` §5.1).

    `graph` is `None` only where the library refused to materialize it, and
    `path` is `None` wherever nothing was written -- including the ordinary case
    of a caller that named no directory. `events` says which of those it was.
    """

    trace_id: str
    #: The value that fired. A caller tells `Quiet` from `Cap` by this, not by
    #: parsing a sentence.
    policy: Policy
    #: The builder's version at the instant it was released.
    version: int
    graph: Graph | None
    path: pathlib.Path | None
    events: tuple[Event, ...] = ()


@dataclass(slots=True)
class _Book:
    """What the router remembers about one trace for completion's sake.

    Not a public type and not a graph: four numbers, which is what `TraceState`
    (`SPEC.md` §5.6) and a generation's file name need. A book **outlives** the
    builder it was opened for, because the gap on a `late_arrival` and the file
    name of a second generation are both facts about a trace already completed
    (`SPEC.md` §5.5), and that cost is stated there rather than hidden here.
    """

    first_record_at: float
    last_record_at: float
    #: When an ended root was first *seen*, never the span's own `ended_at`.
    root_ended_at: float | None = None
    #: 1 for the first builder of this trace, 2 for the one a late arrival
    #: opened, and so on. It is in the file name from 2 onward (`§5.5`).
    generation: int = 1
    #: When this trace was completed, while no builder is held for it.
    completed_at: float | None = None


def trace_id_of(record: Record) -> str | None:
    """The trace a record belongs to, through the adapter surface alone.

    `classify` says which adapters claim this one record; the single claimant's
    `parse` translates it; the trace id is what the resulting spans report.
    That is the whole mechanism, and there is no other branch in it
    (`SPEC.md` §4.2).

    `None` -- "no trace id" -- for each of the four ways the library declines
    to say: nobody claimed the record, more than one adapter claimed it, the
    claimant reported no trace id, or it reported more than one distinct id
    across the spans of one record. §1.1 fixes that answer: an id that cannot
    be had through the adapter surface is absent, not looked up.

    A `SpanweaveError` is also `None`, and is not swallowed by it: the record
    goes to the no-trace builder, whose `feed` reaches the same code and raises
    the same refusal, and `Router.route` reports it with the library's own code.
    """
    try:
        claimants = classify(record)
        if len(claimants) != 1:
            return None
        reported = {
            span.trace_id for span in get(claimants[0]).parse([record]) if span.trace_id
        }
    except SpanweaveError:
        return None
    if len(reported) != 1:
        return None
    return next(iter(reported))


@dataclass(slots=True, kw_only=True)
class Router:
    """One `spanweave.Builder` per trace id (`SPEC.md` §4).

    `adapter` and `temporal` are handed to every `Builder` it makes, so a
    caller that names a dialect or turns temporal edges off gets live what
    `spanweave.build` gives it in batch. The router reads neither.

    `completion` is the caller's policy and the caller's clock (`SPEC.md` §5).
    `tick` evaluates it; `route` keeps the two numbers it needs. A router
    without one holds every builder it ever made and reads no clock, which is
    what R2 was and what gate A still exercises.

    All four settings are **keyword-only**, as `SPEC.md` §4.1 declares them:
    they are independent knobs with no reading order, and a positional order
    here would be a contract the spec never offered.

    It keeps a **count** per event code and no event log: the events of one
    record ride on that record's `Routed`, and an accumulated list grows with
    the stream, which is the cost `SPEC.md` §2.3 is about.
    """

    #: How many identified traces this router will hold builders for, or `None`
    #: for no cap (`SPEC.md` §4.5).
    max_traces: int | None = None
    adapter: str | None = None
    temporal: bool = True
    #: The caller's completion policy, with the caller's clock in it, or `None`
    #: for a router that completes nothing and reads no clock (`SPEC.md` §5).
    completion: Completion | None = None

    _builders: dict[str, Builder] = field(default_factory=dict, init=False)
    _no_trace: Builder | None = field(default=None, init=False)
    _counts: dict[str, int] = field(default_factory=dict, init=False)
    _index: int = field(default=0, init=False)
    _books: dict[str, _Book] = field(default_factory=dict, init=False)

    @property
    def trace_ids(self) -> tuple[str, ...]:
        """The identified traces, in **first arrival order**.

        The order traces were first seen is a fact about the stream; sorting it
        would throw that away. Nothing in any graph depends on it.
        """
        return tuple(self._builders)

    @property
    def no_trace(self) -> Builder:
        """The builder for records that identify no trace (`SPEC.md` §4.3).

        A `Builder` like any other, which is the point: it carries the library's
        own `missing_trace_id` and `unclaimed_record`, so the receiver invents
        no code for either. Made on first use rather than in `__init__` so a
        router that never needed one never built one.
        """
        if self._no_trace is None:
            self._no_trace = Builder(adapter=self.adapter, temporal=self.temporal)
        return self._no_trace

    @property
    def counts(self) -> Mapping[str, int]:
        """How many of each event code, bounded by the number of codes."""
        return dict(self._counts)

    @property
    def routed(self) -> int:
        """How many records have been handed to `route`."""
        return self._index

    def builder(self, trace_id: str | None) -> Builder | None:
        """The builder for `trace_id`, or `None` if this router has none.

        `trace_id=None` is the no-trace builder, which always exists.
        """
        if trace_id is None:
            return self.no_trace
        return self._builders.get(trace_id)

    def route(self, record: Record) -> Routed:
        """Hand one record to its trace's builder; say what happened.

        Never raises for anything the record can cause. A `Builder` refusal --
        the ordinary outcome of a span re-sent under at-least-once export
        (`SPEC.md` §2.2) -- is an `Event` with code `refused` carrying the
        arrival index and the library's `code`, counted, and routing continues
        with the next record.
        """
        self._index += 1
        index = self._index
        trace_id = trace_id_of(record)
        # One reading, and only where there is a policy to measure against: a
        # router with no completion reads no clock at all, which is why R2's
        # behaviour -- gate A included -- is untouched by R3 (`SPEC.md` §5.2).
        now = None if self.completion is None else self.completion.now()
        events: tuple[Event, ...] = ()

        if trace_id is None:
            builder = self.no_trace
        else:
            existing = self._builders.get(trace_id)
            if existing is None:
                if (
                    self.max_traces is not None
                    and len(self._builders) >= self.max_traces
                ):
                    return self._at_cap(index, trace_id)
                existing = Builder(adapter=self.adapter, temporal=self.temporal)
                self._builders[trace_id] = existing
                events += self._began(index, trace_id, now)
            builder = existing
            if now is not None:
                self._activity(trace_id, now)

        try:
            version = builder.feed(record)
        except SpanweaveError as refusal:
            events += (
                self._counted(
                    Event(
                        code=REFUSED,
                        index=index,
                        trace_id=trace_id,
                        spanweave_code=refusal.code,
                        detail=str(refusal),
                    )
                ),
            )
            # The builder is left exactly as it was (`spanweave` §10.5), so the
            # version reported is the one it already had.
            return Routed(
                index=index,
                trace_id=trace_id,
                builder=builder,
                version=builder.version,
                events=events,
            )
        return Routed(
            index=index,
            trace_id=trace_id,
            builder=builder,
            version=version,
            events=events,
        )

    def tick(self) -> tuple[Completed, ...]:
        """Evaluate the completion policies against the clock; complete what is
        due, and return the traces this tick completed (`SPEC.md` §5.4).

        One clock reading for the whole tick, and the traces are evaluated in
        `trace_ids` order, so what a tick does is a function of the stream and
        the reading. Two readings inside one tick could complete one trace and
        not the next for a reason no caller could see.

        With no completion policy it returns `()` and reads nothing: a tick is
        not a thing the receiver wanted, it is a thing the caller asked for.

        The **no-trace builder is never completed**, for the cap's reason
        (`SPEC.md` §4.5): it is not a trace, and releasing it would throw away
        the library's own account of the records that identified none on a
        timeout that was about something else.

        It raises nothing a record can cause, as `route` does not: a graph the
        library refuses is reported, not raised (`SPEC.md` §5.4).
        """
        completion = self.completion
        if completion is None:
            return ()
        now = completion.now()
        watching = completion.watches_root
        completed: list[Completed] = []
        # A tuple snapshot, because completing releases builders out of the dict
        # this iterates.
        for trace_id in self.trace_ids:
            builder = self._builders[trace_id]
            book = self._book(trace_id, now)
            if watching and book.root_ended_at is None and self._root_ended(builder):
                # First *seen*, and recorded once: the grace runs from here, not
                # from the span's own `ended_at` (`SPEC.md` §5.2, §5.6).
                book.root_ended_at = now
            state = TraceState(
                trace_id=trace_id,
                now=now,
                records=builder.version,
                first_record_at=book.first_record_at,
                last_record_at=book.last_record_at,
                root_ended_at=book.root_ended_at,
            )
            policy = completion.fired(state)
            if policy is not None:
                completed.append(
                    self._complete(completion, trace_id, builder, book, policy, now)
                )
        return tuple(completed)

    def _complete(
        self,
        completion: Completion,
        trace_id: str,
        builder: Builder,
        book: _Book,
        policy: Policy,
        now: float,
    ) -> Completed:
        """Say so, materialize, write, release -- each of them reported (§5.4)."""
        index = self._index
        events: list[Event] = [
            self._counted(
                Event(
                    code=COMPLETED,
                    index=index,
                    trace_id=trace_id,
                    spanweave_code=None,
                    detail=(
                        f"the {policy.code} policy fired on {policy!r}: this "
                        f"trace had absorbed {builder.version} records and was "
                        f"last fed at {book.last_record_at!r} on the caller's "
                        f"clock, which now reads {now!r}"
                    ),
                    seconds=now - book.first_record_at,
                )
            )
        ]

        graph: Graph | None = None
        refusal: SpanweaveError | None = None
        try:
            graph = builder.graph()
        except SpanweaveError as error:
            refusal = error

        path: pathlib.Path | None = None
        if completion.out_dir is not None:
            path, written = self._write(
                completion, index, trace_id, book.generation, graph, refusal
            )
            events.append(written)

        version = builder.version
        del self._builders[trace_id]
        book.completed_at = now
        events.append(
            self._counted(
                Event(
                    code=RELEASED,
                    index=index,
                    trace_id=trace_id,
                    spanweave_code=None,
                    detail=(
                        f"the builder for {trace_id!r} was released at version "
                        f"{version}; the router holds {len(self._builders)} "
                        f"identified traces"
                    ),
                )
            )
        )
        return Completed(
            trace_id=trace_id,
            policy=policy,
            version=version,
            graph=graph,
            path=path,
            events=tuple(events),
        )

    def _write(
        self,
        completion: Completion,
        index: int,
        trace_id: str,
        generation: int,
        graph: Graph | None,
        refusal: SpanweaveError | None,
    ) -> tuple[pathlib.Path | None, Event]:
        """Write the final graph, or say why there is no file (`SPEC.md` §5.4).

        Three things stop a write and each is one `not_written`: the library
        refused the graph, the trace id is not usable as one path component, or
        the filesystem refused. None of them raises -- a receiver that died on
        one unwritable file would lose every other trace it was holding.

        The first of the three is **unreachable** through the public surface
        today and kept deliberately (`SPEC.md` §5.4): a builder refuses a graph
        only when nothing in it was claimed, and an identified trace has a
        claimed record by construction. `graph()`'s refusals are the library's to
        define and a pin move can add one.
        """
        if graph is None:
            return None, self._counted(
                Event(
                    code=NOT_WRITTEN,
                    index=index,
                    trace_id=trace_id,
                    spanweave_code=None if refusal is None else refusal.code,
                    detail=(
                        f"the library refused to materialize the graph of "
                        f"{trace_id!r}, so there is nothing to write: {refusal}"
                    ),
                )
            )
        path = completion.path_for(trace_id, generation)
        if path is None:
            return None, self._counted(
                Event(
                    code=NOT_WRITTEN,
                    index=index,
                    trace_id=trace_id,
                    spanweave_code=None,
                    detail=(
                        f"{trace_id!r} is not usable as one path component, so "
                        f"no file was named from it; a trace id is untrusted "
                        f"input and a file named from it must not be able to "
                        f"leave the directory the caller named"
                    ),
                )
            )
        try:
            write(graph, path)
        except OSError as error:
            return None, self._counted(
                Event(
                    code=NOT_WRITTEN,
                    index=index,
                    trace_id=trace_id,
                    spanweave_code=None,
                    detail=f"writing {str(path)!r} failed: {error}",
                )
            )
        return path, self._counted(
            Event(
                code=WRITTEN,
                index=index,
                trace_id=trace_id,
                spanweave_code=None,
                detail=str(path),
            )
        )

    def _root_ended(self, builder: Builder) -> bool:
        """Has this trace's root ended, as far as the graph says (`§5.6`)?

        A graph the library **refuses** is "no root seen yet" and no event: the
        alternative is one event per tick for the life of the stream, which is
        the unbounded accumulation §4.6 exists to avoid, and the condition is
        permanent and reaches the caller the moment it asks for the graph
        (`SPEC.md` §5.7). Nothing was dropped -- a decision was not made.

        Unreachable today for `_write`'s reason, and kept for the same one.
        """
        try:
            graph = builder.graph()
        except SpanweaveError:
            return False
        return root_ended(graph)

    def _book(self, trace_id: str, now: float) -> _Book:
        book = self._books.get(trace_id)
        if book is None:
            book = _Book(first_record_at=now, last_record_at=now)
            self._books[trace_id] = book
        return book

    def _began(self, index: int, trace_id: str, now: float | None) -> tuple[Event, ...]:
        """A builder was just made for this trace; is it a **second** one?

        A book that outlived its builder is a trace the caller's policy
        completed, so this record is late: a new builder is opened, the record
        is absorbed into it, and the gap is reported (`SPEC.md` §5.5). The
        record is not refused, not dropped and not held -- the policy said stop
        holding a builder, not stop receiving telemetry (`SPEC.md` §1.3).
        """
        if now is None:
            return ()
        book = self._books.get(trace_id)
        if book is None:
            self._books[trace_id] = _Book(first_record_at=now, last_record_at=now)
            return ()
        completed_at = book.completed_at
        # This generation's records and this generation's silence.
        book.first_record_at = now
        book.last_record_at = now
        book.root_ended_at = None
        if completed_at is None:
            return ()
        book.completed_at = None
        book.generation += 1
        return (
            self._counted(
                Event(
                    code=LATE_ARRIVAL,
                    index=index,
                    trace_id=trace_id,
                    spanweave_code=None,
                    detail=(
                        f"{trace_id!r} was completed at {completed_at!r} on the "
                        f"caller's clock and a record for it arrived at {now!r}; "
                        f"generation {book.generation} of its builder is open "
                        f"and the record is absorbed into it"
                    ),
                    seconds=now - completed_at,
                )
            ),
        )

    def _activity(self, trace_id: str, now: float) -> None:
        """A record reached this trace's builder, absorbed or refused (`§5.3`).

        Either way it is activity: a re-sent span is the exporter still talking
        about this trace, and counting a refusal as silence would complete a
        trace that is plainly still arriving.
        """
        self._book(trace_id, now).last_record_at = now

    def _at_cap(self, index: int, trace_id: str) -> Routed:
        """A new trace the router has no room for. Refused, in the open."""
        event = self._counted(
            Event(
                code=REFUSED_AT_CAP,
                index=index,
                trace_id=trace_id,
                spanweave_code=None,
                detail=(
                    f"this router already holds {len(self._builders)} traces, "
                    f"which is max_traces, so no builder was made for "
                    f"{trace_id!r} and the record was not absorbed"
                ),
            )
        )
        return Routed(
            index=index,
            trace_id=trace_id,
            builder=None,
            version=None,
            events=(event,),
        )

    def _counted(self, event: Event) -> Event:
        self._counts[event.code] = self._counts.get(event.code, 0) + 1
        return event
