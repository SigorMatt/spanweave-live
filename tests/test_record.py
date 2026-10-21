"""The record a series leaves behind, held to what it says (V4; B10).

A series closes by deleting its `WORKPLAN.md` and folding what outlives it into
`TASKS.md`, and the files a cold session reads first -- `CLAUDE.md`, then
`TASKS.md` -- are then the only place the series is described. Each sentence
below is one of theirs that a test can check without running the library:
the version is one number wherever it is written, the registry names the
batches in the order they ran and each with the commit that closed it, the
decisions log is the plan's §3 at the plan state it cites, as it says, the
reader's half of L1 is the commit spanweave's own registry says it is wherever
it is cited, the entries made after the close run newest first by their
commits, and `CLAUDE.md` says whether a series is open as the tree does, cites
each closed series' last plan state, names every source of a trace id
`SPEC.md` §1.1 names, and names on its `make conformance` line the files that
target runs; `SPEC.md` §8.7's count of the CLI's process tests is
`tests/test_cli.py`'s collection, measured; and `CONTRIBUTING.md`'s rule
against a test that opens a real socket names, as its exceptions, exactly the
test files that import a socket module.

V4 wrote this file for the zoo series, and B10 holds the backlog series the
same way: each series in `SERIES` has its registry, its changelog heading, its
post-close entries and its decisions log held by the same tests, one case a
series; L1's W1 sha is the zoo's alone.

The registry's commits and the plan files are read from history, so the tests
that take the `history` fixture need a git binary and a clone with history:
CI's `check` job checks out with `fetch-depth: 0` for them. Without one they
fail by name rather than passing without having looked: no git binary, a tree
with no `.git` (an sdist, which ships `tests/`, or a `git archive` export),
and a shallow clone are three different messages, and only the last is
fixed by `git fetch --unshallow`.
"""

import ast
import re
import shutil
import subprocess
import sys
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

#: The backlog series' batches in the order they ran (run 1: B1, B2, B3; run 2:
#: B4 to B10).
BACKLOG_BATCHES = [f"B{n}" for n in range(1, 11)]

#: Each series this file holds, newest first: its batches in the order they
#: ran, and the version its close shipped as, whose `CHANGELOG.md` heading
#: carries its entries. The receiver series (R0-R9) is older than this file
#: and its registry is held by review.
SERIES = {
    "backlog": (BACKLOG_BATCHES, "0.0.3"),
    "zoo": (ZOO_BATCHES, "0.0.2"),
}

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
    """A git binary, a `.git` of this tree's own, and all of its history.

    The `.git` is looked for in the tree itself, a directory in a clone and a
    file in a worktree: an sdist unpacked inside some other clone would
    otherwise have git answer for that clone.
    """
    assert shutil.which("git") is not None, (
        "this test reads the registry's commits from history, and there is no "
        "git binary on the PATH"
    )
    assert (REPO / ".git").exists(), (
        "this test reads the registry's commits from history, and this tree "
        "has no .git (an sdist or a `git archive` export has none): run it in "
        "a clone with history"
    )
    shallow = _git("rev-parse", "--is-shallow-repository").stdout.strip()
    assert shallow == "false", (
        "this test reads the registry's commits from history, and this clone "
        "is shallow: run `git fetch --unshallow` (CI's check job checks out "
        "with fetch-depth: 0 for this)"
    )


def plan_states() -> dict[str, tuple[str, str]]:
    """Each closed series, by name: its closing commit and its plan's last state.

    Read from history alone: a series closes with the one commit that deletes
    `WORKPLAN.md`, whose subject says "the <name> series closes", and the
    plan's last state is the last commit before that one to change the file.
    """
    deleted = _git(
        "log",
        "--full-history",
        "--no-merges",
        "--diff-filter=D",
        "--format=%H %s",
        "--",
        "WORKPLAN.md",
    ).stdout
    states = {}
    for line in deleted.splitlines():
        close, _, subject = line.partition(" ")
        named = re.search(r"\bthe (\w+) series closes\b", subject)
        assert named is not None, f"{close} deletes the plan: {subject!r}"
        last = _git("log", "-1", "--format=%H", f"{close}^", "--", "WORKPLAN.md")
        assert last.stdout.strip(), close
        assert named.group(1) not in states, named.group(1)
        states[named.group(1)] = (close, last.stdout.strip())
    assert states, "no commit deletes WORKPLAN.md"
    return states


