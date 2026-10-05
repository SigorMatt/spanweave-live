"""The two pins are one pin, and this test is what makes that true.

`pyproject.toml` depends on `spanweave` at a git sha; `corpus/` is a submodule
of the same repository, and `fixtures/conformance/` is built out of it. If the
two drift, the conformance gate compares live graphs against expected graphs
from a *different* version of the library than the one it imports -- and the
failure that produces points at the code under test instead of at the pin.
So the drift is caught here, where it is one line of output.

Moving the pin is therefore one edit in two places plus `uv.lock`, and this
test is what says so.
"""

import re
import subprocess
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PYPROJECT = REPO / "pyproject.toml"
SUBMODULE_PATH = "corpus"

# A 40-hex git sha, and nothing shorter: an abbreviated pin in one of the two
# places and a full one in the other would compare unequal for no reason a
# reader could act on, so the pin is required to be full-length in both.
SHA = re.compile(r"\b[0-9a-f]{40}\b")


def _spanweave_requirement() -> str:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    requirements = [
        req
        for req in data["project"]["dependencies"]
        if req.split("@")[0].strip().replace("_", "-").lower() == "spanweave"
    ]
    assert len(requirements) == 1, (
        f"expected exactly one spanweave dependency, got {requirements}"
    )
    return requirements[0]


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _submodule_sha() -> str:
    # Read the index rather than `git -C corpus rev-parse HEAD`: the index
    # entry is what this repository RECORDS and what a clone would check out.
    # A submodule working tree left on some other commit is a dirty tree, which
    # is a different complaint, made by `git status` rather than by this test.
    for line in _git("ls-files", "--stage", "--", SUBMODULE_PATH).splitlines():
        mode, sha, _rest = line.split(maxsplit=2)
        if mode == "160000":
            return sha
    raise AssertionError(
        f"no gitlink for {SUBMODULE_PATH!r} in the index; the corpus submodule "
        f"is missing (git submodule add https://github.com/SigorMatt/spanweave.git "
        f"{SUBMODULE_PATH})"
    )


def test_the_dependency_pin_is_a_full_sha():
    requirement = _spanweave_requirement()
    assert "git+https://" in requirement, (
        f"spanweave must be pinned by git over HTTPS so an unauthenticated "
        f"clone resolves it; got {requirement!r}"
    )
    assert SHA.search(requirement), (
        f"spanweave must be pinned to a full 40-character sha, not a tag, a "
        f"branch or an abbreviation; got {requirement!r}"
    )


def test_the_submodule_is_cloned_over_https_too():
    """Both halves of the pin are HTTPS, and this is the half nothing held.

    CI checks the submodule out with `submodules: true`, which authenticates
    with the Actions token over HTTPS: an SSH URL here fails at checkout, on
    every job, with a message about a missing key rather than about a pin. The
    dependency half is asserted above; the submodule half was asserted nowhere,
    and a re-added SSH submodule passed `make check` and failed only at CI
    (`patches/REVIEW-2026-10-04.md` R0-3 / P-5). `SPEC.md` §0.1 states both.

    Read from `.gitmodules`, which is the file a clone reads, rather than from
    `.git/config`, which is one machine's own.
    """
    configured = _git(
        "config", "-f", ".gitmodules", "--get-regexp", r"^submodule\..*\.url$"
    ).splitlines()
    urls = [line.split(maxsplit=1)[1] for line in configured if line.strip()]
    assert urls, "no submodule URL in .gitmodules at all"
    for url in urls:
        assert url.startswith("https://"), (
            f"the corpus submodule must be cloned over HTTPS so CI's own "
            f"checkout (and a stranger's clone) resolves it without a key; got "
            f"{url!r}. Use "
            f"https://github.com/SigorMatt/spanweave.git"
        )


def test_the_dependency_sha_and_the_submodule_sha_are_equal():
    requirement = _spanweave_requirement()
    found = SHA.search(requirement)
    assert found is not None
    dependency_sha = found.group(0)
    assert dependency_sha == _submodule_sha(), (
        "pyproject.toml pins spanweave at one commit and the corpus submodule "
        "is at another. Move both, in one commit, or the conformance gate "
        "compares graphs built by one version against expectations from "
        "another.\n"
        f"  pyproject.toml : {dependency_sha}\n"
        f"  corpus/        : {_submodule_sha()}"
    )


def test_the_lockfile_pins_the_same_sha():
    # The third copy. `uv.lock` is what an install actually resolves, so a lock
    # left behind after the pin moved installs the old library while both
    # assertions above pass.
    lock = (REPO / "uv.lock").read_text(encoding="utf-8")
    found = SHA.search(_spanweave_requirement())
    assert found is not None
    assert found.group(0) in lock, (
        "uv.lock does not mention the pinned spanweave sha; run `uv lock` and "
        "commit the result with the pin move."
    )
