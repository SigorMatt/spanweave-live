"""What routing's second parse costs, against what feeding costs (`SPEC.md` §4.2).

A benchmark, not a test: it reads the real clock, its numbers belong to the
machine that ran it, and nothing in `make check` runs it. `SPEC.md` §4.2 cites
one run of it with its date and its machine as provenance; re-run it to
re-derive the shape of that sentence on yours:

    uv run python tools/bench_routing.py

It times, over `RECORDS` distinct OpenInference `CHAIN` spans of one trace (a
root and its children), `spanweave_live.trace_id_of` on every record and a
fresh `spanweave.Builder`'s `feed` on every record, `REPEATS` times each with
`time.perf_counter`, and prints each repeat's microseconds per record and
`trace_id_of`'s share of `trace_id_of + feed`.
"""

from __future__ import annotations

import platform
import time

import spanweave

from spanweave_live import trace_id_of

RECORDS = 2000
REPEATS = 3


def records(count: int = RECORDS) -> list[dict[str, object]]:
    """`count` distinct OpenInference `CHAIN` spans: a root and its children."""
    return [
        {
            "trace_id": "t1",
            "span_id": f"s{index}",
            "parent_id": None if index == 0 else "s0",
            "name": f"chain.s{index}",
            "start_time": 1_000.0,
            "end_time": 1_001.0,
            "attributes": {"openinference.span.kind": "CHAIN"},
        }
        for index in range(count)
    ]


def per_record(seconds: float, count: int) -> float:
    return seconds / count * 1e6


def main() -> None:
    batch = records()
    print(
        f"{RECORDS} records, {REPEATS} repeats; python {platform.python_version()}, "
        f"{platform.system()} {platform.machine()}"
    )
    for repeat in range(1, REPEATS + 1):
        start = time.perf_counter()
        for record in batch:
            trace_id_of(record)
        identify = per_record(time.perf_counter() - start, len(batch))

        builder = spanweave.Builder()
        start = time.perf_counter()
        for record in batch:
            builder.feed(record)
        feed = per_record(time.perf_counter() - start, len(batch))

        share = identify / (identify + feed) * 100
        print(
            f"repeat {repeat}: trace_id_of {identify:.1f} us, feed {feed:.1f} us, "
            f"trace_id_of is {share:.1f} % of trace_id_of + feed"
        )


if __name__ == "__main__":
    main()
