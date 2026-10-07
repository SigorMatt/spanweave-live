"""The gate, watched failing.

The gate is asserted twice: once against a **planted violation** -- a synthetic
module that deliberately breaks it -- and once against the real package. The
first assertion is the one that matters. A gate that has only ever been seen
passing is indistinguishable from a gate that cannot fail.

Rule implementations live in `tests/gates.py`.
"""

import ast
from pathlib import Path

import pytest

from tests import gates

# Every banned module, in both import forms, because a rule that catches
# `import time` and misses `from time import monotonic` catches nothing.
PLANTED_AMBIENT = [
    ("import time", "time"),
    ("from time import monotonic", "time"),
    ("import datetime", "datetime"),
    ("from datetime import datetime, timezone", "datetime"),
    ("import random", "random"),
    ("from random import Random", "random"),
    ("import socket", "socket"),
    ("from socket import socket as sock", "socket"),
    ("import threading", "threading"),
    ("from threading import Thread", "threading"),
    ("import asyncio", "asyncio"),
    ("from asyncio import sleep", "asyncio"),
    ("import asyncio.subprocess", "asyncio"),
    # The modules the run-2 review verified were *not* caught while the gate
    # was advertised as proving "no module reads a clock"
    # (`reviews/2026-10-06-run2.md` F7). Each is the same ambient runtime
    # under another name: `secrets` and `uuid` are unseeded randomness
    # (`CLAUDE.md` 8), and the last five are concurrency or a child process
    # that no fixture can pin (`CLAUDE.md` 4).
    ("import secrets", "secrets"),
    ("from secrets import token_hex", "secrets"),
    ("import uuid", "uuid"),
    ("from uuid import uuid4", "uuid"),
    ("import concurrent.futures", "concurrent.futures"),
    ("from concurrent.futures import ThreadPoolExecutor", "concurrent.futures"),
    ("import selectors", "selectors"),
    ("import select", "select"),
    ("import subprocess", "subprocess"),
    ("from subprocess import run", "subprocess"),
    ("import sched", "sched"),
]

# The network, which this package does not reach for and had nothing stopping
# it reaching for: `socket` was banned, so the direct form was caught and every
# library that opens a connection for you was not (F8). The parent `spanweave`
# repository has had this gate since its own R0 (`CLAUDE.md` there, "No network
# imports in core"); R6 opens an HTTP endpoint, which is exactly when a
# receiver grows the import that makes "read-only toward the observed system"
# (`CLAUDE.md` 9) a sentence rather than a fact.
PLANTED_NETWORK = [
    ("import urllib.request", "urllib"),
    ("from urllib.request import urlopen", "urllib"),
    ("import http.client", "http"),
    ("from http.client import HTTPConnection", "http"),
    ("import http.server", "http"),
    ("import socketserver", "socketserver"),
    ("import requests", "requests"),
    ("import httpx", "httpx"),
    ("import ftplib", "ftplib"),
    ("import smtplib", "smtplib"),
    ("import ssl", "ssl"),
]

# `os` is the one ambient module the package really imports -- R5 needs
# `os.fstat` and `os.PathLike` (`SPEC.md` §7.1) -- so banning the module would
# ban the one use the spec requires. What is banned is the handful of names on
# it that *are* the clock, randomness or a child process: the review found this
# surface open inside a module the gate called clean (F7).
PLANTED_AMBIENT_OS = [
    ("import os\nos.urandom(8)", "urandom"),
    ("import os\nos.times()", "times"),
    ("import os\nos.fork()", "fork"),
    ("import os\nos.pipe()", "pipe"),
    ("import os\nos.system('date')", "system"),
    ("from os import urandom", "urandom"),
]


# The showcase's rule engine (R8, `SPEC.md` §9.4). The consumer that evaluates
# agentgolden's rules per delta is `tests/showcase.py`; the package must never
# reach for it, and a showcase is the occasion on which one import drifts one
# directory left and passes every other gate.
PLANTED_CONSUMER_RULES = [
    ("import agentgolden", "agentgolden"),
    ("from agentgolden.rules import evaluate", "agentgolden.rules"),
    ("from agentgolden.signature import signature", "agentgolden.signature"),
    ("import agentgolden.rules as rules", "agentgolden.rules"),
]


@pytest.mark.parametrize(("source", "expected"), PLANTED_AMBIENT)
def test_gate_fails_on_a_planted_violation(source, expected):
    found = gates.check_source("spanweave_live/planted.py", source, gates.ALL_RULES)
    assert [v.rule for v in found] == ["no-ambient-runtime"]
    assert expected in found[0].detail


@pytest.mark.parametrize(("source", "expected"), PLANTED_NETWORK)
def test_gate_fails_on_a_planted_network_import(source, expected):
    found = gates.check_source("spanweave_live/planted.py", source, gates.ALL_RULES)
    assert [v.rule for v in found] == ["no-network"]
    assert expected in found[0].detail


