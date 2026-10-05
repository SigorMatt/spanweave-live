"""spanweave-live — a receiver for telemetry in flight.

Plumbing and policy, and nothing else. It frames bytes into records, routes
records to one `spanweave.Builder` per trace, decides when a trace is complete,
and hands graphs and deltas to consumers. It reads no dialect, carries no
rules, enforces nothing, and owns no clock (`CLAUDE.md`, `SPEC.md` §1).

Nothing here is frozen: pre-1.0, by `0.0.x`, deliberately.

This module is the public API. Each batch adds the one name it built
(`SPEC.md` §3 onward): R1 adds `Framer`, R2 `Router` and the types its
decisions come back in, R2b the framer's cap and the event it reports, R3 the
completion policies, the clock the caller supplies with them, and `Router.tick`.
"""

from __future__ import annotations

from spanweave_live.completion import (
    CAP,
    COMPLETED,
    LATE_ARRIVAL,
    NOT_WRITTEN,
    QUIET,
    RELEASED,
    ROOT_ENDED,
    WRITTEN,
    Cap,
    Completion,
    Policy,
    Quiet,
    RootEnded,
    TraceState,
    root_ended,
)
from spanweave_live.framing import FRAGMENT_TOO_LONG, Framer, FramingEvent
from spanweave_live.routing import (
    REFUSED,
    REFUSED_AT_CAP,
    Completed,
    Event,
    Routed,
    Router,
    trace_id_of,
)

__all__ = [
    "CAP",
    "COMPLETED",
    "FRAGMENT_TOO_LONG",
    "LATE_ARRIVAL",
    "NOT_WRITTEN",
    "QUIET",
    "REFUSED",
    "REFUSED_AT_CAP",
    "RELEASED",
    "ROOT_ENDED",
    "WRITTEN",
    "Cap",
    "Completed",
    "Completion",
    "Event",
    "Framer",
    "FramingEvent",
    "Policy",
    "Quiet",
    "RootEnded",
    "Routed",
    "Router",
    "TraceState",
    "__version__",
    "root_ended",
    "trace_id_of",
]

__version__ = "0.0.1"
