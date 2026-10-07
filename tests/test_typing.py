"""The pinned `spanweave` is a typed package, and nothing here follows an
untyped import.

Until R2c the pinned `spanweave` shipped no `py.typed` marker, so `mypy
--strict` refused to analyse it the moment a receiver module imported it, and
`pyproject.toml` carried one override -- `follow_untyped_imports = true` for
`module = ["spanweave.*"]` -- to make it look anyway (`SPEC.md` §0.2). The
marker is now upstream (`SigorMatt/spanweave` PR #4, merged as
`fec7da27af517ad8b58ae3ec57827916aae60674`, which is the sha both halves of the
pin now name), so the override is deleted and these tests are what keep it
deleted.

Three separate things are asserted, because only the three together say what
§0.2 claimed:

1. the package the pin installs really carries the marker -- the fact that
   makes the override unnecessary rather than merely unwanted;
2. no mypy configuration anywhere follows untyped imports or ignores missing
   ones -- the override is gone and its louder cousin never arrives;
3. `mypy --strict`, run with this repository's own configuration, really
   analyses `spanweave` and really reports a type error against its real
   signatures.

(3) is not redundant with (2). Deleting the override while the dependency were
untyped would fail `make check` *loudly*, with mypy saying it is skipping the
module -- so that mistake cannot hide. `ignore_missing_imports = true` is the
one that hides: it makes `Records`, `Diagnostic` and `read_records` all `Any`,
every annotation in this package vacuous, and the gate green. So the gate
checks that the question is still being asked, not only that one spelling of
not-asking is absent.
"""

import pathlib
import re
import subprocess
import sys
import tomllib

import spanweave

REPO = pathlib.Path(__file__).resolve().parent.parent
PYPROJECT = REPO / "pyproject.toml"

# Settings that make an untyped or unresolvable import acceptable to mypy.
# `follow_untyped_imports` was this repository's override and is now deleted;
# `ignore_missing_imports` is the one it was chosen over, and would be worse.
SUPPRESSIONS = ("follow_untyped_imports", "ignore_missing_imports")

# Files other than `pyproject.toml` that mypy reads configuration from. A
# setting moved into one of these would pass a test that read `pyproject.toml`
# alone -- and none of these files exists here, which is itself the assertion.
OTHER_MYPY_CONFIG_FILES = ("mypy.ini", ".mypy.ini", "setup.cfg")

# Where a setting could arrive as a command-line flag instead of a file.
MYPY_INVOCATIONS = ("Makefile", ".github/workflows/ci.yml")


def test_the_pinned_spanweave_ships_the_py_typed_marker():
    """The fact the deleted override was standing in for.

    Read from the installed package rather than from `corpus/`: `corpus/` is
    the submodule the fixtures are read from, but the package mypy and the
    tests import is the one `uv.lock` resolved, and it is that one that has to
    carry the marker.
    """
    installed = pathlib.Path(spanweave.__file__).resolve().parent
    marker = installed / "py.typed"
    assert marker.is_file(), (
        f"the installed spanweave ({installed}) ships no py.typed marker, so "
        f"`mypy --strict` cannot analyse it and SPEC.md §0.2's claim that the "
        f"override is unnecessary is false. The marker arrived upstream in "
        f"SigorMatt/spanweave PR #4; check that both halves of the pin name a "
        f"sha at or after fec7da27af517ad8b58ae3ec57827916aae60674 and that "
        f"`uv sync` has run."
    )


def test_no_mypy_configuration_follows_untyped_imports():
    """The override is gone, and stays gone, everywhere mypy could read it.

    `pyproject.toml` is *parsed*, not grepped: `[tool.mypy]` and every entry of
    `[[tool.mypy.overrides]]` are the only places mypy takes a setting from in
    that file, so parsing them is complete where a text scan would merely be
    broad. It also leaves the file free to *name* the deleted override in a
    comment, which is where a reader meets the decision -- a test that banned
    the word would force the explanation out of the file it explains.

    The other config files mypy reads do not exist here, so for them the
    assertion is an assignment-shaped match rather than a parse, and a flag on
    a command line is checked too.
    """
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    mypy = data.get("tool", {}).get("mypy", {})
    sections = [("[tool.mypy]", mypy)]
    for index, override in enumerate(mypy.get("overrides", [])):
        module = override.get("module")
        sections.append(
            (f"[[tool.mypy.overrides]] #{index} (module={module!r})", override)
        )

    for name, section in sections:
        for suppression in SUPPRESSIONS:
            assert suppression not in section, (
                f"pyproject.toml {name} sets {suppression}. The pinned "
                f"spanweave ships py.typed (R2c), so no import here needs "
                f"following untyped or ignoring: a suppression now hides a "
                f"real error instead of standing in for a missing marker "
                f"(SPEC.md §0.2)."
            )

    for filename in OTHER_MYPY_CONFIG_FILES:
        path = REPO / filename
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for suppression in SUPPRESSIONS:
            enabled = re.search(
                rf"^\s*{suppression}\s*=\s*(?!false|False|0\b)", text, re.MULTILINE
            )
            assert enabled is None, (
                f"{filename} sets {suppression}; mypy reads that file, and "
                f"after R2c nothing in this repository follows an untyped "
                f"import (SPEC.md §0.2)."
            )

    for filename in MYPY_INVOCATIONS:
        path = REPO / filename
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for suppression in SUPPRESSIONS:
            flag = "--" + suppression.replace("_", "-")
            assert flag not in text, (
                f"{filename} passes {flag} to mypy, which is the same "
                f"suppression as the deleted override wearing a command line "
                f"(SPEC.md §0.2)."
            )


def test_mypy_strict_really_analyses_spanweave(tmp_path):
    """Not silently skipping: a wrong annotation against spanweave errors.

    Planted outside the package, checked with this repository's own
    configuration. `read_records` returns `spanweave.Records`, so assigning it
    to an `int` must be an error that names that type. If `spanweave` were
    `Any` -- the `ignore_missing_imports` world -- there would be no error at
    all, and if it were unanalysable mypy would say so in words this test also
    looks for.
    """
    planted = tmp_path / "planted.py"
    planted.write_text(
        "from spanweave import read_records\n\nwrong: int = read_records(b'')\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--config-file",
            str(PYPROJECT),
            "--cache-dir",
            str(tmp_path / ".mypy_cache"),
            str(planted),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr

    assert "Skipping analyzing" not in output and "library stubs" not in output, (
        f"mypy will not analyse spanweave, so `make check` is checking this "
        f"package against nothing:\n{output}"
    )
    assert "Records" in output, (
        f"mypy did not report the planted `int = read_records(b'')` against "
        f"spanweave's real return type, so the import is resolving to `Any` "
        f"and every annotation in this package is being checked "
        f"vacuously:\n{output}"
    )
    assert result.returncode != 0, (
        f"mypy accepted `wrong: int = read_records(b'')`:\n{output}"
    )
