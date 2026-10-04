# WORKPLAN.md — spanweave-live, the receiver series

Status file for the receiver series: where the live graph meets the
network, the clock and the consumer (`spanweave` `OPEN_QUESTIONS.md` §19,
decided 2026-09-29). One batch = one sub-agent = one commit = one concern.
This file plus git is the only state; any session can resume cold from it.

Last updated: 2026-10-04 (run 1 complete: R0, R1, R2 done; awaiting cold review and two decisions).

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
with §3 folded into TASKS.md.

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
| R3 | **Completion is a policy with an injected clock.** `Completion` (SPEC §5): three policies, each a value — `Quiet(seconds)`, `RootEnded(grace_seconds)`, `Cap(records)` — composable as any-of; `now: Callable[[], float]` is injected, never `time.time` inside `spanweave_live/`; `Router.tick()` evaluates policies and returns the traces completed; a completed trace's final graph is materialized, optionally written with `spanweave.dump` to a directory the caller names, and its builder released; a record arriving for a completed trace opens a new builder and emits `late_arrival` with the trace id and the gap. Tests on a fake clock: each policy fires exactly when its definition says; a late arrival is an event, never silent, and never a mutation of the written graph. Mutation: a `Quiet` that fires one tick early fails. | todo | 10 |
| R4 | **Subscription and delta fan-out.** `Subscriptions` (SPEC §6): a consumer registers a callback for one trace or all; after each absorbed record the router hands each subscriber `delta(since=version-1)` (per-record mode) or, for a subscriber that asked for `every=N`, `delta(since=last_seen)`; retention is set from the longest window any subscriber asked for; a callback that raises is isolated — recorded as `consumer_error` with the trace id and version, other subscribers still called, the record still absorbed. Tests: folding every delta a subscriber received onto its first graph equals the final `graph()`; a raising subscriber never stalls another. Mutation: a fan-out that skips the subscriber after the raising one fails. | todo | 10 |
| R5 | **Ingest: file tail and stdin.** `tail(path, *, now, sleep, poll_seconds)` (SPEC §7.1) follows a growing file from an offset through `Framer.push`, survives truncation (restarts from 0 and emits `truncated`), and rotation (reopens by path); `stdin()` reads chunks until EOF. Both are generators of `Records` with `sleep` injected, so the test drives them on a fake clock with a file it appends to between ticks. Tests: a corpus rendering appended in random chunks is routed to the same graphs as gate A; truncation and rotation are events. | awaiting R3 | 10 |
| R6 | **Ingest: OTLP/HTTP JSON endpoint.** (SPEC §7.2) Stdlib `http.server` only; one handler for `POST /v1/traces` with `Content-Type: application/json`, body → `Framer.document`; `Content-Encoding: gzip` accepted; anything else 415; the listener factory is injected so tests use a loopback socket on port 0. Tests: the `otlp_container` renderings posted as bodies route to the batch graph; a non-JSON body is 400 with the receiver's event, never a traceback. | awaiting R5 | 10 |
| R7 | **CLI.** `spanweave-live tail <path> --out <dir> [--quiet S] [--root-grace S] [--cap N] [--deltas]` and `spanweave-live serve --port P --out <dir>`: final graphs written as `<trace_id>.json` with `spanweave.dump`; `--deltas` writes each per-record delta document to stdout as one line; every event to stderr as one JSON line with its code; exit codes documented. Tests through `subprocess` on a corpus rendering. | awaiting R6 | 8 |
| R8 | **Showcase: agentgolden's rules per delta.** agentgolden is `SigorMatt/agentgolden` at `aa1847f`, pinned as a dev dependency by git sha (its own `spanweave>=0.9.1,<1.0` resolves against the pinned spanweave). A consumer that, on each per-record delta, takes the trace's `graph()`, computes agentgolden's `Signature`, evaluates `examples/support_agent/rules.toml` **unchanged** with `agentgolden.rules.evaluate`, and records the first version at which each rule fails. The trace is agentgolden's own `examples/support_agent/candidates/skipped_verification.openinference.jsonl`, replayed through `Framer` + `Router`. Test: the first-failure version table is asserted exactly, and the `verify_identity → issue_refund` order rule fails at the version that absorbs the `llm.plan` span carrying the `issue_refund` request — one version before the `issue_refund` tool span arrives — which is the "when it almost happened" the memo promised; the same rules on the batch graph of the whole trace give the same final verdicts (batch and live are one model). | awaiting R7 | 12 |
| R9 | **The receiver series closes.** `TASKS.md` registry R0–R9 with shas; §3 folded; `reviews/` holds every review byte-for-byte with sha256 and every finding dispositioned; WORKPLAN.md deleted; README covers the CLI and the API; PR `receiver` → `main`. No `plan:` commit follows. | awaiting R8 | 8 |

## 2. Execution order

Run 1 = R0 → R1 → R2, then stop: cold review (aux), decisions. Run 2 = R3
→ R4 → R5, then stop: cold review, decisions. Run 3 = R6 → R7 → R8 → R9, then
a scoped review of the close and the PR. Every batch: CI green on the pushed
tip before `done`. R0 lands on `main` because the repository is empty; R1
onward land on `receiver`.

## 3. Decisions log

| Date | Batch | Decision | By |
|---|---|---|---|
| 2026-10-04 | series | The receiver finds a record's trace id through spanweave's public adapter surface (`classify` + the claiming adapter's `parse`) rather than a new spanweave API; the second parse is paid for now and registered as a thread (`spanweave.trace_id_of(record)` would halve it) to be decided on measurement after R2. The clock is injected everywhere; no module under `spanweave_live/` reads it. `spanweave` is pinned by git sha, and the corpus is a submodule at the same sha. | maintainer |

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
  are the batches that first put a file in it. `make check` runs
  `install-check` as a step, so CI shows six jobs, not seven.
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

## 5. Origins

| ID | Origin |
|---|---|
| R0–R7, R9 | spanweave `OPEN_QUESTIONS.md` §19 (receiver project items 1–5) and its decision of 2026-09-29; spanweave `SPEC.md` §7 (the reader's three properties) and §10.10. |
| R8 | §19 "The live consumer, and why it needs no new rules". |
