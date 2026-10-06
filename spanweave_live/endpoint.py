"""Ingest: the OTLP/HTTP JSON endpoint (`SPEC.md` §7.2).

The sixth piece, and the second of the two ingests. §7.1's `tail` and `stdin`
answer "how do the bytes reach the framer?" for a file and a pipe; this answers
it for an exporter that POSTs them. It frames nothing of its own, routes
nothing, and reads no dialect: a body goes to `Framer.document` and the
`spanweave.Records` that came back go to the caller (`SPEC.md` §1.1, §1.2).

**`Framer.document`, never `Framer.push`.** That is the whole of this module's
one hard rule and it is a trap rather than a preference (`SPEC.md` §3.3). A
pretty-printed export whose body ends in a newline reads *identically* through
`push` -- the same records, no diagnostic, byte for byte -- because the reader's
container detection runs per call and a whole arrival is one call. The same
export with its trailing newline trimmed, which is the ordinary shape of an HTTP
body, loses its last line to the remainder and comes back as hundreds of
`malformed_record`s; compacted onto one line with no terminator it reads as
**nothing at all**. So the wrong method here is not a method that fails, it is a
method that works until it silently does not.

**No socket here, and no `http` import.** Four layers, and the import happens
above all four (`CLAUDE.md`, standing rule 4):

- `Endpoint.handle(request)` is pure: a `Request` value in, an `Exchange` out.
  No stream, no socket, nothing to inject -- which is where every decision this
  module makes lives, and why 415, 400 and gzip are testable without a port.
- `respond(handler, endpoint)` is one request on a
  `http.server.BaseHTTPRequestHandler`-shaped object: it reads
  `Content-Length` bytes, calls `handle`, and writes the status, the headers and
  the body back. The shape is a `Protocol` here, satisfied structurally by the
  stdlib class the caller holds.
- `handler_class(base, endpoint)` builds the handler **class** from the base the
  caller passes in, with every method routed to `respond`. The base class is an
  injected seam with no default, exactly as `Completion.now` and `tail`'s
  `sleep` are.
- `serve(endpoint, listener=...)` drives a listener the caller's factory built
  and yields one `spanweave.Records` per request handled.

So the seam allowlist in `tests/gates.py` is still empty after this batch, as it
was after R3, R4 and R5: `import http.server` lives in the caller, which is
R7's CLI, and in the tests -- where a loopback socket on port 0 and a
single-threaded `handle_request()` make the whole thing a thing a test can
state facts about rather than a race it hopes to win.
"""

from __future__ import annotations

import gzip
import json
import zlib
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any, BinaryIO, Final, Protocol

from spanweave import Records

from spanweave_live.framing import Framer
from spanweave_live.routing import Event

#: The one request this endpoint serves. OTLP/HTTP's own path for traces.
TRACES_TARGET: Final = "/v1/traces"

#: The one media type it reads. Parameters (`; charset=utf-8`) are allowed and
#: ignored; the type itself is matched case-insensitively, as HTTP says it is.
JSON_MEDIA_TYPE: Final = "application/json"

#: The one content coding it accepts beside no coding at all.
GZIP_ENCODING: Final = "gzip"

#: The request was not the one this endpoint serves -- a different method, a
#: different target, a media type it does not read, a content coding it cannot
#: undo, or a transfer coding it cannot unframe. Answered `415`, counted, and
#: the `detail` says which of the five it was (`SPEC.md` §1.5, §7.2).
UNSUPPORTED_MEDIA_TYPE: Final = "unsupported_media_type"

#: The request *was* the one this endpoint serves and the body could not be
#: read: the gzip would not inflate, or the reader skipped every line of it and
#: produced no record. Answered `400`, counted, with the library's own code in
#: `spanweave_code` where the library is the one that said so.
UNREADABLE_BODY: Final = "unreadable_body"

#: What an accepted body answers. `{}` and not OTLP's `partialSuccess` envelope:
#: see `SPEC.md` §7.2 for why an empty one would be a claim this receiver cannot
#: make and a filled one would be a dialect read.
_ACCEPTED_BODY: Final = b"{}"

