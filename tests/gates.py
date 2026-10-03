"""The receiver's invariant gates, as reusable checks over source text.

R0 implements exactly one gate, the one the receiver's whole testability rests
on: **nothing under `spanweave_live/` reaches for ambient runtime.** No module
in the package imports `time`, `datetime`, `random`, `socket`, `threading` or
`asyncio` except a file this module names as a seam.

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
AMBIENT_MODULES = (
    "time",
    "datetime",
    "random",
    "socket",
    "threading",
    "asyncio",
)

# THE SEAM ALLOWLIST. Maintained here and nowhere else.
#
# A key is a path relative to the package root; its value is the set of
# ambient modules that one file may import. The map is EMPTY at R0 and that is
# the point: no file in the package binds a default clock, sleep or listener
# yet, so nothing needs an exemption yet.
#
# Adding a line here is a deliberate, reviewed act, made in the same commit as
# the file it names, and it names the narrowest thing that works: ONE file and
# ONE module. R3 adds the `now`/`sleep` defaults and R6 the listener factory;
# each is one seam module whose whole job is to hold the import that everything
# else is given instead of taking. If an entry would be needed anywhere else,
# that is a design conversation (`CONTRIBUTING.md`), not a line in this dict.
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


def no_ambient_runtime(
    path: str,
    source: str,
    tree: ast.AST,
    *,
    seams: Mapping[str, frozenset[str]] | None = None,
) -> list[Violation]:
    """No clock, randomness, socket or concurrency import outside a seam."""
    allowed = (SEAMS if seams is None else seams).get(_seam_key(path), frozenset())
    found: list[Violation] = []
    for imported, line in _imported_modules(tree):
        for banned in AMBIENT_MODULES:
            if not _matches_module(imported, banned):
                continue
            if banned in allowed:
                continue
            found.append(
                Violation(
                    "no-ambient-runtime",
                    path,
                    line,
                    f"imports {imported!r}; the clock, sleeping and sockets are "
                    f"injected seams, and {banned!r} is not one this file may "
                    f"hold (CLAUDE.md, standing rules; tests/gates.py SEAMS)",
                )
            )
    return found


Rule = Callable[[str, str, ast.AST], list[Violation]]

ALL_RULES: tuple[Rule, ...] = (no_ambient_runtime,)


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
