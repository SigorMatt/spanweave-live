# REVIEW-2026-10-23 — backlog series, run 2 and its close (cold read)

Range: `72d60e8..6aa7750` on `backlog`: B4 `707e58a`, `plan:` `7319ac2`,
B5 `6d2c559`, `plan:` `f0987b5`, B6 `a141fd2`, `plan:` `3159579`, B7 `a467bc5`,
`plan:` `3937f12`, B8 `a743893`, `plan:` `40f0915`, B9 `f6b971b`, `plan:`
`fff8a9e`, B10 `6aa7750`.
Rules: `WORKPLAN.md` §0.2 at `fff8a9e` (`git show fff8a9e:WORKPLAN.md`; B10
deleted the file), and `CONTRIBUTING.md` and `CLAUDE.md` at each commit and at
the tip. Run 1's half, `patches/REVIEW-2026-10-22.md`, was read so as not to
re-raise its findings; where one here extends one there, it is cited as
"run 1's R-n".

**Grading.** This review uses `WORKPLAN.md` §2's merge rule, as this review's
brief states it: **a defect this series introduced is blocking, whether or not
another claim depends on it.** Anything older is a **thread**, given with its
measurements. A **note** records a weakness that is not a defect: a mutation
that survives, or a wording that is loose but true. This is stricter than run
1's grading, which called a defect introduced here with no dependent claim
"non-blocking". Every blocking finding below is a document sentence, a record
line or a process record. None is a behaviour defect in `spanweave_live/`.

Method:
- **Worktrees.** Detached worktrees by absolute path under the aux
  scratchpad: one at each code commit, one at its derived parent (`<sha>^`,
  resolved with `git rev-parse`), and one at `6aa7750`. Each has `corpus/` at
  `17edf61` and `showcase/` at `aa1847f`, cloned from the repo's module store,
  and a venv from `uv sync --extra dev --frozen`, run offline.
- **Clones for edits.** Mutations and planted defects were made only in
  separate `git clone`s under the scratchpad, never in a worktree.
- **One sub-agent per code commit** (seven).
- **Re-derivations** used scripts under the scratchpad that import only
  `spanweave_live`, `spanweave` and the stdlib. None imports a test helper.
- **Not run:** `make install-check`, which needs network. B9's sdist was
  instead built offline with `uv build --sdist --offline` and audited.

## Verdict

**Nine blocking findings, all introduced by this series. Each is a sentence,
a record line or a process record; no library behaviour is wrong.**

Four new document sentences claim more than the code or the tests do:
- R-1: B5's §5.2 sentence;
- R-2: B6's §3.2 sentence and test docstring;
- R-3: B7's §1.3 sentence;
- R-4: B9's `CONTRIBUTING.md` sentence.

Four record lines in `TASKS.md` and `SPEC.md` are false or edited without
saying so (R-5 to R-8). R-9 is run 1's R-3 again: no CI ran on any run 2
batch tip.

Every number the series states that this review re-derived came out the
same: test counts, mutation counts, `released.version`, `ROOTLESS`, §5.3's
schedule, gate A's crossing count, the push mutation's 19, and the
version 0.0.3. The exceptions are the false sentences above.

Five threads are older than the series (T-1 to T-5), and six notes follow
(N-1 to N-6).

## Per-commit checks

