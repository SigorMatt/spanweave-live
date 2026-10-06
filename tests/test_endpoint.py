"""The OTLP/HTTP endpoint, over a real loopback socket (`SPEC.md` §7.2).

Every test here that touches the network binds `127.0.0.1` on port **0** and
lets the kernel choose, writes one request on an `http.client` connection, asks
`serve` for one yield, and then reads the response. There is no thread, no
timeout, no retry and no hard-coded port anywhere in this file: the socket is
real and the schedule is the test's, which is the difference between a fact and
a race.

The load-bearing claims:

- **The corpus' OTLP container renderings, POSTed as bodies, are the graph gate
  A asserts** — in three body spellings, not one. Verbatim (as the corpus
  stores it, newline-terminated), with the trailing newline trimmed, and
  compacted onto one line: the last two are what an HTTP body ordinarily looks
  like, and the two a `Framer.push` would lose. The first is the one it would
  not, which is why the rule is a trap and not a bug (`SPEC.md` §3.3, §7.2).
- **One request is served and everything else is `415`**, counted, with the
  check it failed named in the event.
- **A body that cannot be read is `400` and an event, never a traceback**, and
  its diagnostics still come out in the exchange's `records`.
- **Nothing here imports a socket into the package.** The handler's base class
  and the listener factory are parameters with no defaults, so
  `tests/gates.py`'s `SEAMS` is still `{}` after this batch -- asserted below,
  as R5 asserted it for `sleep`.
"""

from __future__ import annotations

import dataclasses
import gzip
import json
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest
import spanweave

from spanweave_live import (
    GZIP_ENCODING,
    JSON_MEDIA_TYPE,
    TRACES_TARGET,
    UNREADABLE_BODY,
    UNSUPPORTED_MEDIA_TYPE,
    Endpoint,
    Event,
    Exchange,
    Framer,
    Request,
    Response,
    Router,
    handler_class,
    respond,
    serve,
)
from tests import gates

# Gate A's own corpus loader and its comparison, imported rather than
# reimplemented: a second loader or a second graph comparison here would be a
# weaker gate wearing the same name (`SPEC.md` §4.7).
from tests.test_conformance import loaded, rendering_id, renderings

# §4.1's own block test, reused for §7.2's three dataclasses.
from tests.test_routing import declared_fields

JSON = {"Content-Type": JSON_MEDIA_TYPE}


def documents() -> list[Path]:
    """The corpus' OTLP container renderings: the bodies this section serves."""
    return [path for path in renderings() if path.suffix == ".json"]


def spellings(data: bytes) -> dict[str, bytes]:
    """One rendering, in the three shapes an HTTP body comes in.

    `verbatim` is the corpus file's own bytes, which end in a newline; a POST of
    one of those reads **identically** through `Framer.push`, which is the whole
    reason §3.3 is a standing instruction rather than a note. `trimmed` is the
    same document without that terminator, which is what an exporter sends.
    `compact` is the document on one line with no terminator, which is what an
    exporter that is not pretty-printing sends. The last two are the ones a
    `push` loses.
    """
    return {
        "verbatim": data,
        "trimmed": data.rstrip(b"\n"),
        "compact": json.dumps(json.loads(data), separators=(",", ":")).encode("utf-8"),
    }


class Posting:
    """One endpoint, one loopback listener on port 0, one request at a time.

    `serve` is driven by hand: the request is written to the socket first, then
    exactly one yield is taken, then the response is read. Nothing is concurrent
    and nothing waits on a clock.
    """

    def __init__(self, endpoint: Endpoint | None = None) -> None:
        self.endpoint = Endpoint() if endpoint is None else endpoint
        self.server = HTTPServer(
            ("127.0.0.1", 0),
            handler_class(BaseHTTPRequestHandler, self.endpoint),
        )
        self.factories = 0
        self.closed = 0
        self.pending = 0
        self.asked = 0
        self.iterator = serve(self.endpoint, listener=self._listener, until=self._until)

    @property
    def address(self) -> tuple[str, int]:
        host, port = self.server.server_address[0], self.server.server_address[1]
        assert isinstance(host, str) and isinstance(port, int)
        return host, port

    def _listener(self) -> Any:
        self.factories += 1
        outer = self

        class Counting:
            def handle_request(self) -> None:
                outer.server.handle_request()

            def server_close(self) -> None:
                outer.closed += 1
                outer.server.server_close()

        return Counting()

    def _until(self) -> bool:
        self.asked += 1
        return self.pending == 0

    def post(
        self,
        body: bytes = b"",
        *,
        method: str = "POST",
        target: str = TRACES_TARGET,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, bytes, spanweave.Records]:
        host, port = self.address
        connection = HTTPConnection(host, port)
        connection.request(
            method,
            target,
            body=body,
            headers=dict(JSON if headers is None else headers),
        )
        self.pending = 1
        records = next(self.iterator)
        self.pending = 0
        reply = connection.getresponse()
        status, payload = reply.status, reply.read()
        connection.close()
        return status, payload, records

    def close(self) -> None:
        self.iterator.close()