#: Read nothing, and said so. A request that was refused still yields, as a poll
#: that read nothing still yields in §7.1: "nothing arrived" and "nothing was
#: readable" are different answers and neither is an absence (`SPEC.md` §1.5).
_NOTHING: Final = Records(records=(), diagnostics=(), skipped_records=0)


@dataclass(frozen=True, slots=True)
class Request:
    """One HTTP request, reduced to the five facts this endpoint decides on.

    A value and not a stream: by the time a `Request` exists the body has been
    read, so `Endpoint.handle` is a pure function and every decision below can
    be tested without a socket. `respond` is what turns a live handler into one
    of these.

    The three header fields are `None` when the header was absent, which is a
    different answer from an empty string and is why they are not `str`.
    """

    method: str
    target: str
    body: bytes
    content_type: str | None = None
    content_encoding: str | None = None
    #: `Transfer-Encoding`, which this endpoint cannot unframe. Declared so the
    #: refusal is a refusal: `respond` reads `Content-Length` bytes, a chunked
    #: body has no `Content-Length`, and accepting one would mean answering
    #: `200` to a body nobody read -- the silence `SPEC.md` §1.5 refuses.
    transfer_encoding: str | None = None


@dataclass(frozen=True, slots=True)
class Response:
    """What goes back on the wire: a status, a body, and the body's type."""

    status: int
    body: bytes
    content_type: str = JSON_MEDIA_TYPE


@dataclass(frozen=True, slots=True)
class Exchange:
    """One request, its answer, and what the reader made of its body.

    The records ride **beside** the response rather than in it, as the framer's
    events ride beside its `Records` (`SPEC.md` §3.1): a response is bytes for
    the poster and records are values for the consumer, and one type carrying
    both would be a second name for each.

    `records` is `spanweave.Records` even for a refusal, and then it is empty
    rather than absent -- except for an unreadable body, where it carries the
    reader's own diagnostics, which is the only place those bytes survive.
    """

    request: Request
    response: Response
    records: Records
    events: tuple[Event, ...] = ()


def _media_type(header: str | None) -> str:
    """The media type of a `Content-Type`, lowercased, parameters dropped."""
    if header is None:
        return ""
    return header.split(";", 1)[0].strip().lower()


def _coding(header: str | None) -> str:
    """A content or transfer coding, lowercased. Absent reads as `identity`."""
    if header is None:
        return "identity"
    return header.strip().lower() or "identity"