@pytest.mark.parametrize(("source", "expected"), PLANTED_AMBIENT_OS)
def test_gate_fails_on_a_planted_ambient_use_of_os(source, expected):
    found = gates.check_source("spanweave_live/planted.py", source, gates.ALL_RULES)
    assert [v.rule for v in found] == ["no-ambient-os"]
    assert expected in found[0].detail


@pytest.mark.parametrize(("source", "expected"), PLANTED_CONSUMER_RULES)
def test_gate_fails_on_a_planted_import_of_the_consumer_s_rule_engine(source, expected):
    found = gates.check_source("spanweave_live/planted.py", source, gates.ALL_RULES)
    assert [v.rule for v in found] == ["no-consumer-rules"]
    assert expected in found[0].detail


def test_the_consumer_rule_engine_has_no_seam_and_cannot_be_given_one():
    """The one rule with no exemption, held where the allowlist is held.

    Standing rule 2 is not a cost the way the clock is: no file of the package
    has to bind a rule engine, because the package never evaluates anything. So
    unlike `time` there is no caller at the edge to concede to, and the real
    `SEAMS` names no `agentgolden` for any file (`SPEC.md` §9.4).
    """
    for allowed in gates.SEAMS.values():
        assert "agentgolden" not in allowed


def test_the_os_the_package_really_needs_is_not_banned():
    """`os.fstat` and `os.PathLike` are what `tail` is built on (§7.1).

    The rule names attributes, not the module, because a module ban would have
    to be a seam entry for the one file that legitimately reads a file's
    identity -- and a seam entry would then exempt every other `os.` name in
    that same file, which is the opposite of narrow.
    """
    source = "import os\n\n\ndef identity(handle):\n    return os.fstat(handle)\n"
    assert gates.check_source("spanweave_live/ingest.py", source, gates.ALL_RULES) == []


def test_the_gate_states_what_it_does_not_catch():
    """A dynamic import escapes an AST walk, and the gate says so rather than
    being advertised as more than it is (`reviews/2026-10-06-run2.md` T11).

    Recorded as a test so the limit is not a comment someone deletes: if the
    rule is ever broadened to flag `importlib.import_module("time")`, this is
    the assertion that has to change in the same commit as the broadening.
    """
    escapes = 'import importlib\nimportlib.import_module("time").time()\n'
    found = gates.check_source("spanweave_live/sneaky.py", escapes, gates.ALL_RULES)
    assert found == []
    assert "static" in gates.no_ambient_runtime.__doc__


def test_the_gate_reports_where_the_import_is():
    source = "\n".join(['"""Docstring."""', "", "import json", "import time"])
    found = gates.check_source("spanweave_live/planted.py", source, gates.ALL_RULES)
    assert [(v.path, v.line) for v in found] == [("spanweave_live/planted.py", 4)]


def test_the_gate_does_not_fire_on_things_that_merely_look_alike():
    # The first false positive is what gets a gate switched off, which is worse
    # than not having one. Prose, comments and identifiers are not imports.
    innocent = "\n".join(
        [
            '"""Timestamps, sockets and random seeds are the caller\'s."""',
            "# a later batch injects sleep here",
            "import json",
            "from spanweave_live import __version__",
            "",
            "def elapsed(now, started):",
            "    return now() - started",
            "",
            "RANDOM_SEEDS = (0, 1, 2)",
            "socket_factory = None",
        ]
    )
    found = gates.check_source("spanweave_live/innocent.py", innocent, gates.ALL_RULES)
    assert found == []


def test_a_seam_may_hold_the_one_module_it_names():
    # The allowlist mechanism, exercised with a map of its own rather than with
    # the real one -- which is empty at R0 and must stay empty until a batch
    # has a seam file to add.
    seams = {"clock.py": frozenset({"time"})}
    assert (
        gates.no_ambient_runtime(
            "spanweave_live/clock.py",
            "import time",
            ast.parse("import time"),
            seams=seams,
        )
        == []
    )


def test_a_seam_allows_only_the_module_it_names():
    seams = {"clock.py": frozenset({"time"})}
    source = "import time\nimport socket"
    found = gates.no_ambient_runtime(
        "spanweave_live/clock.py",
        source,
        ast.parse(source),
        seams=seams,
    )
    assert [v.line for v in found] == [2]
    assert "socket" in found[0].detail


def test_a_seam_may_hold_the_network_module_it_names():
    """One allowlist for both rules, which is what R6 will ask of it.

    `SPEC.md` §7.2 says the OTLP endpoint is stdlib `http.server` and that the
    listener factory is injected. If that batch finds it cannot inject the
    import away -- as R3 and R5 each could -- the narrow answer is one file and
    one module here, and the mechanism has to exist before the batch needs it.
    """
    seams = {"listener.py": frozenset({"http.server"})}
    source = "import http.server\nimport urllib.request"
    found = gates.no_network(
        "spanweave_live/listener.py",
        source,
        ast.parse(source),
        seams=seams,
    )
    assert [v.line for v in found] == [2]
    assert "urllib" in found[0].detail


