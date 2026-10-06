"""Each pin is one pin, and this test is what makes that true.

`pyproject.toml` depends on `spanweave` at a git sha; `corpus/` is a submodule
of the same repository, and `fixtures/conformance/` is built out of it. If the
two drift, the conformance gate compares live graphs against expected graphs
from a *different* version of the library than the one it imports -- and the
failure that produces points at the code under test instead of at the pin.
So the drift is caught here, where it is one line of output.

Moving the pin is therefore one edit in two places plus `uv.lock`, and this
test is what says so.

R8 added a **second** pair of the same shape, for the same reason, and it is a
dev dependency rather than a runtime one: `agentgolden` at a git sha in the
`dev` extra, and `showcase/` a submodule of that repository at that sha. The
showcase (`SPEC.md` §9) imports the library and reads the rules file and the
trace from the submodule's `examples/`, which the wheel does not ship -- so a
drift between the two would evaluate one commit's rules over another commit's
trace, and the first-failure table would move with no commit to explain it.
The resolution itself is asserted too: `agentgolden` requires
`spanweave>=0.9.1,<1.0`, and that the *pinned* spanweave satisfies it is a
fact this file measures rather than a sentence `WORKPLAN.md` R8 asserts.
"""

import importlib.metadata
import re
import subprocess
import tomllib
from pathlib import Path

import spanweave
from packaging.requirements import Requirement
from packaging.version import Version

REPO = Path(__file__).resolve().parent.parent
PYPROJECT = REPO / "pyproject.toml"
SUBMODULE_PATH = "corpus"

#: R8's pair: the dev dependency and the submodule the showcase reads.
SHOWCASE_SUBMODULE_PATH = "showcase"

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


