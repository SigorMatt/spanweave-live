"""The record a series leaves behind, held to what it says (V4).

A series closes by deleting its `WORKPLAN.md` and folding what outlives it into
`TASKS.md`, and the files a cold session reads first -- `CLAUDE.md`, then
`TASKS.md` -- are then the only place the series is described. Each sentence
below is one of theirs that a test can check without running the library:
the version is one number wherever it is written, the registry names the
batches in the order they ran and each with the commit that closed it, the
decisions log is the length it says, the reader's half of L1 is the commit
spanweave's own registry says it is, and `CLAUDE.md` says whether a series is
open as the tree does, names every source of a trace id `SPEC.md` §1.1 names,
and names on its `make conformance` line the files that target runs.

The registry's commits are read from history, so this file needs a clone with
history: CI's `check` job checks out with `fetch-depth: 0` for it, and a
shallow clone fails here with the command that fixes it rather than passing
without having looked.
"""

import re
import subprocess
import tomllib
from pathlib import Path

import pytest

import spanweave_live

REPO = Path(__file__).resolve().parent.parent
TASKS = REPO / "TASKS.md"
CHANGELOG = REPO / "CHANGELOG.md"
CLAUDE = REPO / "CLAUDE.md"
SPEC = REPO / "SPEC.md"
PLAN = REPO / "WORKPLAN.md"

#: The zoo series' batches in the order they ran (run 1: V0, V1, V2; run 2:
#: V1a, V3, V4). V1a was inserted after V2 and keeps its id.
ZOO_BATCHES = ["V0", "V1", "V2", "V1a", "V3", "V4"]

#: A series' last batch cannot name the commit that carries it.
CLOSING = "**done** (the closing commit of the series)"

WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=False
    )


@pytest.fixture(scope="module")
def history() -> None:
    shallow = _git("rev-parse", "--is-shallow-repository").stdout.strip()
    assert shallow == "false", (
        "this test reads the registry's commits from history, and this clone "
        "is shallow: run `git fetch --unshallow` (CI's check job checks out "
        "with fetch-depth: 0 for this)"
    )


def section(text: str, heading: str) -> str:
    """From `heading` (a whole line) to the next heading of its level or above."""
    level = len(heading) - len(heading.lstrip("#"))
    start = text.index(f"\n{heading}\n") + 1
    following = re.compile(rf"^#{{1,{level}}} ", re.M)
    found = following.search(text, start + len(heading))
    return text[start : found.start() if found else len(text)]


def zoo() -> str:
    return section(TASKS.read_text(encoding="utf-8"), "# The zoo series")


def registry() -> list[tuple[str, str]]:
    """The zoo series' batch table, as `(id, status)` rows in file order."""
    table = section(zoo(), "## The batches, with final status")
    return [
        (cells[0], cells[-1])
        for line in table.splitlines()
        if line.startswith("| V")
        for cells in [[cell.strip() for cell in line.strip("|").split("|")]]
    ]


def released() -> tuple[str, str]:
    """The newest versioned `CHANGELOG.md` heading's version, and its section."""
    text = CHANGELOG.read_text(encoding="utf-8")
    heading = re.search(r"^## (\d+\.\d+\.\d+)\b.*$", text, re.M)
    assert heading is not None, "CHANGELOG.md has no versioned heading"
    return heading.group(1), section(text, heading.group(0))


# --------------------------------------------------------------------------
# The version.
# --------------------------------------------------------------------------


def test_the_version_is_one_number_wherever_it_is_written():
    """`pyproject.toml`, the package, `uv.lock` and the changelog agree.

    V4 moved it to `0.0.2`: nothing is frozen, and the event-code set grew
    (`no_trace`, V2). It stays `0.0.x` until something freezes (`CLAUDE.md`
    standing rule 7), which is the one thing this test says about its value.
    """
    project = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    declared = project["project"]["version"]
    lock = (REPO / "uv.lock").read_text(encoding="utf-8")
    locked = re.search(
        r'^name = "spanweave-live"\nversion = "([^"]+)"\n'
        r'source = \{ editable = "\." \}',
        lock,
        re.M,
    )
    assert locked is not None
    version, _ = released()
    assert declared == spanweave_live.__version__ == locked.group(1) == version
    assert re.fullmatch(r"0\.0\.\d+", declared), "pre-1.0, by 0.0.x"


