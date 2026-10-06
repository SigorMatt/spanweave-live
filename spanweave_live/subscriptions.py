"""Subscriptions: the deltas go out, and nothing is concluded about them
(`SPEC.md` §6).

The fourth piece. A consumer registers a callback; after every **absorbed**
record the router hands it what changed, as a `spanweave.Delta` and the builder
it came from. That is the whole of it, and the three things it is careful not to
be are `SPEC.md` §1 read in this direction:

- It is a **fan-out, not an evaluation** (`SPEC.md` §1.2). Nothing here looks at
  what a delta contains. A subscriber narrows by **trace id** and by **how
  often** -- facts about the stream -- and by nothing else; what it concludes is
  its own business, and a filter by meaning would be a rule the receiver holds.
- It **enforces nothing** (`SPEC.md` §1.3). A consumer that raises does not stop
  the record, the other consumers or the stream.
- It is **not silent** (`SPEC.md` §1.5). A callback that raised, a delta the
  journal could no longer produce, and a window a released builder took with it
  are each an `Event` with a code, counted.

This module is the **lower** of the two layers, as `completion.py` is
(`SPEC.md` §5.1, §6.1): values, the registry, the cursors, and the three pure
questions "who is due?", "who is behind?" and "how much journal does this trace
need?". It emits no events and imports nothing from `routing.py` -- calling a
consumer, catching what it raises and keeping the books are the router's,
because events are a router's to make.

No clock, no randomness, no socket: a fan-out is a function of the records
absorbed and the order consumers registered in (`SPEC.md` §6.2).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final

from spanweave import Builder, Delta

#: A consumer's callback raised. Caught, recorded with the trace id and the
#: version, counted -- and the remaining subscribers are still called, and the
#: record stays absorbed. Isolation is not suppression (`SPEC.md` §6.5).
CONSUMER_ERROR: Final = "consumer_error"

#: `builder.delta(since=...)` was refused because retention no longer holds that
#: version. Unreachable for a builder whose retention the router sets
#: (`SPEC.md` §6.4); reachable by a caller narrowing a `Routed.builder`'s own,
#: which is legal, and this event is the honest answer to it (`SPEC.md` §6.5).
DELTA_UNAVAILABLE: Final = "delta_unavailable"

#: A trailing window could not be handed over. A subscriber behind its trace's
#: final version is **flushed** at completion and at an explicit
#: `Router.flush` -- the tail of a trace is a delta, not a statistic -- so this
#: is what is left when that delivery is impossible: `delta(since=...)` refused
#: by a journal the caller narrowed itself (`SPEC.md` §6.4). The window is then
#: gone with the builder, and saying so is all that is left (`SPEC.md` §6.5).
DELTA_UNSENT: Final = "delta_unsent"


@dataclass(frozen=True, slots=True)
class Update:
    """What changed, handed to one consumer (`SPEC.md` §6.1).

    There is deliberately **no graph** on it and no field that says anything
    about what the change *means*. The graph is `builder.graph()`, which is the
    consumer's to ask for when it wants one: materializing a graph per record
    for every subscriber is the cost `SPEC.md` §2.3 is about, and a consumer
    that only folds deltas should not pay it.

    `since` is the window's lower end, so a consumer can fold onto the version
    it last held without keeping a counter of its own.
    """

    #: The trace this update is about, or `None` for the no-trace builder --
    #: which a `trace_id=None` subscription does receive (`SPEC.md` §6.3).
    trace_id: str | None
    #: The version the absorbed record produced: the builder's own count.
    version: int
    #: `delta(since=...)`: the version this difference is measured from.
    since: int
    delta: Delta
    builder: Builder


#: One consumer. It is handed an `Update` and its return value is ignored: the
#: receiver has nothing to do with what a consumer concluded (`SPEC.md` §1.2).
Consumer = Callable[[Update], None]


@dataclass(frozen=True, slots=True)
class Subscription:
    """One registration: who, which trace, how often, and in what order.

    `every` is versions, not seconds -- there is no clock here (`SPEC.md` §1.4)
    and "every N records of this trace" is a fact about the stream rather than
    about the wall. `every=1` is per-record mode (`SPEC.md` §6.2).
    """

    consumer: Consumer
    #: One trace id, or `None` for every builder the router feeds, the no-trace
    #: builder included (`SPEC.md` §6.3).
    trace_id: str | None
    every: int
    #: Registration order, 0-based. **This is the fan-out order** -- a fact the
    #: caller controls and can predict, where `id()`, a `hash()` and a callback's
    #: name are each either unstable across processes or a ranking nobody chose
    #: (`SPEC.md` §6.2).
    order: int


@dataclass(frozen=True, slots=True)
class Delivery:
    """One subscriber that is due, and the window it is due for."""

    subscription: Subscription
    since: int


@dataclass(slots=True)
class Subscriptions:
    """Who is subscribed, how far behind each is, and what that costs to keep.

    Mutable, unlike a completion policy, and that is the difference between the
    two (`SPEC.md` §6.1): a policy is a value the caller constructed, while a
    subscription list is something consumers join. The router is handed this and
    the caller keeps its reference.

    The cursors are bounded: one `int` per subscription per trace the router
    **currently holds a builder for**, forgotten when the builder is released
    (`SPEC.md` §6.4, §6.5), so `max_traces` bounds them.
    """

    _registered: list[Subscription] = field(default_factory=list, init=False)
    #: `(trace_id, subscription.order) -> the version last handed over`. Keyed
    #: rather than iterated, so no dict order is ever read (`CLAUDE.md` 8).
    _cursors: dict[tuple[str | None, int], int] = field(
        default_factory=dict, init=False
    )

    def subscribe(
        self,
        consumer: Consumer,
        *,
        trace_id: str | None = None,
        every: int = 1,
    ) -> Subscription:
        """Register `consumer`; return the `Subscription` that was made.

        `trace_id=None` is every builder this router feeds (`SPEC.md` §6.3).
        `every` is a count of versions and must be at least 1: `every=0` is not
        a frequency, and it is a `ValueError` at registration rather than an
        event, because nothing about the stream caused it -- it is the same kind
        of mistake as `spanweave`'s own `retain(-1)`.
        """
        if not isinstance(every, int) or isinstance(every, bool) or every < 1:
            raise ValueError(
                f"every is a count of versions and is at least 1 (1 is "
                f"per-record mode, `SPEC.md` §6.2); {every!r} is not"
            )
        subscription = Subscription(
            consumer=consumer,
            trace_id=trace_id,
            every=every,
            order=len(self._registered),
        )
        self._registered.append(subscription)
        return subscription

    @property
    def registered(self) -> tuple[Subscription, ...]:
        """Every subscription, in registration order -- the fan-out order."""
        return tuple(self._registered)

    def covering(self, trace_id: str | None) -> tuple[Subscription, ...]:
        """The subscriptions that receive this trace, in registration order."""
        return tuple(
            subscription
            for subscription in self._registered
            if subscription.trace_id is None or subscription.trace_id == trace_id
        )

    def window(self, trace_id: str | None) -> int | None:
        """How much journal this trace needs, or `None` if nobody is watching.

        The **longest window any covering subscriber asked for**, which is the
        oldest `since` that is still going to be asked about and not one version
        more (`SPEC.md` §6.4). `None` -- nobody covers this trace -- is not `0`:
        a builder nobody subscribed to keeps the library's own default, because
        `Routed.builder` is public and narrowing a journal this section never
        promised to narrow would break a caller that folds its own deltas.
        """
        covering = self.covering(trace_id)
        if not covering:
            return None
        return max(subscription.every for subscription in covering)

    def seen(self, subscription: Subscription, trace_id: str | None) -> int:
        """The version this subscription was last handed for this trace."""
        return self._cursors.get((trace_id, subscription.order), 0)

    def due(self, trace_id: str | None, version: int) -> tuple[Delivery, ...]:
        """Who is due at this version, and from where -- and advance them.

        Due is `version - cursor >= every`, and the window is `since=cursor`, so
        per-record mode is not a second code path: at `every=1` the cursor is
        always `version - 1` (`SPEC.md` §6.2).

        The cursors advance **here**, before the consumers are called, which is
        the decision that makes isolation not a retry queue: a subscriber that
        raises is not re-sent to on the next record, because re-sending would let
        one consumer's failure change what another sees and would be a policy
        nobody asked for (`SPEC.md` §6.2).
        """
        due: list[Delivery] = []
        for subscription in self.covering(trace_id):
            key = (trace_id, subscription.order)
            cursor = self._cursors.get(key, 0)
            if version - cursor < subscription.every:
                continue
            self._cursors[key] = version
            due.append(Delivery(subscription=subscription, since=cursor))
        return tuple(due)

    def flush(self, trace_id: str | None, version: int) -> tuple[Delivery, ...]:
        """Who is **behind** this version, and from where -- and advance them.

        `due`'s question asked at the caller's moment instead of the record's:
        the condition is `version > cursor` rather than `version - cursor >=
        every`, because the point of a flush is the residue a window never
        covered. A subscriber already at `version` is not behind and gets
        nothing, so a flush with nothing to hand over hands nothing over.

        The cursors advance here, before the consumers are called, for `due`'s
        reason, and that is also what makes a second flush with no record in
        between a no-op.

        It is the lower half of the trailing delta: an `every=N` subscriber
        whose trace ends between multiples of `N` would otherwise never see the
        tail of it, which is a dropped delta rather than a window nobody asked
        for (`SPEC.md` §6.6, `WORKPLAN.md` §3, 2026-10-06). What to do with
        these deliveries is the router's, because events are.
        """
        behind: list[Delivery] = []
        for subscription in self.covering(trace_id):
            key = (trace_id, subscription.order)
            cursor = self._cursors.get(key, 0)
            if cursor >= version:
                continue
            self._cursors[key] = version
            behind.append(Delivery(subscription=subscription, since=cursor))
        return tuple(behind)

    def forget(self, trace_id: str | None) -> None:
        """Drop this trace's cursors: its builder has been released.

        Forgetting is what keeps the cursors bounded (`SPEC.md` §6.4), and it is
        *correct* rather than merely cheap: a late arrival opens a new builder
        whose versions start at 0 (`SPEC.md` §5.5), so a cursor for the next
        generation of this trace is 0 whether it was forgotten or not.

        It is called **after** the trailing delta has gone out (`SPEC.md` §5.4's
        fifth step), so a released trace leaves no cursor behind and no window
        unsent that could have been sent.
        """
        for subscription in self._registered:
            self._cursors.pop((trace_id, subscription.order), None)