| Check | B4 `707e58a` | B5 `6d2c559` | B6 `a141fd2` | B7 `a467bc5` |
|---|---|---|---|---|
| Spec in the same commit | pass (§4.1, §5.4, §6.1; detail byte-identical to the parent's) | pass (§5.2, §5.3, §5.5; README trap 3); no code moved, but one new sentence is false (R-1) | pass (§3.2, §4.7); no code moved, but one clause is false (R-2) | pass (§1.3; CLAUDE.md rule 9); no library code moved; overclaim (R-3) |
| Red on the derived parent | 2 failed / 66 passed on `72d60e8` | pins, and they say so: 117 passed on `7319ac2` | pins, and they say so: 394 passed on `f0987b5` | 19 failed / 59 passed on `3159579`, as the body says |
| Parent sha recorded in the body | `72d60e8`, correct | `7319ac2`, correct | `f0987b5`, correct | `3159579`, correct |
| Named mutation caught | `version=None`: 2 red | reset deleted: 4 red in the whole suite, the four re-feed cases and nothing else, at the commit and at the tip; `ROOTLESS = ()`: 1 red | partial BOM handed on: 1 red on the new sweep, green on the parent's; drop after the last newline: 1 red on the new pass, the 28 existing tests green | exec dropped: 5 red; rule left out of `ALL_RULES`: 17 red |
| Two more mutations | `book.generation`, `index`, `len(_builders)+1`, `completed` given a version: all caught | reset set to `now`: 4 red; book backdated or opened at 0.0: 1 red each; each §5.3 number edited: red | count never incremented: red; one pair only: red; weak or same-trace count: **survived** (N-2) | output unsorted: caught; exact `==` for pickle: survived, equivalent; empty self-alias map: **survived**, not equivalent (N-3) |
| Ambient runtime outside `SEAMS` | none (imports unchanged; gates green) | none | none | none |
| Pins | spanweave = corpus = `uv.lock` `17edf61`; agentgolden = showcase = `uv.lock` `aa1847f`; `test_pins.py` green at every commit | | | |
| One concern | yes | yes | yes | yes |
| Suite count | 998 (§4: 998) | 1006 (§4: 1006) | 1008 (§4: 1008) | 1028 (§4: 1028); gates 71→91 |

| Check | B8 `a743893` | B9 `f6b971b` | B10 `6aa7750` |
|---|---|---|---|
| Spec in the same commit | none needed (tests and CHANGELOG only) | pass (§4.2, §6.5, §7.2; CONTRIBUTING); one sentence false (R-4) | §0 changed, with a misattribution (R-7) |
| Red on the derived parent | each plant (X6, X8, X9, X10, X13, R-7's swap): parent's test 12 passed, B8's test 1 failed / 13 passed | socket test 1 red on `40f0915`; joiner test a pin, green there, and the body says so | 6 failed / 14 passed on `fff8a9e`, as the body says |
| Parent sha recorded in the body | `3937f12`, correct | `40f0915`, correct | `fff8a9e`, correct |
| Named mutation caught | the body's two reproduce | cursor rolled back: 2 red; `import socket` and `from http import client` planted: red | `__version__` left at 0.0.2: red |
| Two more mutations | last plan state taken at the close: 2 red; "one child" relaxed: survived, redundant with the ancestry check; "review" batch check dropped: survived on a defect the real test catches | `"http.client"` dropped from the list: survived, equivalent today; `imported.add(node.module)` dropped: **survived**, not equivalent (R-4) | open-items row pointed at `7319ac2`: **survived**; an in-place close mark deleted: **survived** (N-5) |
| Ambient runtime outside `SEAMS` | none | none (`tools/` is outside `spanweave_live/`) | none; only `__version__` moved |
| Pins | as above | as above | as above |
| One concern | yes | yes (five record items, one row) | yes (the close) |
| Suite count | 1030 (§4: 1030) | 1032 (§4: 1032); sdist ships `tools/` and its audit fails without it | 1037 (body: 1037); conformance 126, showcase 12; `--version` 0.0.3 |

The six `plan:` commits each touch `WORKPLAN.md` alone. Each row correction
recorded in §4 matches what was measured here, except the T9 premise (R-5).

## Independent re-derivations

**B4.** The fake clock and `Completion(policies=(Cap(4), Quiet(5.0)))`
were used, with traces t1 and t2 and a no-trace record interleaved.
- **First generation.** `released.version` = 4 = `Completed.version` = the
  builder's version before the tick. The inputs were chosen so that 4 differs
  from the generation (1), the index (7), `len(builders)` and `routed`.
  `completed.version` is `None`, and the detail still says "released at
  version 4;".
- **Generation opened by a late arrival.** `released.version` = 3 =
  `Completed.version`. That is not the generation (2), the index (12) or the
  first generation's 4.
- **Version-bearing events.** Across all completion events, the only (code,
  version) pairs are (completed, None), (released, 4) and (released, 3). On
  `72d60e8` the script fails at the first assertion.
- **CLI.** `spanweave-live tail in.jsonl --out <dir> --once` over three spans
  writes this stderr line at `707e58a` and at `6aa7750`:
  `{"code": "released", "detail": "…released at version 3; …", "index": 3,
  "layer": "router", "trace_id": "tq", "version": 3}`. On the parent the line
  has no `version` key. No document quotes the line.

**B5.**
- **(a) Attach after routing.** z3-real was routed with `completion=None`,
  and `Quiet(1.0)` was attached at t=3600. Ticks at 3600, 3600.999 and 3601
  complete the trace at 3601 only, with `seconds` 1.0. The CLI half is also
  true: `cli.py` always builds a `Completion`, so every book opens at its
  first record, and end of input under `Cap(0)` reports `seconds` from it.
  The tick-only wording of §5.2 is false for one case (R-1).
- **(b) Second generation under `RootEnded(1.0)`.** Z3 and Z1 complete
  generation 1 at `last + 1.0`. Body 0 was re-fed at `+1.0`, and ticks at
  `+0.5`, `+1.0`, `+1.5`, `+3600` and 10^6 complete nothing.
- **(c) `ROOTLESS` and §5.3.** All twelve captures were built from their
  manifests, and roots were computed independently. Only z5 real and z5
  recorded have none, so `ROOTLESS` is Z5's two captures. Each of §5.3's
  numbers is re-derived:
  - **`now = k`:** under `Quiet(0.5)`, the tick minus `seconds` gives feed
    instants 0, 1, 2, …
  - **`last + 0.5`:** `RootEnded(1.0)` with no at-body tick fires at
    `last + 1.5`.
  - **"*N*-th record":** `Cap(N)` fires at record N, for N = 102, 31, 23 and
    26.
  - **The documents test:** each of the three, edited, is red. `ROOTLESS = ()`
    is red. `last + 0.5` and "*N*-th" are held as literals and `now = k` by a
    run, which is what CHANGELOG says.
- **(d) A root from an earlier generation.** A later generation is never
  completed by `RootEnded` alone. `Cap(0)` at end of input completes it at
  version 24 (z3) and 22 (z1) and writes `<id>.2.json`.
- **The reset deleted.** Deleting the per-generation `root_ended_at = None`
  makes exactly four tests red at `6d2c559` (1002 passed) and at `6aa7750`
  (1033 passed): the two re-feed pins × {z3, z1}.

**B6.**
- **The BOM sweep.** The stream was built here: a BOM, then lines with 2-, 3-
  and 4-byte characters. It was split two ways at every offset, plus one byte
  at a time, for 146 chunkings. Through the real Framer, all 146 equal the
  one-shot read.
  - The sweep crosses offsets 1 and 2 inside the BOM.
  - The control holds: the BOM's halves read in two calls are
    `undecodable_bytes`.
  - A framer that hands on a partial BOM is wrong on 3 chunkings (split at 1,
    split at 2, bytewise), and on 0 without the BOM.
  - `removeprefix` and `lstrip` framers are wrong on none (R-2, T-1).
- **Gate A's one-stream pass.** Pairs, relabelling, interleaving and chunking
  were all written here. The remainder was computed independently of the
  framer and checked equal to `pending_bytes` on every push. The pairs are
  1354: 55 renderings, 1460 pairs, and 1354 with both sides `.jsonl`.
  - At the first seed there are **1433 arrivals** where the remainder holds
    one trace's partial line while the other trace's bytes arrive. 213 pairs
    have none, at most 3 occur in any pair, and every pair equals its batch
    graph.
  - A print planted in the test also counts 1433.
  - Over all ten seeds the count is 15 389, from 1264 to 1974 per seed.
  - The test asserts only "> 0", at seed 0, and §4.7 and §4 say "at the first
    seed".
  - No `.jsonl` lacks its final newline, so the existing passes are
    line-atomic, as §4.7 says.

**B7.** Each form below was planted as a real module under `spanweave_live/`,
in a clone at `a467bc5` and again at `6aa7750`, with identical results. Each
was run through `gates.check_package(gates.ALL_RULES)`, and four together
through `pytest tests/test_gates.py`, which names exactly the banned files.

| Named `no-execution-of-content` | Not named |
|---|---|
| `eval(x)`, `exec(x)`, `builtins.eval`, `import builtins as b; b.exec`, `from builtins import eval as e`, `f = eval`; `import pickle`, `from pickle import loads`, `import pickle as p`, `from pickle import *`; `yaml.load(s)`, `import yaml as y; y.load`, `from yaml import load`, `from yaml import load as L`, and `yaml.load` in a nested subpackage | `getattr(builtins, "eval")` (stated, and held by a test); `m = yaml; m.load` (stated in the docstring only); `importlib.import_module("pickle")` (covered by §1.4's general limit); `__import__("pickle")`, `marshal.loads`, `import _pickle`, `import cPickle`, `import shelve`, `import dill`, `jsonpickle`, `plistlib.loads`, `compile(…)`, `runpy.run_path`, `code.InteractiveInterpreter().runsource`, `__builtins__['eval']`, `sys.modules['builtins'].eval`; `yaml.unsafe_load`, `yaml.full_load`, `yaml.load_all`, `yaml.full_load_all`, `yaml.unsafe_load_all`, `from yaml import unsafe_load`, `from yaml import *; load(s)` (none stated) |

The stated `getattr` limit holds: `getattr(builtins, "eval")` passes, and
`test_gates.py` holds that it does. The limit is not the whole of what passes
(R-3).

**B8.**
- **The zoo review's probes.** X6, X8, X9, X10 and X13 are defined in
  `reviews/2026-10-19-zoo-run2.md:812-816`, and R-7 in
  `reviews/2026-10-20-zoo-fixes.md`. Each was planted at the parent and at
  the commit:
  - at the parent: green (12 passed);
  - at the commit: red (1 failed, 13 passed), each with its own message.
    For example X8 shows `(9, 7) == (9, 8)`, and R-7's swap shows "567febe…
    is not before 1df7a35…".
- **Post-close order.** This was checked with plain `git rev-list --all
  --children`, not the test's code.
  - Each of the 14 cited "Derived parent" shas has exactly one child. That
    child changes `CHANGELOG.md`, adds that entry's heading, and has the
    matching subject.
  - Each child is the next-newer entry's cited parent, so the chain runs
    from `e883fa3` to `6024cb1` and the file is newest-first.
  - Two adjacent entries swapped with their dates unchanged is red. A cited
    sha with two children (`cddc694`) is red, with `assert 2 == 1`.
- **A tree with no `.git`.** A `git archive` export with corpus and showcase
  copied in gives 9 passed and 5 errors. Each error says "this tree has no
  .git (an sdist or a `git archive` export has none)". "Shallow" does not
  appear, nothing is skipped, and the exit code is 1. A `--depth 1` clone is
  named shallow. With `PATH=/nonexistent`, the error names no git binary.
- **Last plan states**, as history gives them: `b500342` (receiver),
  `3077bec` (zoo) and `fff8a9e` (backlog). Each closing commit's only parent
  is that state. CI's `check` job checks out with `fetch-depth: 0`
  (`ci.yml:47`).

**B9.**
- **(a) The push mutation.** `endpoint.py:439`'s `document(body)` was changed
  to `push(body)`. It takes down **19** tests at `40f0915` (of 1030), at
  `f6b971b` and at `6aa7750`: 18 in `test_endpoint.py` and 1 in
  `test_cli.py`. §7.2 states no count at the commit or at the tip. "ten" and
  "16" survive only in dated history (CHANGELOG, and `TASKS.md`'s closed
  R-14 row).
- **(b) Who opens a socket.** A pytest plugin written here wraps socket
  `__init__`, `bind`, `connect` and `connect_ex`, and `Popen`. Over the full
  suite (1032 passed), only `test_endpoint.py` (51 tests) and `test_cli.py`
  (7 tests, via the spawned `serve`) open an INET socket. Every `bind` is
  `('127.0.0.1', 0)`, and no other test spawns `serve`. So today's list
  matches the tests. The record test's guarantee does not (R-4).
- **(c) The lost window.** `Subscriptions.due` moves the cursor before the
  delta is asked for (`subscriptions.py:216-221`), and a refusal `continue`s
  (`routing.py:634`). A script of my own records one `delta_unavailable`,
  with windows (6,10), (10,14) and (14,15). The first graph has 10 nodes, and
  the fold from it equals the final graph byte for byte. With the journal
  narrowed (`retain(0)`, `every=2`) there are four separate
  `delta_unavailable` events.
- **(d) T9.** `test_framing.py` collects 68 items at `9a2e40f` and 172 at
  `7fdbff3`.
  - At `7fdbff3`, R2a's mutation with `-k "not corrupt and not skipped"`
    gives **69 passed**. That is R2a's "69/69": the dedup-cache test, added
    by R2a for another finding, stays selected.
  - Deselecting it as well gives 68.
  - The body's "52 red" reproduces, as does the parent's "125 passed" (R-5).
- **(e) The benchmark.** `uv run python tools/bench_routing.py` runs at
  `f6b971b` and at `6aa7750`. It imports `platform`, `time`, `spanweave` and
  `spanweave_live.trace_id_of`, and nothing from `tests/` or the network.
  It is ruff- and `mypy --strict`-clean.
  - §4.2 cites it with its date (2026-10-22), machine (Intel Core i7-4600U,
    Linux x86_64) and Python (3.14.6). This machine and the script's header
    match.
  - Measured here, under load from the review's other agents: `trace_id_of`
    26.4–35.0 µs, feed 135.3–162.5 µs, share 15.5–18.6 %.
  - §4.2 states 24.4–25.0 µs, 124.3–127.1 µs and 16.4–16.5 %. That is the
    same order.
  - The run that produced §4.2's exact figures is not itself recorded, but
    its format is the script's.

**B10.**
- **The registry.** B1–B9 each name the batch commit: subject, position, and
  `plan: Bn done…` as the next commit (`c4ec4a4`, `29b2996`, `72d60e8`,
  `7319ac2`, `f0987b5`, `3159579`, `3937f12`, `40f0915`, `fff8a9e`). B10 is
  "the closing commit of the series", in the same words V4 and R9 carry.
- **§3 and §4 folded.** All 7 decisions rows are byte-identical. §4 is folded
  by batch, with two false sentences (R-6).
- **The open-items table.** It has 24 rows at `fff8a9e`, and 24 in
  `TASKS.md`: 18 taken, each with the right batch sha, 3 declined and 3
  deferred. One "What" cell was edited (R-8).
- **Marked in place.** All 22 underlying rows are marked, dated 2026-10-22,
  except zoo run 1's R-10 (R-8).
- **Rule 5's `no_graph` clause.** `git log -S no_graph -- CLAUDE.md` returns
  only `6aa7750`. The zoo plan's §0.6 (`3077bec`) has only "a record that
  reaches no trace". The backlog plan's §0.6 (`11a1452`) first wrote "a trace
  no adapter can read", and the behaviour dates from the zoo review's fix
  `d52669c`.
  - So the preamble ("rule 5's `no_graph` clause the backlog series'": where
    the words were written) and rule 5 ("since the zoo series' review": when
    the event began) are both true, and consistent.
  - The code emits it as `self._counted(Event(code=NO_GRAPH, …))`.
- **CHANGELOG.** B1–B10 sit under `## 0.0.3 — the backlog series
  (2026-10-22)`, each heading `### Bn — `. B1–B9's text is unchanged but for
  the heading, and everything from `## 0.0.2` down is byte-identical. There
  are no backlog post-close entries yet.
- **Version 0.0.3.** It is stated in `pyproject.toml`, `__version__`,
  `uv.lock`, `--version` and `test_record.py`. README, SPEC, `CLAUDE.md` and
  `CONTRIBUTING.md` state only "0.0.x", and nothing claims 0.0.2 is current.
- **What depends on the close commit's subject.** `plan_states()` requires
  every commit that deletes `WORKPLAN.md` to match
  `\bthe (\w+) series closes\b`. In a clone, `6aa7750` was amended to "docs:
  close out the backlog work and delete its plan".
  - **5 red**, all at the assert on line 138: `post_close[backlog]`,
    `post_close[zoo]`, `decisions_log[backlog]`, `decisions_log[zoo]` and
    `claude_md_and_the_changelog_cite…`.
  - "docs: B10, the backlog series closes" stays green (20 passed).
  - A `plan:` subject reworded with `git replace` (same shas) stays green. A
    real history rewrite turns 3 red, only because the later shas move.
  - A batch subject reworded stays green, unless it becomes `plan: B4 done`,
    which is 1 red in the commits test (N-6).

## Findings

**R-1 — `6d2c559` (B5). Rule: `CLAUDE.md` definition of done, "`SPEC.md`
reflects the behaviour"; `CONTRIBUTING.md`, spec first. Grade: blocking.**

SPEC §5.2's new paragraph (tip line 1257–1268) says: "the first tick after
the attach takes its one reading and opens each held trace's book at it.
`Quiet` then counts silence from **that tick**." That is false for a held
trace whose next record arrives after the attach and before any tick. With
a completion set, `route` reads the clock, and `_activity` → `_book` opens
that trace's book at the record.

Measured: body 0 was routed with no completion, `Quiet(1.0)` was attached at
3600, and body 1 was routed at 3600.5 with no tick in between. The trace
completed at 3601.5 with `seconds` 1.0, measured from the record at 3600.5,
not from a tick. No test covers this order.

The true sentence is "the first clock reading after the attach — a tick, or
a record routed for that trace — opens its book". The T1 pin's own case,
attach then tick, is right and stays.

**R-2 — `a141fd2` (B6). Rule: a new SPEC sentence must hold; the commit's own
§4 correction. Grade: blocking.**

Two sentences name, as the thing the new sweep catches, the form §4 recorded
as **green**:
- SPEC §3.2 (tip line 418–419): "what it catches is a framer that took the
  head of the stream out of the reader's hands and accepted a BOM only whole
  at offset 0 of a push";
- the `test_framing.py` docstring (line 311–312): "one that recognised a BOM
  only at offset 0 of each push".

A `removeprefix` or `lstrip` framer fits both descriptions, and it is green
on `test_framing.py` (293 passed) and on the whole suite. `3159579`'s §4 line
says exactly this: such a framer "stays green when the framer strips it …
it is red only as a partial BOM handed on across two reader calls".

The commit body and CHANGELOG word it correctly. Only SPEC and the
docstring do not.

**R-3 — `a467bc5` (B7). Rule: a new SPEC/`CLAUDE.md` sentence must hold; the
row's "its stated limit". Grade: blocking.**

SPEC §1.3 (tip line 192–199) says nothing from a trace "is executed or
deserialized into objects", and that the rule "holds that statically". The
only limit it states is the syntactic one, illustrated by
`getattr(builtins, "eval")`.

The B7 table above shows that most of what passes is not a syntactic escape.
These are names the rule does not list, since `UNSAFE_BUILTINS = ("eval",
"exec")`, `UNSAFE_MODULES = ("pickle",)` and `UNSAFE_MEMBERS["yaml"] =
("load",)`:
- deserializers: `marshal.loads`, `_pickle`, `shelve`, `dill`, `jsonpickle`;
- `yaml.unsafe_load`, `yaml.full_load` and `yaml.load_all`;
- `compile`, `runpy` and `code`;
- `__import__("pickle")`.

So "deserialized into objects … holds that statically" claims more than the
rule holds. `CLAUDE.md` rule 9's "Both halves are gated … bans those names"
is literally true for the four names, but it reads as the posture gated.

No module uses any of these today (`grep` finds none, and pyyaml is not in
`uv.lock`). The defect is the sentence. There are two fixes: say the rule
bans exactly those four names, or widen the lists to the families above.
Run 1 of the receiver series closed the same class of thing for the clock
gate, its T11 ("stated as static"). This is that thread's sibling.

**R-4 — `f6b971b` (B9). Rule: a new `CONTRIBUTING.md` sentence must hold
against the tests. Grade: blocking.**

`CONTRIBUTING.md`'s socket bullet says: "A test file that opens one anywhere
else is red in the record test (`test_record.py`), which holds this list to
the test files that import a socket module." The test holds the second
clause, not the first. Three planted tests that open a socket each leave
the record test green (2 passed):
- one in `test_framing.py` that calls
  `spanweave_live.real.http_listener(("127.0.0.1", 0), …)`;
- one in `test_routing.py` that calls `urllib.request.urlopen`;
- one in `test_routing.py` whose child process binds a socket.

Two related points:
- `test_cli.py` qualifies only through a function-level `import http.server`
  at line 916, in a test that opens no socket, and not through the spawn the
  bullet names. Dropping `"http.client"` from the module list survives.
- The `from <module> import <name>` half of the scan is held by no committed
  case. Dropping `imported.add(node.module)` survives, and is not
  equivalent: with `from socket import create_connection` planted, it
  passes.

Today's list is right: the spy run above finds socket use in exactly the two
named files. The fix is to say "imports a socket module" in place of "opens
one", or to make the check behavioural.

**R-5 — `f6b971b` (B9; the plan row's T9 premise, `fff8a9e`). Rule: §0.3, "a
number you state … is a citation"; a correction must itself be precise.
Grade: blocking.**

`TASKS.md`'s R2a bullet (tip line 995–1001) and the open-items row ("the
'69/69' is not reproducible (68)") call R2a's number wrong. It reproduces:
- **69 passed** at `7fdbff3` under R2a's mutation, with R2a's corrupted- and
  skipped-record tests deselected
  (`-k "not corrupt and not skipped"`);
- **68** only when R2a's dedup-cache test is deselected too. That test was
  added by R2a for a different finding.

The two numbers answer two deselection sets. The record line should name
both instead of correcting 69 to 68. This is the precision defect in a
correction that the receiver series' T10 names as "the one place a project
that strikes through its own premises cannot afford one".

**R-6 — `6aa7750` (B10). Rule: §0.3, a stated fact is a citation. Grade:
blocking.**

Two sentences of the folded §4 in `TASKS.md` are false:
- Line 138–139: "each batch's `make check` count is in its commit body".
  `git log -1 --format=%B <sha> | grep -c -E 'make check|passed'` gives 0
  for B1 `3ceb8df`, B2 `57ad222`, B3 `303f50f`, B4 `707e58a` and B5
  `6d2c559`. B6 `a141fd2`'s only hit is "28 passed", which is not a
  `make check` count. Only B7–B10's bodies carry one.
- Line 172: "the counts are in `57ad222`'s body and the plan's last §4".
  `57ad222`'s body has none of 82, 164 or 1822. They are only in
  `fff8a9e:WORKPLAN.md` §4.

Nothing is lost, because the plan's §4 holds every count. The sentences send
a reader to a place that does not have them.

**R-7 — `6aa7750` (B10). Rule: a stated fact is a citation. Grade:
blocking.**

SPEC §0 (tip line 32–34) says "Sections 3 onward are written by the batch
that builds them (… amended since by … the backlog series' B1–B7 and B9)".
B7's only SPEC hunk is §1.3 (`git diff a467bc5^ a467bc5 -- SPEC.md` has one
`@@`, at line 187). B7 amended no section from 3 onward. B8 is rightly left
out.

**R-8 — `6aa7750` (B10). Rule: the B10 row, "folded" and "marked closed …
in place"; "the declined and deferred rows say so in place" (B10's body).
Grade: blocking.**

Three folding defects:
- **An open-items cell edited without saying so.** Zoo run 1's R-14's "What"
  read "is 16" at `fff8a9e`. It reads "is more" in `TASKS.md` (line 75),
  with no note. The 19 measured by B9 is the reason, but the table claims to
  be the plan's, folded.
- **One row not marked in place.** Zoo run 1's R-10 (line 675, "registered
  at V4 as V2(b) … open for spanweave's next series") carries no dated
  in-place mark. Its pair, V2(b), is marked deferred, and run 1's R-9, paired
  with V2(a), is marked. The row's text is not false, but it is the one row
  of the 22 left unmarked.
- **Marks run into the old text.** The in-place marks on receiver T9 and T12
  (lines 1524, 1527) are appended with no separator: "…re-derivable
  **Closed by B9**…" and "…the series did not add one **Closed by B9**…". So
  each row reads "open" and "Closed" in one sentence. A dated mark should
  stand apart from what it replaces.

**R-9 — `7319ac2`, `f0987b5`, `3159579`, `3937f12`, `40f0915`, `fff8a9e`
(plan). Rule: `WORKPLAN.md` §2, "Every batch: CI green on the pushed tip
before `done`". Extends run 1's R-3. Grade: blocking (a process record).**

B4–B9 were each marked `done` with no push and no CI run on their tips.
`gh run list --branch backlog` shows runs only at `11a1452`, `72d60e8` and
`6aa7750`. All seven jobs at `6aa7750` are green, including the ruleset's
six required ones.

Run 1's R-3 asked that §2's per-batch rule and §0.1 step 8's per-run push
agree "before run 2 marks B4 done". At `fff8a9e` they still disagree, and the
contradiction recurred six times. CI at the tip makes the `done` claims
true now. The record does not say they were made without it.

History cannot be re-run, so the fix is a record line in `TASKS.md`. The
next plan should carry one rule, not two.

## Threads (older than the series, with their measurements)

**T-1 — the framer's mid-stream BOM depends on chunking (`spanweave_live/
framing.py`, older than B6).** Take the stream line1 + BOM + line2. The
one-shot read gives 1 record and `malformed_record`. Through the Framer:
- splits at 1–42 give the same;
- splits at 43–46 give **2 clean records**, because the reader forgives a
  BOM at the start of every call and the split puts the BOM there.

So a diagnostic depends on where chunks fall, against §3.2's aim and
`CLAUDE.md` rule 8 ("chunk boundaries … never ambient"). A related gap
follows from the same cause. A BOM-stripping framer differs from the real
one on a BOM inside a line at a push boundary (it drops the U+FEFF), and no
test can tell, because the sweep's fixture holds one BOM, at offset 0.

**T-2 — a tree with no `.git` fails more than B10 registered (extends B10's
registered §8.7 thread).** In a `git archive` export with `corpus/` and
`showcase/` copied in:
- 3 failed, 1026 passed and 8 errors at `6aa7750`;
- 3 failed, 1022 passed and 5 errors at `a743893`.

The 3 failures are older tests that shell out to git: two in `test_pins.py`
(dependency against submodule sha), and
`test_showcase.py::test_the_rules_file_and_the_trace_are_the_pinned_submodule_s_own_bytes`.
Without `corpus/`, §8.7's test fails `assert 34 == 87`, as registered, and
B8's W1 check fails too (no `corpus/TASKS.md`).

**T-3 — `TASKS.md` line 590 is stale (older, zoo series).** It still says
"PR `zoo` → `main` is open, as #2". The preamble says it was merged at
`2478e2c`.

**T-4 — README's gate A count is the main pass's alone (older, since B2's
named passes).** README line 173–176 gives "1460 cross-scenario pairs × 10
seeds × 2 graphs per pair = 29 200 byte-for-byte comparisons" as gate A.
Gate A now also runs B2's named-adapter passes and B6's one-stream pass
(2 × 1354 comparisons). The arithmetic is true of the pass it describes,
but it is no longer gate A's total.

**T-5 — `late_arrival`'s `Event.version` is held by no test (older).**
Setting `version=book.generation` on the `LATE_ARRIVAL` event
(`routing.py:1210`) passes `test_completion.py`, `test_routing.py` and
`test_cli.py`. §4.1's "`None` for every code that is not about one" is true
in the code and unpinned for that code.

## Notes (not defects)

- **N-1 (B4).** §4.1's "since B4 it is §5's fourth code about a version"
  (tip line 672) follows "§6's three codes" and means the fourth such code,
  §5's only one. It is true in context. "The fourth code about a version,
  and §5's only one" would not need the context.
- **N-2 (B6).** The crossing count is computed right (1433, equal to the
  count here), but nothing pins its condition. Counting every push with a
  non-empty remainder (2939 at seed 0) survives, as does counting the same
  trace. The weak form would be above zero on gate A's existing passes too,
  which cut lines mid-line. Then the "> 0" would no longer tell the
  one-stream pass from those passes, which is the guard §4.7 gives it.
- **N-3 (B7).** `import yaml.constructor` followed by `yaml.load(s)` is
  caught by the rule's default self-alias map, but no planted case holds it.
  Emptying the map survives.
- **N-4 (B8).** "It fails rather than skips" is true: nothing is skipped and
  the exit code is 1. Pytest reports the five as fixture ERRORs, not FAILED.
- **N-5 (B10).** The open-items table's shas and the in-place close marks
  are held by no test. Pointing the B4 row at its `plan:` commit `7319ac2`
  survives (20 passed), as does deleting the "Closed by B5" mark on zoo run
  2's R-11. The plan declined tests for prose. A sha in a table is a
  citation, though, and the registry's own shas are held.
- **N-6 (B10).** `tests/test_record.py`'s `plan_states()` finds each closing
  commit by its subject, `\bthe (\w+) series closes\b`. Rewording `6aa7750`'s
  subject so it lacks the phrase turns 5 tests red, both zoo cases among
  them, because every deleting commit must match. Any future close must use
  the phrase. The test's docstring (line 121) says so; `CONTRIBUTING.md` and
  `CLAUDE.md` do not. `plan:` and batch subjects can be reworded freely,
  except a batch subject reworded to `plan: Bn done…`.

## Run 1's findings, at the tip

Not re-raised. The two halves are dispositioned together under §2. At
`6aa7750`:
- R-1: no record line for `3ceb8df`'s parent yet.
- R-2: §5.5's late unclaimed arrival at a full bound still has no test.
- R-3: recurred (R-9 above).
- R-4 and R-6 stand as threads.
- R-5's SPEC §4.8 "because" is unchanged.

## Process note

- **The main checkout.** No command read its working tree, moved its HEAD,
  index or files, or changed `.git/config`. Reads of the repository were
  `git show`, `log`, `diff`, `rev-parse` and `ls-tree` on fixed shas, plus
  this brief's own exceptions: `patches/REVIEW-2026-10-22.md`, and one
  sub-agent's read-only use of the archived zoo reviews to find X6–X13. Their
  text is also tracked under `reviews/` in the worktrees.
- **Worktrees.** `git worktree add` registered fourteen detached worktrees
  under the aux scratchpad: the seven commits and their seven parents.
  `git worktree prune` clears them once the scratchpad is gone.
- **Clones.** Every edit (mutations, plants, amended subjects) was made in
  separate `git clone`s under the scratchpad. No tracked file changed in any
  worktree or in either repository, and nothing was committed.