#: A `CHANGELOG.md` entry's date, the last thing on its heading.
DATED = re.compile(r".+ \((\d{4}-\d\d-\d\d)\)")


def test_the_version_s_changelog_entries_are_the_registry_s_batches():
    """One `### <id> — …` entry per zoo batch under the version, newest first.

    Above them, and only above them, the version carries the entries of the
    commits made after the series closed, newest first, as `## 0.0.1` carries
    the receiver series' (`The record made true — …` above `R9`). Such an
    entry's heading names no batch and ends in its date, and the dates run
    newest first down to the close's, V4's. Below the batches it is red.
    """
    _, entries = released()
    headings = re.findall(r"^### (.*)$", entries, re.M)
    first = next(
        (at for at, heading in enumerate(headings) if re.match(r"\S+ — ", heading)),
        len(headings),
    )
    later, batches = headings[:first], headings[first:]
    named = [heading.partition(" — ")[0] for heading in batches]
    assert named == [batch for batch, _ in reversed(registry())], (
        f"below the batches, an entry names no batch: {batches}"
    )
    dates = []
    for heading in [*later, batches[0]]:
        dated = DATED.fullmatch(heading)
        assert dated is not None, f"an entry is undated: {heading}"
        dates.append(dated.group(1))
    assert dates == sorted(dates, reverse=True), f"not newest first: {later}"


# --------------------------------------------------------------------------
# The registry.
# --------------------------------------------------------------------------


def test_the_zoo_registry_lists_its_batches_in_the_order_they_ran():
    rows = registry()
    assert [batch for batch, _ in rows] == ZOO_BATCHES
    stated = re.search(r"^(\w+) batches across (\w+) runs", zoo(), re.M)
    assert stated is not None
    assert WORDS[stated.group(1).lower()] == len(rows)
    runs = re.findall(r"run (\d) was (V\w+(?: → V\w+)*)", zoo())
    assert [batch for _, chain in runs for batch in chain.split(" → ")] == ZOO_BATCHES
    assert WORDS[stated.group(2)] == len(runs)


def test_each_registered_commit_is_its_batch(history):
    """Every sha but the last is a batch commit of this branch, for that batch.

    Not a `plan:` commit (they interleave, one after each batch), an ancestor
    of the tip, and a body that names the batch by its id as a word. The word
    alone does not tell the batches apart: `V1` matches `V1a`'s body
    (`a856ec2`, "V1's §4 thread"), and V0's `024fc66` names V1, V2 and V3.
    What holds the registry is that match **and** the shas' uniqueness, the
    last assert: V1 registered as `024fc66` passes every check of its row and
    is red only there.
    """
    rows = registry()
    *batches, (last, closing) = rows
    assert (last, closing) == ("V4", CLOSING)
    shas = []
    for batch, status in batches:
        done = re.fullmatch(r"\*\*done\*\* \(`([0-9a-f]{7})`\)", status)
        assert done is not None, f"{batch}: {status}"
        sha = done.group(1)
        assert _git("merge-base", "--is-ancestor", sha, "HEAD").returncode == 0, sha
        message = _git("log", "-1", "--format=%s%n%b", sha).stdout
        subject, _, body = message.partition("\n")
        assert not subject.startswith("plan:"), f"{batch}: {sha} is {subject!r}"
        assert re.search(rf"\b{re.escape(batch)}\b", body), f"{batch}: {sha}"
        shas.append(sha)
    assert len(set(shas)) == len(shas)