class Endpoint:
    """The OTLP/HTTP endpoint, as a pure function of the requests it is handed.

    One `Endpoint` per `Framer`, and the framer is injected for §7.1's reason:
    the caller sets the remainder's cap and keeps a handle on it. The cap does
    not apply to a body (`SPEC.md` §3.3) -- a body is not a remainder -- so an
    endpoint's framer holds nothing between requests, and that is a property
    the tests assert rather than a thing this docstring claims.

    Everything it decides, it decides here: the target, the method, the media
    type, the content coding, and whether the reader could read the body. There
    is no socket in this class and no `http` import in this module; `respond`,
    `handler_class` and `serve` below are the three thin layers that put one on
    top of it, each with its seam injected by the caller.
    """

    __slots__ = ("_counts", "_framer", "_last", "_requests")

    def __init__(self, *, framer: Framer | None = None) -> None:
        self._framer = Framer() if framer is None else framer
        self._requests = 0
        self._last: Exchange | None = None
        self._counts: dict[str, int] = {}

    @property
    def framer(self) -> Framer:
        """The framer the bodies go to, so a caller can read its counts."""
        return self._framer

    @property
    def requests(self) -> int:
        """How many requests have been handled, refusals included.

        The number `Event.index` counts, which is §4.1's "1-based arrival
        index" read one layer up: a request here, a chunk in §7.1, a record in
        §4.
        """
        return self._requests

    @property
    def last(self) -> Exchange | None:
        """The most recent exchange, or `None` before the first request.

        One stored object rather than a response, a records and an events
        property that could drift apart. `serve` yields `last.records`.
        """
        return self._last

    @property
    def events(self) -> tuple[Event, ...]:
        """The events of the **most recent request**, and no further back.

        The framer's choice (`SPEC.md` §3.1) and the router's (§4.6): a log that
        grows with the stream is a cost nobody asked for, and `counts` is the
        running total, bounded by the number of codes.
        """
        return () if self._last is None else self._last.events

    @property
    def counts(self) -> Mapping[str, int]:
        """How many of each event code, for the life of this endpoint."""
        return dict(self._counts)

    def handle(self, request: Request) -> Exchange:
        """Decide about one request, and read its body if it is the one.

        `POST /v1/traces` with `Content-Type: application/json` and no coding
        this endpoint cannot undo goes to `Framer.document`. Everything else is
        a `415` with an `unsupported_media_type` event naming which of the five
        checks it failed. A body that cannot be inflated, or that the reader
        skipped every line of, is a `400` with an `unreadable_body` event.

        It never raises for anything a request can carry, which is §4.4's rule
        one layer up: a refusal is an event and the endpoint keeps serving.
        """
        self._requests += 1
        exchange = self._decide(request)
        self._last = exchange
        for event in exchange.events:
            self._counts[event.code] = self._counts.get(event.code, 0) + 1
        return exchange

    def _decide(self, request: Request) -> Exchange:
        refusal = self._unsupported(request)
        if refusal is not None:
            return self._refused(request, 415, UNSUPPORTED_MEDIA_TYPE, refusal)
        try:
            body = self._decoded(request)
        except (OSError, EOFError, zlib.error) as error:
            # `gzip.decompress` raises `BadGzipFile` (an `OSError`), `EOFError`
            # on a truncated member, or a `zlib.error` on a corrupt deflate
            # stream. Three exception families for one fact -- the bytes are
            # not a gzip member -- so all three are caught and reported as the
            # one thing the poster needs to know (`SPEC.md` §1.5).
            return self._refused(
                request,
                400,
                UNREADABLE_BODY,
                f"the body declared {GZIP_ENCODING!r} and could not be "
                f"inflated ({type(error).__name__}: {error})",
            )
        read = self._framer.document(body)
        if not read.records and read.skipped_records:
            # The reader skipped every line and produced no record: these bytes
            # are not records in any dialect it knows. Its own diagnostics ride
            # out in `records` -- the only place the text survives -- and the
            # poster is told `400` rather than being thanked for an export that
            # went nowhere.
            return Exchange(
                request=request,
                response=Response(status=400, body=self._coded(UNREADABLE_BODY)),
                records=read,
                events=(
                    self._event(
                        UNREADABLE_BODY,
                        f"the body was read as {read.skipped_records} skipped "
                        f"record(s) and no record at all",
                        spanweave_code=_first_code(read),
                    ),
                ),
            )
        return Exchange(
            request=request,
            response=Response(status=200, body=_ACCEPTED_BODY),
            records=read,
        )

    @staticmethod
    def _unsupported(request: Request) -> str | None:
        """Why this request is not the one this endpoint serves, or `None`.

        Five checks, one status. `415` for a wrong target and a wrong method
        too, rather than `404` and `405`: this endpoint serves exactly one
        request, and three statuses would be three policies where `SPEC.md`
        §7.2 states one. Which check failed is in the event's `detail`, so the
        single status hides nothing (`SPEC.md` §1.5).
        """
        if request.method.upper() != "POST":
            return (
                f"{request.method!r} is not POST, and POST {TRACES_TARGET} is "
                f"the one request this endpoint serves"
            )
        if request.target != TRACES_TARGET:
            return (
                f"{request.target!r} is not {TRACES_TARGET!r}, which is the "
                f"one target this endpoint serves"
            )
        media_type = _media_type(request.content_type)
        if media_type != JSON_MEDIA_TYPE:
            return (
                f"{media_type!r} is not {JSON_MEDIA_TYPE!r}; this endpoint "
                f"reads OTLP/HTTP JSON and not protobuf"
            )
        transfer = _coding(request.transfer_encoding)
        if transfer != "identity":
            return (
                f"Transfer-Encoding {transfer!r} is a framing this endpoint "
                f"does not unframe, and a body it did not read must not be "
                f"answered 200"
            )
        coding = _coding(request.content_encoding)
        if coding not in ("identity", GZIP_ENCODING):
            return (
                f"Content-Encoding {coding!r} is a coding this endpoint "
                f"cannot undo; it accepts {GZIP_ENCODING!r} and no coding"
            )
        return None

    def _decoded(self, request: Request) -> bytes:
        """The body, inflated if it said it was gzipped."""
        if _coding(request.content_encoding) == GZIP_ENCODING:
            return gzip.decompress(request.body)
        return request.body

    def _refused(
        self, request: Request, status: int, code: str, detail: str
    ) -> Exchange:
        return Exchange(
            request=request,
            response=Response(status=status, body=self._coded(code)),
            records=_NOTHING,
            events=(self._event(code, detail),),
        )

    def _event(
        self, code: str, detail: str, *, spanweave_code: str | None = None
    ) -> Event:
        return Event(
            code=code,
            index=self._requests,
            trace_id=None,
            spanweave_code=spanweave_code,
            detail=detail,
        )

    @staticmethod
    def _coded(code: str) -> bytes:
        """A refusal's body: the receiver's own code, and nothing else.

        `sort_keys=True` and a separator with no spaces, because a response is
        output and output here is byte-identical for identical input
        (`CLAUDE.md` 8).
        """
        return json.dumps({"code": code}, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )


