"""spanweave-live — a receiver for telemetry in flight.

Plumbing and policy, and nothing else. It frames bytes into records, routes
records to one `spanweave.Builder` per trace, decides when a trace is complete,
and hands graphs and deltas to consumers. It reads no dialect, carries no
rules, enforces nothing, and owns no clock (`CLAUDE.md`, `SPEC.md` §1).

Nothing here is frozen: pre-1.0, by `0.0.x`, deliberately.

This module is the public API. Each batch adds the one name it built
(`SPEC.md` §3 onward): R1 adds `Framer`, R2 `Router` and the types its
decisions come back in.
"""

from __future__ import annotations

from spanweave_live.framing import Framer
from spanweave_live.routing import (
    REFUSED,
    REFUSED_AT_CAP,
    Event,
    Routed,
    Router,
    trace_id_of,
)

__all__ = [
    "REFUSED",
    "REFUSED_AT_CAP",
    "Event",
    "Framer",
    "Routed",
    "Router",
    "__version__",
    "trace_id_of",
]

__version__ = "0.0.1"
