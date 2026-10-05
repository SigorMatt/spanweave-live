# WORKPLAN.md — spanweave-live, the receiver series

Status file for the receiver series: where the live graph meets the
network, the clock and the consumer (`spanweave` `OPEN_QUESTIONS.md` §19,
decided 2026-09-29). One batch = one sub-agent = one commit = one concern.
This file plus git is the only state; any session can resume cold from it.

Last updated: 2026-10-05 (run 2 stopped after R5: R2a, R2b, R3, R4, R5 done; R2c awaiting PR #4).

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
8. `git push origin receiver`. A run is not finished until the push succeeds
   **and the GitHub checks on the pushed tip are green, or every failing
   check is explained in the run report**; local `make check` is not a
   substitute — the CI matrix runs interpreters the machine does not have.

### 0.2 Aux — cold reader

On the prompt `Review WORKPLAN.md commits since <sha>`: for each code commit,
in a sub-agent per commit, check against `CONTRIBUTING.md` and `CLAUDE.md`:
spec changed in the same commit where behaviour changed; the new test fails
on the parent commit, where the parent is `<sha>^` **derived**, never a sha a
brief names (`plan:` commits interleave) — and because a tests-only batch's
derived parent is a `plan:` commit, which makes the parent run vacuous, a
**mutation the new test catches** is required for every code commit, not only
the parent run; worktrees are created by **absolute path under the
scratchpad**, never relative, never inside the repo; no clock read, no
randomness, no network in `spanweave_live/` except behind the injected
`now`/`sleep`/socket seams the spec names; commit is one concern. Write
findings to `patches/REVIEW-<date>.md` (untracked) and print them. **Aux
never edits tracked files and never commits**: a finding that needs a commit
is made by the builder from the review file, never by the reviewer.

### 0.3 Batch brief (template the builder passes to a sub-agent)

```
You are executing batch <ID> of WORKPLAN.md in the spanweave-live repo.
Read, in this order: CLAUDE.md, the WORKPLAN.md row for <ID> and §5, then
the SPEC.md sections the row names, then only the source and test files
the batch touches. Rules: spec first (SPEC.md edited in this commit if
behaviour changes); write the failing test before the fix and confirm it
fails on the parent (`<sha>^`, in a worktree by absolute path under the
scratchpad); name one mutation the test catches and show it caught; then
implement; then `make check` and `make conformance`. Add a CHANGELOG
entry. Commit once: `<area>: <one line>` with a body naming <ID> and the
SPEC sections touched. Never edit WORKPLAN.md. If completing the batch
would require a change in spanweave itself, a dialect read outside
spanweave's adapters, a rule or a policy the spec does not already state —
stop, write the options to OPEN_QUESTIONS.md under a heading "<ID>: …",
commit that alone, and report `awaiting decision`. Report in ≤12 lines:
commit sha, files changed, tests added, mutation shown, make check result,
anything the orchestrator must know.
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
- A prompt that starts a run names `run N` within its first 100 characters,
  so the watcher's transcript derivation can see it. Decisions files are
  copied to `patches/` by the relay before the builder is prompted.

### 0.6 Standing rules (from CLAUDE.md, repeated because load-bearing)

The receiver owns plumbing and policy and nothing else. It never reads a
dialect: a record's trace id, span id or kind comes from spanweave's
adapters (`spanweave.adapters.classify` and the claiming adapter's `parse`),
never from a key the receiver looks up itself. It carries no rules and no
semantics — a consumer evaluates graphs; the receiver hands them over. It
enforces nothing: detection is observation, and holding or refusing a call
belongs to a gate the receiver does not know exists. The clock, sleeping and
sockets are injected seams (`now`, `sleep`, a listener factory) so that every
test runs on a fake clock and the conformance gate is deterministic. Nothing
is dropped silently: a refusal, a cap, a late arrival or a consumer error is
an event with a code, counted and reported. `spanweave` is pinned to one
commit in `pyproject.toml` and the corpus submodule is at the same commit; a
test holds the two equal.

TASKS.md is the item registry (one line per batch, written at series
close); this file is execution state only and is deleted at series close
with §3 and §4 folded into TASKS.md.

### 0.7 Watch (aux, read-only, report-then-stop)

While the builder is on a run, aux may run `~/spanweave-ops/watch_monitor.sh`
with `--base` set to the run's plan commit; it derives the branch and the
builder PIDs itself. Triggers and tripwires are as `~/spanweave-ops/WATCH.md`
states; the series-close commit that deletes this file is the one plan
commit that cannot say `plan:`, and the watcher exempts it once per series.

---

## 1. Batch list

| ID | Batch | Status | Calls |
|---|---|---|---|
| R0 | **Repository skeleton, on `main`.** `pyproject.toml` (package `spanweave_live`, CLI `spanweave-live`, Python 3.11–3.14, `spanweave` pinned as `spanweave @ git+https://github.com/SigorMatt/spanweave@e42f257b91be1bd9c7be6bcdbd31313947401288`); `uv.lock`; git submodule `corpus/` = spanweave at the same sha, read-only, used only for `fixtures/conformance/`; `tests/test_pins.py` asserting the dependency sha and the submodule sha are equal; `Makefile` with `check` (ruff, format, `mypy --strict`, pytest, gates), `conformance`, `install-check` (wheel into a throwaway venv, run from outside the repo); `.github/workflows/ci.yml` as spanweave's (`check` on 3.11–3.14; `conformance` on ubuntu and macos; submodules checked out); `CLAUDE.md` with §0.6; `CONTRIBUTING.md` with the batch bar; `SPEC.md` with §1 non-goals (no dialect, no rules, no enforcement, no own clock) and §2 the three properties the receiver designs around, quoted from spanweave `SPEC.md` §7 (no buffering across calls; dedup per call; reading is cheap, absorbing is not); `tests/gates.py` with one gate: no module under `spanweave_live/` imports `time`, `datetime`, `random`, `socket`, `threading` or `asyncio` outside the files §0.6's seams name; `README.md` one paragraph; `CHANGELOG.md`. `make check` green, CI green on `main`. Then `git switch -c receiver`; every later batch lands on `receiver`. | done (696702f) | 10 |
| R1 | **Framing: bytes in, complete records out.** `Framer` (SPEC §3): `push(chunk: bytes) -> Records` splits on `\n`, keeps the remainder, hands only complete lines to `spanweave.read_records`; `document(body: bytes) -> Records` hands a whole OTLP-JSON body over unsplit; `flush() -> Records` reads the remainder as a final line and reports it; `pending_bytes` is the remainder's length. Diagnostics from `read_records` are re-issued per chunk with the absolute line offset added. Tests red on the parent: over every rendering of the corpus, feeding the bytes in seeded random chunk sizes (1 to whole) yields `read_records(whole)`'s records exactly; a chunk boundary inside a multi-byte character yields no `undecodable_bytes`; a truncated final line is `pending_bytes > 0` and not a `malformed_record` until `flush()`. Mutation: a framer that hands partial lines over fails the first test. | done (a4fec60) | 10 |
| R2 | **Partition: one `Builder` per trace, and conformance gate A.** `Router` (SPEC §4): `route(record) -> Routed` finds the trace id through `spanweave.adapters.classify` and the claiming adapter's `parse`, never by a key of its own; one `Builder` per trace id, created on first sight; a record with no trace id or no claimant goes to the no-trace builder (which carries `missing_trace_id`/`unclaimed_record` as batch does); a `Builder` refusal is an event `refused` with the record index and the spanweave code, counted, and routing continues; `max_traces` is a cap — at the cap a new trace is `refused_at_cap`, counted, never dropped silently. Gate A, `tests/test_conformance.py`: for every pair of renderings from two scenarios, interleave their records by a seeded shuffle, push through `Framer` + `Router`, and assert each trace's `graph()` serializes byte for byte to `spanweave.build` of its own rendering; run it for ten seeds. Tests red on the parent; mutation: a router keyed by the record's own `trace_id` key (a dialect read) fails `tests/test_routing.py::test_a_record_no_adapter_claims_is_not_routed_by_its_trace_id_key`. ~~fails on `otlp_container`~~ — corrected by R2, see §4. | done (d762484) | 15 |
| R2a | **The run-1 review's eight `next batch` items, closed.** Read `patches/REVIEW-2026-10-04.md` and close every `next batch` item as the file states it, one commit, tests first. Among them: the import gate is held to walking (a test asserts the gate's module set equals `rglob` of `spanweave_live/`, and a planted nested module importing `time` is caught with no gate edit); the 612-framing sweep gains renderings that carry a diagnostic and a skipped record (a corpus rendering with one line corrupted, generated from the corpus at test time, never a hand-copied fixture), so the diagnostics and `skipped_records` assertions compare non-empty sequences and a `push` reporting `skipped_records=0` fails; SPEC states the HTTPS pin for both the dependency and the submodule, held by a test; SPEC and CHANGELOG state the `py.typed` override and why; SPEC §3.3 states the `push`-vs-`document` trap in full (a whole body pushed happens to read; chunked it does not). Items the file lists that this row does not name are closed too. | done (7fdbff3) | 8 |
| R2b | **The remainder has a caller-set cap.** `Framer(max_pending_bytes=None)`; SPEC §3.4 rewritten from "no cap" to the policy in §3. Tests red on the parent: a stream with no `\n` past the cap yields one `malformed_record`, `skipped_records=1`, one `fragment_too_long` event with the length, and the framer continues on the next chunk; with the cap `None`, R1's behaviour is unchanged across the whole sweep. Mutation: a framer that drops the oversize remainder silently fails the `skipped_records` assertion. | done (d152c3b) | 5 |
| R2c | **Pins bumped to a spanweave that ships `py.typed`; the override deleted.** After PR #4 merges: `pyproject.toml` pin and `corpus/` submodule to the new `main` sha (the two-way pin test holds them equal); `[tool.mypy]` override for `spanweave.*` deleted, and a test asserts no `follow_untyped_imports` remains; `make check` green with `mypy --strict` analysing spanweave itself. If PR #4 is not merged when this row is reached, status `awaiting PR #4` and the run stops. | awaiting PR #4 | 4 |
| R3 | **Completion is a policy with an injected clock.** `Completion` (SPEC §5): three policies, each a value — `Quiet(seconds)`, `RootEnded(grace_seconds)`, `Cap(records)` — composable as any-of; `now: Callable[[], float]` is injected, never `time.time` inside `spanweave_live/`; `Router.tick()` evaluates policies and returns the traces completed; a completed trace's final graph is materialized, optionally written with `spanweave.dump` to a directory the caller names, and its builder released; a record arriving for a completed trace opens a new builder and emits `late_arrival` with the trace id and the gap. Tests on a fake clock: each policy fires exactly when its definition says; a late arrival is an event, never silent, and never a mutation of the written graph. Mutation: a `Quiet` that fires one tick early fails. | done (e09af3f) | 10 |
| R4 | **Subscription and delta fan-out.** `Subscriptions` (SPEC §6): a consumer registers a callback for one trace or all; after each absorbed record the router hands each subscriber `delta(since=version-1)` (per-record mode) or, for a subscriber that asked for `every=N`, `delta(since=last_seen)`; retention is set from the longest window any subscriber asked for; a callback that raises is isolated — recorded as `consumer_error` with the trace id and version, other subscribers still called, the record still absorbed. Tests: folding every delta a subscriber received onto its first graph equals the final `graph()`; a raising subscriber never stalls another. Mutation: a fan-out that skips the subscriber after the raising one fails. | done (54a6009) | 10 |
| R5 | **Ingest: file tail and stdin.** `tail(path, *, now, sleep, poll_seconds)` (SPEC §7.1) follows a growing file from an offset through `Framer.push`, survives truncation (restarts from 0 and emits `truncated`), and rotation (reopens by path); `stdin()` reads chunks until EOF. Both take `sleep` injected, so the test drives them on a fake clock with a file it appends to between ticks. ~~Both are generators of `Records`~~ — corrected by R5: `stdin()` is a generator, but `tail` returns a `Tail` object that *is* the iterator, because §3.1 forbids wrapping `Records` and a bare generator has nowhere to carry its events; see §4. Tests: a corpus rendering appended in random chunks is routed to the same graphs as gate A; truncation and rotation are events. | done (a7ade79) | 10 |
| R6 | **Ingest: OTLP/HTTP JSON endpoint.** (SPEC §7.2) Stdlib `http.server` only; one handler for `POST /v1/traces` with `Content-Type: application/json`, body → `Framer.document`; `Content-Encoding: gzip` accepted; anything else 415; the listener factory is injected so tests use a loopback socket on port 0. Tests: the `otlp_container` renderings posted as bodies route to the batch graph; a non-JSON body is 400 with the receiver's event, never a traceback. | awaiting R5 | 10 |
| R7 | **CLI.** `spanweave-live tail <path> --out <dir> [--quiet S] [--root-grace S] [--cap N] [--deltas]` and `spanweave-live serve --port P --out <dir>`: final graphs written as `<trace_id>.json` with `spanweave.dump`; `--deltas` writes each per-record delta document to stdout as one line; every event to stderr as one JSON line with its code; exit codes documented. Tests through `subprocess` on a corpus rendering. | awaiting R6 | 8 |
| R8 | **Showcase: agentgolden's rules per delta.** agentgolden is `SigorMatt/agentgolden` at `aa1847f`, pinned as a dev dependency by git sha (its own `spanweave>=0.9.1,<1.0` resolves against the pinned spanweave). A consumer that, on each per-record delta, takes the trace's `graph()`, computes agentgolden's `Signature`, evaluates `examples/support_agent/rules.toml` **unchanged** with `agentgolden.rules.evaluate`, and records the first version at which each rule fails. The trace is agentgolden's own `examples/support_agent/candidates/skipped_verification.openinference.jsonl`, replayed through `Framer` + `Router`. Test: the first-failure version table is asserted exactly, and the `verify_identity → issue_refund` order rule fails at the version that absorbs the `llm.plan` span carrying the `issue_refund` request — one version before the `issue_refund` tool span arrives — which is the "when it almost happened" the memo promised; the same rules on the batch graph of the whole trace give the same final verdicts (batch and live are one model). | awaiting R7 | 12 |
| R9 | **The receiver series closes.** `TASKS.md` registry R0–R9 with shas; §3 folded; `reviews/` holds every review byte-for-byte with sha256 and every finding dispositioned; WORKPLAN.md deleted; README covers the CLI and the API; PR `receiver` → `main`. No `plan:` commit follows. | awaiting R8 | 8 |

