"""The receiver's invariant gates, as reusable checks over source text.

R0 implemented exactly one gate, the one the receiver's whole testability rests
on: **nothing under `spanweave_live/` reaches for ambient runtime.** No module
in the package imports `time`, `datetime`, `random`, `socket`, `threading` or
`asyncio` -- the six `CLAUDE.md` standing rule 4 names -- except a file this
module names as a seam.

R5a added two more rules and widened the first, because the run-2 review
measured the difference between what the gate was advertised as proving and
what it enforced (`patches/REVIEW-2026-10-06.md` F7, F8):

- **no-ambient-runtime** also bans `secrets`, `uuid`, `concurrent.futures`,
  `selectors`, `select`, `subprocess` and `sched`: the same clock, randomness
  and concurrency under other names, each one verified to pass the six-module
  form.
- **no-network** bans the libraries that open a connection for you --
  `urllib`, `http`, `requests`, `httpx` and the rest -- because `socket` alone
  caught only the direct form, and the receiver is read-only toward the system
  it watches (`CLAUDE.md` 9). The parent `spanweave` repository has had this
  gate from its own start. R6's `http.server` endpoint is the one place this
  rule was expected to bite, and it did not: see `SEAMS` below.
- **no-ambient-os** bans `os.times`, `os.urandom`, `os.fork`, `os.pipe` and
  their kin without banning `os`, which `SPEC.md` §7.1's tail legitimately
  needs for `os.fstat` and `os.PathLike`.

All three are **static**: a dynamic `importlib.import_module("time")` passes,
and that limit is stated in the rule's own docstring and held by a test rather
than left for a reader to discover (T11).

Why this and not a style rule: the clock, sleeping and sockets are *injected*
in this project (`CLAUDE.md`, standing rules). A `time.time()` anywhere in the
package makes one test non-deterministic and the conformance gate a flake, and
it does so while every other test stays green -- which is the definition of
something that belongs in a gate rather than in review. The same is true of
`random` (an unseeded shuffle), of a direct `socket` (a test that needs a real
port), and of `threading`/`asyncio` (an interleaving no fixture pins).

The check is an AST walk, not a grep, because a grep is fooled by the word
`time` in a docstring and an AST is not.

The rules live here, apart from `test_gates.py`, so each can be run against a
**planted violation** -- a synthetic module that deliberately breaks it -- as
well as against the real package. A gate nobody has watched fail is a gate
nobody knows works.

This module is in `tests/`, not in `spanweave_live/`, on purpose: it
necessarily contains the very words it bans.
"""

from __future__ import annotations

import ast
import pathlib
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass

PACKAGE_ROOT = pathlib.Path(__file__).resolve().parent.parent / "spanweave_live"

# The ambient runtime a receiver is tempted to read directly, and must not.
#
# `time`/`datetime`  -- the clock is the injected `now` seam (SPEC.md section 5).
# `random`           -- test shuffles are seeded, in the test, never here.
# `socket`           -- the listener is an injected factory (SPEC.md section 7.2).
# `threading`/`asyncio` -- concurrency a fixture cannot pin.
#
# The first six are the ones `CLAUDE.md` standing rule 4 names. The rest were
# added by R5a, because the run-2 review verified that the gate was advertised
# as proving "no module reads a clock" while every one of these passed it
# (`patches/REVIEW-2026-10-06.md` F7):
#
# `secrets`/`uuid`   -- unseeded randomness under another name (CLAUDE.md 8);
#                       `uuid.uuid4()` is the obvious one.
# `concurrent.futures`/`selectors`/`select`/`subprocess`/`sched`
#                    -- concurrency, polling and child processes, which is the
#                       family `threading` and `asyncio` are banned as. R6 is
#                       the listener batch, and an `os.pipe`/`selectors`
#                       listener is exactly what slipped through a
#                       `socket`-only ban.
AMBIENT_MODULES = (
    "time",
    "datetime",
    "random",
    "socket",
    "threading",
    "asyncio",
    "secrets",
    "uuid",
    "concurrent.futures",
    "selectors",
    "select",
    "subprocess",
    "sched",
)