def cited_states(text: str, pattern: str) -> dict[str, str]:
    """`pattern`'s `series` and `sha` groups in `text`, whitespace folded.

    One sha a series: a series cited at two states is red here.
    """
    found: dict[str, set[str]] = {}
    for match in re.finditer(pattern, " ".join(text.split())):
        found.setdefault(match["series"], set()).add(match["sha"])
    assert all(len(shas) == 1 for shas in found.values()), found
    return {series: shas.pop() for series, shas in found.items()}


def table_rows(text: str) -> list[str]:
    """The dated rows of a decisions-log table, in file order."""
    return [
        line for line in text.splitlines() if re.match(r"\| \d{4}-\d\d-\d\d \|", line)
    ]


def section(text: str, heading: str) -> str:
    """From `heading` (a whole line) to the next heading of its level or above."""
    level = len(heading) - len(heading.lstrip("#"))
    start = text.index(f"\n{heading}\n") + 1
    following = re.compile(rf"^#{{1,{level}}} ", re.M)
    found = following.search(text, start + len(heading))
    return text[start : found.start() if found else len(text)]


def registered(series: str) -> str:
    """`TASKS.md`'s part for `series`, from its `# The <name> series` heading."""
    return section(TASKS.read_text(encoding="utf-8"), f"# The {series} series")


def zoo() -> str:
    return registered("zoo")


def registry(series: str = "zoo") -> list[tuple[str, str]]:
    """A series' batch table, as `(id, status)` rows in file order."""
    batches, _ = SERIES[series]
    prefix = f"| {batches[0][0]}"
    table = section(registered(series), "## The batches, with final status")
    return [
        (cells[0], cells[-1])
        for line in table.splitlines()
        if line.startswith(prefix)
        for cells in [[cell.strip() for cell in line.strip("|").split("|")]]
    ]


def released() -> tuple[str, str]:
    """The newest versioned `CHANGELOG.md` heading's version, and its section."""
    text = CHANGELOG.read_text(encoding="utf-8")
    heading = re.search(r"^## (\d+\.\d+\.\d+)\b.*$", text, re.M)
    assert heading is not None, "CHANGELOG.md has no versioned heading"
    return heading.group(1), section(text, heading.group(0))


def shipped(series: str) -> str:
    """The `CHANGELOG.md` section of the version `series` shipped as.

    Its heading names the version and the series: `## <version> — the <name>
    series (<date>)`.
    """
    _, version = SERIES[series]
    text = CHANGELOG.read_text(encoding="utf-8")
    heading = re.search(
        rf"^## {re.escape(version)} — the {series} series \(\d{{4}}-\d\d-\d\d\)$",
        text,
        re.M,
    )
    assert heading is not None, f"CHANGELOG.md has no {version} heading for {series}"
    return section(text, heading.group(0))


# --------------------------------------------------------------------------
# The version.
# --------------------------------------------------------------------------