def test_a_seam_exempts_only_the_file_it_names():
    seams = {"clock.py": frozenset({"time"})}
    found = gates.no_ambient_runtime(
        "spanweave_live/router.py",
        "import time",
        ast.parse("import time"),
        seams=seams,
    )
    assert [v.rule for v in found] == ["no-ambient-runtime"]


def test_the_real_allowlist_names_one_seam_file_and_nothing_else():
    # R0 had no seam file, and R7 has exactly one. This is not a style
    # preference: it is the fact the gate's whole value rests on, and a batch
    # that changes this entry changes this assertion deliberately, in the same
    # commit, with a reason.
    #
    # R3 was the batch expected to need the first entry — completion is a
    # timeout policy, and a timeout policy wants a clock — and it needed none:
    # `Completion.now` has no default, so the caller holds the import
    # (`SPEC.md` §5.2). The allowlist was **still empty after R3**, the batch
    # that was supposed to grow it, and what finally grew it was R7 —
    # `{"real.py": frozenset({"time", "http.server"})}`, one file and two
    # modules, which is the literal this test asserts below
    # (`tests/gates.py:237`).
    #
    # R5 (`sleep`) and R6 (the listener) were the other two candidates R0 named
    # and both declined it too. R6 is the one worth reading twice, because this
    # gate bans `http` outright and §7.2's endpoint is `http.server`: the seam
    # is the handler's **base class** and the listener **factory**, two
    # parameters with no defaults, so the import lives in the caller.
    #
    # **R7 is the caller, and it is the one entry.** Something has to hand
    # `Completion.now`, `tail`'s `now`/`sleep` and `serve`'s listener factory
    # the real thing, and a process has nobody to take them from, so
    # `spanweave_live/real.py` imports `time` and `http.server` and this
    # allowlist names that file and exactly those two modules (`SPEC.md` §8.2).
    # The entry is held here **literally**, rather than by a length or a key
    # check, so that widening it -- a second file, a third module, `http`
    # instead of `http.server` -- is a deliberate edit to this line with a
    # reason in its commit body. `tests/test_cli.py` is where the narrowness is
    # argued: `cli.py` is run through these rules with an empty allowlist.
    assert dict(gates.SEAMS) == {"real.py": frozenset({"time", "http.server"})}


def test_the_package_reaches_for_no_ambient_runtime():
    found = gates.check_package(gates.ALL_RULES)
    assert found == [], "\n".join(str(v) for v in found)


def test_the_gate_scans_every_module_in_the_package_and_not_a_list():
    """The gate's inputs are the tree, held against an independent walk.

    A gate that silently scans zero files passes forever; so does one that
    scans a hand-written list of two, which is what the previous form of this
    tripwire (`len(package_files()) >= 2`) accepted. `package_files()` was
    mutated to `[PACKAGE_ROOT / "__init__.py", PACKAGE_ROOT / "cli.py"]`, a
    `spanweave_live/completion.py` importing `time` and `random` was added, and
    `make check` stayed green (`reviews/2026-10-04-run1.md` R0-2).

    So the set is compared against an `rglob` computed here, from this file's
    own location rather than from `gates.PACKAGE_ROOT`: the two have to agree,
    which means every `*.py` under the package at any depth is scanned, and
    nothing outside it is.
    """
    package = Path(__file__).resolve().parent.parent / "spanweave_live"
    walked = sorted(package.rglob("*.py"))
    assert walked, "no modules under spanweave_live/ at all"
    assert gates.package_files() == walked
    # Named rather than implied: the package really has subdirectories to reach
    # once a batch adds one, and the walk above is what reaches them.
    assert {p.name for p in walked} >= {
        "__init__.py",
        "completion.py",
        "framing.py",
        "routing.py",
    }


def test_the_walk_reaches_a_module_nested_in_a_subpackage(tmp_path, monkeypatch):
    """A planted nested module is caught, with no edit to the gate.

    `spanweave_live/` is flat today, so the depth of the walk is not something
    the real package can demonstrate. A synthetic one can: three levels, with
    the ambient import at the bottom, scanned by the same `check_package` the
    real gate runs. The allowlist is keyed by the path relative to the package
    root, so the nested path is *not* exempt -- which is the other half of what
    this plant shows.
    """
    root = tmp_path / gates.PACKAGE_ROOT.name
    (root / "ingest" / "deep").mkdir(parents=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "ingest" / "__init__.py").write_text("", encoding="utf-8")
    (root / "ingest" / "deep" / "listener.py").write_text(
        "import time\n", encoding="utf-8"
    )
    monkeypatch.setattr(gates, "PACKAGE_ROOT", root)

    assert sorted(str(p.relative_to(tmp_path)) for p in gates.package_files()) == [
        "spanweave_live/__init__.py",
        "spanweave_live/ingest/__init__.py",
        "spanweave_live/ingest/deep/listener.py",
    ]
    found = gates.check_package(gates.ALL_RULES)
    assert [(v.rule, v.path, v.line) for v in found] == [
        ("no-ambient-runtime", "spanweave_live/ingest/deep/listener.py", 1)
    ]
    assert "time" in found[0].detail