# The network. The receiver is read-only toward the system it watches
# (`CLAUDE.md` 9): it reads bytes and writes files, stdout and callbacks, and
# it never calls back into the observed system. `socket` above catches the
# direct form; these catch every library that opens the connection for you.
#
# The parent `spanweave` repository has had this gate since its own R0 and this
# one did not, which the run-2 review found by planting `import urllib.request`
# under the package and watching it pass (`patches/REVIEW-2026-10-06.md` F8).
#
# `http` is here and `SPEC.md` §7.2's endpoint is `http.server`: that is
# deliberate. R6 either injected the listener so the import lives in the caller,
# as R3 did with `now` and R5 with `sleep`, or wrote one narrow SEAMS line for
# one file and said why injection was not enough. **It injected**: the handler's
# base class and the listener factory are both parameters with no defaults, and
# `spanweave_live/endpoint.py` passes this rule unexempted.
NETWORK_MODULES = (
    "urllib",
    "http",
    "socketserver",
    "xmlrpc",
    "ftplib",
    "smtplib",
    "poplib",
    "imaplib",
    "telnetlib",
    "ssl",
    "requests",
    "httpx",
    "aiohttp",
    "websockets",
)

# `os` is not a banned module: `SPEC.md` §7.1's tail needs `os.fstat` for the
# file's size and identity, and `os.PathLike` for its own signature. What is
# banned is the set of names *on* it that are the clock, randomness or a child
# process -- the surface the review found open inside a module the gate called
# clean (F7). A module ban would have had to be a seam entry, and a seam entry
# exempts every other `os.` name in the same file, which is the opposite of
# narrow.
AMBIENT_OS_ATTRIBUTES = (
    "times",
    "urandom",
    "getrandom",
    "pipe",
    "pipe2",
    "fork",
    "forkpty",
    "posix_spawn",
    "system",
    "popen",
)

# THE SEAM ALLOWLIST. Maintained here and nowhere else.
#
# A key is a path relative to the package root; its value is the set of banned
# modules that one file may import -- ambient or network, since R5a there are
# two module rules and one allowlist between them. The map is EMPTY at R0 and
# that is the point: no file in the package binds a default clock, sleep or
# listener yet, so nothing needs an exemption yet.
#
# Adding a line here is a deliberate, reviewed act, made in the same commit as
# the file it names, and it names the narrowest thing that works: ONE file and
# ONE module. If an entry would be needed anywhere else, that is a design
# conversation (`CONTRIBUTING.md`), not a line in this dict.
#
# R0 predicted that R3 would add the `now` default and R6 the listener factory.
# **R3 added nothing**, and that is worth recording rather than quietly leaving:
# `Completion.now` has no default at all, so the caller supplies the clock and
# no module under the package has an import to exempt (`SPEC.md` §5.2).
#
# **R5 added nothing either**, which was the other prediction: `tail` takes
# `sleep` with no default, as `Completion` takes `now` with none, so the only
# `time` in the project is the one R7's CLI will bind (`SPEC.md` §7.1). Two
# batches that were each expected to need the first entry did not, and the
# pattern they share is a parameter with no default.
#
# **R6 added nothing either, and it was the last candidate.** The endpoint
# (`SPEC.md` §7.2) was made to prove it needed a line and could not: the seam
# turned out to be *two* parameters with no defaults rather than one, and
# neither of them lives here. `handler_class(base, endpoint)` takes the
# handler's base class -- `http.server.BaseHTTPRequestHandler` -- and builds
# the class with `type(...)`, because a `class` statement would need the base
# at import time and that is the very import being avoided;
# `serve(endpoint, listener=...)` takes the listener factory. So
# `import http.server` lives in the caller, which is R7's CLI and
# `tests/test_endpoint.py`. Three predictions of the first entry, three batches
# that declined it, one pattern: a parameter with no default. Nothing is left
# that was predicted to want a line, so a batch that wants one now is proposing
# something new and says so in its commit body.
SEAMS: Mapping[str, frozenset[str]] = {}


@dataclass(frozen=True)
class Violation:
    """One gate failure, located precisely enough to fix."""

    rule: str
    path: str
    line: int
    detail: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: [{self.rule}] {self.detail}"


