"""Completion: when the caller's policy says to stop holding a builder
(`SPEC.md` §5).

Nothing in a live stream says a trace is over, so **"finished" is not a fact
this receiver can know** (`SPEC.md` §5). What it can do is stop holding a
builder, and that is all completion is: a policy the caller chose, evaluated
against a clock the caller supplied. The policies here are *values* -- a caller
constructs `Quiet(30.0)`, and the receiver evaluates it without believing
anything about it (`SPEC.md` §1.2).

This module is the **lower layer** of the two. It holds values and pure
functions only -- the policies, the state they are allowed to see, the one graph
question `RootEnded` asks, and the event codes -- and it imports nothing from
`routing.py`. The bookkeeping, the events, the writes and the releases are the
router's, because they are what a router has (`SPEC.md` §5.1).

**No clock here.** `now` is the caller's `Callable[[], float]`, with no default,
so no module under `spanweave_live/` imports `time` and the seam allowlist in
`tests/gates.py` stays empty (`SPEC.md` §1.4, §5.2). Every duration is measured
on that clock and never on a span's timestamps: those are the observed system's
clock, and a receiver decision that depended on two clocks agreeing would
complete traces early or never (`SPEC.md` §5.2).
"""

from __future__ import annotations

import pathlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar, Final, Protocol

import spanweave
from spanweave import EdgeKind, Graph

# -- the policy codes (`SPEC.md` §5.3) -------------------------------------

#: No record for this trace for long enough, on the caller's clock.
QUIET: Final = "quiet"
#: An ended root was seen, and the caller's grace has run since.
ROOT_ENDED: Final = "root_ended"
#: This trace has absorbed enough records.
CAP: Final = "cap"

# -- the event codes (`SPEC.md` §5.4, §5.5) --------------------------------

#: A policy fired and the trace was completed. Carries the trace's open
#: lifetime in `seconds`, and the policy that fired in `detail`.
COMPLETED: Final = "completed"
#: The final graph was written. `detail` is the path.
WRITTEN: Final = "written"
#: There is no file for this completed trace, and `detail` says why: the
#: library refused the graph, the trace id is not usable as one path component,
#: or the write failed. Never silence (`SPEC.md` §1.5).
NOT_WRITTEN: Final = "not_written"
#: The builder was dropped. The point of the whole section (`SPEC.md` §2.3).
RELEASED: Final = "released"
#: A record arrived for a trace that was completed. A new builder is opened and
#: the record is absorbed: the caller's policy said stop holding a builder, not
#: stop receiving telemetry (`SPEC.md` §1.3, §5.5). `seconds` is the gap.
LATE_ARRIVAL: Final = "late_arrival"

#: The diagnostic that tells an orphan from a root. `spanweave`'s own code, read
#: rather than redefined (`spanweave` `SPEC.md` §4.0).
_ORPHAN_PARENT: Final = "orphan_parent"


@dataclass(frozen=True, slots=True)
class TraceState:
    """Everything a policy is allowed to see: an id, a clock and four numbers.

    There is deliberately **no span, no node, no name and no kind** here
    (`SPEC.md` §5.6). A policy that could consult what a record meant would be
    a rule the receiver carries, and a completion policy firing on a tool's
    name would be a detector with a timeout. A test holds this field set.
    """

    trace_id: str
    #: The tick's one clock reading. One per tick, so every trace in a tick is
    #: evaluated against the same instant (`SPEC.md` §5.2).
    now: float
    #: Records **absorbed** into this builder -- its own `version`, so there is
    #: no second counter to drift from it. A refused record is not absorbed.
    records: int
    first_record_at: float
    last_record_at: float
    #: When an ended root was **first seen**, on the receiver's clock, or `None`
    #: if one has not been. Never the span's own `ended_at` (`SPEC.md` §5.2).
    root_ended_at: float | None


class Policy(Protocol):
    """One completion policy: a value that answers one question about a trace.

    `code` and `watches_root` are the type's, not the instance's: the code names
    the policy, and `watches_root` is how a router knows whether it must
    materialize a graph at all this tick (`SPEC.md` §5.7).
    """

    code: ClassVar[str]
    watches_root: ClassVar[bool]

    def fires(self, state: TraceState) -> bool: ...


@dataclass(frozen=True, slots=True)
class Quiet:
    """No record for this trace for `seconds`, on the caller's clock.

    Any record the router routed to the trace is activity, **absorbed or
    refused**: a re-sent span is the exporter still talking about this trace,
    and counting a refusal as silence would complete a trace that is plainly
    still arriving (`SPEC.md` §5.3).

    The boundary is **inclusive**: it fires at the first tick at which the
    silence has lasted `seconds`, not the one after. `Quiet(0)` completes a
    trace on the first tick after any record, which is legal -- how long is too
    quiet is the caller's number and the receiver holds no opinion about it
    (`SPEC.md` §1.2).
    """

    seconds: float

    code: ClassVar[str] = QUIET
    watches_root: ClassVar[bool] = False

    def fires(self, state: TraceState) -> bool:
        return state.now - state.last_record_at >= self.seconds


@dataclass(frozen=True, slots=True)
class RootEnded:
    """An ended root has been seen, and `grace_seconds` have run since.

    The grace runs from the moment the **receiver** first saw the root's end
    (`TraceState.root_ended_at`), not from the span's own `ended_at` and not
    from the second tick that noticed the same thing (`SPEC.md` §5.2, §5.6).
    Inclusive boundary, as `Quiet`'s is.

    What counts as a root, and as ended, is `root_ended` below -- read off
    structure the graph already states, never a dialect (`SPEC.md` §1.1).
    """

    grace_seconds: float

    code: ClassVar[str] = ROOT_ENDED
    watches_root: ClassVar[bool] = True

    def fires(self, state: TraceState) -> bool:
        if state.root_ended_at is None:
            return False
        return state.now - state.root_ended_at >= self.grace_seconds