def _agentgolden_requirement() -> str:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    requirements = [
        req
        for req in data["project"]["optional-dependencies"]["dev"]
        if req.split("@")[0].strip().replace("_", "-").lower() == "agentgolden"
    ]
    assert len(requirements) == 1, (
        f"expected exactly one agentgolden dev dependency, got {requirements}"
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


def _submodule_sha(path: str = SUBMODULE_PATH) -> str:
    # Read the index rather than `git -C corpus rev-parse HEAD`: the index
    # entry is what this repository RECORDS and what a clone would check out.
    # A submodule working tree left on some other commit is a dirty tree, which
    # is a different complaint, made by `git status` rather than by this test.
    for line in _git("ls-files", "--stage", "--", path).splitlines():
        mode, sha, _rest = line.split(maxsplit=2)
        if mode == "160000":
            return sha
    raise AssertionError(
        f"no gitlink for {path!r} in the index; that submodule is missing "
        f"(git submodule add <https url> {path})"
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


def test_every_submodule_is_cloned_over_https_too():
    """Both halves of each pin are HTTPS, and this is the half nothing held.

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
    assert len(urls) == 2, (
        f"two submodules are expected -- corpus/ (spanweave) and showcase/ "
        f"(agentgolden) -- and both are read through a pin; got {urls}"
    )
    for url in urls:
        assert url.startswith("https://"), (
            f"every submodule must be cloned over HTTPS so CI's own checkout "
            f"(and a stranger's clone) resolves it without a key; got {url!r}. "
            f"Use https://github.com/SigorMatt/spanweave.git for corpus/ and "
            f"https://github.com/SigorMatt/agentgolden.git for showcase/"
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


# --------------------------------------------------------------------------
# R8's pair: the showcase's dev dependency and the submodule it reads from.
# --------------------------------------------------------------------------


def test_the_showcase_dependency_pin_is_a_full_sha():
    requirement = _agentgolden_requirement()
    assert "git+https://" in requirement, (
        f"agentgolden must be pinned by git over HTTPS so an unauthenticated "
        f"clone (CI, a stranger) resolves it; got {requirement!r}"
    )
    assert SHA.search(requirement), (
        f"agentgolden must be pinned to a full 40-character sha, not a tag, a "
        f"branch or an abbreviation; got {requirement!r}"
    )


def test_the_showcase_dependency_is_a_dev_dependency_and_not_a_runtime_one():
    """Standing rule 2, held in `pyproject.toml` (`SPEC.md` §1.2, §9.4).

    `agentgolden` evaluates rules. The receiver evaluates nothing, so a user
    who installs `spanweave-live` must not get a rule engine with it: the
    consumer that uses one is a test. The gate in `tests/gates.py` holds the
    import side; this holds the packaging side, which is the half a gate over
    source text cannot see.
    """
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    runtime = [
        req.split("@")[0].strip().replace("_", "-").lower()
        for req in data["project"]["dependencies"]
    ]
    assert runtime == ["spanweave"], (
        f"the receiver has exactly one runtime dependency; got {runtime}"
    )


def test_the_showcase_dependency_sha_and_its_submodule_sha_are_equal():
    requirement = _agentgolden_requirement()
    found = SHA.search(requirement)
    assert found is not None
    dependency_sha = found.group(0)
    assert dependency_sha == _submodule_sha(SHOWCASE_SUBMODULE_PATH), (
        "pyproject.toml pins agentgolden at one commit and the showcase/ "
        "submodule is at another. Move both, in one commit, or the showcase "
        "imports one commit's rule engine and reads another commit's rules "
        "file and trace -- and its first-failure table moves with no commit "
        "to explain it.\n"
        f"  pyproject.toml : {dependency_sha}\n"
        f"  showcase/      : {_submodule_sha(SHOWCASE_SUBMODULE_PATH)}"
    )


def test_the_lockfile_pins_the_showcase_sha_too():
    lock = (REPO / "uv.lock").read_text(encoding="utf-8")
    found = SHA.search(_agentgolden_requirement())
    assert found is not None
    assert found.group(0) in lock, (
        "uv.lock does not mention the pinned agentgolden sha; run `uv lock` "
        "and commit the result with the pin move."
    )


def test_the_showcase_dependency_resolves_against_the_pinned_spanweave():
    """`WORKPLAN.md` R8's parenthetical, measured instead of assumed.

    The row says agentgolden's own `spanweave>=0.9.1,<1.0` "resolves against
    the pinned spanweave". It does -- the pinned commit is `0.9.1` -- and the
    interesting part is the margin: it is the *lower* bound that is exactly
    met, so a pin move to a spanweave that bumps to `1.0` breaks the showcase
    and this assertion is where it says so, rather than in a resolver error
    with no sentence attached.

    `packaging` is a hard dependency of `pytest`, so importing it here adds
    nothing to the dev extra.
    """
    specifiers = [
        Requirement(req)
        for req in importlib.metadata.requires("agentgolden") or ()
        if Requirement(req).name == "spanweave"
    ]
    assert len(specifiers) == 1, f"expected one spanweave requirement, {specifiers}"
    requirement = specifiers[0]
    assert str(requirement.specifier) == "<1.0,>=0.9.1", (
        "agentgolden's spanweave range moved; the showcase's pin pair is what "
        "has to move with it"
    )
    assert requirement.specifier.contains(Version(spanweave.__version__)), (
        f"the pinned spanweave is {spanweave.__version__}, which does not "
        f"satisfy agentgolden's {requirement.specifier}: the two pins cannot "
        f"be installed together"
    )


def test_the_installed_spanweave_is_the_pinned_commit_and_not_a_released_one():
    """The resolution above is only meaningful if the git pin is what won.

    agentgolden depends on `spanweave` by *range*, and PyPI has releases in it.
    If the resolver had satisfied agentgolden from PyPI and left the git pin to
    the receiver alone, two spanweaves would be in play and the showcase's
    graphs would come from whichever import won. `uv` resolves one package per
    name, and this is the assertion that says so out loud.
    """
    direct = importlib.metadata.distribution("spanweave").read_text("direct_url.json")
    assert direct is not None, (
        "spanweave was not installed from a direct URL; the git pin did not win"
    )
    found = SHA.search(_spanweave_requirement())
    assert found is not None
    assert found.group(0) in direct, (
        f"the installed spanweave is not the pinned commit:\n  {direct}"
    )