def _imported_modules(tree: ast.AST) -> Iterator[tuple[str, int]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            yield node.module, node.lineno


def _matches_module(imported: str, banned: str) -> bool:
    return imported == banned or imported.startswith(banned + ".")


def _seam_key(path: str) -> str:
    """The allowlist key for a scanned path.

    Paths reach the rule in two shapes -- `spanweave_live/clock.py` from a
    package scan, and whatever a planted test calls its synthetic module. Both
    are reduced to a path relative to the package directory when they are under
    it, so the allowlist is written the way a reader expects.
    """
    parts = pathlib.PurePosixPath(path).parts
    if parts and parts[0] == PACKAGE_ROOT.name:
        return str(pathlib.PurePosixPath(*parts[1:]))
    return str(pathlib.PurePosixPath(path))


def _banned_imports(
    rule: str,
    banned_modules: Sequence[str],
    sentence: str,
    path: str,
    tree: ast.AST,
    seams: Mapping[str, frozenset[str]] | None,
) -> list[Violation]:
    """Every **static** import of a banned module, outside this file's seam."""
    allowed = (SEAMS if seams is None else seams).get(_seam_key(path), frozenset())
    found: list[Violation] = []
    for imported, line in _imported_modules(tree):
        for banned in banned_modules:
            if not _matches_module(imported, banned):
                continue
            # A seam entry may name the banned module (`time`) or something
            # narrower under it (`http.server`), and the narrower spelling is
            # the one this allowlist asks for: ONE file and ONE module.
            if any(_matches_module(imported, entry) for entry in allowed):
                continue
            found.append(
                Violation(
                    rule,
                    path,
                    line,
                    f"imports {imported!r}; {sentence}, and {banned!r} is not "
                    f"one this file may hold (CLAUDE.md, standing rules; "
                    f"tests/gates.py SEAMS)",
                )
            )
    return found


def no_ambient_runtime(
    path: str,
    source: str,
    tree: ast.AST,
    *,
    seams: Mapping[str, frozenset[str]] | None = None,
) -> list[Violation]:
    """No **static** import of a clock, randomness, socket or concurrency
    module outside a seam.

    "Static" is the whole of the claim and is said out loud:
    `importlib.import_module("time")` and `__import__("time")` are an AST walk's
    blind spot and pass this rule (`patches/REVIEW-2026-10-06.md` T11). Nothing
    in the package imports `importlib`, and either form is conspicuous in
    review, so the honest answer is to state the limit rather than to advertise
    the gate as more than it enforces.
    """
    return _banned_imports(
        "no-ambient-runtime",
        AMBIENT_MODULES,
        "the clock, sleeping and sockets are injected seams",
        path,
        tree,
        seams,
    )


def no_network(
    path: str,
    source: str,
    tree: ast.AST,
    *,
    seams: Mapping[str, frozenset[str]] | None = None,
) -> list[Violation]:
    """No **static** network import outside a seam (`CLAUDE.md` 9)."""
    return _banned_imports(
        "no-network",
        NETWORK_MODULES,
        "the receiver reads bytes and writes files, stdout and callbacks, and "
        "never calls back into the system it watches",
        path,
        tree,
        seams,
    )


def _os_names_used(tree: ast.AST) -> Iterator[tuple[str, int]]:
    """Every `os.<name>` attribute read, and every `from os import <name>`."""
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "os"
        ):
            yield node.attr, node.lineno
        elif isinstance(node, ast.ImportFrom) and node.module == "os":
            for alias in node.names:
                yield alias.name, node.lineno


def no_ambient_os(
    path: str,
    source: str,
    tree: ast.AST,
    *,
    seams: Mapping[str, frozenset[str]] | None = None,
) -> list[Violation]:
    """`os` may be imported; the clock, randomness and `fork` on it may not.

    The module itself is not banned because `SPEC.md` §7.1's tail is built on
    `os.fstat` and `os.PathLike`. This is the narrower rule that keeps the one
    legitimate use from carrying `os.urandom`, `os.times` and `os.pipe` in with
    it (`patches/REVIEW-2026-10-06.md` F7).
    """
    allowed = (SEAMS if seams is None else seams).get(_seam_key(path), frozenset())
    if "os" in allowed:
        return []
    return [
        Violation(
            "no-ambient-os",
            path,
            line,
            f"uses os.{name}; the clock, randomness and child processes are the "
            f"caller's, and `os` is imported here for the file's size and "
            f"identity alone (CLAUDE.md, standing rules; SPEC.md §7.1)",
        )
        for name, line in _os_names_used(tree)
        if name in AMBIENT_OS_ATTRIBUTES
    ]


Rule = Callable[[str, str, ast.AST], list[Violation]]

ALL_RULES: tuple[Rule, ...] = (no_ambient_runtime, no_network, no_ambient_os)


def check_source(path: str, source: str, rules: Sequence[Rule]) -> list[Violation]:
    """Run `rules` over one module's source. Used for planted violations too."""
    tree = ast.parse(source, filename=path)
    found: list[Violation] = []
    seen: set[tuple[str, int]] = set()
    for rule in rules:
        for violation in rule(path, source, tree):
            # One violation per rule per line: an import that matches twice
            # says nothing extra the second time.
            key = (violation.rule, violation.line)
            if key in seen:
                continue
            seen.add(key)
            found.append(violation)
    return found


def package_files() -> list[pathlib.Path]:
    return sorted(PACKAGE_ROOT.rglob("*.py"))


def check_package(rules: Sequence[Rule]) -> list[Violation]:
    found: list[Violation] = []
    for file in package_files():
        relative = str(file.relative_to(PACKAGE_ROOT.parent))
        found.extend(check_source(relative, file.read_text(encoding="utf-8"), rules))
    return found