## 2. Execution order

Run 1 = R0 → R1 → R2, then stop: cold review (aux), decisions. Run 2 = R2a
→ R2b → R3 → R4 → R5 → R2c, then stop: cold review (aux), decisions. Run 3
= R6 → R7 → R8 → R9, then a scoped review of the close and the PR. Every
batch: CI green on the pushed tip before `done`. R0 lands on `main` because
the repository is empty; R1 onward land on `receiver`.

## 3. Decisions log

| Date | Batch | Decision | By |
|---|---|---|---|
| 2026-10-04 | series | The receiver finds a record's trace id through spanweave's public adapter surface (`classify` + the claiming adapter's `parse`) rather than a new spanweave API; the second parse is paid for now and registered as a thread (`spanweave.trace_id_of(record)` would halve it) to be decided on measurement after R2. The clock is injected everywhere; no module under `spanweave_live/` reads it. `spanweave` is pinned by git sha, and the corpus is a submodule at the same sha. | maintainer |
| 2026-10-05 | review run 1 | Nothing blocks. The review's eight `next batch` items are one fix batch (R2a) made by the builder from the review file; its ten threads are registered at close. The `trace_id_of` thread stays a thread: re-measured at 15.5–17.1 % of routing, it is an optimisation and gets no batch until a receiver workload makes routing the cost. | maintainer |
| 2026-10-05 | framer cap | The framer's remainder gets a caller-set cap, `max_pending_bytes`, default `None` (unbounded, as R1 shipped). When a push would exceed it, the remainder plus the chunk's bytes up to the next `\n` are handed to the reader as one line — so they surface as `malformed_record` with `skipped_records` counted, never dropped — and the framer emits `fragment_too_long` with the length. Policy, not mechanism, so it is the caller's number (R2b). | maintainer |
| 2026-10-05 | py.typed | spanweave gains `spanweave/py.typed` in its own one-commit PR (#4) to `main`, made by the builder, merged after its checks are fetched. The receiver then bumps both pins to the new `main` sha and deletes the `follow_untyped_imports` override (R2c), with a test that the override is gone. | maintainer |
| 2026-10-05 | §0.6 | At series close both §3 and §4 fold into TASKS.md, not §3 alone; corrected in this commit. | maintainer |
| 2026-10-05 | run 2 | R2a → R2b → R3 → R4 → R5 → R2c, then stop for a cold review. R2c is last so that PR #4 has merged by the time it runs; if it has not, R2c ends `awaiting PR #4` and the run stops there. | maintainer |

## 4. Resume note

- 2026-10-04: series opened. spanweave `main` after PR #3 is
  `e42f257b91be1bd9c7be6bcdbd31313947401288`; agentgolden is
  `SigorMatt/agentgolden` at `aa1847f`, which R8 pins.
- 2026-10-04 R0 (`696702f`, CI green on `main`, 6/6 jobs): the spanweave pin
  and the `corpus/` submodule are both **HTTPS**, not SSH — CI's
  `submodules: true` checkout uses the Actions token, which SSH would have
  broken; `git ls-remote` over HTTPS was verified unauthenticated. hatchling
  needs `[tool.hatch.metadata] allow-direct-references = true` to accept a
  sha-pinned dependency. `make conformance` exists but **asserts nothing**
  until R2 brings gate A: it prints "NO GATE YET … It is not a pass", so a
  green `conformance` job is not evidence of anything before R2. The gate's
  seam allowlist is currently **empty** (a test holds that) — R3 and R5/R6
  are the batches that first put a file in it. `install-check` is a step of
  the CI `check` job, not a prerequisite of `make check` (the Makefile keeps
  it deliberately separate), so CI shows six jobs, not seven.
- 2026-10-04 R1 (`a4fec60`, CI green on the `receiver` tip, 6/6): **`spanweave`
  ships no `py.typed`** — not in the wheel and not in the repo — so
  `mypy --strict` refuses to analyse it as soon as a receiver module imports
  it. `pyproject.toml` carries one narrow override,
  `follow_untyped_imports = true` for `spanweave.*`, chosen over
  `ignore_missing_imports` because the latter would make `Records`,
  `Diagnostic` and `read_records` all `Any` and every annotation in this repo
  vacuous; a planted `x: int = read_records(b"")` was shown to still error.
  **Thread:** adding `spanweave/py.typed` is a one-line upstream change that
  would let this override be deleted — decide alongside the
  `spanweave.trace_id_of(record)` thread in §3.
- 2026-10-04 R1: `push` is **not** a second way to read a document. The
  reader's container detection is per call, so a pretty-printed OTLP body
  pushed whole happens to read, but pushed in chunks becomes one
  `malformed_record` per line. Asserted both ways in SPEC §3.3: **R6 must
  hand POST bodies to `Framer.document`, never `push`** (its row already says
  so). SPEC §3.4 records that the remainder has **no cap** — `pending_bytes`
  makes unbounded growth visible, and naming a cap would have been inventing
  a policy the spec does not state, so R1 declined rather than guessed. If a
  cap is wanted it is a decision for §3, not a patch.
- 2026-10-04 R2 (`d762484`, CI green on the `receiver` tip, 6/6): gate A is
  live and `make conformance` finally asserts something — 29 scenarios, 53
  renderings (51 `.jsonl` through `Framer.push` in seeded chunks, 2 OTLP
  documents through `Framer.document`), 1354 cross-scenario pairs × 10 seeds
  (`0,1,2,3,7,11,13,101,1009,20261004`) = **27 080** byte-for-byte graph
  comparisons, ~25 s. Note the premise gate A had to repair to be a real
  test: **every corpus rendering is trace `t1`**, so one side of each pair is
  relabelled `t1`→`zz1`, or the pair would share a single builder and the
  test would assert nothing. A guard test holds that premise.
- 2026-10-04 R2 — **the row's mutation criterion was wrong and is corrected
  above.** `spanweave.read_records` normalizes a container's `traceId` to
  `trace_id` while unpacking, so a router keyed by `record["trace_id"]`
  disagrees with the adapter surface on **no** corpus record (0 of 53
  renderings, verified record by record) — `otlp_container` does not catch
  the dialect read, and gate A passed 13/13 with the mutation planted. What
  catches it is an **unclaimed** record:
  `tests/test_routing.py::test_a_record_no_adapter_claims_is_not_routed_by_its_trace_id_key`
  (`assert 3 == 2`). The row now names that test. Gate A was separately shown
  able to fail, by planting "a new builder per record". The lesson for later
  rows: the corpus's renderings agree on key names far more than the dialect
  story suggests, so a mutation aimed at a dialect read needs a record no
  adapter claims, not an exotic container.
- 2026-10-04 R2 — **measurement for the §3 `spanweave.trace_id_of(record)`
  thread, which §3 said to decide after R2**: on an OpenInference span,
  `trace_id_of` costs 23.7 µs/record against `Builder.feed`'s 111.3 µs, so
  the second parse is **~18%** of per-record routing cost, not the ~50% the
  thread assumed. On this number the upstream API is an optimisation, not a
  necessity. **Awaiting maintainer decision** (together with the `py.typed`
  thread from R1); R3 does not depend on either.
- 2026-10-05: run-1 cold review read and decided (§3). Nothing blocked;
  the review's eight items become R2a, the framer cap is R2b, and
  spanweave's missing `py.typed` is fixed upstream (PR #4) with the pin bump
  as R2c at the end of run 2. §0.6 now folds §3 and §4 at close.
- 2026-10-05 R2a (`7fdbff3`, CI green on the `receiver` tip, 6/6): the
  review's items are closed and **five tests that could not fail now can**.
  Tests 105 → 232. The sweep is 51 renderings × **2 forms** × 12 framings =
  **1224** framings: the second form is generated by `corrupted()` from
  corpus bytes at test time (middle line → `{"oops`), so the `diagnostics`
  and `skipped_records` assertions now compare non-empty sequences — a `push`
  reporting `skipped_records=0` fails 52 tests where before it failed none.
  The import gate is held to walking the tree (`package_files()` vs an
  `rglob` computed in the test), and a planted three-level nested module
  importing `time` is caught **with no gate edit** — the old gate went green
  on it, which was the vacuity. Gate A is **unchanged at ~25 s**; the
  corrupted-rendering cost lands in `test_framing.py` alone (0.23 s → 0.45 s).
  `Router` is now `kw_only=True`.
- 2026-10-05 R2a — **one review item needed no commit from R2a**: the false
  "`make check` runs `install-check`" line in §4's R0 note was already
  corrected by the plan commit `9a2e40f` (§5 of the decisions file), and the
  plan is not a batch's file to edit. Recorded here so the item reads as
  closed by `9a2e40f`, not as skipped. R2a confirmed nothing else states it
  wrongly.
- 2026-10-05 R2a — the `py.typed` override is now stated as a **temporary**
  fact in SPEC §0.2, `CHANGELOG.md` and a `pyproject.toml` comment, each
  citing PR #4 (`bea9d44`, open, green, **unmerged**). No pin moved and the
  override is intact: that is R2c's work. The `trace_id_of` measurement
  (15.5–17.1 % of routing) now lives in SPEC §4.2 rather than only in this
  file, and its citations point at "§3 while the series runs, `TASKS.md`
  after" — so the number outlives WORKPLAN.md's deletion at close.
- 2026-10-05 R2b (`d152c3b`, CI green on that sha, 6/6): the framer cap is in
  as §3 decided — `Framer(*, max_pending_bytes=None)`, strict `>` boundary,
  `document` and `flush` uncapped. Tests 232 → 340; gate A still ~25.4 s. The
  **red-on-parent run was real this time** (parent `7fdbff3` is code, not a
  `plan:` commit): 108 failed / 172 passed, and R1's other framing tests all
  still passed there, which is what makes the 108 meaningful.
- 2026-10-05 R2b — two surface choices the decision left to the batch, now in
  SPEC §3.1: `FramingEvent` is **its own type**, not routing's `Event` (a
  framing event has a length and no record index, trace id or spanweave code,
  and `framing.py` importing from `routing.py` would be an upward import);
  and events ride **beside** the return value (`Framer.events`,
  `Framer.counts`) because §3.1 forbids wrapping `spanweave.Records`. R3's
  completion events and R4's `consumer_error` should follow routing's `Event`,
  not this one — the split is deliberate, not an inconsistency to tidy.
- 2026-10-05 R2b — **a consequence worth carrying forward** (SPEC §3.4): a cut
  line's fragments are each numbered as a line, so **line numbers downstream
  of a `fragment_too_long` are the framer's count, not the input's**. Any
  later batch that reports a line number to a human (R7's CLI especially)
  inherits this.
- 2026-10-05 R3 (`e09af3f`, CI green on that sha, 6/6): completion is in as
  three composable values on an injected clock. Tests 340 → 385; gate A
  unchanged at ~25.5 s. Red on the code parent `d152c3b` was meaningful: the
  parent's own 340 passed and all 45 new tests were red.
- 2026-10-05 R3 — **the seam allowlist is still empty, and R0's prediction
  that R3 would need the first entry was wrong.** `Completion.now` has **no
  default**, so no module under `spanweave_live/` imports `time` at all; the
  real clock enters at the caller, which is R7's CLI. The wrong prediction is
  now corrected in `gates.py` and in the allowlist test's comment. R5 (`sleep`)
  and R6 (a listener) are the next candidates for a first entry — and on this
  evidence they should be made to prove they need one.
- 2026-10-05 R3 — judgement the row did not settle, now in SPEC §5.6:
  `RootEnded` completes on **at least one root and *every* root ended** (the
  conservative reading — "any root" would complete a trace whose other
  top-level operation is still open), and the grace runs from **the tick that
  first saw the end**, not from the span's `ended_at`, because those are two
  different clocks. Root = no incoming `parent` edge **and** no
  `orphan_parent` diagnostic naming it, both read through spanweave's public
  graph surface; no dialect read, no spanweave change, so no halt.
- 2026-10-05 R3 — **a known unbounded cost, stated rather than invented away**
  (SPEC §5.5): the router keeps four numbers and a flag **per trace id it ever
  completed**, because the `late_arrival` gap and the new builder's generation
  name need them. `max_traces` does **not** bound this. The fix is a
  *forgetting* policy, which is a §3 decision, not a batch's to invent —
  **awaiting maintainer decision**, and it does not block R4 or R5.
- 2026-10-05 R3 — two smaller facts: routing's `Event` gained one optional
  field `seconds` (`FramingEvent` stays separate, per R2b); and the
  "not written because the library refused" branch is **unreachable through
  the public surface** (an identified trace has a claimed record by
  construction), kept deliberately and labelled as such in SPEC §5.4, so it
  has no test. `README.md`'s "R1–R7 will bring…" sentence is stale a third
  time over; **R9 owns the README** and no batch before it should patch that
  line piecemeal.
- 2026-10-05 R4 (`54a6009`, CI green on that sha, 6/6): subscriptions and
  delta fan-out are in. Tests 385 → 410; gate A ~25.2 s, unchanged. Red on the
  code parent `e09af3f` was meaningful: its own 385 passed, all 25 new red.
  The central claim is asserted twice (per-record and `every=2`), and in a form
  that cannot skip a delta: the first delta's additions **are** the first
  graph, and folding the rest onto it equals `graph()` byte for byte.
- 2026-10-05 R4 — **R4 bounds a cost rather than adding one.** A `spanweave`
  `Builder` defaults to `retain("all")`, so every router since R2 has been
  holding a journal entry per absorbed record; retention is now
  `builder.retain(max(every for covering subscriptions))` per trace, applied
  only when the window **changes**, and `window(trace_id)` is `None` — leaving
  retention **untouched, not 0** — when nobody covers a trace, because
  `Routed.builder` is public and a caller's own `retain` must not become a
  traceback instead of a `delta_unavailable` event. Cursors are one `int` per
  subscription per *currently held* builder, forgotten on release, so
  `max_traces` bounds them. **R3's §5.5 per-trace-id book is still the
  series' only unbounded thread**, untouched and not depended on.
- 2026-10-05 R4 — specified choices: subscriber order is **registration
  order** (SPEC §6.2) because `id()`/`hash()`/callback names are either
  unstable across processes or a ranking nobody chose; `trace_id=None`
  subscribes to the **no-trace builder too**, deliberately unlike §4.5/§5.4,
  because reporting throws nothing away while releasing does (§6.3); and
  `delta_unsent` is a **report, not a flush** — an `every=N` subscriber's
  residual window is an event, never a final partial delivery. Routing's
  `Event` gained one optional field `version`, following R3's `seconds`.
- 2026-10-05 R4 — **the seam allowlist is still empty**; R4 needed no entry
  either. R5 (`sleep`) and R6 (a listener) remain the only candidates.
- 2026-10-05 R5 (`a7ade79`, CI green on that sha, 6/6 **including macOS
  conformance**, which matters because rotation detection is a platform fact):
  file tail and stdin are in. Tests 410 → 444; gate A **25.22 s, unchanged**;
  R5's own file costs 1.2 s. Red on the code parent `54a6009` was meaningful:
  its own 410 passed there. The central test reaches gate A's own comparison
  through a real file, importing `loaded`/`chunked`/`undigested` from
  `tests/test_conformance.py` rather than inventing a weaker check.
- 2026-10-05 R5 — **the seam allowlist is still `{}`, and R0 was wrong twice.**
  `tail` takes `now` and `sleep` with no defaults, exactly as `Completion.now`
  does, so nothing under `spanweave_live/` imports `time` or `asyncio`; R7's
  CLI binds the real pair. `tests/gates.py` now records both wrong predictions
  and says **R6's listener must be made to prove it needs a line**. A test
  asserts `SEAMS == {}` and that ingest is gate-clean.
- 2026-10-05 R5 — detection, read rather than chosen: truncation is
  `os.fstat` of the **open handle** reporting `st_size < offset`, checked
  before each poll's reads; rotation is `path.stat()` disagreeing with
  `os.fstat(handle)` on `(st_dev, st_ino)`, checked **only on a poll that read
  nothing**, so the old inode's unread bytes are handed over first. Both
  restarts **flush the framer**, so held bytes come back as a
  `malformed_record` and are never joined to new content. `(st_dev, st_ino)`
  is the platform's own answer, so no policy was invented and no halt was
  needed. Also `vanished` (once per vanishing) and `reopen_failed`.
- 2026-10-05 R5 — three things stated instead of smoothed over: a
  truncate-and-regrow **past** the old offset between two polls is
  **indistinguishable from growth** (SPEC §7.1, a limitation, not a
  heuristic); **no event for a short read**, because `read(n)` returning fewer
  bytes is how a file says "that is all for now" and a code would fire every
  poll; and the row's "both are generators" was wrong — corrected in §1 above.
  `routing.Event` gained one optional field `offset`, following `seconds`
  (R3) and `version` (R4).
- 2026-10-05 **run 2 stops here. R2c is `awaiting PR #4`**: the upstream
  `py.typed` PR (`SigorMatt/spanweave` #4, commit `bea9d44`) is **open,
  mergeable, all checks green, and unmerged**, so the new `main` sha R2c must
  pin does not exist yet. This is the §3 run-2 decision's own stated outcome,
  not a failure. When #4 merges, R2c is `todo` and needs only the merge sha:
  bump the `pyproject.toml` pin and the `corpus/` submodule to it (the two-way
  pin test holds them equal), delete the `follow_untyped_imports` override
  with a test that it is gone, and confirm `mypy --strict` analyses spanweave
  itself. Nothing else in run 2 is blocked by it.

## 5. Origins

| ID | Origin |
|---|---|
| R0–R7, R9 | spanweave `OPEN_QUESTIONS.md` §19 (receiver project items 1–5) and its decision of 2026-09-29; spanweave `SPEC.md` §7 (the reader's three properties) and §10.10. |
| R8 | §19 "The live consumer, and why it needs no new rules". |