def _first_code(read: Records) -> str | None:
    """The first diagnostic's code in the library's own order, or `None`.

    `Event.spanweave_code` is one field and a read can report several
    diagnostics. The library states the order of a collection of them
    (`spanweave` `SPEC.md` §5.2) and `Framer` hands them back in it, so "the
    first" is a deterministic answer rather than whichever one came out first.
    """
    return read.diagnostics[0].code if read.diagnostics else None


class HttpHandler(Protocol):
    """What `http.server.BaseHTTPRequestHandler` already is.

    Declared as a `Protocol` rather than imported, which is the whole point:
    the stdlib class satisfies this structurally, so `respond` works on the
    real thing while nothing under `spanweave_live/` imports `http`
    (`tests/gates.py`, `CLAUDE.md` standing rule 4). The members are read-only
    properties so that a subclass's plain attributes satisfy them.

    It is **documentation plus duck typing, not a checked claim**: `mypy` never
    sees the stdlib class handed to `respond`, because the call site is the
    caller's. What makes the shape true is `tests/test_endpoint.py` driving a
    real `http.server.HTTPServer` over a loopback socket -- said here rather
    than left for a reader to assume.
    """

    @property
    def command(self) -> str:
        """The request method, as the stdlib handler spells it."""

    @property
    def path(self) -> str:
        """The request target, as the stdlib handler spells it."""

    @property
    def headers(self) -> Mapping[str, str]:
        """The request headers. `email.message.Message` is one of these."""

    @property
    def rfile(self) -> BinaryIO:
        """The request body's stream."""

    @property
    def wfile(self) -> BinaryIO:
        """The response's stream."""

    def send_response(self, code: int, message: str | None = None) -> None: ...

    def send_header(self, keyword: str, value: str) -> None: ...

    def end_headers(self) -> None: ...


def _content_length(handler: HttpHandler) -> int:
    """How many body bytes to read, and `0` for a header that is not a number.

    A `Content-Length` that is absent, empty or not an integer is read as no
    body rather than raised on: the request still reaches `Endpoint.handle`,
    which answers it, and an endpoint that raised here would turn a malformed
    header into a traceback instead of a status (`SPEC.md` §7.2).
    """
    try:
        return max(0, int(handler.headers.get("Content-Length") or 0))
    except ValueError:
        return 0


def respond(handler: HttpHandler, endpoint: Endpoint) -> Exchange:
    """Serve one request on a live handler, and hand back what it was.

    Reads `Content-Length` bytes, asks `endpoint.handle`, and writes the
    status, the two headers and the body. It is the only function here that
    touches a stream, and it still opens no socket: the handler is the caller's
    and the socket is underneath it.

    It does not catch exceptions of its own, because `Endpoint.handle` raises
    for nothing a request can carry: a body that is not JSON, not gzip, not
    UTF-8 or not there at all is a status and an event, never a traceback.
    """
    request = Request(
        method=handler.command,
        target=handler.path,
        body=handler.rfile.read(_content_length(handler)),
        content_type=handler.headers.get("Content-Type"),
        content_encoding=handler.headers.get("Content-Encoding"),
        transfer_encoding=handler.headers.get("Transfer-Encoding"),
    )
    exchange = endpoint.handle(request)
    response = exchange.response
    handler.send_response(response.status)
    handler.send_header("Content-Type", response.content_type)
    handler.send_header("Content-Length", str(len(response.body)))
    handler.end_headers()
    handler.wfile.write(response.body)
    return exchange


