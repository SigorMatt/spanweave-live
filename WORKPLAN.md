# WORKPLAN.md — spanweave-live, the backlog series

Status file for the series that takes this repository's registered open
items off the list. Two series and their reviews left them in `TASKS.md`
(the receiver series' run-1 and run-2 threads; the zoo series' cold review,
its bounded fix review and Qodo's review of PR #2). Every one of them is
decided below: taken into a batch, declined with the reason, or deferred
with the series it waits for. The one an outsider can trigger leads: since
the zoo series, a client that can POST to `serve` can grow memory without
bound with exports no adapter can read. One batch = one sub-agent = one
commit = one concern. This file plus git is the only state; any session can
resume cold from it.

Last updated: 2026-10-21 (series drafted; opens on `backlog` from `main` at
`2478e2c`; run 1 not started.)

## The open items, taken or not

Every item `TASKS.md` registers as open at `2478e2c`, by its id there. A
plan that leaves one of them without a decision is not ready to open (§3,
the series row).

| Item (`TASKS.md`) | What | Decision |
|---|---|---|
| zoo, Qodo 2 | `max_traces` does not bound the builders of traces no adapter claims; a client that can POST grows them without bound | **taken, B1** |
| zoo, V2(a), with run 1's R-9 (both shapes) | under `Router(adapter=X)`, routing classifies across every adapter: a record two adapters claim reaches the no-trace builder unannounced, and a flat record no adapter claims is read as X's there, where `spanweave.build(…, adapter=X)` puts both in their trace | **taken, B2** |
| zoo, run 2's R-9 and R-13 | a refusal's `{"code": …}` is OTLP's `Status` in neither encoding | **taken, B3** |
| receiver, T5 | `released` carries its version in `detail` only, though `Event.version` exists | **taken, B4** |
| receiver, T1 | a completion attached after records were routed measures `Quiet` from the tick; no §5 sentence says so and no test covers it | **taken, B5** |
| zoo, run 2's R-11 | the per-generation reset of `root_ended_at` is held by no test | **taken, B5** |
| zoo, run 2's R-14 | `ROOTLESS` is not asserted, and three §5.3 numbers are not re-derived | **taken, B5** |
| zoo, run 2's R-15 | `RootEnded` acts per generation, and the trap names the rootless case only | **taken, B5** |
| receiver, R1-6 | the BOM-split consequence of §3.2 is untested | **taken, B6** |
| receiver, R2-2 | gate A's interleaving is line-atomic; the framer's remainder never holds one trace's partial line while another's bytes arrive | **taken, B6** |
| receiver, R0-4 (its open half) | standing rule 9 (no `eval`, `exec`, `pickle`, `yaml.load` on trace content) is gated nowhere | **taken, B7** |
| zoo, run 2's R-16 and R-18 | `tests/test_record.py` holds lengths and resolvability, not contents, and names a tree with no `.git` "shallow" | **taken, B8** |
| zoo, the bounded review's R-7 | the CHANGELOG's post-close entries are held newest-first by date alone | **taken, B8** |
| zoo, run 1's R-14 | SPEC §7.2's "ten" tests the `push` mutation takes down is 16, held by no test | **taken, B9** |
| zoo, run 2's R-10 | two test files open loopback sockets, against `CONTRIBUTING.md`'s rule, and no review disposed of the conflict | **taken, B9** |
| receiver, T4 | the cursor's advance on `delta_unavailable` is unspecified in §6.5 | **taken, B9** |
| receiver, T9 | R2a's commit body's "69/69" is not reproducible (68) | **taken, B9** (a record line) |
| receiver, T12 | §4.2's measurement has no artifact anyone can re-run | **taken, B9** |
| zoo, conformant `partial_success` (the bounded review's R-2) | a body the reader read in part is answered with OTLP's full-success message | **declined** (§3): an OTLP/HTTP body is one export, read whole or refused; a body read in part is not one export, and the count OTLP asks for is of spans, which only a dialect read counts. §7.2 states the departure, and stays |
| zoo, run 1's R-11, its CLI half | the CLI's `no_trace` line carries the code, not which envelope field failed | **declined** (§3): every receiver event carries a code; a library caller holds the record and can ask `spanweave.envelope`. The CLI has no record to ask about |
| zoo, run 2's R-16 (its prose part) and the bounded review's R-8 | `CLAUDE.md`'s prose is held by no test | **declined** (§3): a number is held by a test; prose is held by review. The `make conformance` line, which names files, stays held |
| zoo, V2(b), with run 1's R-10 | routing tells an unpacked record by `spanweave.read.Unpacked`, which spanweave does not export | **deferred to spanweave's next series** (*the reader's malformed input*), which gives a public way; then a pin move here drops the import |
| zoo, run 1's R-15 | `read_protobuf` refuses a body nested 60 deep or more (the parser's recursion limit) | **deferred to spanweave's next series**: the reader's, not this repository's |
| receiver, the `trace_id_of` thread (2026-10-05) | an upstream `spanweave.trace_id_of(record)` would save the second parse | **deferred, no series**, as decided on 2026-10-05: an optimisation, until a receiver workload makes routing the cost |

---

## 0. Operating protocol

### 0.1 Builder — orchestrator loop

The builder's own context must stay small. It reads this file, dispatches,
verifies, records, and moves on. It does not read source files itself,
does not debug itself, and does not carry batch detail in its context: all
of that happens inside a sub-agent whose context is discarded.

On the prompt `Execute WORKPLAN.md run N` (or `Resume WORKPLAN.md`):

1. `git status`. If the tree is dirty: dispatch one sub-agent with the
   **recovery brief** (0.4). Do not proceed until the tree is clean and
   `make check` is green (verify with a sub-agent; the builder runs no
   commands longer than `git status` / `git log --oneline -5` itself).
2. Read §1 and §2. Take the first batch of the requested run whose status is
   not `done` / `dropped` / `awaiting decision`. A status `awaiting <batch>`
   is `todo` once that batch is `done`.
3. Dispatch **one sub-agent** with the **batch brief** (0.3) for that batch.
   Wait for its ≤12-line report.
4. Verify: `git log --oneline -3` shows the batch commit; the report says
   `make check` passed. If not, dispatch the same batch once more with the
   report's failure appended. If it fails twice: set status
   `blocked: <one line>`, write the resume note, and continue to the next
   batch **unless** the blocked batch is a dependency of the next.
5. Edit this file: status → `done (<sha>)`, one line under §4 if anything
   was learned. If a row's acceptance number or premise was shown wrong by
   the batch, correct the row in the same edit and say why in the §4 line
   — a wrong criterion has an owner, and it is this step. Commit the plan
   edit together with nothing else (`plan: <batch> done`; a second clause
   after the batch id is allowed when it records something a reader needs).
6. Repeat from 2. Stop when: the run's batches are exhausted; a batch ends
   `awaiting decision`; or the same batch has failed twice.
7. Final step of a run: dispatch a sub-agent to `git format-patch main -o
   patches/` and print `git log --oneline main..HEAD`. Report to the human:
   batches done, blocked, awaiting decision, and the memo file paths to read.
8. `git push origin backlog`. A run is not finished until the push succeeds
   **and the GitHub checks on the pushed tip are green, or every failing
   check is explained in the run report**; local `make check` is not a
   substitute. A series branch is never force-pushed. An amended batch is a
   new commit on top; the replaced sha is recorded in §4 with the reason.

### 0.2 Aux — cold reader

On the prompt `Review commits since <sha>`: for each code commit, in a
sub-agent per commit, check against `CONTRIBUTING.md` and `CLAUDE.md`: spec
changed in the same commit where behaviour changed; the new test fails on
the parent commit, where the parent is `<sha>^` **derived**, never a sha a
brief names (`plan:` commits interleave); a **mutation the new test catches**
is required for every code commit, and the reviewer tries two more plausible
mutations of any code the commit adds; worktrees are created by **absolute
path under the scratchpad**, never relative, never inside the repo; no
ambient runtime under `spanweave_live/` outside the `SEAMS` allowlist; both
pins equal; commit is one concern. Write findings to
`~/git/spanweave-live/patches/REVIEW-<date>.md` (untracked; the absolute path, since the aux starts in `~/git/spanweave`) and print them. **Aux never edits
tracked files and never commits.**

### 0.3 Batch brief (template the builder passes to a sub-agent)

```
You are executing batch <ID> of WORKPLAN.md in the spanweave-live repo.
Read, in this order: CLAUDE.md, the WORKPLAN.md row for <ID> and §5, then
the SPEC.md sections the row names, then only the source and test files
the batch touches. Rules: spec first (SPEC.md edited in this commit if
behaviour changes); write the failing test before the fix and confirm it
fails on the parent (`<sha>^`, in a worktree by absolute path under the
scratchpad); name one mutation the test catches and show it caught, and
try two more plausible mutations of any code you add; then implement; then
`make check`, `make conformance`, `make showcase`, and `make install-check`
when packaging or dependencies moved. Add a CHANGELOG entry. Commit once:
`<area>: <one line>` with a body naming <ID>, the SPEC sections touched and
the probes answered. Never edit WORKPLAN.md. Never write under `corpus/` or
`showcase/`. A number you state in a document is a citation with a test
that re-derives it, or it is not stated. If completing the batch would
require a change in spanweave itself, a dialect read outside spanweave's
adapters or its public envelope, a rule or a policy the spec does not
already state, or a change to a graph's bytes — stop, write the options to
OPEN_QUESTIONS.md under a heading "<ID>: …", commit that alone, and report
`awaiting decision`. Report in ≤12 lines: commit sha, files changed, tests
added, mutations shown, make check result, anything the orchestrator must
know.
```

### 0.4 Recovery brief (dirty tree or interrupted batch)

```
The previous batch was interrupted. Read WORKPLAN.md §4. Run git status
and git diff --stat. If the in-progress work is complete enough to pass
`make check`, finish it under the batch brief rules and commit. Otherwise
`git stash` it with the message `wip <ID> <date>` and report what was
stashed and where it stopped. Leave the tree clean either way.
```

### 0.5 Context management (for the human)

- Builder: **clear context** before `Execute WORKPLAN.md run N` and before
  any `Resume WORKPLAN.md`. Continuity lives in this file and git, not in
  the session. The only time not to clear is when the builder has asked a
  question and is waiting for the answer.
- Aux: **always clear** before a review or a status check. Every aux task
  is stateless.
- A prompt that starts a run names `run N` within its first 100 characters.
  Decisions files are copied to `patches/` by the relay before the builder
  is prompted, and are cited in the record by their TASKS.md decisions-log
  row, never by file name.

### 0.6 Standing rules (from CLAUDE.md, repeated because load-bearing)

The receiver owns plumbing and policy and nothing else. It never reads a
dialect: a record's trace id, span id or kind comes from spanweave's
adapters (`spanweave.adapters.classify` and the claiming adapter's `parse`)
**or, for a record the reader unpacked from an OTLP export that no adapter
claims, from spanweave's public `envelope()` — the transport's id, which the
stranger series decided is not a dialect** — never from a key the receiver
looks up itself. It carries no rules and no semantics. It enforces nothing.
The clock, sleeping and sockets are injected seams so that every test runs
on a fake clock and the conformance gate is deterministic; `SEAMS` has one
entry and grows only for a seam. Nothing is dropped silently: a refusal, a
cap, a late arrival, a consumer error, a record that reaches no trace, a
trace no adapter can read — is an event with a code, counted and reported. `spanweave` is
pinned to one commit in `pyproject.toml` and the `corpus/` submodule is at
the same commit; a test holds the two equal, and the `agentgolden` pin and
`showcase/` likewise.

The corpus is read in place through `corpus/`, never copied, and that
includes `corpus/fixtures/zoo/` — the twelve captures (JSON and raw bodies,
manifests) at the zoo's pin. The receiver's own gate over them, the **zoo
gate**, holds for every capture that the graph the receiver writes at
end of input equals `spanweave.build` of the same records byte for byte;
every batch keeps it green or moves it with the reason.

TASKS.md is the item registry (one line per batch, written at series
close); this file is execution state only and is deleted at series close
with §3 and §4 folded into TASKS.md. The opening commit of the series makes
whatever the doc-truth gates need for WORKPLAN.md to exist, as the zoo
series' opener `0de9f55` did, and nothing else.

---

## 1. Batch list

| ID | Batch | Status | Calls |
|---|---|---|---|
| B1 | **The traces no adapter can read are bounded too.** Zoo Qodo 2. `Router` gains `max_unclaimed_traces: int \| None = None`, and the CLI `--max-unclaimed-traces N` beside `--max-traces`. It bounds the traces the router holds a builder for that hold no claimed record, the ones `max_traces` does not count (§4.5). At the bound, an unclaimed record that would start a new such trace is `refused_at_cap`, counted, its `detail` naming the bound it met; no builder, no book, no cursor is made. A record for such a trace already held is never refused by it. A trace that absorbs its first claimed record leaves this count and is `max_traces`' from then (the claimed record that would join it at a full `max_traces` is `refused_at_cap`, as today, and the trace stays in this count). Completion releases a trace from whichever count holds it. The no-trace builder, for records with no trace id, is bounded by neither, and SPEC says so. Both defaults are no bound, and SPEC §4.5 and README's `serve` line say what an unbounded `serve` costs. SPEC §4.1, §4.5, §6.4 and §8 amended. Tests red on the parent: `Router(max_unclaimed_traces=2)` fed five health-check exports with fresh trace ids holds two builders and emits three counted `refused_at_cap` naming the bound; a further record for a held one is absorbed; one held trace absorbing a claimed record frees a place, and the next health check is admitted; a claimed trace is never refused by this bound; the bounded review's `cap_bound` shape, `max_traces=1` and `max_unclaimed_traces=10` with one claimed trace and 100 health checks, holds 11 builders and 11 cursors, with 90 refused; the CLI flag sets the field. Mutations: the bound counted over every trace is red; a held unclaimed-only trace's further record refused is red; a trace that gained a claimed record kept in this count is red. | todo | 5 |
| B2 | **A named adapter routes as it builds.** Zoo V2(a), with run 1's R-9, both shapes. Under `Router(adapter=X)`, `trace_id_of` asks X alone, X's `parse` of the record, with no `classify` across adapters and no envelope fallback, because `spanweave.build(…, adapter=X)` reads every record as X's: SPEC §4.1's "a caller that names a dialect … gets the same thing live as `spanweave.build` gives it in batch" is the rule, and routing that classified across adapters broke it. A record X reports no single trace id for is `no_trace` (`no_id`). Before any code, the batch measures, over the corpus and the zoo, under each named adapter, that each trace's live graph equals the batch build under the same name of that trace's records; if any differs, it stops (`awaiting decision`). §4.3's exception, its pin test (`test_under_a_named_adapter_an_ambiguous_record_reaches_no_trace_unannounced`) and the sentences that name it (README's `Router` row, SPEC §1.1, §8.3) go or are corrected. SPEC §4.1, §4.2 and §4.3 amended. Tests red on the parent: run 1's R-9 table under each named adapter — a record both adapters claim reaches the trace X's parse names (live 2 nodes, batch 2), and a flat record no adapter claims does too; gate A run once under each named adapter over that dialect's renderings. Mutations: `classify` across adapters under a name is red; the envelope asked under a name is red. | awaiting B1 | 5 |
| B3 | **A refusal is OTLP's `Status`, in the request's encoding.** Zoo run 2's R-9 and R-13. A `400` or `415` is answered with OTLP's `Status`, the receiver's code as its `message` and its `code` omitted (OTLP: a server "MAY omit `Status.code`"). A request declaring `application/json` gets `{"message": "<code>"}` as `application/json`; one declaring `application/x-protobuf` gets the `Status` with field 2 alone, `application/x-protobuf`: the byte `0x12`, the varint length, the code's ASCII. A request declaring neither gets the JSON form. Writing one field of the receiver's own reply is not reading a dialect, so no protobuf import comes under `spanweave_live/` and V1's decision holds. SPEC §7.2's refusal departure goes; its `partial_success` departure stays (declined). README and CHANGELOG say the refusal body changed. Tests red on the parent: every refusal row of `tests/test_endpoint.py`, in both encodings, decodes as a `Status` (in the tests only: protobuf through the `otlp` extra, JSON through `json_format.Parse`) whose `message` is the event's code, with the declared type; a refusal of a request declaring neither type is JSON. Mutations: a protobuf refusal with the JSON body is red; `code` sent as the receiver's string is red (`json_format` refuses it); the length byte off by one is red. | awaiting B2 | 3 |
| B4 | **`released` carries its version.** Receiver T5. A `released` event's `Event.version` is the builder's version at release, as `completed`'s is; `detail` keeps its text. SPEC §4.1 and §6.1 say it is done. Tests red on the parent: `released.version == completed.version` for one completion and for a generation opened by a late arrival. Mutation: `version` left `None` on `released` is red. | awaiting B3 | 2 |
| B5 | **Completion's edges, stated and pinned.** Receiver T1; zoo run 2's R-11, R-14 and R-15. No behaviour change; if a test shows one is needed, stop. (a) §5.2 says what a completion attached after records were routed measures: `Quiet` from the tick that opens the book, and `Completed.seconds` from it; a test pins the thread's own case (routed with `completion=None`, `Quiet(1.0)` attached later). (b) A test holds the per-generation reset of `root_ended_at`: under `RootEnded(1.0)`, a second generation of Z3 or Z1, opened by re-feeding body 0 after completion, does not complete on generation 1's root. (c) `ROOTLESS` is asserted to be Z5's two captures, and §5.3's `now = k`, `last + 0.5` and "*N*-th record" are re-derived by the documents test. (d) §5.3 and README's third trap say `RootEnded` acts per generation: a later generation of a trace whose root arrived in an earlier one is never completed by `RootEnded` alone either, and end of input completes it; a test pins it on Z3 and Z1. Tests are pins and say so; mutations: the reset deleted is red; `ROOTLESS = ()` is red; each of the three §5.3 numbers edited is red. | awaiting B4 | 4 |
| B6 | **The framer's remainder, tested where it crosses.** Receiver R1-6 and R2-2. (a) `MULTI_BYTE_STREAM` gains a BOM prefix, so the two-way split sweep crosses the BOM's boundaries. (b) Gate A gains one pass that chunks the concatenated interleaved stream, so the framer's remainder holds one trace's partial line while the other trace's bytes arrive; the test counts those arrivals and asserts the count is above zero, and §4.7 states it. Pins, and they say so; mutations: a BOM accepted only at offset 0 of each push is red; the remainder dropped at each push boundary is red under (b) and not under gate A's line-atomic pass. | awaiting B5 | 3 |
| B7 | **The trace-content gate.** Receiver R0-4, its open half. `tests/gates.py` gains a rule banning `eval`, `exec`, `pickle` and `yaml.load` under `spanweave_live/`, with planted-violation tests as its other rules have; `CLAUDE.md`'s standing rule 9 says it is gated. Red on the parent: the planted violations pass there. | awaiting B6 | 2 |
| B8 | **The record test reads what it holds.** Zoo run 2's R-16 and R-18; the bounded review's R-7. `tests/test_record.py` compares the decisions log with the plan's §3 at the plan sha it cites (`git show <sha>:WORKPLAN.md`), checks that `CLAUDE.md` cites each series' last plan state, and checks the CHANGELOG's W1 sha against the corpus' registry: the review's X6, X8, X9, X10 and X13 each go red. A tree with no `.git` is named as that, not "shallow". The post-close entries are held newest-first by the order of their commits, not their dates alone; if no truthful mapping from an entry to its commit exists, the batch states the limit and stops at the date. | awaiting B7 | 3 |
| B9 | **The record made true.** Zoo run 1's R-14 and run 2's R-10; receiver T4, T9 and T12. (a) SPEC §7.2's "ten" is the measured count, re-derived by a test, or the sentence states no number. (b) `CONTRIBUTING.md`'s "No test that … opens a real socket" names its exceptions as SPEC §7.2 argues them — the endpoint's adapter layer bound on `127.0.0.1` port 0, and `tests/test_cli.py`'s spawned process — so the rule and the tests agree. (c) §6.5 says a window lost to `delta_unavailable` is not retried and not re-reported, and the consumer's first update starts its fold from `builder.graph()`. (d) A record line: R2a's "69/69 green with R2a's tests deselected" is 68, as T9 measured. (e) §4.2's measurement gets its artifact: the benchmark script under `tools/` (timings are not a test), and §4.2 cites it with its date and machine as provenance. Docs and one test. | awaiting B8 | 3 |
| B10 | **The series closes.** TASKS.md: registry B1–B10 with shas; §3 and §4 folded; the open-items table above folded with each row's outcome (taken → its batch's sha, declined, deferred); the receiver and zoo rows it closes marked closed, dated, in place. CHANGELOG; version `0.0.3` (a `Router` field and a CLI flag were added, `released` gained its version and a refusal its `Status` body; nothing is frozen); `CLAUDE.md` says no series is open; WORKPLAN.md deleted. No `plan:` commit follows. The series reaches `main` only through the PR `backlog` → `main` (§2), a merge commit through ruleset 25363236, whose required checks are `check (macos-latest, 3.12)`, `check (ubuntu-latest, 3.11)` to `check (ubuntu-latest, 3.14)`, `conformance (macos-latest)` and `conformance (ubuntu-latest)`; a CI job this series adds or renames is added to the ruleset after the merge, once it has run on `main`. | awaiting B9 | 4 |

## 2. Execution order

Run 1 = B1 → B2 → B3, the three behaviour changes. Run 2 = B4 → B5 → B6 →
B7 → B8 → B9 → B10. Every batch: CI green on the pushed tip before `done`.
The branch is `backlog`, from `main` at `2478e2c` (§4).

The aux cold review runs in two halves, as the zoo series' did: run 1's
(`<opener>..<run 1's tip>`) while run 2 executes, from worktrees at fixed
shas and never the builder's checkout, and run 2's after B10. The aux
starts in `~/git/spanweave`, so its prompts name every path in this
repository absolutely, its review file included. The two halves' findings
are dispositioned together as one set; then that set's commits, the PR
`backlog` → `main`, one bounded review of those commits read together with
Qodo's review of the PR (first fetch archived), that set's commits, Qodo's
post-push diff, and the merge.

The merge rule is the zoo series' (its `WORKPLAN.md` §2 at `3077bec`), and
spanweave's decisions log D39 and D40 before it: only a defect this series
introduces, or one a claim it makes depends on, blocks the merge; an older
defect is registered in TASKS.md with its measurements, and the next plan's
open-items table decides it. A review of fix commits is bounded: the
standard per-commit rules (§0.2) plus the previous review's own survivors
and probes, and no new search. If it finds a blocking defect, that fix is
made and goes to the merge on green CI without a further review: the loop
ends there.

## 3. Decisions log

| Date | Batch | Decision | By |
|---|---|---|---|
| 2026-10-21 | series | The registry is the plan's first input: every item `TASKS.md` registers as open is taken into a batch, declined with the reason, or deferred with the series it waits for, in a table at the head of the plan, and a plan that leaves one without a decision is not ready to open. A registered thread is a to-do, not an archive. | maintainer |
| 2026-10-21 | B1 | The traces no adapter can read get their own bound rather than a share of `max_traces`, so that the traces the library can read are never crowded out by the ones it cannot (§4.5's reason, kept). No bound by default, as `max_traces` has none; what an unbounded `serve` costs is said where its flags are. | maintainer |
| 2026-10-21 | B2 | A named adapter is the claimant for every record, in routing as in `build`: §4.1's live-equals-batch under a named dialect is the rule. Routing that classified across adapters while the builder read as one was the defect, not the spec. | maintainer |
| 2026-10-21 | B3 | A refusal is OTLP's `Status`: the receiver's code in `message`, `code` omitted as OTLP allows, in the request's declared encoding. The one protobuf field the endpoint writes is its own reply's, not a dialect read, so it needs no runtime. | maintainer |
| 2026-10-21 | declined | Conformant `partial_success`: an OTLP/HTTP body is one export, read whole or refused; a body read in part is not one export, and the count OTLP asks for is of spans, which only a dialect read can count (§1.1). §7.2's stated departure stands. | maintainer |
| 2026-10-21 | declined | The CLI's `no_trace` line naming the envelope field that failed: every receiver event carries a code, and the library caller who holds the record can ask `spanweave.envelope` for the sentence. | maintainer |
| 2026-10-21 | declined | Tests for `CLAUDE.md`'s prose: a number is held by a test, prose by review. | maintainer |

## 4. Resume note

- 2026-10-21: series drafted. Opens on `backlog` from `main` at `2478e2c`
  (PR #2's merge, the zoo series). The spanweave pin stays at `17edf61`: no
  batch here needs a pin move, and V2(b)'s import waits for spanweave's next
  series. Version `0.0.2` at the open, `0.0.3` at the close (B10). `main`
  is protected (ruleset 25363236), so the opening commit lands on
  `backlog`.

## 5. Origins

| ID | Origin (`TASKS.md` at `2478e2c`) |
|---|---|
| B1 | The zoo series, Qodo's review of PR #2, finding 2. |
| B2 | The zoo series, V2(a), and its cold review's run 1, R-9. |
| B3 | The zoo series' cold review, run 2, R-9 and R-13. |
| B4 | The receiver series' run-2 review, T5. |
| B5 | The receiver series' run-2 review, T1; the zoo series' cold review, run 2, R-11, R-14 and R-15. |
| B6 | The receiver series' run-1 review, R1-6 and R2-2. |
| B7 | The receiver series' run-1 review, R0-4. |
| B8 | The zoo series' cold review, run 2, R-16 and R-18; its bounded fix review, R-7. |
| B9 | The zoo series' cold review, run 1, R-14, and run 2, R-10; the receiver series' run-2 review, T4, T9 and T12. |
| B10 | Close. |