@pytest.fixture
def posting() -> Any:
    live = Posting()
    try:
        yield live
    finally:
        live.close()


# --------------------------------------------------------------------------
# The surface `SPEC.md` §7.2 declares is the surface the code has.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["Request", "Response", "Exchange"])
def test_the_blocks_in_SPEC_are_the_dataclasses_the_code_has(name):
    """§7.2 says the block is declared exactly as the code accepts it. Held.

    The same test §4.1 earned the hard way (`patches/REVIEW-2026-10-06.md` F5),
    applied to this section's three dataclasses from the day they exist rather
    than after three batches amended a fence by hand.
    """
    declared = declared_fields("7.2", name)
    actual = [
        (field.name, field.default is not dataclasses.MISSING)
        for field in dataclasses.fields(
            {"Request": Request, "Response": Response, "Exchange": Exchange}[name]
        )
    ]
    assert declared == actual


def test_the_endpoints_framer_is_keyword_only_and_injected():
    """A policy the caller sets, not a reading order (`SPEC.md` §3.1, §7.2)."""
    with pytest.raises(TypeError):
        Endpoint(Framer())  # type: ignore[misc]
    framer = Framer(max_pending_bytes=8)
    assert Endpoint(framer=framer).framer is framer
    assert Endpoint().framer.max_pending_bytes is None


def test_the_handler_base_class_is_positional_and_has_no_default():
    """The base class is the seam, and a seam with no default is the point."""
    with pytest.raises(TypeError):
        handler_class()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        handler_class(base=BaseHTTPRequestHandler, endpoint=Endpoint())  # type: ignore[call-arg]
    built = handler_class(BaseHTTPRequestHandler, Endpoint())
    assert issubclass(built, BaseHTTPRequestHandler)
    assert built is not BaseHTTPRequestHandler


def test_the_listener_factory_has_no_default():
    """`serve` cannot be called without one, which is why no socket is opened."""
    with pytest.raises(TypeError):
        serve(Endpoint())  # type: ignore[call-arg]


# --------------------------------------------------------------------------
# The claim: a posted document is the graph gate A asserts.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", documents(), ids=rendering_id)
@pytest.mark.parametrize("spelling", ["verbatim", "trimmed", "compact"])
def test_a_posted_rendering_is_the_graph_gate_a_asserts(
    posting: Posting, path: Path, spelling: str
) -> None:
    """Gate A's comparison, reached through a socket (`SPEC.md` §4.7, §7.2).

    Three spellings of one document, because one of them is the spelling a
    `Framer.push` would pass: the corpus stores its two container renderings
    newline-terminated, and a whole newline-terminated arrival reads identically
    through `push` (`SPEC.md` §3.3). The other two are what an HTTP body
    actually looks like, and they are the ones that make this test an assertion
    about the method and not only about the plumbing.
    """
    rendering = loaded(path, second=False)
    body = spellings(rendering.data)[spelling]

    status, reply, records = posting.post(body)

    assert status == 200
    assert reply == b"{}"
    assert records.skipped_records == 0
    assert records.records, "the body produced no records at all"

    router = Router()
    for record in records.records:
        router.route(record)
    builder = router.builder(rendering.trace_id)
    assert builder is not None
    assert spanweave.dumps(builder.graph()) == rendering.graph
    # A body is not a remainder, so the framer holds nothing between requests
    # (`SPEC.md` §3.3).
    assert posting.endpoint.framer.pending_bytes == 0
    assert posting.endpoint.events == ()
    assert posting.endpoint.counts == {}


