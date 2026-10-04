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
pin. The cost of doing it properly is a second parse per record; it is paid
deliberately and registered as a thread (`WORKPLAN.md` §3), not worked around.

Nothing here reads the clock, sleeps, opens a socket or shuffles anything.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from spanweave import Builder, SpanweaveError
from spanweave.adapters import classify, get

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
    #: line number: the router never saw the bytes.
    index: int
    trace_id: str | None
    spanweave_code: str | None
    detail: str


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


@dataclass(slots=True)
class Router:
    """One `spanweave.Builder` per trace id (`SPEC.md` §4).

    `adapter` and `temporal` are handed to every `Builder` it makes, so a
    caller that names a dialect or turns temporal edges off gets live what
    `spanweave.build` gives it in batch. The router reads neither.

    It keeps a **count** per event code and no event log: the events of one
    record ride on that record's `Routed`, and an accumulated list grows with
    the stream, which is the cost `SPEC.md` §2.3 is about.
    """

    #: How many identified traces this router will hold builders for, or `None`
    #: for no cap (`SPEC.md` §4.5).
    max_traces: int | None = None
    adapter: str | None = None
    temporal: bool = True

    _builders: dict[str, Builder] = field(default_factory=dict, init=False)
    _no_trace: Builder | None = field(default=None, init=False)
    _counts: dict[str, int] = field(default_factory=dict, init=False)
    _index: int = field(default=0, init=False)

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
            builder = existing

        try:
            version = builder.feed(record)
        except SpanweaveError as refusal:
            event = self._counted(
                Event(
                    code=REFUSED,
                    index=index,
                    trace_id=trace_id,
                    spanweave_code=refusal.code,
                    detail=str(refusal),
                )
            )
            # The builder is left exactly as it was (`spanweave` §10.5), so the
            # version reported is the one it already had.
            return Routed(
                index=index,
                trace_id=trace_id,
                builder=builder,
                version=builder.version,
                events=(event,),
            )
        return Routed(index=index, trace_id=trace_id, builder=builder, version=version)

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