def test_every_plan_citation_resolves(history):
    """Each `git show <sha>:WORKPLAN.md` a document gives is a file there."""
    cited = set()
    for name in ("TASKS.md", "CLAUDE.md", "CHANGELOG.md", "CONTRIBUTING.md"):
        text = (REPO / name).read_text(encoding="utf-8")
        cited.update(re.findall(r"git show ([0-9a-f]{7,40}):WORKPLAN\.md", text))
    assert cited
    for sha in sorted(cited):
        assert _git("cat-file", "-e", f"{sha}:WORKPLAN.md").returncode == 0, sha


def test_the_decisions_log_is_as_long_as_it_says():
    log = section(zoo(), "## Decisions taken  *(`WORKPLAN.md` §3, folded)*")
    stated = re.search(r"^(\w+) rows", log, re.M)
    assert stated is not None
    rows = [
        line for line in log.splitlines() if re.match(r"\| \d{4}-\d\d-\d\d \|", line)
    ]
    assert WORDS[stated.group(1).lower()] == len(rows)


def test_the_reader_s_half_of_l1_is_the_commit_spanweave_registers_for_w1():
    """L1's disposition names W1's sha; spanweave's own registry, at the pin, agrees."""
    stated = re.findall(r"spanweave's W1 \(`([0-9a-f]{7})`\)", zoo())
    upstream = (REPO / "corpus" / "TASKS.md").read_text(encoding="utf-8")
    row = re.search(r"^\| W1 \|.* done `([0-9a-f]{7})` \|$", upstream, re.M)
    assert row is not None
    assert stated and set(stated) == {row.group(1)}


# --------------------------------------------------------------------------
# CLAUDE.md.
# --------------------------------------------------------------------------


def test_claude_md_says_whether_a_series_is_open_as_the_tree_does():
    """A plan file exists exactly while `CLAUDE.md` says a series is open.

    The receiver series' close left the other half of this false for a day
    (`TASKS.md`, R9): the plan was gone and `CLAUDE.md` still described it.
    """
    claude = CLAUDE.read_text(encoding="utf-8")
    says_open = re.search(r"series is open on `\w+`", claude) is not None
    says_none = "No series is open at this tip" in claude
    assert says_open != says_none
    assert says_open == PLAN.exists()


def test_standing_rule_one_names_every_source_spec_1_1_names():
    """Rule 1 names the adapters and the envelope, as `SPEC.md` §1.1 does (V2)."""
    claude = CLAUDE.read_text(encoding="utf-8")
    rule = claude[claude.index("1. **It never reads a dialect.**") :]
    rule = " ".join(rule[: rule.index("\n\n2. ")].split())
    spec = " ".join(
        section(SPEC.read_text(encoding="utf-8"), "### 1.1 No dialect").split()
    )
    for source, in_spec in (
        ("`spanweave.adapters.classify`", "`spanweave.adapters.classify`"),
        ("the claiming adapter's `parse`", "the claiming adapter's `parse`"),
        ("`envelope()`", "`spanweave.envelope(record)`"),
    ):
        assert source in rule, source
        assert in_spec in spec, in_spec
    assert "unpacked from an OTLP export" in rule
    assert "(`SPEC.md` §1.1.)" in rule


def test_claude_md_s_make_conformance_line_names_the_files_the_target_runs():
    """`CLAUDE.md`'s `make conformance` line names what the Makefile runs.

    V0 added the zoo gate to the target, and README's line with it; this line
    named gate A's file alone until the series' cold review found it (run 1's
    R-4, run 2's R-2).
    """
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    target = makefile[makefile.index("\nconformance:\n") + 1 :]
    runs = set(re.findall(r"tests/\w+\.py", target[: target.index("\n\n")]))
    line = re.search(
        r"^make conformance +#.*$", CLAUDE.read_text(encoding="utf-8"), re.M
    )
    assert line is not None
    assert runs
    assert set(re.findall(r"tests/\w+\.py", line.group(0))) == runs


def test_ci_s_check_job_has_the_history_this_file_reads():
    """The claim in this module's docstring, held where CI reads it."""
    workflow = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    check = workflow[workflow.index("  check:") : workflow.index("  conformance:")]
    assert re.search(r"^\s+fetch-depth: 0$", check, re.M)