@pytest.mark.parametrize("path", documents(), ids=rendering_id)
def test_a_gzipped_body_is_inflated_and_is_the_same_graph(
    posting: Posting, path: Path
) -> None:
    """`Content-Encoding: gzip`, which is what a real exporter sends."""
    rendering = loaded(path, second=False)
    body = spellings(rendering.data)["compact"]

    status, _reply, records = posting.post(
        gzip.compress(body),
        headers={**JSON, "Content-Encoding": GZIP_ENCODING},
    )

    assert status == 200
    router = Router()
    for record in records.records:
        router.route(record)
    builder = router.builder(rendering.trace_id)
    assert builder is not None
    assert spanweave.dumps(builder.graph()) == rendering.graph


@pytest.mark.parametrize("path", documents(), ids=rendering_id)
def test_the_bodies_this_section_posts_are_bodies_a_push_would_lose(
    path: Path,
) -> None:
    """The control that keeps the test above honest (`SPEC.md` §3.3, §7.2).

    Stated at the framer, with no endpoint and no socket in it, so that the
    named mutation of §7.2 is a mutation this suite can only fail: the verbatim
    corpus body reads the same either way, and the other two spellings do not.
    A suite whose bodies were all verbatim would pass with `push` and the rule
    would be prose.
    """
    bodies = spellings(loaded(path, second=False).data)

    whole = Framer().document(bodies["verbatim"]).records
    assert len(whole) == len(Framer().push(bodies["verbatim"]).records), (
        "the premise of the trap: a newline-terminated body pushed whole reads "
        "identically, so `push` is not a method that fails"
    )

    pushed_trimmed = Framer().push(bodies["trimmed"])
    assert pushed_trimmed.records == ()
    assert pushed_trimmed.skipped_records > 0
    assert len(Framer().document(bodies["trimmed"]).records) == len(whole)

    pushed_compact = Framer().push(bodies["compact"])
    assert pushed_compact.records == ()
    assert pushed_compact.skipped_records == 0, "it read nothing and said nothing"
    assert len(Framer().document(bodies["compact"]).records) == len(whole)


# --------------------------------------------------------------------------
# One request is served, and everything else is 415.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("request_", "which"),
    [
        (Request(method="GET", target=TRACES_TARGET, body=b""), "is not POST"),
        (
            Request(method="POST", target="/v2/traces", body=b"{}"),
            "is not '/v1/traces'",
        ),
        (
            Request(
                method="POST",
                target=TRACES_TARGET,
                body=b"{}",
                content_type="application/x-protobuf",
            ),
            "not protobuf",
        ),
        (
            Request(method="POST", target=TRACES_TARGET, body=b"{}"),
            "not protobuf",
        ),
        (
            Request(
                method="POST",
                target=TRACES_TARGET,
                body=b"{}",
                content_type=JSON_MEDIA_TYPE,
                content_encoding="br",
            ),
            "cannot undo",
        ),
        (
            Request(
                method="POST",
                target=TRACES_TARGET,
                body=b"{}",
                content_type=JSON_MEDIA_TYPE,
                transfer_encoding="chunked",
            ),
            "does not unframe",
        ),
    ],
)
def test_every_request_that_is_not_the_one_served_is_415_and_says_which(
    request_, which
):
    """Five checks, one status, and the `detail` names the check (`§7.2`)."""
    endpoint = Endpoint()
    exchange = endpoint.handle(request_)
    assert exchange.response.status == 415
    assert json.loads(exchange.response.body) == {"code": UNSUPPORTED_MEDIA_TYPE}
    assert exchange.records.records == ()
    assert exchange.records.diagnostics == ()
    assert [event.code for event in exchange.events] == [UNSUPPORTED_MEDIA_TYPE]
    assert which in exchange.events[0].detail
    assert endpoint.counts == {UNSUPPORTED_MEDIA_TYPE: 1}


def test_the_media_type_is_matched_as_http_matches_it():
    """Case-insensitively, parameters dropped: HTTP's rule about its own header."""
    endpoint = Endpoint()
    for header in (
        JSON_MEDIA_TYPE,
        "Application/JSON",
        "application/json; charset=utf-8",
        "  application/json  ",
    ):
        exchange = endpoint.handle(
            Request(
                method="POST", target=TRACES_TARGET, body=b"[]", content_type=header
            )
        )
        assert exchange.response.status == 200, header
    assert endpoint.counts == {}
    # And `post`/`Post` is the same method.
    assert (
        endpoint.handle(
            Request(
                method="post",
                target=TRACES_TARGET,
                body=b"[]",
                content_type=JSON_MEDIA_TYPE,
            )
        ).response.status
        == 200
    )


