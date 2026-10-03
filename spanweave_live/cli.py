"""The `spanweave-live` entry point.

A skeleton: R0 ships `--version` and nothing else, so that `make check` and
`make install-check` can both prove the console script a wheel installs
actually runs. The real commands (`tail`, `serve`) arrive in R7 with
`SPEC.md` §8; this module gains no behaviour before then.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from spanweave_live import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spanweave-live",
        description=(
            "Turn telemetry in flight into live spanweave graphs. "
            "PRE-1.0: nothing is frozen -- not this CLI, not the event codes, "
            "not the API."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"spanweave-live {__version__} (pre-1.0; nothing is frozen)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    # R0 has no command to run. Say so on stderr and exit 2 (usage), rather
    # than exiting 0 on a run that did nothing.
    print(
        "spanweave-live: no commands yet -- R0 is the repository skeleton. "
        "`tail` and `serve` arrive in R7 (SPEC.md section 8).",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
