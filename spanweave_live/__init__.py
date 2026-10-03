"""spanweave-live — a receiver for telemetry in flight.

Plumbing and policy, and nothing else. It frames bytes into records, routes
records to one `spanweave.Builder` per trace, decides when a trace is complete,
and hands graphs and deltas to consumers. It reads no dialect, carries no
rules, enforces nothing, and owns no clock (`CLAUDE.md`, `SPEC.md` §1).

Nothing here is frozen: pre-1.0, by `0.0.x`, deliberately.

This module is the public API. At R0 it exports the version alone; each later
batch adds the one name it built (`SPEC.md` §3 onward).
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.0.1"