def test_a_refused_request_over_the_socket_is_the_status_and_the_count(
    posting: Posting,
) -> None:
    """The same refusals, through the handler class, with a method that has no
    `do_` of its own in the stdlib base."""
    assert posting.post(b"", method="GET")[:2] == (
        415,
        b'{"code":"unsupported_media_type"}',
    )
    assert posting.post(b"{}", target="/v2/traces")[0] == 415
    assert posting.post(b"{}", method="DELETE")[0] == 415
    assert posting.endpoint.counts == {UNSUPPORTED_MEDIA_TYPE: 3}
    assert posting.endpoint.requests == 3


# --------------------------------------------------------------------------
# A body that cannot be read is 400 and an event, never a traceback.
# --------------------------------------------------------------------------


def test_a_non_json_body_is_400_with_the_receivers_event_and_no_traceback(
    posting: Posting,
) -> None:
    """The row's second test, over the socket (`SPEC.md` §7.2).

    The connection gets a status line, not a dropped socket: a traceback inside
    the handler would come back as `500` or as a closed connection, and either
    one fails these assertions.
    """
    status, reply, records = posting.post(b"not json at all, not even close")

    assert status == 400
    assert json.loads(reply) == {"code": UNREADABLE_BODY}
    assert records.records == ()
    # The reader's own diagnostics still come out: the only place those bytes
    # survive (`SPEC.md` §1.5).
    assert [d.code for d in records.diagnostics] == ["malformed_record"]
    assert records.skipped_records == 1

    (event,) = posting.endpoint.events
    assert event.code == UNREADABLE_BODY
    assert event.index == 1
    assert event.trace_id is None
    assert event.spanweave_code == "malformed_record"
    assert "1 skipped record(s)" in event.detail
    assert posting.endpoint.counts == {UNREADABLE_BODY: 1}
    # And the endpoint keeps serving: the next request is answered normally.
    assert posting.post(b"[]")[0] == 200
    assert posting.endpoint.counts == {UNREADABLE_BODY: 1}


def test_a_body_that_is_not_utf8_is_400_and_not_a_traceback(posting: Posting) -> None:
    status, _reply, records = posting.post(b"\x89PNG\r\n\x1a\n\xff\xfe")
    assert status == 400
    assert records.records == ()
    assert records.skipped_records > 0
    assert posting.endpoint.counts == {UNREADABLE_BODY: 1}


def test_a_body_that_declared_gzip_and_will_not_inflate_is_400(
    posting: Posting,
) -> None:
    """Three exception families for one fact, all of them a status.

    `b""` is deliberately **not** in the list: `gzip.decompress(b"")` is `b""`
    -- no members, so nothing to inflate -- and an empty gzipped body is
    therefore an empty body and a `200`, by the same rule an empty body is
    (`SPEC.md` §7.2). Read from the platform rather than assumed, and asserted
    below so the reading is held.
    """
    for body in (
        b"\x1f\x8b not a member",
        gzip.compress(b"[]")[:12],
        b"\x00" * 4,
        b"[]",
    ):
        status, reply, records = posting.post(
            body, headers={**JSON, "Content-Encoding": GZIP_ENCODING}
        )
        assert status == 400, body
        assert json.loads(reply) == {"code": UNREADABLE_BODY}
        assert records.records == ()
    assert posting.endpoint.counts == {UNREADABLE_BODY: 4}
    assert posting.endpoint.events[0].spanweave_code is None
    assert (
        posting.post(b"", headers={**JSON, "Content-Encoding": GZIP_ENCODING})[0] == 200
    )


def test_a_body_the_reader_read_is_200_even_when_it_held_no_record():
    """An empty body and an empty container were **read** (`SPEC.md` §7.2).

    Calling them a `400` would be the receiver deciding a body should have held
    spans, which is a judgement about what the bytes mean -- a dialect read
    (§1.1).
    """
    endpoint = Endpoint()
    for body in (b"", b"[]", b"\n"):
        exchange = endpoint.handle(
            Request(
                method="POST",
                target=TRACES_TARGET,
                body=body,
                content_type=JSON_MEDIA_TYPE,
            )
        )
        assert exchange.response.status == 200, body
        assert exchange.response.body == b"{}"
        assert exchange.records.records == ()
        assert exchange.events == ()
    assert endpoint.counts == {}


def test_a_body_with_one_readable_record_and_one_unreadable_is_200(
    posting: Posting,
) -> None:
    """It was read, and the diagnostics say what was skipped."""
    status, _reply, records = posting.post(b'{"name": "a"}\nnot json\n')
    assert status == 200
    assert len(records.records) == 1
    assert records.skipped_records == 1
    assert posting.endpoint.counts == {}


