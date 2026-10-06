"""Prove that what SHIPS works (`make install-check`).

Everything `make check` runs happens under `uv run`, with the source tree on
the path, so every gate it runs answers a question about the *repository*. A
packaging break -- a missing package directory, a console script pointing at a
function that is not there, a dependency the wheel forgets to declare -- passes
every one of those gates and fails for the first stranger.

So this target builds the sdist and the wheel, installs the wheel into a
throwaway virtualenv, and runs it from a working directory **outside** the
repo -- and *asserts* that it is doing that rather than assuming it: the
interpreter under test reports its own `sys.path` and the file it imported
`spanweave_live` from, and this harness checks both.

It needs the network, once, for the same reason `uv sync` does: the receiver's
one dependency is `spanweave` pinned at a git sha, and installing the wheel
resolves it. It never publishes anything.

Deliberately NOT a prerequisite of `make check`: it builds a wheel and a venv,
and `check` is the fast gate a batch must pass. CI runs both.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DIST = REPO / "dist"

# What the interpreter under test is asked. Printed as JSON on stdout so this
# harness reads facts rather than parsing prose.
PROBE = """
import json, sys
import spanweave, spanweave_live
print(json.dumps({
    "cwd": __import__("os").getcwd(),
    "sys_path": sys.path,
    "spanweave_live_file": spanweave_live.__file__,
    "spanweave_live_version": spanweave_live.__version__,
    "spanweave_file": spanweave.__file__,
}))
"""


def run(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    print(f"  $ {' '.join(str(a) for a in args)}   (in {cwd})")
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise SystemExit(f"FAILED ({result.returncode}): {' '.join(map(str, args))}")
    return result


def build() -> tuple[Path, Path]:
    if DIST.exists():
        shutil.rmtree(DIST)
    run(["uv", "build"], cwd=REPO)
    wheels = sorted(DIST.glob("*.whl"))
    sdists = sorted(DIST.glob("*.tar.gz"))
    assert len(wheels) == 1, f"expected one wheel, got {wheels}"
    assert len(sdists) == 1, f"expected one sdist, got {sdists}"
    return wheels[0], sdists[0]


def audit_wheel(wheel: Path) -> None:
    """The wheel ships the library and nothing else."""
    names = zipfile.ZipFile(wheel).namelist()
    assert any(n.startswith("spanweave_live/") for n in names), names
    for forbidden in ("corpus/", "showcase/", "tests/", "reviews/"):
        leaked = [n for n in names if n.startswith(forbidden)]
        assert not leaked, f"wheel ships {forbidden}: {leaked}"
    print(f"  wheel ships {len(names)} entries, library only")


def audit_sdist(sdist: Path) -> None:
    """The sdist ships this project's own content, at a sha for everything else.

    `[tool.hatch.build.targets.sdist].include` is an allowlist, so a directory
    added to the repository is absent from the sdist until someone lists it --
    which is the right default and the reason it is asserted rather than
    assumed. Three things must hold at once: the documents a reader needs are
    in (`TASKS.md` among them, because it is where the series' decisions and
    every review's disposition live); the two submodules are out, since each is
    another repository's working tree and an sdist carrying one would be a copy
    nothing holds at a sha; and `reviews/` is out, because it is a tracked
    archive of this repository's process and not part of what installs.
    """
    with tarfile.open(sdist) as archive:
        members = archive.getnames()
    inside = {name.split("/", 1)[1] for name in members if "/" in name}
    for required in ("spanweave_live/__init__.py", "README.md", "TASKS.md", "SPEC.md"):
        assert required in inside, f"sdist is missing {required}"
    for forbidden in ("corpus/", "showcase/", "reviews/"):
        leaked = sorted(n for n in inside if n.startswith(forbidden))
        assert not leaked, f"sdist ships {forbidden}: {leaked}"
    print(f"  sdist ships {len(members)} entries, no submodule and no reviews/")


def check_installed(wheel: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="spanweave-live-install-") as tmp:
        outside = Path(tmp)
        # Asserted, not assumed: a working directory inside the repo would put
        # the source tree on sys.path and this whole check would prove nothing.
        assert REPO not in outside.parents and outside != REPO
        venv = outside / "venv"
        run(["uv", "venv", str(venv)], cwd=outside)
        python = venv / "bin" / "python"
        if not python.exists():  # pragma: no cover - Windows layout
            python = venv / "Scripts" / "python.exe"
        run(
            ["uv", "pip", "install", "--python", str(python), str(wheel)],
            cwd=outside,
        )

        probe = run([str(python), "-c", PROBE], cwd=outside)
        facts = json.loads(probe.stdout)
        print(f"  cwd under test        : {facts['cwd']}")
        print(f"  spanweave_live from   : {facts['spanweave_live_file']}")
        print(f"  spanweave from        : {facts['spanweave_file']}")
        for entry in facts["sys_path"]:
            if entry and Path(entry).resolve() == REPO:
                raise SystemExit(f"the repo is on sys.path under test: {entry}")
        for key in ("spanweave_live_file", "spanweave_file"):
            imported = Path(facts[key]).resolve()
            if REPO in imported.parents:
                raise SystemExit(f"{key} was imported from the repo: {imported}")

        script = python.parent / "spanweave-live"
        assert script.exists(), f"no console script at {script}"
        version = run([str(script), "--version"], cwd=outside)
        print(f"  console script says   : {version.stdout.strip()}")
        assert facts["spanweave_live_version"] in version.stdout

        # And it runs a **command**, not just `--version` (R7, `SPEC.md` §8):
        # one corpus record piped to `tail -`, from outside the repo, and the
        # graph has to land as `<trace_id>.json`. `--version` proves the console
        # script exists; this proves the thing a human runs works in what ships.
        record = (
            REPO
            / "corpus"
            / "fixtures"
            / "conformance"
            / "single_tool_call"
            / "dialects"
            / "openinference.jsonl"
        ).read_bytes()
        out = Path(tmp) / "graphs"
        tailed = subprocess.run(
            [str(script), "tail", "-", "--out", str(out)],
            cwd=outside,
            input=record,
            capture_output=True,
        )
        if tailed.returncode != 0:
            sys.stderr.write(tailed.stderr.decode())
            raise SystemExit(f"FAILED ({tailed.returncode}): the shipped `tail`")
        written = sorted(path.name for path in out.iterdir())
        print(f"  shipped tail wrote    : {written}")
        assert written == ["t1.json"], written


def main() -> int:
    print("install-check: building what ships")
    wheel, sdist = build()
    print(f"  wheel : {wheel.name}")
    print(f"  sdist : {sdist.name}")
    audit_wheel(wheel)
    audit_sdist(sdist)
    print("install-check: installing the wheel into a throwaway venv, outside the repo")
    check_installed(wheel)
    print("install-check: OK -- what ships imports, resolves spanweave, and runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
