"""The gate, watched failing.

The gate is asserted twice: once against a **planted violation** -- a synthetic
module that deliberately breaks it -- and once against the real package. The
first assertion is the one that matters. A gate that has only ever been seen
passing is indistinguishable from a gate that cannot fail.

Rule implementations live in `tests/gates.py`.
"""

import ast

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
]


@pytest.mark.parametrize(("source", "expected"), PLANTED_AMBIENT)
def test_gate_fails_on_a_planted_violation(source, expected):
    found = gates.check_source("spanweave_live/planted.py", source, gates.ALL_RULES)
    assert [v.rule for v in found] == ["no-ambient-runtime"]
    assert expected in found[0].detail


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


def test_a_seam_exempts_only_the_file_it_names():
    seams = {"clock.py": frozenset({"time"})}
    found = gates.no_ambient_runtime(
        "spanweave_live/router.py",
        "import time",
        ast.parse("import time"),
        seams=seams,
    )
    assert [v.rule for v in found] == ["no-ambient-runtime"]


def test_the_real_allowlist_is_empty_until_a_batch_adds_a_seam():
    # R0 has no seam file. This is not a style preference: it is the fact the
    # gate's whole value rests on, and a batch that adds an entry here changes
    # this assertion deliberately, in the same commit, with a reason.
    assert dict(gates.SEAMS) == {}


def test_the_package_reaches_for_no_ambient_runtime():
    found = gates.check_package(gates.ALL_RULES)
    assert found == [], "\n".join(str(v) for v in found)


def test_the_gate_actually_scanned_something():
    # A gate that silently scans zero files passes forever. This is the
    # tripwire for that.
    assert len(gates.package_files()) >= 2