def test_handling_never_raises_for_anything_a_request_can_carry():
    """§4.4's rule one layer up: a refusal is an event, and serving continues."""
    endpoint = Endpoint()
    bodies = [b"", b"{", b"[[[", b"\xff" * 64, b"null", b"0", b'"a"', b"\x00"]
    for body in bodies:
        for content_type in (None, JSON_MEDIA_TYPE, "", "text/plain"):
            for encoding in (None, GZIP_ENCODING, "deflate"):
                exchange = endpoint.handle(
                    Request(
                        method="POST",
                        target=TRACES_TARGET,
                        body=body,
                        content_type=content_type,
                        content_encoding=encoding,
                    )
                )
                assert exchange.response.status in (200, 400, 415)
    assert endpoint.requests == len(bodies) * 4 * 3


# --------------------------------------------------------------------------
# `serve`, the listener factory, and one yield per request.
# --------------------------------------------------------------------------


def test_serve_yields_once_per_request_including_a_refusal(
    posting: Posting,
) -> None:
    """§7.1's rule for a poll that read nothing, for the same reason (§7.2)."""
    refused = posting.post(b"", method="GET")[2]
    assert refused.records == ()
    assert refused.diagnostics == ()
    assert refused.skipped_records == 0
    accepted = posting.post(b'{"name": "a"}')[2]
    assert len(accepted.records) == 1
    assert posting.endpoint.requests == 2


def test_the_listener_factory_is_called_once_and_the_listener_is_closed() -> None:
    live = Posting()
    try:
        live.post(b"[]")
        live.post(b"[]")
        assert live.factories == 1
        assert live.closed == 0
    finally:
        live.close()
    assert live.closed == 1, "the listener is closed when the iteration ends"


def test_until_is_asked_once_before_each_request_and_stops_the_loop() -> None:
    live = Posting()
    try:
        assert live.asked == 0, "the factory runs on the first `next`, not before"
        live.post(b"[]")
        assert live.asked == 1
        live.post(b"[]")
        assert live.asked == 2
        # `pending` is 0, so the next `next` stops rather than serving.
        with pytest.raises(StopIteration):
            next(live.iterator)
        assert live.asked == 3
    finally:
        live.close()
    assert live.closed == 1


def test_serve_with_no_until_is_not_asked_and_the_listener_still_closes() -> None:
    """`None` serves forever; the stop is then the caller's own iteration."""
    endpoint = Endpoint()
    closed: list[int] = []

    class Nothing:
        def handle_request(self) -> None:
            endpoint.handle(
                Request(
                    method="POST",
                    target=TRACES_TARGET,
                    body=b"[]",
                    content_type=JSON_MEDIA_TYPE,
                )
            )

        def server_close(self) -> None:
            closed.append(1)

    iterator = serve(endpoint, listener=Nothing)
    assert next(iterator).records == ()
    assert next(iterator).records == ()
    iterator.close()
    assert closed == [1]
    assert endpoint.requests == 2


def test_a_listener_that_handled_nothing_still_yields() -> None:
    """`Endpoint.last` is `None` before the first request, and the yield is
    empty rather than absent (`SPEC.md` §1.5, §7.2)."""
    endpoint = Endpoint()

    class Idle:
        def handle_request(self) -> None:
            return None

        def server_close(self) -> None:
            return None

    iterator = serve(endpoint, listener=Idle)
    assert next(iterator) == spanweave.Records(
        records=(), diagnostics=(), skipped_records=0
    )
    assert endpoint.last is None
    iterator.close()


# --------------------------------------------------------------------------
# `respond`: the one layer that touches a stream.
# --------------------------------------------------------------------------


class FakeHandler:
    """A `BaseHTTPRequestHandler`-shaped object, for the header edge cases.

    The real class is driven over a real socket everywhere else in this file;
    this is for the three header spellings a client is not obliged to send.
    """

    def __init__(self, headers: dict[str, str], body: bytes) -> None:
        import io

        self.command = "POST"
        self.path = TRACES_TARGET
        self.headers = headers
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.sent: list[Any] = []

    def send_response(self, code: int, message: str | None = None) -> None:
        self.sent.append(("status", code))

    def send_header(self, keyword: str, value: str) -> None:
        self.sent.append((keyword, value))

    def end_headers(self) -> None:
        self.sent.append(("end", None))