#: The methods the built handler class answers. Every one of them, so that a
#: request this endpoint does not serve gets the endpoint's own `415` and its
#: event rather than `http.server`'s bare `501`: a refusal nobody counted is
#: the silence `SPEC.md` §1.5 refuses, and `Endpoint._unsupported` is where the
#: method check belongs.
_METHODS: Final = (
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "HEAD",
    "OPTIONS",
)


def handler_class(base: type[Any], endpoint: Endpoint, /) -> type[Any]:
    """Build the request-handler class for `base`, routed to `endpoint`.

    `base` is `http.server.BaseHTTPRequestHandler`, and it is an **injected
    seam with no default**, exactly as `Completion.now` and `tail`'s `sleep`
    are (`SPEC.md` §5.2, §7.1): the import lives in the caller, so the seam
    allowlist in `tests/gates.py` stays empty and this module can be read
    without wondering what it opens.

    The class is built with `type` rather than written with a `class`
    statement because a `class` statement needs the base at import time, which
    is the import this module does not make. Every method in `_METHODS` is
    answered through `respond`, and `log_message` is silenced -- the stdlib's
    default writes a line per request to `sys.stderr`, and what reaches a
    human is the caller's business (`SPEC.md` §1.2), with `Endpoint.counts` and
    `Endpoint.events` as the receiver's own answer.
    """

    def _method(self: HttpHandler) -> None:
        respond(self, endpoint)

    def _quiet(self: HttpHandler, _format: str, *_args: object) -> None:
        return None

    namespace: dict[str, Any] = {
        "endpoint": endpoint,
        "protocol_version": "HTTP/1.0",
        "log_message": _quiet,
        "__doc__": (
            f"spanweave-live's OTLP/HTTP handler: POST {TRACES_TARGET}, "
            f"built on {base.__name__}."
        ),
    }
    for method in _METHODS:
        namespace[f"do_{method}"] = _method
    return type("SpanweaveLiveHandler", (base,), namespace)


class Listener(Protocol):
    """What `http.server.HTTPServer` already is, in the two calls `serve` makes.

    `handle_request` serves exactly one request and returns, which is what
    makes `serve` single-threaded and a test deterministic: the test writes a
    request, asks for one yield, and reads the response, with no thread and no
    timeout in it. A caller that wants concurrency brings its own listener --
    that is the point of the factory, and `threading` is banned here
    (`CLAUDE.md` standing rule 4).
    """

    def handle_request(self) -> None: ...

    def server_close(self) -> None: ...


def serve(
    endpoint: Endpoint,
    *,
    listener: Callable[[], Listener],
    until: Callable[[], bool] | None = None,
) -> Iterator[Records]:
    """Drive a listener and yield what each request's body read.

    `listener` is the **caller's factory** and has no default, so the socket is
    bound outside this package: a test binds `127.0.0.1` on port `0` and R7's
    CLI binds the port a human asked for. It is called once, and the listener
    is closed when the iteration ends, however it ends.

    **One yield per request handled**, refusals included, with
    `spanweave.Records` that is empty rather than absent -- §7.1's rule for a
    poll that read nothing, for the same reason: "nothing arrived" and "nothing
    was readable" are different answers, and `Endpoint.last` is where the
    second one is visible beside the yield.

    `until` is the caller's stop condition, asked once before each request;
    `None` serves forever. It is the caller's because "stop after this many" is
    a policy (`SPEC.md` §1.2) and because a test needs a stop that is not a
    timeout.
    """
    server = listener()
    try:
        while until is None or not until():
            server.handle_request()
            last = endpoint.last
            yield _NOTHING if last is None else last.records
    finally:
        server.server_close()
