"""The CLI, as a process (`SPEC.md` §8).

Every test here runs `spanweave-live` through `subprocess`, never by calling
`main` in-process: an in-process call tests the functions and this section's
claim is about the thing a human runs — its files, its two streams and its exit
status. The one exception is the parser, which is read rather than run so that
§8.1's usage block can be held against it flag by flag.

The central test is **gate A's comparison reached through a process**: every
line-delimited corpus rendering piped to `spanweave-live tail - --out <dir>`,
and the `<trace_id>.json` the run leaves behind compared byte for byte with
`spanweave.dumps` of `spanweave.build` of that rendering, using gate A's own
loader and comparison (`SPEC.md` §4.7). The two OTLP documents go the same way
through `serve`. A second loader or a second comparison here would be a weaker
gate wearing the same name.

**Nothing in this file waits on a clock.** The three ingests each give the stop
away for free: stdin's EOF is end of input, `--poll-seconds 0` leaves a tail's
one trailing poll nothing to wait out, and `--port 0` with the `listening` line
means no port is ever written down. Where a test needs the process to have
reached somewhere before it acts, the barrier is a **read** — the `listening`
line on stderr, a delta line on stdout — and never a sleep.
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import http.client
import json
import pathlib
import re
import signal
import subprocess
import sys

import pytest
import spanweave

from spanweave_live import cli
from tests import gates

# Gate A's own corpus helpers and its comparison, imported rather than
# reimplemented (`SPEC.md` §4.7, §8.7).
from tests.test_conformance import loaded, rendering_id, renderings, undigested

REPO = pathlib.Path(__file__).resolve().parent.parent

#: How the CLI is started. `-m` rather than the installed console script so the
#: test runs the source tree it is in; `make install-check` is what proves the
#: console script a wheel ships (`CLAUDE.md`, Commands).
CLI = (sys.executable, "-m", "spanweave_live.cli")

#: A rendering with more than one line, named rather than "the first one with
#: enough lines", so a corpus change moves the test instead of quietly changing
#: what it feeds. Four records, one trace.
MULTI = "llm_tool_llm/openinference.jsonl"


def jsonl() -> list[pathlib.Path]:
    return [path for path in renderings() if path.suffix == ".jsonl"]


def documents() -> list[pathlib.Path]:
    return [path for path in renderings() if path.suffix == ".json"]


def by_id(wanted: str) -> pathlib.Path:
    for path in renderings():
        if rendering_id(path) == wanted:
            return path
    raise AssertionError(f"the corpus no longer holds {wanted}")


def run(
    *args: str, stdin: bytes = b"", timeout: float = 120.0
) -> subprocess.CompletedProcess[bytes]:
    """One CLI run to completion. No `shell`, no environment of its own."""
    return subprocess.run(
        [*CLI, *args],
        input=stdin,
        capture_output=True,
        cwd=REPO,
        timeout=timeout,
        check=False,
    )


def lines(stderr: bytes) -> list[dict[str, object]]:
    """Every stderr line, parsed. Each must be one JSON object (`§8.3`)."""
    out: list[dict[str, object]] = []
    for raw in stderr.decode("utf-8").splitlines():
        assert raw.strip(), "a blank line on stderr says nothing and is not an event"
        parsed = json.loads(raw)
        assert isinstance(parsed, dict), raw
        out.append(parsed)
    return out


def codes(stderr: bytes) -> list[str]:
    return [str(line["code"]) for line in lines(stderr)]


def only(stderr: bytes, code: str) -> dict[str, object]:
    found = [line for line in lines(stderr) if line["code"] == code]
    assert len(found) == 1, f"{len(found)} lines of code {code!r}: {found}"
    return found[0]


def expected_graph(data: bytes) -> bytes:
    """What `spanweave.build` of these bytes serializes to (gate A's answer)."""
    return spanweave.dumps(undigested(spanweave.build(data)))


# --------------------------------------------------------------------------
# §8.1 — the usage block is the parser.
# --------------------------------------------------------------------------


def declared_usage() -> dict[str, set[str]]:
    """§8.1's usage block, parsed: command -> the flags it declares.

    The spec's own text, read rather than paraphrased, as
    `tests/test_routing.py::declared_fields` reads §4.1's dataclasses (R5a, F5).
    """
    spec = (REPO / "SPEC.md").read_text(encoding="utf-8")
    start = spec.index("### 8.1 ")
    end = spec.index("\n### ", start + 1)
    block = spec[start:end]
    fence = block.index("```text") + len("```text")
    usage = block[fence : block.index("```", fence)]
    declared: dict[str, set[str]] = {}
    for paragraph in usage.strip().split("\n\n"):
        command = paragraph.split()[1]
        declared[command] = set(re.findall(r"--[a-z][a-z-]*", paragraph))
    return declared


def parser_flags() -> dict[str, set[str]]:
    """The flags the parser really has, per subcommand.

    `argparse` keeps its subparsers in a private action, and reaching for it is
    deliberate: the alternative is a second list of flags in the code for a
    test to read, which is the drift this test exists to catch.
    """
    found: dict[str, set[str]] = {}
    for action in cli.build_parser()._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                found[name] = {
                    option
                    for child in sub._actions
                    for option in child.option_strings
                    if option.startswith("--") and option != "--help"
                }
    return found


def test_the_usage_block_in_SPEC_is_the_parser_the_code_has() -> None:
    """§8.1 says it is the whole surface. Held, in both directions.

    A flag built and not written down is a surface this document does not
    describe; a flag written down and not built is a promise. The two sets are
    compared per command, so `--once` on `serve` or `--port` on `tail` fails.
    """
    assert declared_usage() == parser_flags()


def test_the_two_commands_are_the_two_SPEC_declares() -> None:
    assert sorted(parser_flags()) == ["serve", "tail"]


# --------------------------------------------------------------------------
# §8.7 — gate A's comparison, reached through a process.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", jsonl(), ids=rendering_id)
def test_a_rendering_piped_to_tail_is_written_as_gate_As_graph(path, tmp_path) -> None:
    """The central test: `<trace_id>.json` is the batch graph, byte for byte.

    stdin, so there is no clock in it at all: EOF is end of input (`§7.1`), the
    CLI's final tick completes the trace that is still open (`§8.5`), and the
    file is `spanweave.dump` of the graph the records built (`§5.4`).
    """
    rendering = loaded(path, second=False)
    out = tmp_path / "out"
    result = run("tail", "-", "--out", str(out), stdin=rendering.data)
    assert result.returncode == 0, result.stderr.decode()
    written = out / f"{rendering.trace_id}.json"
    assert written.read_bytes() == rendering.graph
    assert sorted(p.name for p in out.iterdir()) == [written.name]


@pytest.mark.parametrize("path", documents(), ids=rendering_id)
def test_a_document_posted_to_serve_is_written_as_gate_As_graph(path, tmp_path) -> None:
    """The same comparison through a socket the CLI bound itself (`§7.2`).

    `--port 0` and the `listening` line: the kernel chooses the port and the
    CLI says which, so nothing here is written down and nothing is retried.
    """
    rendering = loaded(path, second=False)
    out = tmp_path / "out"
    with serving("--out", str(out), "--requests", "1") as server:
        status, _ = server.post(rendering.data)
    assert status == 200
    assert server.returncode == 0, server.stderr.decode()
    written = out / f"{rendering.trace_id}.json"
    assert written.read_bytes() == rendering.graph


class serving:
    """`spanweave-live serve --port 0`, with the bound port read off stderr.

    The barrier is a **read**: `__enter__` blocks on stderr until the
    `listening` line arrives, so a POST is never written to a socket that is
    not bound yet and no test sleeps to find out (`§8.3`, `§8.7`).
    """

    def __init__(self, *args: str) -> None:
        self.args = args
        self.host = ""
        self.port = 0
        self.stderr = b""
        self.stdout = b""
        self.returncode: int | None = None

    def __enter__(self) -> serving:
        self.process = subprocess.Popen(
            [*CLI, "serve", "--port", "0", *self.args],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=REPO,
        )
        assert self.process.stderr is not None
        self.prologue: list[dict[str, object]] = []
        while True:
            raw = self.process.stderr.readline()
            assert raw, "the process ended before it said it was listening"
            line = json.loads(raw.decode("utf-8"))
            self.prologue.append(line)
            if line["code"] == "listening":
                assert line["layer"] == "cli"
                self.host, self.port = str(line["host"]), int(str(line["port"]))
                assert self.port > 0, "port 0 was reported rather than the bound one"
                return self

    def post(
        self,
        body: bytes,
        content_type: str = "application/json",
        target: str = "/v1/traces",
    ) -> tuple[int, bytes]:
        connection = http.client.HTTPConnection(self.host, self.port)
        try:
            connection.request("POST", target, body, {"Content-Type": content_type})
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def __exit__(self, *_: object) -> None:
        self.stdout, rest = self.process.communicate(timeout=120)
        self.stderr = (
            b"".join(json.dumps(line).encode() + b"\n" for line in self.prologue) + rest
        )
        self.returncode = self.process.returncode

    def lines(self) -> list[dict[str, object]]:
        return lines(self.stderr)


# --------------------------------------------------------------------------
# §8.3 — events on stderr, one JSON line each.
# --------------------------------------------------------------------------


def test_every_event_reaches_stderr_as_one_json_line_with_its_code(tmp_path) -> None:
    """A refusal is an event with a code, and the line is one line (`§1.5`).

    The same record is POSTed **twice**, which is two `document` calls and
    therefore two reads: the reader deduplicates per call and not across calls
    (`§2.2`), so the second arrival reaches the builder and is `refused` with
    the library's own code (`§4.4`). None of it is a failure, so the run still
    exits 0 (`§8.6`).
    """
    body = by_id(MULTI).read_bytes().splitlines(keepends=True)[0]
    out = tmp_path / "out"
    with serving("--out", str(out), "--requests", "2") as server:
        assert server.post(body)[0] == 200
        assert server.post(body)[0] == 200
    assert server.returncode == 0, server.stderr.decode()
    reported = server.lines()
    for line in reported:
        assert set(line) >= {"code", "layer"}, line
        assert None not in line.values(), f"a null field is a field left in: {line}"
    refusal = only(server.stderr, "refused")
    assert refusal["layer"] == "router"
    assert refusal["trace_id"] == "t1"
    assert refusal["spanweave_code"]
    assert refusal["index"] == 2
    said = [str(line["code"]) for line in reported]
    assert said.count("completed") == 1
    assert said.count("written") == 1


def test_a_duplicate_within_one_read_is_the_readers_answer_and_not_a_refusal(
    tmp_path,
) -> None:
    """The other half of §2.2, reached through the CLI.

    The same rendering piped twice arrives as **one** read, so the reader drops
    the second copy itself and says `duplicate_record`; the router never sees it
    and there is nothing to refuse. The two tests together are why a `refused`
    count is a fact about arrivals and not about bytes.
    """
    rendering = loaded(by_id(MULTI), second=False)
    out = tmp_path / "out"
    result = run("tail", "-", "--out", str(out), stdin=rendering.data * 2)
    assert result.returncode == 0, result.stderr.decode()
    said = codes(result.stderr)
    assert "refused" not in said
    assert said.count("duplicate_record") == 4
    assert (out / f"{rendering.trace_id}.json").read_bytes() == rendering.graph


def test_finished_is_the_last_line_and_carries_the_counts(tmp_path) -> None:
    rendering = loaded(by_id(MULTI), second=False)
    out = tmp_path / "out"
    result = run("tail", "-", "--out", str(out), stdin=rendering.data)
    last = lines(result.stderr)[-1]
    assert last["code"] == "finished"
    assert last["layer"] == "cli"
    assert last["exit"] == 0
    assert last["routed"] == 4
    counts = last["counts"]
    assert isinstance(counts, dict)
    assert counts == {"completed": 1, "released": 1, "written": 1}
    assert codes(result.stderr).count("finished") == 1


def test_the_cli_codes_and_layers_are_the_ones_SPEC_names() -> None:
    """§8.3's two lists, held against the module (`SPEC.md` §8.3).

    The seven things the process says about itself are a table in the spec and
    seven constants here, and the six layers are a sentence there and six
    constants here. A code added to the code and not to §8.3 is an event a
    reader of this project has no account of, which is what §1.5 is about.
    """
    spec = (REPO / "SPEC.md").read_text(encoding="utf-8")
    section = spec[spec.index("### 8.3 ") : spec.index("### 8.4 ")]
    declared = [
        found.group(1)
        for row in section.splitlines()
        if (found := re.match(r"\| `([a-z_]+)` \|", row)) is not None
    ]
    constants = {
        cli.LISTENING,
        cli.START_FAILED,
        cli.LINE_NUMBERS_DIVERGED,
        cli.MAY_OVERWRITE,
        cli.PENDING,
        cli.INTERRUPTED,
        cli.FINISHED,
    }
    assert sorted(declared) == sorted(constants)
    assert len(constants) == 7
    layers = {cli.INGEST, cli.FRAMER, cli.READER, cli.ENDPOINT, cli.ROUTER, cli.CLI}
    assert len(layers) == 6
    for layer in layers:
        assert f"`{layer}`" in section, layer


def test_a_framing_events_line_number_is_named_as_the_framers_count(tmp_path) -> None:
    """R2b's consequence, honoured where a human reads it (`§3.4`, `§8.3`).

    The input is 70,000 bytes with **no newline in it at all**, so it holds
    zero lines — and with `--max-pending-bytes 64` the framer cuts the
    remainder loose twice and numbers the two fragments as lines 1 and 2. A key
    spelled `line` would be read as the input's line, which does not exist, so
    the key is `framer_line` and the run says `line_numbers_diverged` once.
    """
    out = tmp_path / "out"
    result = run(
        "tail", "-", "--out", str(out), "--max-pending-bytes", "64", stdin=b"x" * 70_000
    )
    assert result.returncode == 0, result.stderr.decode()
    framing = [line for line in lines(result.stderr) if line["layer"] == "framer"]
    assert [line["code"] for line in framing] == ["fragment_too_long"] * 2
    assert [line["framer_line"] for line in framing] == [1, 2]
    for line in framing:
        assert "line" not in line, (
            "a `line` key would be read as the input's line number, and after a "
            "cut it is the framer's count of lines handed over (SPEC.md §3.4)"
        )
        assert line["length"] > 64
    notice = only(result.stderr, "line_numbers_diverged")
    assert notice["layer"] == "cli"
    # And the premise is held rather than assumed, which is R2's and R6's
    # lesson twice over: the **corpus cannot reach this code at all**. Every
    # rendering's lines end in `\n`, so the remainder after a push is empty and
    # the cap never bites — a suite whose only inputs were the corpus' own bytes
    # would have left the renaming above untested and green.
    unbitten = run(
        "tail",
        "-",
        "--out",
        str(tmp_path / "corpus-out"),
        "--max-pending-bytes",
        "64",
        stdin=loaded(by_id(MULTI), second=False).data,
    )
    assert unbitten.returncode == 0, unbitten.stderr.decode()
    assert "fragment_too_long" not in codes(unbitten.stderr)
    assert "line_numbers_diverged" not in codes(unbitten.stderr)
    # And the divergence is real: the reader is numbering lines of an input
    # that has none.
    messages = [
        str(line["message"])
        for line in lines(result.stderr)
        if line["layer"] == "reader"
    ]
    assert any(message.startswith("line 1 ") for message in messages), messages
    assert any(message.startswith("line 2 ") for message in messages), messages


def test_a_reader_diagnostic_reaches_stderr_under_the_librarys_own_field_names(
    tmp_path,
) -> None:
    """The library's text verbatim: the only place a skipped line survives."""
    out = tmp_path / "out"
    result = run("tail", "-", "--out", str(out), stdin=b"{not json}\n")
    assert result.returncode == 0, result.stderr.decode()
    reader = [line for line in lines(result.stderr) if line["layer"] == "reader"]
    assert len(reader) == 1
    assert set(reader[0]) >= {"code", "layer", "message", "level"}
    assert reader[0]["message"].startswith("line 1 ")  # type: ignore[union-attr]


# --------------------------------------------------------------------------
# §8.4 — deltas on stdout.
# --------------------------------------------------------------------------


def test_deltas_are_one_document_per_line_and_cover_every_record(tmp_path) -> None:
    """One line per absorbed record, each the library's own canonical bytes.

    The windows are contiguous and the last one's `until` is the version the
    graph was written at, so the lines account for every record of the trace.
    That is **not** §6.6's fold, which folds `Delta` values onto a graph and is
    `tests/test_subscriptions.py`' test; what is held here is the CLI's half —
    one line per record, nothing wrapped around it, and the line is the
    document.
    """
    rendering = loaded(by_id(MULTI), second=False)
    out = tmp_path / "out"
    result = run("tail", "-", "--out", str(out), "--deltas", stdin=rendering.data)
    assert result.returncode == 0, result.stderr.decode()
    raw = result.stdout.splitlines(keepends=True)
    assert len(raw) == 4, result.stdout
    deltas = [json.loads(line) for line in raw]
    assert [delta["since"] for delta in deltas] == [0, 1, 2, 3]
    assert [delta["until"] for delta in deltas] == [1, 2, 3, 4]
    assert {delta["trace_id_after"] for delta in deltas} == {rendering.trace_id}
    assert all(delta["kind"] == "delta" for delta in deltas)
    # stdout is deltas and nothing else: no event ever reached it.
    assert all("code" not in delta for delta in deltas)


def test_without_deltas_stdout_is_empty(tmp_path) -> None:
    rendering = loaded(by_id(MULTI), second=False)
    out = tmp_path / "out"
    result = run("tail", "-", "--out", str(out), stdin=rendering.data)
    assert result.stdout == b""
    assert "consumer_error" not in codes(result.stderr)


# --------------------------------------------------------------------------
# §8.5 — the tick, the final tick, and the file a bound can lose.
# --------------------------------------------------------------------------


def test_the_input_ending_completes_every_trace_still_held_with_cap_zero(
    tmp_path,
) -> None:
    """No policy at all, and the graph is still written (`§8.5`).

    The policy on the `completed` event is `Cap(records=0)`, which is the honest
    report: it completed because the input ended.
    """
    rendering = loaded(by_id(MULTI), second=False)
    out = tmp_path / "out"
    result = run("tail", "-", "--out", str(out), stdin=rendering.data)
    completed = only(result.stderr, "completed")
    assert "Cap(records=0)" in str(completed["detail"])
    assert (out / f"{rendering.trace_id}.json").read_bytes() == rendering.graph


def test_forgetting_a_completion_writes_the_second_file_over_the_first(
    tmp_path,
) -> None:
    """R3a's consequence, surfaced to a human (`§5.5`, `§8.5`).

    Two POSTs of two records of **one** trace, with `--cap 1` so each completes
    on its own request's tick and `--max-completed 0` so the completion is
    forgotten in the tick that made it. The second generation therefore has no
    generation number to carry and is written as `<trace_id>.json` **over** the
    first — which is why the CLI says `may_overwrite` the first time it sees a
    `forgotten` with `--out` set.
    """
    data = by_id(MULTI).read_bytes()
    first, second = data.splitlines(keepends=True)[:2]
    out = tmp_path / "out"
    with serving(
        "--out", str(out), "--requests", "2", "--cap", "1", "--max-completed", "0"
    ) as server:
        assert server.post(first)[0] == 200
        assert server.post(second)[0] == 200
    assert server.returncode == 0, server.stderr.decode()
    reported = server.lines()
    said = [str(line["code"]) for line in reported]
    assert said.count("forgotten") == 2
    assert said.count("written") == 2
    assert said.count("may_overwrite") == 1, "once per run, not once per id (§4.6)"
    assert "late_arrival" not in said, "a forgotten id is a first sighting (§5.5)"
    written = [line for line in reported if line["code"] == "written"]
    assert written[0]["detail"] == written[1]["detail"], "two generations, one name"
    # The file is the SECOND generation's graph: the first was written over.
    graph = (out / "t1.json").read_bytes()
    assert graph == expected_graph(second)
    assert graph != expected_graph(first)
    assert sorted(p.name for p in out.iterdir()) == ["t1.json"]
    notice = only(server.stderr, "may_overwrite")
    assert "OVER" in str(notice["detail"])
    assert notice["trace_id"] == "t1"


def test_the_default_remembers_every_completion_and_writes_a_second_generation(
    tmp_path,
) -> None:
    """The other side of the same trade: with no bound, nothing is lost."""
    data = by_id(MULTI).read_bytes()
    first, second = data.splitlines(keepends=True)[:2]
    out = tmp_path / "out"
    with serving("--out", str(out), "--requests", "2", "--cap", "1") as server:
        assert server.post(first)[0] == 200
        assert server.post(second)[0] == 200
    said = [str(line["code"]) for line in server.lines()]
    assert "forgotten" not in said
    assert "may_overwrite" not in said
    assert said.count("late_arrival") == 1
    assert sorted(p.name for p in out.iterdir()) == ["t1.2.json", "t1.json"]
    assert (out / "t1.json").read_bytes() == expected_graph(first)
    assert (out / "t1.2.json").read_bytes() == expected_graph(second)


def test_tail_of_a_file_once_drains_it_flushes_and_stops(tmp_path) -> None:
    """The file path, with `--poll-seconds 0` so the trailing poll waits for
    nothing, and a last line with no terminator so the flush is what reads it.
    """
    rendering = loaded(by_id(MULTI), second=False)
    source = tmp_path / "app.jsonl"
    source.write_bytes(rendering.data.rstrip(b"\n"))
    out = tmp_path / "out"
    result = run(
        "tail", str(source), "--out", str(out), "--once", "--poll-seconds", "0"
    )
    assert result.returncode == 0, result.stderr.decode()
    assert (out / f"{rendering.trace_id}.json").read_bytes() == rendering.graph
    assert "pending" not in codes(result.stderr)


# --------------------------------------------------------------------------
# §8.6 — exit codes.
# --------------------------------------------------------------------------


def test_a_usage_error_is_exit_2() -> None:
    assert run("tail", "-", "--no-such-flag").returncode == 2
    assert run("tail").returncode == 2
    assert run("serve", "--out", "x").returncode == 2


def test_a_path_that_will_not_open_is_exit_1_and_says_so(tmp_path) -> None:
    result = run("tail", str(tmp_path / "absent.jsonl"), "--out", str(tmp_path / "o"))
    assert result.returncode == 1
    failed = only(result.stderr, "start_failed")
    assert failed["layer"] == "cli"
    assert lines(result.stderr)[-1]["exit"] == 1


def test_a_socket_that_will_not_bind_is_exit_1_and_says_so(tmp_path) -> None:
    """A TEST-NET-3 address (RFC 5737) is not local, so the bind cannot work."""
    result = run(
        "serve", "--port", "0", "--host", "203.0.113.1", "--out", str(tmp_path / "o")
    )
    assert result.returncode == 1
    assert only(result.stderr, "start_failed")["layer"] == "cli"
    assert "listening" not in codes(result.stderr)


def test_a_graph_that_could_not_be_written_is_exit_3(tmp_path) -> None:
    """`--out` is an existing file, so the directory cannot be made.

    The run still finishes — a receiver that died on one unwritable file would
    lose every other trace it was holding (`§5.4`) — and the exit code is what
    says something it had was not delivered.
    """
    rendering = loaded(by_id(MULTI), second=False)
    blocked = tmp_path / "not-a-dir"
    blocked.write_bytes(b"")
    result = run("tail", "-", "--out", str(blocked), stdin=rendering.data)
    assert result.returncode == 3, result.stderr.decode()
    assert only(result.stderr, "not_written")["layer"] == "router"
    assert "completed" in codes(result.stderr)
    assert lines(result.stderr)[-1]["exit"] == 3


def test_a_refused_body_is_an_observation_and_the_run_exits_0(tmp_path) -> None:
    """A `415` and a `400` are what the endpoint saw, not what it could not do."""
    out = tmp_path / "out"
    with serving("--out", str(out), "--requests", "2") as server:
        assert server.post(b"{}", content_type="text/plain")[0] == 415
        assert server.post(b"{nonsense}")[0] == 400
    assert server.returncode == 0, server.stderr.decode()
    said = [str(line["code"]) for line in server.lines()]
    assert "unsupported_media_type" in said
    assert "unreadable_body" in said
    assert not out.exists(), "nothing completed, so no directory was made"


def test_an_interrupt_is_exit_130_and_leaves_what_was_written(tmp_path) -> None:
    """`SIGINT` while following forever (`§8.6`).

    The barrier is a read: the delta line on stdout proves the process is past
    its first poll, so the signal is never raced against startup. Nothing is
    ticked on the way out, so the trace that was open leaves no file.
    """
    rendering = loaded(by_id(MULTI), second=False)
    source = tmp_path / "app.jsonl"
    source.write_bytes(rendering.data)
    out = tmp_path / "out"
    process = subprocess.Popen(
        [
            *CLI,
            "tail",
            str(source),
            "--out",
            str(out),
            "--deltas",
            "--poll-seconds",
            "0.01",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=REPO,
    )
    assert process.stdout is not None
    assert process.stdout.readline(), "no delta before the interrupt"
    process.send_signal(signal.SIGINT)
    _, stderr = process.communicate(timeout=120)
    assert process.returncode == 130, stderr.decode()
    said = [str(line["code"]) for line in lines(stderr)]
    assert said.count("interrupted") == 1
    assert "completed" not in said, "a signal is not end of input (§8.6)"
    assert not out.exists() or list(out.iterdir()) == []
    assert lines(stderr)[-1]["exit"] == 130


# --------------------------------------------------------------------------
# §8.2 — the one seam, and the blast radius of the one allowlist entry.
# --------------------------------------------------------------------------


def unexempted(source: str, name: str) -> list[gates.Violation]:
    """Every rule run over `source` with an **empty** allowlist.

    The rules take their own `seams`, so this asks what the gate would say
    about a file nothing exempts -- which is the question both tests below are
    about, and it needs no new function in `tests/gates.py`.
    """
    tree = ast.parse(source, filename=name)
    return [
        violation
        for rule in gates.ALL_RULES
        for violation in rule(f"spanweave_live/{name}", source, tree, seams={})
    ]


def test_the_seam_allowlist_names_one_file_and_two_modules() -> None:
    """The project's first allowlist entry, written down here as well (`§8.2`).

    R0 predicted it for R3's clock, R5's `sleep` and R6's listener, and all
    three declined it because each seam was a parameter with no default. R7 is
    the caller those three were deferring to: something has to pass the real
    `time.monotonic`, the real `time.sleep` and a real `HTTPServer`, and a
    process has no caller to take them from.
    """
    assert dict(gates.SEAMS) == {"real.py": frozenset({"time", "http.server"})}


def test_the_exempted_file_is_the_binding_module_and_not_the_cli() -> None:
    """The entry exempts a whole file, so the file is as small as it can be.

    `cli.py` is where a stray `time.monotonic()` could actually hide, so it
    stays under the gate unexempted; `real.py` does nothing but hand back the
    real thing.
    """
    source = (gates.PACKAGE_ROOT / "real.py").read_text(encoding="utf-8")
    assert (
        gates.check_source("spanweave_live/real.py", source, gates.ALL_RULES) == []
    ), "the seam entry is what makes the binding module legal"
    assert {violation.rule for violation in unexempted(source, "real.py")} == {
        "no-ambient-runtime",
        "no-network",
    }, "without its entry the binding module breaks both module rules"
    assert len(source.splitlines()) < 60, (
        "an allowlist entry exempts the whole file, so the exempted file stays "
        "small enough to read in one go (SPEC.md §8.2)"
    )


def test_the_cli_itself_imports_no_clock_and_no_socket() -> None:
    source = (gates.PACKAGE_ROOT / "cli.py").read_text(encoding="utf-8")
    assert "real.py" in gates.SEAMS and "cli.py" not in gates.SEAMS
    assert unexempted(source, "cli.py") == []


def test_the_binding_module_is_not_public_api() -> None:
    """`real.py` is what a process binds at its edge, not API (`§8.2`)."""
    import spanweave_live

    assert "real" not in spanweave_live.__all__
    assert not hasattr(spanweave_live, "monotonic")


def test_the_binding_module_binds_the_real_things() -> None:
    """The four names, each the real one. Read in-process, which is the point
    of their being in one file: nothing else in the package can be asked this.
    """
    import http.server
    import time

    from spanweave_live import real

    assert real.monotonic is time.monotonic
    assert real.sleep is time.sleep
    assert real.HTTP_HANDLER_BASE is http.server.BaseHTTPRequestHandler


# --------------------------------------------------------------------------
# Pre-1.0 is said in the one place a tool reads it.
# --------------------------------------------------------------------------


def unwrapped(stdout: bytes) -> str:
    """`argparse` wraps its text, so a phrase is matched with the wrap undone."""
    return " ".join(stdout.decode("utf-8").lower().split())


def test_version_and_help_both_say_nothing_is_frozen() -> None:
    version = run("--version")
    assert version.returncode == 0
    assert "nothing is frozen" in unwrapped(version.stdout)
    for argv in (("--help",), ("tail", "--help"), ("serve", "--help")):
        helped = run(*argv)
        assert helped.returncode == 0
        assert "nothing is frozen" in unwrapped(helped.stdout), argv


def test_the_max_completed_help_states_the_overwrite(tmp_path) -> None:
    """R3a's consequence, where a human reads it first (`§8.5`)."""
    for command in ("tail", "serve"):
        text = unwrapped(run(command, "--help").stdout)
        assert "--max-completed" in text
        assert "writes <trace_id>.json over the file" in text, text
        assert "loses its generation" in text


def test_dataclasses_are_not_reinvented_for_the_cli() -> None:
    """The CLI reports the receiver's own values; it declares none of its own.

    A dataclass here would be a second name for a routing `Event` or a
    `FramingEvent` (`SPEC.md` §3.1, §4.1), which is what §8 says it does not
    add.
    """
    declared = [
        name
        for name, value in vars(cli).items()
        if dataclasses.is_dataclass(value)
        and getattr(value, "__module__", "") == cli.__name__
    ]
    assert declared == []