def test_respond_reads_content_length_bytes_and_writes_the_response():
    endpoint = Endpoint()
    handler = FakeHandler({"Content-Length": "13", **JSON}, b'{"name": "a"}trailing')
    exchange = respond(handler, endpoint)  # type: ignore[arg-type]
    assert exchange.response.status == 200
    assert len(exchange.records.records) == 1
    assert handler.wfile.getvalue() == b"{}"
    assert handler.sent == [
        ("status", 200),
        ("Content-Type", JSON_MEDIA_TYPE),
        ("Content-Length", "2"),
        ("end", None),
    ]


@pytest.mark.parametrize("length", [None, "", "not a number", "-5"])
def test_a_content_length_that_is_not_a_number_is_no_body_and_not_a_traceback(length):
    """A malformed header is a status, as a malformed body is (`SPEC.md` §7.2)."""
    headers = dict(JSON) if length is None else {"Content-Length": length, **JSON}
    handler = FakeHandler(headers, b'{"name": "a"}')
    exchange = respond(handler, Endpoint())  # type: ignore[arg-type]
    assert exchange.response.status == 200
    assert exchange.records.records == ()


# --------------------------------------------------------------------------
# The seams, and the allowlist.
# --------------------------------------------------------------------------


def test_the_endpoint_needs_no_entry_in_the_seam_allowlist() -> None:
    """R6's seam question, asserted rather than asserted-about.

    R0 predicted that R6's listener would be the entry the allowlist finally
    needed, as it predicted R3's clock and R5's sleep. All three were wrong, and
    for the same reason: the handler's base class and the listener factory are
    parameters with **no defaults**, so no module under `spanweave_live/`
    imports `http`, `socketserver` or `socket` (`SPEC.md` §1.4, §7.2). R7's CLI
    is where `import http.server` finally appears.
    """
    source = gates.PACKAGE_ROOT / "endpoint.py"
    assert source.exists()
    assert (
        gates.check_source(
            f"spanweave_live/{source.name}",
            source.read_text(encoding="utf-8"),
            gates.ALL_RULES,
        )
        == []
    )
    assert gates.SEAMS == {}, "R6 added no seam file: the caller supplies the socket"


def test_the_endpoint_events_are_routings_event_and_carry_no_new_field() -> None:
    """One `Event` type for the layers above framing (`SPEC.md` §3.1, §7.1).

    R6 added **no** field, unlike R3 (`seconds`), R4 (`version`), R5 (`offset`)
    and R3a (`at`): a `415` and a `400` are about a request, and `index`,
    `spanweave_code` and `detail` are the three facts they have. The HTTP status
    is on the `Response` beside them, which is the one place it is not `None`
    for every other code.
    """
    assert [field.name for field in dataclasses.fields(Event)] == [
        "code",
        "index",
        "trace_id",
        "spanweave_code",
        "detail",
        "seconds",
        "version",
        "offset",
        "at",
    ]
    endpoint = Endpoint()
    endpoint.handle(Request(method="GET", target=TRACES_TARGET, body=b""))
    (event,) = endpoint.events
    assert (event.seconds, event.version, event.offset, event.at) == (
        None,
        None,
        None,
        None,
    )


def test_the_endpoint_binds_no_port_of_its_own(posting: Posting) -> None:
    """The kernel chose it, which is why no number appears in this file."""
    host, port = posting.address
    assert host == "127.0.0.1"
    # The kernel's answer: a port the test never named. `Posting` asks for 0.
    assert port > 0
    source = Path(__file__).read_text(encoding="utf-8")
    assert '("127.0.0.1", 0)' in source


def test_the_endpoint_is_deterministic_for_identical_requests() -> None:
    """Same bytes in, same bytes out, including the response (`CLAUDE.md` 8)."""
    path = documents()[0]
    body = spellings(loaded(path, second=False).data)["compact"]
    answers = []
    for _ in range(3):
        endpoint = Endpoint()
        exchange = endpoint.handle(
            Request(
                method="POST",
                target=TRACES_TARGET,
                body=body,
                content_type=JSON_MEDIA_TYPE,
            )
        )
        router = Router()
        for record in exchange.records.records:
            router.route(record)
        builder = router.builder(loaded(path, second=False).trace_id)
        assert builder is not None
        answers.append((exchange.response, spanweave.dumps(builder.graph())))
    assert answers[0] == answers[1] == answers[2]
