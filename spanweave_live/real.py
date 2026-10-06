"""The one module that binds the real world (`SPEC.md` §8.2).

Four names, and nothing else in the file: the real clock, the real sleep, the
real HTTP handler base class and the real listener. It exists so that the seam
allowlist in `tests/gates.py` can name **one** file, and so that the file it
names is small enough to read in one go -- an allowlist entry exempts a whole
file, and exempting `cli.py` would exempt every line of it.

`tests/gates.py`'s `SEAMS` therefore holds exactly
`{"real.py": {"time", "http.server"}}`, which is the project's first entry after
three batches that were each predicted to need one and each declined it: R3's
clock (`SPEC.md` §5.2), R5's `sleep` (§7.1) and R6's listener (§7.2), all three
because the seam turned out to be a parameter with no default. R7 cannot decline
it. `Completion.now`, `tail`'s `now` and `sleep` and `serve`'s listener factory
are those parameters, and **something has to hand them the real thing**: a
process has no caller to take them from.

Deliberately **not** exported from `spanweave_live/__init__.py`. The public API
is what that file exports (`CLAUDE.md`), and these are not API -- they are what
one process binds at its edge. A library caller that wants the real clock
imports `time` in its own code, where it is visible.
"""

from __future__ import annotations

import http.server
import time
from collections.abc import Callable
from typing import Any

#: `Completion.now` and `tail`'s `now`. Monotonic rather than wall-clock: every
#: duration the receiver reports is an interval on its own clock, and a clock
#: that can step backwards would complete traces early or never (`SPEC.md` §5.2).
monotonic: Callable[[], float] = time.monotonic

#: `tail`'s `sleep` (`SPEC.md` §7.1).
sleep: Callable[[float], None] = time.sleep

#: What `handler_class` is given (`SPEC.md` §7.2). `Any` because the receiver
#: states the shape it needs as the `HttpHandler` protocol and never as this
#: class, which is the whole reason the stdlib class is a parameter.
HTTP_HANDLER_BASE: type[Any] = http.server.BaseHTTPRequestHandler


def http_listener(address: tuple[str, int], handler: type[Any], /) -> Any:  # noqa: ANN401
    """An `HTTPServer` bound to `address`, answering with `handler`.

    Bound here, eagerly, rather than inside `serve`'s factory, because the
    caller needs the **bound** address before any request is served: `--port 0`
    lets the kernel choose and the CLI then says which (`SPEC.md` §8.3).
    Positional-only, as `handler_class` is, for the same reason: these are the
    thing and the thing it serves, not policies.
    """
    return http.server.HTTPServer(address, handler)