def test_the_version_is_one_number_wherever_it_is_written():
    """`pyproject.toml`, the package, `uv.lock` and the changelog agree.

    V4 moved it to `0.0.2`: nothing is frozen, and the event-code set grew
    (`no_trace`, V2). B10 moved it to `0.0.3`: a `Router` field and a CLI flag
    were added (B1), `released` gained its version (B4) and a refusal its
    `Status` body (B3). It stays `0.0.x` until something freezes (`CLAUDE.md`
    standing rule 7), which is the one thing this test says about its value
    beyond its being the newest series' (`SERIES`).
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
    _, newest = next(iter(SERIES.values()))
    assert version == newest, (version, newest)
    assert re.fullmatch(r"0\.0\.\d+", declared), "pre-1.0, by 0.0.x"


#: A `CHANGELOG.md` entry's date, the last thing on its heading.
DATED = re.compile(r".+ \((\d{4}-\d\d-\d\d)\)")


@pytest.mark.parametrize("series", list(SERIES))
def test_the_version_s_changelog_entries_are_the_registry_s_batches(series):
    """One `### <id> — …` entry per batch under the series' version, newest first.

    Above them, and only above them, the version carries the entries of the
    commits made after the series closed, newest first, as `## 0.0.1` carries
    the receiver series' (`The record made true — …` above `R9`). Such an
    entry's heading names no batch and ends in its date, and the dates run
    newest first down to the close's, V4's or B10's. Below the batches it is
    red. Every post-close entry of the zoo series is dated 2026-10-20, so the
    dates do not order them among themselves; their commits do, in the next
    test. The backlog series has none at its close.
    """
    entries = shipped(series)
    headings = re.findall(r"^### (.*)$", entries, re.M)
    first = next(
        (at for at, heading in enumerate(headings) if re.match(r"\S+ — ", heading)),
        len(headings),
    )
    later, batches = headings[:first], headings[first:]
    named = [heading.partition(" — ")[0] for heading in batches]
    assert named == [batch for batch, _ in reversed(registry(series))], (
        f"below the batches, an entry names no batch: {batches}"
    )
    dates = []
    for heading in [*later, batches[0]]:
        dated = DATED.fullmatch(heading)
        assert dated is not None, f"an entry is undated: {heading}"
        dates.append(dated.group(1))
    assert dates == sorted(dates, reverse=True), f"not newest first: {later}"


@pytest.mark.parametrize("series", list(SERIES))
def test_the_post_close_entries_run_newest_first_by_their_commits(history, series):
    """Each entry above the batches is its commit's, and they run newest first.

    The mapping from an entry to its commit is the entry's own: each one opens
    with "Derived parent `<sha>`.", and its commit is that parent's one child
    in the tip's history, which changes `CHANGELOG.md` and whose parent's
    `CHANGELOG.md` has no such heading. `git blame` on the heading gives the
    same commits today, but it names the last commit to touch a line, and a
    heading corrected later would move it; the cited parent does not move.
    The commits must then run newest first, each a strict descendant of the
    next, and the oldest one a strict descendant of the commit that closed
    the series. Swapping the newest and the oldest entry, which every date
    survives (the bounded fix review's R-7), is red here. The zoo series has
    such entries and must; the backlog series has none at its close, and an
    entry added above B10 is held as the zoo's are.
    """
    entries = shipped(series)
    later = []
    for block in re.split(r"^### ", entries, flags=re.M)[1:]:
        heading, _, body = block.partition("\n")
        if re.match(r"\S+ — ", heading):
            break
        later.append((heading, body))
    assert later or series != "zoo"
    children: dict[str, list[str]] = {}
    for line in _git("rev-list", "--parents", "HEAD").stdout.splitlines():
        commit, *parents = line.split()
        for parent in parents:
            children.setdefault(parent, []).append(commit)
    commits = []
    for heading, body in later:
        cited = re.match(r"\s*Derived parent `([0-9a-f]{7,40})`\.", body)
        assert cited is not None, f"an entry names no derived parent: {heading}"
        parent = _git("rev-parse", "--verify", f"{cited.group(1)}^{{commit}}")
        assert parent.returncode == 0, cited.group(1)
        sha = parent.stdout.strip()
        assert len(children.get(sha, [])) == 1, (heading, children.get(sha))
        (commit,) = children[sha]
        changed = _git("diff", "--quiet", sha, commit, "--", "CHANGELOG.md")
        assert changed.returncode == 1, f"{commit} leaves CHANGELOG.md: {heading}"
        before = _git("show", f"{sha}:CHANGELOG.md").stdout
        assert f"\n### {heading}\n" not in before, f"already at {sha}: {heading}"
        commits.append(commit)
    close, _ = plan_states()[series]
    for newer, older in zip(
        commits, [*commits[1:], close][: len(commits)], strict=True
    ):
        assert newer != older, newer
        assert _git("merge-base", "--is-ancestor", older, newer).returncode == 0, (
            f"not newest first by commit: {older} is not before {newer}"
        )


# --------------------------------------------------------------------------
# The registry.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("series", list(SERIES))
def test_the_registry_lists_its_batches_in_the_order_they_ran(series):
    batches, _ = SERIES[series]
    letter = batches[0][0]
    rows = registry(series)
    assert [batch for batch, _ in rows] == batches
    text = registered(series)
    stated = re.search(r"^(\w+) batches across (\w+) runs", text, re.M)
    assert stated is not None
    assert WORDS[stated.group(1).lower()] == len(rows)
    runs = re.findall(rf"run (\d) was ({letter}\w+(?: → {letter}\w+)*)", text)
    assert [batch for _, chain in runs for batch in chain.split(" → ")] == batches
    assert WORDS[stated.group(2)] == len(runs)


@pytest.mark.parametrize("series", list(SERIES))
def test_each_registered_commit_is_its_batch(history, series):
    """Every sha but the last is a batch commit of this branch, for that batch.

    Not a `plan:` commit (they interleave, one after each batch), an ancestor
    of the tip, and a body that names the batch by its id as a word. The word
    alone does not tell the batches apart: `V1` matches `V1a`'s body
    (`a856ec2`, "V1's §4 thread"), and V0's `024fc66` names V1, V2 and V3.
    What holds the registry is that match **and** the shas' uniqueness, the
    last assert: V1 registered as `024fc66` passes every check of its row and
    is red only there. The backlog's `B1` does not match `B10`'s body, since
    the word boundary needs a non-word character after the `1`.
    """
    rows = registry(series)
    *batches, (last, closing) = rows
    assert (last, closing) == (SERIES[series][0][-1], CLOSING)
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


@pytest.mark.parametrize("series", list(SERIES))
def test_the_decisions_log_is_the_plan_s_at_the_plan_state_it_cites(history, series):
    """The folded log is the plan's §3 at the sha it cites, but for what it says.

    The sha the section cites must be the series' last plan state, read from
    history (`plan_states`). The log says how many rows it has, how many of
    them moved from the plan, whether a sentence of one row moved, and how
    many were taken after the close; each count is held, and the moved rows
    are the plan's rows in the plan's order. The zoo's says one sentence of
    one row moved, and that row is the plan's with the sentence the paragraph
    below the table quotes replaced by the sentence it says the row now
    carries; the backlog's says none did, and every moved row is the plan's as
    it stood. A row dropped and the count lowered (the review's X8), and
    thread V2(c) undone in the row (X6), are red here; the log's length alone
    held neither.
    """
    log = section(
        registered(series), "## Decisions taken  *(`WORKPLAN.md` §3, folded)*"
    )
    cited = set(re.findall(r"git show ([0-9a-f]{7,40}):WORKPLAN\.md", log))
    _, last = plan_states()[series]
    assert len(cited) == 1 and last.startswith(cited.pop()), (cited, last)
    plan = _git("show", f"{last}:WORKPLAN.md")
    assert plan.returncode == 0, last
    planned = table_rows(section(plan.stdout, "## 3. Decisions log"))
    rows = table_rows(log)

    prose = " ".join(log.split())
    stated = re.search(
        r"\b(\w+) rows: (\w+) moved here as they stood(?: but for (\w+) sentence"
        r" of (\w+) row)?, and (?:the last )?(\w+) taken after the close",
        prose,
    )
    assert stated is not None
    total, moved, sentences, changed, after = (
        0 if word is None else {**WORDS, "none": 0}[word.lower()]
        for word in stated.groups()
    )
    assert (total, moved) == (len(rows), len(planned))
    assert after == total - moved and sentences == changed <= 1
    assert all(row.split(" | ")[1] == "review" for row in rows[moved:]), rows[moved:]

    differ = [at for at, row in enumerate(rows[:moved]) if row != planned[at]]
    assert len(differ) == changed, differ
    if not changed:
        return
    was = re.search(r'the row said the receiver "([^"]+)"', prose)
    now = re.search(r"The row now says what is true: (.+?\.) ", prose)
    assert was is not None and now is not None
    sentence = now.group(1)
    (at,) = differ
    assert rows[at] == planned[at].replace(
        f", and {was.group(1)}.", f". {sentence[0].upper()}{sentence[1:]}"
    )


def test_the_reader_s_half_of_l1_is_the_commit_spanweave_registers_for_w1():
    """L1's W1 sha, in the registry and the changelog; spanweave's registry agrees.

    The changelog's V4 entry gives the sha too (`spanweave's W1 \\`4ecf414\\``),
    and a changed one there (the review's X13) was held by nothing.
    """
    upstream = (REPO / "corpus" / "TASKS.md").read_text(encoding="utf-8")
    row = re.search(r"^\| W1 \|.* done `([0-9a-f]{7})` \|$", upstream, re.M)
    assert row is not None
    for text in (zoo(), CHANGELOG.read_text(encoding="utf-8")):
        stated = re.findall(r"spanweave's W1 \(?`([0-9a-f]{7,40})`", text)
        assert stated and set(stated) == {row.group(1)}, stated


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


def test_claude_md_and_the_changelog_cite_each_closed_series_last_plan_state(
    history,
):
    """Each closed series' plan is cited at its last state, read from history.

    `CLAUDE.md` says where each closed series' plan last stood, and the
    changelog's preamble where its entries' plan citations resolve. Each must
    name every series `plan_states` finds, and that series' last state: a sha
    that resolves to some other `WORKPLAN.md` (the zoo's `5369cac`, the
    review's X9, or the receiver's `b500342`, X10) passed the resolvability
    test alone.
    """
    states = {series: last for series, (_, last) in plan_states().items()}
    for text, pattern in (
        (
            CLAUDE.read_text(encoding="utf-8"),
            r"the (?P<series>\w+) series' (?:last state is )?at "
            r"`git show (?P<sha>[0-9a-f]{7,40}):WORKPLAN\.md`",
        ),
        (
            CHANGELOG.read_text(encoding="utf-8").split("\n## ", 1)[0],
            r"at `git show (?P<sha>[0-9a-f]{7,40}):WORKPLAN\.md` "
            r"for the (?P<series>\w+) series'",
        ),
    ):
        cited = cited_states(text, pattern)
        assert set(cited) == set(states), (cited, states)
        for series, sha in cited.items():
            assert states[series].startswith(sha), (series, sha, states[series])


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


def _reaches_a_process(source: str) -> set[str]:
    """The module-level names in `source` whose bodies start the CLI, closed.

    A name starts it when its body names `CLI` (the argv a run is given) or
    `subprocess`, or names another module-level name that does: `run` and
    `serving` directly, and through them every test that calls one.
    """
    tree = ast.parse(source)
    uses = {
        node.name: {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    reaching = {name for name, used in uses.items() if used & {"CLI", "subprocess"}}
    while True:
        grown = reaching | {name for name, used in uses.items() if used & reaching}
        if grown == reaching:
            return reaching
        reaching = grown


def test_spec_s_count_of_the_cli_s_process_tests_is_the_measured_one():
    """§8.7's two numbers and its nine names, re-derived from `tests/test_cli.py`.

    The items are pytest's own collection of the file, each parametrized case
    one item; an item runs the CLI as a process when its test function reaches
    `CLI` or `subprocess` (`_reaches_a_process`). The nine §8.7 names must be
    exactly the items that do not. The sentence said 72 of 81 from the receiver
    series until the bounded fix review of PR #2 measured 77 of 86 (its R-3),
    and 78 of 87 since B1 added the `--max-unclaimed-traces` process test.
    """
    text = section(
        SPEC.read_text(encoding="utf-8"), "### 8.7 What this section is tested against"
    )
    paragraph = text.split("\n\n")[1]
    stated = re.search(
        r"\*\*(\d+) of its (\d+) collected items run the CLI as a\s+process\*\*",
        paragraph,
    )
    other = re.search(r"The other \*\*(\w+)\*\*", paragraph)
    assert stated is not None and other is not None
    process, total = int(stated.group(1)), int(stated.group(2))
    named = re.findall(r"`(test_\w+)`", paragraph)
    assert len(set(named)) == len(named) == WORDS[other.group(1)] == total - process

    collected = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "tests/test_cli.py",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert collected.returncode == 0, collected.stdout + collected.stderr
    items = [
        line.split("::", 1)[1]
        for line in collected.stdout.splitlines()
        if line.startswith("tests/test_cli.py::")
    ]
    functions = [item.split("[", 1)[0] for item in items]
    source = (REPO / "tests" / "test_cli.py").read_text(encoding="utf-8")
    reaching = _reaches_a_process(source)
    in_process = [name for name in functions if name not in reaching]
    assert len(items) == total
    assert len(functions) - len(in_process) == process
    assert sorted(in_process) == sorted(named)


#: The modules a test file opens a real socket with: the stdlib's socket layer
#: and the two HTTP halves built on it.
SOCKET_MODULES = frozenset({"socket", "socketserver", "http.client", "http.server"})


def _opens_a_socket(path: Path) -> bool:
    """Whether a test file imports a module it could open a real socket with.

    Read off the file's imports, not its text: `tests/test_gates.py` and
    `tests/gates.py` hold `import socket` in strings, as planted violations,
    and open nothing.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)
    return not imported.isdisjoint(SOCKET_MODULES)


def test_contributing_s_socket_rule_names_the_test_files_that_open_one():
    """`CONTRIBUTING.md`'s "no test that … opens a real socket" names its
    exceptions, and they are the test files that do (the zoo series' run 2,
    R-10; B9).

    The exceptions are the ones `SPEC.md` §7.2 and §8.7 argue: the endpoint's
    tests, bound on `127.0.0.1` port 0, and `tests/test_cli.py`'s spawned
    `serve`. Every `tests/<file>.py` the rule's bullet names must import a
    socket module, and every test file that imports one must be named there, so
    a new test that opens a socket either is argued in the rule or is red here.
    """
    text = (REPO / "CONTRIBUTING.md").read_text(encoding="utf-8")
    start = text.index("**No test that reads the real clock, opens a real socket")
    end = text.find("\n- [ ]", start)
    bullet = text[start : end if end != -1 else text.index("\n## ", start)]
    named = set(re.findall(r"`(tests/\w+\.py)`", bullet))
    opening = {
        f"tests/{path.name}"
        for path in sorted((REPO / "tests").glob("*.py"))
        if _opens_a_socket(path)
    }
    assert opening, "no test file opens a socket: the scan reads nothing"
    assert named == opening