@dataclass(frozen=True, slots=True)
class Cap:
    """This trace has absorbed `records` records or more (`SPEC.md` §5.3).

    The count is the builder's own `version`. A refused record does not count,
    because it was not absorbed (`spanweave` `SPEC.md` §10.5) -- it is already
    reported as `refused` (`SPEC.md` §4.4).
    """

    records: int

    code: ClassVar[str] = CAP
    watches_root: ClassVar[bool] = False

    def fires(self, state: TraceState) -> bool:
        return state.records >= self.records


def root_ended(graph: Graph) -> bool:
    """Has this graph got a root, and has every root of it ended?

    Both halves are the library's, not the receiver's (`SPEC.md` §5.6):

    - A **root** is a node with no incoming `parent` edge and no
      `orphan_parent` diagnostic naming it. `spanweave` `SPEC.md` §4.0: "a
      record that names no parent at all is a **root**, and a root is not a
      truncated trace", while "`orphan_parent` reports a parent the record
      *named* and this input does not carry". The second half is what makes
      this usable live, where a trace's root arriving after its children is the
      ordinary case (`spanweave` §10.6): an orphan has no `parent` edge either,
      and reading it as a root would complete traces whose real root is still
      in flight. Only `parent` edges are consulted -- `call_result`, `data` and
      `link` assert something else and `temporal` is derived.
    - **Ended** is `ended_at is not None`: the span reported an end. A dialect
      that reports no end time therefore never satisfies this, which is the
      honest answer rather than a guess; such a caller wants `Quiet`.

    **At least one** root, and **every** root ended. A trace can have several
    roots (nodes with no parent are siblings at trace root, `spanweave` §4.3),
    so "any" and "all" are a real choice and this is the conservative one: with
    "any", one finished sibling would complete a trace whose other top-level
    operation was still running. A graph of nothing but orphans has no root and
    is not ended -- there is nothing there whose end could mean the trace's.
    """
    orphans = frozenset(
        diagnostic.node_id
        for diagnostic in graph.diagnostics
        if diagnostic.code == _ORPHAN_PARENT and diagnostic.node_id is not None
    )
    roots = [
        node
        for node in graph.nodes()
        if not graph.parents(node.id, EdgeKind.PARENT) and node.id not in orphans
    ]
    if not roots:
        return False
    return all(node.ended_at is not None for node in roots)


@dataclass(frozen=True, slots=True, kw_only=True)
class Completion:
    """The caller's completion policy: any-of, a clock, and where to write.

    `now` has **no default**, which is the design (`SPEC.md` §5.2): a module
    holding `time.monotonic` as a default would have earned an entry in the
    seam allowlist, and requiring the argument costs the caller one line and
    the test suite nothing. R7's CLI binds the real clock.

    `policies` compose as **any-of** and the caller's order is the order: the
    first that fires is the one that completed the trace. "The strictest" would
    be the receiver ranking somebody else's policies, and "first in the tuple"
    is a fact a caller can predict. An empty tuple never completes anything,
    which is a legal thing to ask for and not a reason to invent a default.
    """

    policies: tuple[Policy, ...] = ()
    now: Callable[[], float]
    #: Where final graphs go, with `spanweave.dump`, or `None` to write none.
    out_dir: pathlib.Path | None = None

    @property
    def watches_root(self) -> bool:
        """Does any policy here need the graph? (`SPEC.md` §5.7.)"""
        return any(policy.watches_root for policy in self.policies)

    def fired(self, state: TraceState) -> Policy | None:
        """The first policy that fires for this state, or `None` (`§5.4`)."""
        for policy in self.policies:
            if policy.fires(state):
                return policy
        return None

    def path_for(self, trace_id: str, generation: int) -> pathlib.Path | None:
        """Where this generation's graph goes, or `None` if it cannot go.

        Generation 1 is `<trace_id>.json` -- the name `SPEC.md` §8's CLI
        documents -- and generation *n* > 1 is `<trace_id>.<n>.json`, beside the
        first rather than over it, because editing a report the receiver already
        made would make its output depend on what arrived after it made it
        (`SPEC.md` §5.5).

        `None` when the trace id is not usable as **one** path component: empty,
        `.`, `..`, or carrying a separator or a NUL. A trace id is untrusted
        input (`CLAUDE.md` 9) and a file named from it must not be able to leave
        the directory the caller named. `None` is also what a `Completion` with
        no `out_dir` answers, and the router asks only when there is one, so the
        two cannot be confused there.
        """
        if self.out_dir is None or not usable_as_one_path_component(trace_id):
            return None
        stem = trace_id if generation <= 1 else f"{trace_id}.{generation}"
        return self.out_dir / f"{stem}.json"


def usable_as_one_path_component(trace_id: str) -> bool:
    """Can a file be named from this trace id without leaving a directory?

    The test is deliberately about the *id*, not about the platform: a
    separator of either kind, a NUL, an empty id, and the two relative names are
    refused everywhere, so a receiver on Linux and one on Windows refuse the
    same ids and `NOT_WRITTEN` means the same thing in both reports.
    """
    if trace_id in ("", ".", ".."):
        return False
    return not any(character in trace_id for character in ("/", "\\", "\0"))


def write(graph: Graph, path: pathlib.Path) -> None:
    """`spanweave.dump` into `path`, creating the caller's directory if needed.

    Here rather than in the router so that the router's `tick` reads as the four
    steps `SPEC.md` §5.4 lists. Raises what the filesystem raises; the router is
    what turns that into `NOT_WRITTEN`.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    spanweave.dump(graph, path)
