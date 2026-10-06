"""The `spanweave-live` entry point (`SPEC.md` §8).

Two commands -- `tail` and `serve` -- and no mechanism of its own. Every flag
sets a value an earlier section declared, the files written are §5.4's writes,
the lines on stdout are §6's deltas and the lines on stderr are §1.5's events.
What is new here is only what a process needs and a library does not: where the
bytes come from, when to stop, and what to exit with.

This module imports **no** clock and **no** socket: `spanweave_live/real.py` is
the one file that does, and it is the one entry in `tests/gates.py`'s seam
allowlist (`SPEC.md` §8.2). So the several hundred lines below -- the place where
a stray `time.monotonic()` could actually hide -- stay under the gate.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Final, TextIO

import spanweave
from spanweave import Diagnostic, Records

from spanweave_live import __version__, real
from spanweave_live.completion import Cap, Completion, Policy, Quiet, RootEnded
from spanweave_live.endpoint import Endpoint, handler_class, serve
from spanweave_live.framing import FRAGMENT_TOO_LONG, Framer, FramingEvent
from spanweave_live.ingest import Tail, stdin, tail
from spanweave_live.routing import Event, Router
from spanweave_live.subscriptions import (
    CONSUMER_ERROR,
    DELTA_UNSENT,
    Subscriptions,
    Update,
)

# -- the layers an event line can come from (`SPEC.md` §8.3) ----------------

INGEST: Final = "ingest"
FRAMER: Final = "framer"
READER: Final = "reader"
ENDPOINT: Final = "endpoint"
ROUTER: Final = "router"
CLI: Final = "cli"

# -- the seven things the process says about itself (`SPEC.md` §8.3) --------

#: `serve` bound its socket; carries the **bound** host and port, which is what
#: makes `--port 0` usable.
LISTENING: Final = "listening"
#: The path would not open, or the socket would not bind. Exit 1.
START_FAILED: Final = "start_failed"
#: The run's first `fragment_too_long`: every line number after it is the
#: framer's count of lines handed over, not the input's (`SPEC.md` §3.4).
LINE_NUMBERS_DIVERGED: Final = "line_numbers_diverged"
#: The run's first `forgotten`: the generation is gone, so the next record for
#: that id writes `<trace_id>.json` over the file (`SPEC.md` §5.5, §8.5).
MAY_OVERWRITE: Final = "may_overwrite"
#: The run stopped holding bytes in the framer's remainder it did not flush.
PENDING: Final = "pending"
#: `SIGINT`. What had been written stays written; nothing is completed.
INTERRUPTED: Final = "interrupted"
#: The last line of every run that started: `routed`, `exit` and `counts`.
FINISHED: Final = "finished"

# -- exit codes (`SPEC.md` §8.6) -------------------------------------------

EXIT_OK: Final = 0
EXIT_NO_START: Final = 1
EXIT_USAGE: Final = 2
EXIT_UNDELIVERED: Final = 3
EXIT_INTERRUPTED: Final = 130

#: The three codes that mean "it had something and could not hand it over",
#: which is what exit 3 is about -- and the only thing it is about. A refusal, a
#: cap, a late arrival, a truncation, a 415 and a 400 are observations and leave
#: the exit code at 0 (`SPEC.md` §1.3, §8.6).
UNDELIVERED: Final = ("not_written", DELTA_UNSENT, CONSUMER_ERROR)

#: What a `forgotten` costs where files are being written, said in full because
#: it is the one way this CLI can lose a graph (`SPEC.md` §5.5, §8.5).
_OVERWRITE = (
    "the completion of {trace_id!r} has been forgotten because of "
    "--max-completed, so its generation is gone: the next record for that "
    "trace id opens generation 1 again and its completion writes "
    "<trace_id>.json OVER the file the earlier completion wrote, rather than "
    "beside it as <trace_id>.2.json. SPEC.md 5.5's 'the file already written "
    "is not rewritten' holds only while the completion is remembered. Said "
    "once per run, not once per id"
)

_DIVERGED = (
    "a line was cut loose by --max-pending-bytes, and each fragment of a cut "
    "line is numbered as a line of its own: from here on a framer_line, and "
    "the 'line N' that opens a reader diagnostic's message, is the framer's "
    "count of lines handed over and NOT the input's count of lines written "
    "(SPEC.md 3.4, 7.1). Said once per run"
)


class Reporter:
    """Events to stderr, one JSON object per line (`SPEC.md` §8.3).

    Sorted keys and ASCII escapes, so a line is one line whatever a trace
    payload held, and flushed as it is written: an event a reader cannot see
    until the process exits is an event that is not reported while it matters.

    A field that is `None` is **left out** rather than written as `null`:
    `seconds` absent and `seconds: null` would be the same fact in two
    spellings, and §4.1 put those fields on `Event` so a caller could match on
    them.
    """

    __slots__ = ("_stream",)

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream

    def say(self, layer: str, code: str, **fields: object) -> None:
        payload: dict[str, object] = {"code": code, "layer": layer}
        payload.update(
            {name: value for name, value in fields.items() if value is not None}
        )
        self._stream.write(json.dumps(payload, sort_keys=True) + "\n")
        self._stream.flush()

    def event(self, layer: str, event: Event) -> None:
        """One routing `Event` (`SPEC.md` §4.1), from the layer that made it."""
        self.say(
            layer,
            event.code,
            index=event.index,
            detail=event.detail,
            trace_id=event.trace_id,
            spanweave_code=event.spanweave_code,
            seconds=event.seconds,
            version=event.version,
            offset=event.offset,
            at=event.at,
        )

    def framing(self, event: FramingEvent) -> None:
        """One `FramingEvent` (`SPEC.md` §3.1), with its `line` renamed.

        **`framer_line`, never `line`**: once a line has been cut by the cap,
        each fragment is numbered as a line, so the number is the framer's count
        of lines *handed over* and not the input's count of lines *written*
        (`SPEC.md` §3.4, §7.1). A key spelled `line` would be read as the
        second, which is the one thing it is not.
        """
        self.say(
            FRAMER,
            event.code,
            framer_line=event.line,
            length=event.length,
            detail=event.detail,
        )

    def diagnostic(self, diagnostic: Diagnostic) -> None:
        """One `spanweave.Diagnostic`, under the library's own field names.

        Verbatim, because a diagnostic's message is the only place a skipped
        line's bytes survive (`SPEC.md` §1.5) -- including the `line N` it opens
        with, which carries the same divergence `framing` renames around and
        cannot be renamed because it is inside the library's text (§3.5).
        """
        self.say(
            READER,
            diagnostic.code,
            message=diagnostic.message,
            level=str(diagnostic.level),
            node_id=diagnostic.node_id,
            source=diagnostic.source,
        )


class Run:
    """One run's receiver: a framer, a router, and the two output streams.

    It owns no policy of its own. The flags are read once, here, into the
    values §3 through §6 declare, and everything after that is the library's.
    """

    def __init__(self, args: argparse.Namespace, reporter: Reporter) -> None:
        self.reporter = reporter
        self.out = pathlib.Path(args.out)
        self.framer = Framer(max_pending_bytes=args.max_pending_bytes)
        subscriptions: Subscriptions | None = None
        if args.deltas:
            subscriptions = Subscriptions()
            subscriptions.subscribe(self._delta, trace_id=None, every=1)
        self.router = Router(
            max_traces=args.max_traces,
            max_completed=args.max_completed,
            completion=Completion(
                policies=policies(args), now=real.monotonic, out_dir=self.out
            ),
            subscriptions=subscriptions,
        )
        self.undelivered = 0
        self._stdout = sys.stdout.buffer
        self._said_diverged = False
        self._said_overwrite = False

    # -- stdout: the deltas, and nothing else (`SPEC.md` §8.4) -------------

    def _delta(self, update: Update) -> None:
        """One delta document per line, in the library's own canonical bytes.

        `delta_dumps` already ends in one `\\n` and holds no other, so "one
        document per line" is a property of `spanweave`'s encoder and not of a
        second encoder here. Nothing is wrapped around it: the line **is** the
        document, and the trace is `trace_id_after` inside it.

        A write that raises -- a closed pipe -- is §6.5's `consumer_error`: the
        router isolates it, counts it and goes on, and §8.6's exit 3 is where it
        shows up. The CLI's own output is treated exactly like a stranger's
        callback, deliberately.
        """
        self._stdout.write(spanweave.delta_dumps(update.delta))
        self._stdout.flush()

    # -- stderr: everything the receiver said ------------------------------

    def events(self, layer: str, events: Iterable[Event]) -> None:
        for event in events:
            self.reporter.event(layer, event)
            if event.code in UNDELIVERED:
                self.undelivered += 1
            if event.code == "forgotten" and not self._said_overwrite:
                self._said_overwrite = True
                self.reporter.say(
                    CLI,
                    MAY_OVERWRITE,
                    trace_id=event.trace_id,
                    detail=_OVERWRITE.format(trace_id=event.trace_id),
                )

    def absorb(self, records: Records) -> None:
        """One yield from an ingest: report it, then route what it read.

        The framer's events first -- they are what happened to the bytes --
        then the reader's diagnostics, then one routing decision per record.
        `self.framer.events` is the events of the one framer call this yield
        came from, which is why it is read here and not later (`SPEC.md` §3.1).
        """
        for event in self.framer.events:
            self.reporter.framing(event)
            if event.code == FRAGMENT_TOO_LONG and not self._said_diverged:
                self._said_diverged = True
                self.reporter.say(CLI, LINE_NUMBERS_DIVERGED, detail=_DIVERGED)
        for diagnostic in records.diagnostics:
            self.reporter.diagnostic(diagnostic)
        for record in records.records:
            self.events(ROUTER, self.router.route(record).events)

    def tick(self) -> None:
        """One tick per yield, never one per record (`SPEC.md` §8.5)."""
        for completed in self.router.tick():
            self.events(ROUTER, completed.events)

    def finish(self) -> None:
        """End of input: complete every trace still held (`SPEC.md` §8.5).

        The completion is replaced with one whose only policy is `Cap(0)` -- a
        value §5.3 already defines, firing at `records >= 0`, which is every
        trace -- and ticked once. So `Completed.policy` on those is
        `Cap(records=0)`, which is the honest report: they completed because the
        input ended, and the CLI invents no code of its own for that.
        """
        self.router.completion = Completion(
            policies=(Cap(0),), now=real.monotonic, out_dir=self.out
        )
        self.tick()

    def report_pending(self) -> None:
        """Bytes the framer is still holding, where nothing flushed them.

        Only an interrupt gets here with a remainder: `--once` and EOF are the
        two stops that **are** end of input, and both flush (`SPEC.md` §7.1).
        """
        if self.framer.pending_bytes:
            self.reporter.say(
                CLI,
                PENDING,
                pending_bytes=self.framer.pending_bytes,
                detail=(
                    "the run stopped with an incomplete final line in the "
                    "framer's remainder; it was not flushed, because the stop "
                    "was not end of input (SPEC.md 7.1, 8.6)"
                ),
            )


class Drained:
    """`--once`: stop at the first poll that read nothing (`SPEC.md` §8.5).

    A replay's stop, expressed as the `until` §7.1 already takes rather than as
    a timeout: the file is drained when a poll goes by without a yield. It is
    asked before each poll, so the tail's own poll count is the whole state.
    """

    __slots__ = ("polls", "tail")

    def __init__(self) -> None:
        self.tail: Tail | None = None
        self.polls = 0

    def yielded(self) -> None:
        if self.tail is not None:
            self.polls = self.tail.polls

    def __call__(self) -> bool:
        return self.tail is not None and self.tail.polls > self.polls


def policies(args: argparse.Namespace) -> tuple[Policy, ...]:
    """The caller's policies, in the order §8.1's table lists them.

    `--quiet`, then `--root-grace`, then `--cap`, because §5.4's any-of is "the
    first policy in the caller's tuple that fires" and a command line has no
    tuple order of its own. Picking an order is unavoidable; hiding which one
    it is would not be.
    """
    chosen: list[Policy] = []
    if args.quiet is not None:
        chosen.append(Quiet(args.quiet))
    if args.root_grace is not None:
        chosen.append(RootEnded(args.root_grace))
    if args.cap is not None:
        chosen.append(Cap(args.cap))
    return tuple(chosen)


def _tail(args: argparse.Namespace, run: Run) -> None:
    """Follow a file, or read stdin to EOF (`SPEC.md` §7.1)."""
    if args.path == "-":
        for records in stdin(framer=run.framer):
            run.absorb(records)
            run.tick()
        # `stdin` flushes itself: EOF **is** end of input (`SPEC.md` §7.1).
        return
    drained = Drained()
    source = tail(
        args.path,
        now=real.monotonic,
        sleep=real.sleep,
        poll_seconds=args.poll_seconds,
        framer=run.framer,
        until=drained if args.once else None,
    )
    drained.tail = source
    for records in source:
        run.absorb(records)
        run.tick()
        drained.yielded()
    if args.once:
        # `--once` declares the stop to be end of input, so the remainder is a
        # record and not a fragment of one still arriving (`SPEC.md` §7.1).
        run.absorb(run.framer.flush())
        run.tick()


def _serve(args: argparse.Namespace, run: Run) -> None:
    """Serve `POST /v1/traces` on a socket this process bound (`SPEC.md` §7.2).

    The listener is bound **before** the loop so the bound address can be
    reported: `--port 0` lets the kernel choose and `listening` says which,
    which is what keeps a test off a written-down port.
    """
    endpoint = Endpoint(framer=run.framer)
    listener = real.http_listener(
        (args.host, args.port), handler_class(real.HTTP_HANDLER_BASE, endpoint)
    )
    address = listener.server_address
    run.reporter.say(
        CLI,
        LISTENING,
        host=str(address[0]),
        port=int(address[1]),
        detail=f"POST http://{address[0]}:{address[1]}/v1/traces",
    )
    stop: Callable[[], bool] | None = None
    if args.requests is not None:
        requested = args.requests
        stop = lambda: endpoint.requests >= requested  # noqa: E731
    for records in serve(endpoint, listener=lambda: listener, until=stop):
        run.events(ENDPOINT, endpoint.events)
        run.absorb(records)
        run.tick()


def _common(parser: argparse.ArgumentParser) -> None:
    """The flags both commands carry (`SPEC.md` §8.1)."""
    parser.add_argument(
        "--out",
        required=True,
        metavar="DIR",
        help=(
            "where a completed trace's final graph is written, as "
            "<trace_id>.json (SPEC.md 5.4); a second generation of the same "
            "trace is <trace_id>.<n>.json beside it. Created if it does not "
            "exist. Required: a CLI whose default was compute-and-discard "
            "would look like it was working and leave nothing behind"
        ),
    )
    parser.add_argument(
        "--quiet",
        type=float,
        metavar="S",
        help=(
            "complete a trace that has had no record for S seconds on this "
            "process's monotonic clock (SPEC.md 5.3)"
        ),
    )
    parser.add_argument(
        "--root-grace",
        type=float,
        metavar="S",
        help=(
            "complete a trace S seconds after an ended root was first seen "
            "(SPEC.md 5.3); a dialect that reports no end time never satisfies "
            "it, and such a stream wants --quiet"
        ),
    )
    parser.add_argument(
        "--cap",
        type=int,
        metavar="N",
        help="complete a trace once it has absorbed N records (SPEC.md 5.3)",
    )
    parser.add_argument(
        "--max-traces",
        type=int,
        metavar="N",
        help=(
            "hold builders for at most N identified traces; at the cap a new "
            "trace is refused_at_cap, counted, never dropped (SPEC.md 4.5)"
        ),
    )
    parser.add_argument(
        "--max-completed",
        type=int,
        metavar="N",
        help=(
            "remember at most N completed trace ids, oldest forgotten first, "
            "one forgotten event each (SPEC.md 5.5). BEWARE: forgetting a "
            "completed trace id loses its generation, so a later record for a "
            "forgotten id writes <trace_id>.json OVER the file the earlier "
            "completion wrote instead of beside it. The default remembers "
            "every completion -- about 220 bytes an id -- and overwrites "
            "nothing"
        ),
    )
    parser.add_argument(
        "--max-pending-bytes",
        type=int,
        metavar="N",
        help=(
            "the most the framer will hold back as an incomplete final line; "
            "past it the remainder is read as one line, reported as a "
            "malformed_record and counted (SPEC.md 3.4). Note that each "
            "fragment of a cut line is numbered as a line, so line numbers "
            "after the first fragment_too_long are the framer's count and not "
            "the input's"
        ),
    )
    parser.add_argument(
        "--deltas",
        action="store_true",
        help=(
            "write each per-record delta document to stdout as one line, in "
            "spanweave's own canonical bytes (SPEC.md 6.1, 8.4). Without it "
            "the router computes no delta at all"
        ),
    )


_FROZEN = (
    "PRE-1.0: nothing is frozen -- not this CLI, not the event codes, not the API."
)


def build_parser() -> argparse.ArgumentParser:
    """The two commands and their flags, exactly as `SPEC.md` §8.1 declares.

    A test parses that usage block out of the spec and compares it with this
    parser flag by flag, in both directions, so a flag here and not there --
    or there and not here -- fails the build.
    """
    parser = argparse.ArgumentParser(
        prog="spanweave-live",
        description=f"Turn telemetry in flight into live spanweave graphs. {_FROZEN}",
        epilog=(
            "Exit codes: 0 the input ended and everything was delivered; 1 it "
            "could not start (the path would not open, or the socket would not "
            "bind); 2 usage; 3 it ran to the end but something it had could "
            "not be delivered (not_written, delta_unsent or consumer_error); "
            "130 interrupted. A refusal, a cap, a late arrival, a 415 and a "
            "400 are observations and leave the code at 0 (SPEC.md 8.6). "
            "Events go to stderr as one JSON line each, with a code; stdout "
            "carries deltas and nothing else."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"spanweave-live {__version__} (pre-1.0; nothing is frozen)",
    )
    commands = parser.add_subparsers(dest="command", metavar="{tail,serve}")

    follow = commands.add_parser(
        "tail",
        help="follow a file, or read stdin to EOF",
        description=f"Follow a growing file, or read stdin to EOF. {_FROZEN}",
    )
    follow.add_argument(
        "path",
        metavar="<path>",
        help="the file to follow, or - for stdin (where EOF is end of input)",
    )
    _common(follow)
    follow.add_argument(
        "--poll-seconds",
        type=float,
        default=1.0,
        metavar="S",
        help="how long to sleep between polls of the file (file only)",
    )
    follow.add_argument(
        "--once",
        action="store_true",
        help=(
            "read what is in the file now, then stop -- a replay. The stop is "
            "end of input, so the framer is flushed (file only). Without it "
            "the file is followed until the process is interrupted"
        ),
    )

    served = commands.add_parser(
        "serve",
        help="receive OTLP/HTTP JSON over a socket this process binds",
        description=f"Serve POST /v1/traces on one socket. {_FROZEN}",
    )
    served.add_argument(
        "--port",
        type=int,
        required=True,
        metavar="P",
        help="the port to bind; 0 lets the kernel choose and `listening` says which",
    )
    _common(served)
    served.add_argument(
        "--host",
        default="127.0.0.1",
        metavar="H",
        help=(
            "the address to bind (default 127.0.0.1: a receiver on every "
            "interface is a decision the caller makes, not a default)"
        ),
    )
    served.add_argument(
        "--requests",
        type=int,
        metavar="N",
        help="serve N requests and stop; without it, serve until interrupted",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one command and return its exit code (`SPEC.md` §8.6)."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_usage(sys.stderr)
        print(
            "spanweave-live: a command is required: tail or serve (SPEC.md section 8).",
            file=sys.stderr,
        )
        return EXIT_USAGE
    reporter = Reporter(sys.stderr)
    run = Run(args, reporter)
    code = EXIT_OK
    try:
        if args.command == "tail":
            _tail(args, run)
        else:
            _serve(args, run)
        run.finish()
        if run.undelivered:
            code = EXIT_UNDELIVERED
    except KeyboardInterrupt:
        # Nothing is ticked on the way out: the stop was not end of input, and
        # completing traces here would be the CLI inventing a policy a signal
        # did not state (`SPEC.md` §1.2, §8.6).
        reporter.say(
            CLI,
            INTERRUPTED,
            detail=(
                "interrupted; what was written stays written and traces still "
                "open were not completed (SPEC.md 8.6)"
            ),
        )
        code = EXIT_INTERRUPTED
    except OSError as error:
        # The source would not start: the path would not open, or the socket
        # would not bind. Those are the two an `OSError` reaches here from.
        reporter.say(CLI, START_FAILED, detail=f"{error}")
        code = EXIT_NO_START
    run.report_pending()
    reporter.say(
        CLI,
        FINISHED,
        routed=run.router.routed,
        **{"exit": code},
        counts=counts(run.router.counts),
    )
    return code


def counts(running: Mapping[str, int]) -> dict[str, int]:
    """The router's count per code, sorted so two runs read the same."""
    return dict(sorted(running.items()))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
