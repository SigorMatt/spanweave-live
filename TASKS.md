# TASKS.md — the receiver series, registered

This is the item registry for `spanweave-live`: one line per batch, with the
commit that closed it, plus the decisions the series took, the facts its batches
measured, and the disposition of every finding of every review.

It exists because `WORKPLAN.md` does not. That file was the series' **execution
state** — the operating protocol, the batch rows with their acceptance criteria,
the decisions log (§3) and the resume note (§4) — and it was written to be
deleted at series close, so that a reader looking for what this project is never
has two places to look. Its §0.6 said so from the start: *"TASKS.md is the item
registry (one line per batch, written at series close); this file is execution
state only and is deleted at series close with §3 and §4 folded into TASKS.md."*
Both are folded here. The file itself is not gone, only untracked from the tip:
it is at `git show b500342:WORKPLAN.md`, its last state, and at
`git show 696702f:WORKPLAN.md` for the form the series opened with.

What is **not** here, because it is in the spec and the spec outlives this file
too: every rule the receiver obeys (`CLAUDE.md`), everything it does
(`SPEC.md`), and the bar a change clears (`CONTRIBUTING.md`). This registry
records what happened, not what holds.

---

## The batches, with final status

Fifteen batches across three runs, one commit each. R0 landed on `main` because
the repository was empty; every other batch landed on `receiver`. The
out-of-order ids are
real: `R2a`/`R2b`/`R2c`/`R3a`/`R5a` were inserted into a numbered plan after it
was written, and they are kept at the position they were inserted rather than
renumbered, so that a commit message or a review naming `R5a` still resolves.

| ID | What it was | Status |
|---|---|---|
| R0 | Repository skeleton on `main`: `pyproject.toml` with `spanweave` pinned by git sha, `corpus/` as a submodule of that repository at the same sha, `tests/test_pins.py` holding the two equal, the `Makefile` gates, CI, `CLAUDE.md`, `CONTRIBUTING.md`, `SPEC.md` §1–§2, the ambient-import gate, `README.md`, `CHANGELOG.md` | **done** (`696702f`) |
| R1 | Framing: `Framer.push`/`document`/`flush`/`pending_bytes` — bytes in arbitrary chunks, complete records out, diagnostics re-issued with the absolute line offset (`SPEC.md` §3) | **done** (`a4fec60`) |
| R2 | Routing: one `spanweave.Builder` per trace, the trace id read through `spanweave`'s adapter surface, refusals and `max_traces` as counted events — and **conformance gate A**, the project's central claim (`SPEC.md` §4) | **done** (`d762484`) |
| R2a | The run-1 review's eight `next batch` items closed, and five tests that could not fail made able to fail | **done** (`7fdbff3`) |
| R2b | The framer's remainder gets a caller-set cap, `max_pending_bytes`, and the oversize fragment is reported rather than dropped (`SPEC.md` §3.4) | **done** (`d152c3b`) |
| R2c | Both pins moved to a `spanweave` that ships `py.typed`, and the `follow_untyped_imports` override deleted rather than merely unused (`SPEC.md` §0.2) | **done** (`a4ce94b`) |
| R3 | Completion is a policy with an injected clock: `Quiet`, `RootEnded`, `Cap` as composable values, `Router.tick()`, the final graph written and the builder released (`SPEC.md` §5) | **done** (`e09af3f`) |
| R3a | Completed trace ids are forgotten by the caller's bound, `Router(max_completed=…)`, one `forgotten` event per id — the series' only unbounded cost, bounded (`SPEC.md` §5.5) | **done** (`baa32cb`) |
| R4 | Subscriptions and delta fan-out: per-record and `every=N`, retention set to the hungriest subscriber's window, a raising consumer isolated as `consumer_error` (`SPEC.md` §6) | **done** (`54a6009`) |
| R5 | Ingest: `tail` follows a growing file through truncation and rotation, `stdin` reads a pipe to EOF, both on injected seams (`SPEC.md` §7.1) | **done** (`a7ade79`) |
| R5a | The run-2 review's twelve `next batch` items closed, including the `every=N` trailing delta on completion and `Router.flush`, and `check (macos-latest, 3.12)` added to CI | **done** (`c1e6946`) |
| R6 | Ingest: the OTLP/HTTP JSON endpoint, stdlib `http.server` only, the listener injected so tests bind port 0 (`SPEC.md` §7.2) | **done** (`8ae7a5d`) |
| R7 | The CLI: `spanweave-live tail` and `spanweave-live serve`, graphs written as `<trace_id>.json`, every event one JSON line on stderr, exit codes documented (`SPEC.md` §8) | **done** (`d21859d`) |
| R8 | The showcase: `agentgolden`'s support-agent rules, unchanged, evaluated on every per-record delta, with the first-failure version table asserted exactly — and the row's own central claim falsified (`SPEC.md` §9) | **done** (`c3dcab0`) |
| R9 | The series closes: this registry, §3 and §4 folded in, the citations re-pointed, `reviews/` holding both reviews byte-for-byte with every finding dispositioned, the README rewritten to cover the CLI and the API, `WORKPLAN.md` deleted | **done** (the closing commit of the series) |

Run boundaries, for reading the history: run 1 was R0 → R1 → R2; run 2 was
R2a → R2b → R3 → R4 → R5 and stopped at R2c `awaiting PR #4`; run 3 was
R2c → R5a → R3a → R6 → R7 → R8 → R9.

### The one commit of the series that could not say `plan:`

Every batch was one code commit followed by one `plan:` commit that recorded its
status and what it taught — seventeen `plan:` commits in all (the series opener
`f5f5ce2`, fourteen batch closes, and the two review decisions `9a2e40f` and
`63cbcca`), each touching `WORKPLAN.md` and nothing else. R9 is the exception,
stated in advance by §0.7: *"the series-close
commit that deletes this file is the one plan commit that cannot say `plan:`,
and the watcher exempts it once per series."* It is a code-area commit that
happens to carry the plan's deletion, because a `plan:` commit that deleted the
plan would have nothing left to be the plan of.

---

## Decisions taken  *(`WORKPLAN.md` §3, folded)*

Twelve rows, moved here as they stood — counted in this table, where an earlier
reading of this line said thirteen. These are the decisions the maintainer
took during the series; a batch never took one of these itself, and a batch that
needed one halted (`CONTRIBUTING.md`, "Halt, do not improvise").

| Date | Batch | Decision | By |
|---|---|---|---|
| 2026-10-04 | series | The receiver finds a record's trace id through spanweave's public adapter surface (`classify` + the claiming adapter's `parse`) rather than a new spanweave API; the second parse is paid for now and registered as a thread (`spanweave.trace_id_of(record)` would halve it) to be decided on measurement after R2. The clock is injected everywhere; no module under `spanweave_live/` reads it. `spanweave` is pinned by git sha, and the corpus is a submodule at the same sha. | maintainer |
| 2026-10-05 | review run 1 | Nothing blocks. The review's eight `next batch` items are one fix batch (R2a) made by the builder from the review file; its ten threads are registered at close. The `trace_id_of` thread stays a thread: re-measured at 15.5–17.1 % of routing, it is an optimisation and gets no batch until a receiver workload makes routing the cost. | maintainer |
| 2026-10-05 | framer cap | The framer's remainder gets a caller-set cap, `max_pending_bytes`, default `None` (unbounded, as R1 shipped). When a push would exceed it, the remainder plus the chunk's bytes up to the next `\n` are handed to the reader as one line — so they surface as `malformed_record` with `skipped_records` counted, never dropped — and the framer emits `fragment_too_long` with the length. Policy, not mechanism, so it is the caller's number (R2b). | maintainer |
| 2026-10-05 | py.typed | spanweave gains `spanweave/py.typed` in its own one-commit PR (#4) to `main`, made by the builder, merged after its checks are fetched. The receiver then bumps both pins to the new `main` sha and deletes the `follow_untyped_imports` override (R2c), with a test that the override is gone. | maintainer |
| 2026-10-05 | §0.6 | At series close both §3 and §4 fold into TASKS.md, not §3 alone; corrected in this commit. | maintainer |
| 2026-10-05 | run 2 | R2a → R2b → R3 → R4 → R5 → R2c, then stop for a cold review. R2c is last so that PR #4 has merged by the time it runs; if it has not, R2c ends `awaiting PR #4` and the run stops there. | maintainer |
| 2026-10-06 | review run 2 | Nothing blocks. The review's twelve `next batch` items are one fix batch (R5a) made by the builder from the review file; the thirteen threads are registered at close. Three review premises of the brief's own were false and are decided here rather than left as findings: (c) the `every=N` fold, (d) macOS coverage, (d) the `Tail` wording. | maintainer |
| 2026-10-06 | R4 `every=N` | A subscriber with `every=N` receives a trailing delta — `delta(since=last_seen)` for the records after the last multiple — when its trace completes (R3's completion hook) and on an explicit ~~`Subscriptions.flush(trace_id)`~~ `Router.flush(trace_id)` (the entry point this decision named is the router's, not the subscription registry's — corrected by R5a, below); SPEC §6.6's fold claim is restated as holding after completion or flush, and the test runs at a record count that is not a multiple of N. Without this a subscriber silently never sees the tail of a trace, which is a dropped delta. | maintainer |
| 2026-10-06 | CI | No ingest test has run on macOS: the only macOS job runs `make conformance`. CI gains `check (macos-latest, 3.12)` running `make check`, so rotation and truncation detection (`st_dev`, `st_ino`) are proven on both platforms the series claims. The §4 sentence that claimed macOS coverage for R5 is corrected. | maintainer |
| 2026-10-06 | forgetting | The per-completed-trace-id book (~220 B per id, unbounded) gets a caller-set bound: `Router(max_completed: int \| None = None)`, default `None` (as shipped). At `tick()`, when the book exceeds the bound, the oldest-completed ids are evicted, one `forgotten` event per id with the trace id and its completion tick. A record for a forgotten id is a new trace at generation 1 and emits no `late_arrival` — the consequence of the policy, stated in SPEC §5.5, never a surprise. Memory is what the bound is for, so it is a count, not a time (R3a). | maintainer |
| 2026-10-06 | R2c | Run 2 stopped at `awaiting PR #4`; PR #4 is merged and spanweave `main` is `fec7da27af517ad8b58ae3ec57827916aae60674`. R2c is first in run 3 and pins to that sha. | maintainer |
| 2026-10-06 | run 3 | R2c → R5a → R3a → R6 → R7 → R8 → R9, then the scoped review of the close and the PR. | maintainer |

The `2026-10-05 | §0.6` row above says *both* §3 and §4. The R9 row that an
agent actually executes had said "§3 folded" until the run-2 review found the
gap (**F12**), which is why both are here and not one.

---

## What the batches learned  *(`WORKPLAN.md` §4, folded)*

The resume note. Every entry below was written by the orchestrator after a batch
reported, and several of them are **corrections of the plan's own rows**: a
batch that falsified its acceptance criterion had that criterion rewritten in
the same plan commit, with the reason. Those are the entries worth keeping, so
they are kept.

Where a measurement already lives in `SPEC.md`, this section **points at the
spec rather than copying it** — deliberately, because two copies of a number
drift and the spec is the one a reader of the library reaches first.

### R0 — the skeleton (`696702f`, CI green on `main`, 6/6 jobs)

- Both halves of the pin are **HTTPS**, not SSH: CI's `submodules: true`
  checkout uses the Actions token, which SSH would have broken, and
  `git ls-remote` over HTTPS was verified unauthenticated. `tests/test_pins.py`
  holds it; R8 broadened that test to every submodule.
- hatchling needs `[tool.hatch.metadata] allow-direct-references = true` to
  accept a sha-pinned dependency at all.
- `make conformance` existed from R0 but **asserted nothing** until R2: it
  printed "NO GATE YET … It is not a pass", so a green `conformance` job before
  R2 is not evidence of anything. (Thread **R0-5**: a deliberately vacuous
  target should say so in the *job name*, not only in the log.)
- `install-check` is a second **step of the CI `check` job**, not a job of its
  own, and the `Makefile` keeps it deliberately out of `make check`'s
  prerequisites. The plan first stated the mechanism backwards; see **R0-1**.

### R1 — the `Framer` (`a4fec60`, CI green, 6/6)

- The pinned `spanweave` shipped **no `py.typed`**, so `mypy --strict` refused
  to analyse it the moment a receiver module imported it. R1 carried one narrow
  `follow_untyped_imports` override — chosen over `ignore_missing_imports`,
  which would have made `Records`, `Diagnostic` and `read_records` all `Any` and
  every annotation in this repo vacuous. Fixed upstream (PR #4) and deleted by
  R2c; `SPEC.md` §0.2 tells the whole story.
- **`push` is not a second way to read a document.** The reader's container
  detection is per call, so a pretty-printed OTLP body pushed whole happens to
  read, but pushed in chunks becomes one `malformed_record` per line. Both
  directions are asserted in `SPEC.md` §3.3 — which is why R6 hands POST bodies
  to `Framer.document` and never to `push`, and why R6 refuses a **chunked**
  body `415` at the transport rather than mis-reading it.
- `SPEC.md` §3.4 originally recorded that the remainder has **no cap**:
  `pending_bytes` makes unbounded growth visible, and naming a cap would have
  been inventing a policy the spec did not state, so R1 declined rather than
  guessed. The cap was then **decided** (2026-10-05, above) and built as R2b.

### R2 — routing and gate A (`d762484`, CI green, 6/6)

- Gate A is live and `make conformance` finally asserts something: 29 scenarios,
  53 renderings (51 `.jsonl` through `Framer.push` in seeded chunks, 2 OTLP
  documents through `Framer.document`), **1354 cross-scenario pairs × 10 seeds
  (`0,1,2,3,7,11,13,101,1009,20261004`) × 2 graphs compared per pair = 27 080**
  byte-for-byte graph comparisons, ~25 s. The plan's own arithmetic omitted the
  factor of two and gave 27 080 for `1354 × 10`, which is 13 540; the code states
  it unambiguously (`assert checked == 2 * PAIRS_EXPECTED`). That is thread
  **P-3**, closed here by writing the equation out.
- **The premise gate A had to repair to be a real test:** every corpus rendering
  is trace `t1`, so one side of each pair is relabelled `t1` → `zz1`, or the pair
  would share a single builder and the test would assert nothing. A guard test
  holds that premise, so it cannot quietly stop being true.
- **R2's row named the wrong mutation, and the row was corrected.**
  `spanweave.read_records` normalizes a container's `traceId` to `trace_id`
  while unpacking, so a router keyed by `record["trace_id"]` disagrees with the
  adapter surface on **no** corpus record (0 of 53 renderings, verified record by
  record): `otlp_container` does not catch the dialect read, and gate A passed
  13/13 with the mutation planted. What catches it is an **unclaimed** record —
  `tests/test_routing.py::test_a_record_no_adapter_claims_is_not_routed_by_its_trace_id_key`.
  Gate A was separately shown able to fail, by planting "a new builder per
  record".
- **The lesson, and it recurred:** the corpus' renderings agree on key names far
  more than the dialect story suggests, so **a mutation aimed at a dialect or a
  framing read needs an input the corpus does not already normalize** — a record
  no adapter claims, not an exotic container. R6 met the same wall from the other
  side (below), which is why it is stated here as a rule and not as an anecdote.
- The `trace_id_of` measurement that answered the series' first thread is in
  **`SPEC.md` §4.2**, put there by R2a precisely so it would outlive the plan:
  `trace_id_of` is **15.5–17.1 %** of `trace_id_of + feed`, not the ~50 % the
  thread assumed, so an upstream `spanweave.trace_id_of(record)` is an
  optimisation and not a necessity. It gets no batch.

### R2a — the run-1 review's items (`7fdbff3`, CI green, 6/6)

- **Five tests that could not fail now can.** Tests 105 → 232. The framing sweep
  is 51 renderings × **2 forms** × 12 framings = **1224** framings: the second
  form is generated by `corrupted()` from corpus bytes at test time (middle line
  → `{"oops`), so the `diagnostics` and `skipped_records` assertions compare
  non-empty sequences — a `push` reporting `skipped_records=0` fails 52 tests
  where before it failed none.
- The import gate is held to **walking the tree** (`package_files()` against an
  `rglob` computed independently in the test), and a planted three-level nested
  module importing `time` is caught **with no gate edit**. The old gate went
  green on it, which was the vacuity.
- Gate A is **unchanged at ~25 s**; the corrupted-rendering cost lands in
  `test_framing.py` alone (0.23 s → 0.45 s). `Router` became `kw_only=True`.
- **One review item needed no commit from R2a**: the false "`make check` runs
  `install-check`" line was already corrected by the plan commit `9a2e40f`, and
  the plan is not a batch's file to edit. It reads as **closed by `9a2e40f`**,
  not as skipped.

### R2b — the framer's cap (`d152c3b`, CI green, 6/6)

- `Framer(*, max_pending_bytes=None)`, strict `>` boundary, `document` and
  `flush` uncapped. Tests 232 → 340; gate A still ~25.4 s. The red-on-parent run
  was the strong form here (the derived parent is code, not a `plan:` commit):
  **108 failed / 172 passed**, with R1's other framing tests all still passing
  there, which is what makes the 108 meaningful.
- Two surface choices, now in `SPEC.md` §3.1: `FramingEvent` is **its own type**,
  not routing's `Event` (a framing event has a length and no record index, trace
  id or spanweave code, and `framing.py` importing from `routing.py` would be an
  upward import); and events ride **beside** the return value (`Framer.events`,
  `Framer.counts`) because §3.1 forbids wrapping `spanweave.Records`. R3's
  completion events and R4's `consumer_error` follow routing's `Event`, not this
  one — the split is deliberate, not an inconsistency to tidy.
- **A consequence that propagated to the end of the series** (`SPEC.md` §3.4): a
  cut line's fragments are each numbered as a line, so **line numbers downstream
  of a `fragment_too_long` are the framer's count, not the input's**. R7's CLI
  inherited it, reports `framer_line`, and its mutation test turns on exactly
  this.

### R2c — the pins move (`a4ce94b`, CI green, 6/6)

- Both pins are at `fec7da2` and the typing override is **gone**, not merely
  unused: the `[[tool.mypy.overrides]]` block is deleted and a comment in its
  place says why there is none. Tests 444 → 447.
- The new tests cannot go green vacuously: the configuration test **parses**
  `pyproject.toml` rather than grepping it, so the explanatory comment may still
  name the deleted setting; and one test plants `int = read_records(b"")` and
  requires `mypy --strict` to error on it.
- The deletion is confirmed by **what mypy now reads, not by its silence**:
  `mypy --verbose` pulls 20 `site-packages/spanweave/*` modules into the build
  and `reveal_type` gives `read_records` as
  `def (bytes | bytearray | memoryview[int]) -> Records`, not `Any`. Mutation:
  deleting `py.typed` from the installed spanweave makes mypy print
  `Skipping analyzing "spanweave"` and the test fails.

### R3 — completion (`e09af3f`, CI green, 6/6)

- Three composable policy values on an injected clock. Tests 340 → 385; gate A
  unchanged. Red on the code parent `d152c3b` was meaningful: the parent's own
  340 passed and all 45 new tests were red.
- **The seam allowlist stayed empty, and R0's prediction that R3 would need the
  first entry was wrong.** `Completion.now` has **no default**, so no module
  under `spanweave_live/` imports `time` at all; the real clock enters at the
  caller. Corrected in `gates.py` and in the allowlist test's comment at the
  time, rather than left standing.
- Judgement the row did not settle, now `SPEC.md` §5.6: `RootEnded` completes on
  **at least one root and every root ended** — the conservative reading, because
  "any root" would complete a trace whose other top-level operation is still
  open — and the grace runs from **the tick that first saw the end**, not from
  the span's `ended_at`, because those are two different clocks. Root = no
  incoming `parent` edge **and** no `orphan_parent` diagnostic naming it, both
  read through spanweave's public graph surface.
- **A known unbounded cost, stated rather than invented away** (`SPEC.md` §5.5):
  the router keeps a small record **per trace id it ever completed**, because the
  `late_arrival` gap and the new builder's generation name need them, and
  `max_traces` does not bound it. R3 declined to invent a forgetting policy and
  registered it as a halt instead; it was decided (2026-10-06) and built as R3a.
- Two smaller facts: routing's `Event` gained one optional field `seconds`; and
  the "not written because the library refused" branch is **unreachable through
  the public surface** (an identified trace has a claimed record by
  construction), kept deliberately and labelled as such in `SPEC.md` §5.4, so it
  has no test.

### R4 — subscriptions (`54a6009`, CI green, 6/6)

- Tests 385 → 410; gate A unchanged. Red on the code parent `e09af3f` was
  meaningful: its own 385 passed, all 25 new red. The central claim is asserted
  twice (per-record and `every=2`) in a form that cannot skip a delta: the first
  delta's additions **are** the first graph, and folding the rest onto it equals
  `graph()` byte for byte.
- **R4 bounded a cost rather than adding one.** A `spanweave` `Builder` defaults
  to `retain("all")`, so every router since R2 had been holding a journal entry
  per absorbed record; retention is now
  `builder.retain(max(every for covering subscriptions))` per trace, applied only
  when the window **changes**, and `window(trace_id)` is `None` — leaving
  retention **untouched, not 0** — when nobody covers a trace, because
  `Routed.builder` is public and a caller's own `retain` must not become a
  traceback instead of a `delta_unavailable` event.
- Specified choices: subscriber order is **registration order** (`SPEC.md` §6.2)
  because `id()`/`hash()`/callback names are either unstable across processes or
  a ranking nobody chose; `trace_id=None` subscribes to the **no-trace builder
  too**, deliberately unlike §4.5/§5.4, because reporting throws nothing away
  while releasing does; and `delta_unsent` is a **report, not a flush**.
  Routing's `Event` gained one optional field `version`.

### R5 — file tail and stdin (`a7ade79`, CI green, 6/6)

- Tests 410 → 444; gate A **25.22 s, unchanged**. The central test reaches gate
  A's own comparison through a real file, importing `loaded`/`chunked`/
  `undigested` from `tests/test_conformance.py` rather than inventing a weaker
  check.
- **The allowlist was still `{}` and R0 was wrong twice.** `tail` takes `now` and
  `sleep` with no defaults, exactly as `Completion.now` does, so nothing under
  `spanweave_live/` imports `time` or `asyncio`. `tests/gates.py` recorded both
  wrong predictions and said **R6's listener must be made to prove it needs a
  line**.
- Detection, read rather than chosen: truncation is `os.fstat` of the **open
  handle** reporting `st_size < offset`, checked before each poll's reads;
  rotation is `path.stat()` disagreeing with `os.fstat(handle)` on
  `(st_dev, st_ino)`, checked **only on a poll that read nothing**, so the old
  inode's unread bytes are handed over first. Both restarts **flush the framer**,
  so held bytes come back as a `malformed_record` and are never joined to new
  content. `(st_dev, st_ino)` is the platform's own answer, so no policy was
  invented.
- Three things stated instead of smoothed over: a truncate-and-regrow **past**
  the old offset between two polls is **indistinguishable from growth**
  (`SPEC.md` §7.1 — a limitation, not a heuristic); **no event for a short
  read**, because `read(n)` returning fewer bytes is how a file says "that is all
  for now" and a code would fire every poll; and the row's "both are generators"
  was wrong — `stdin()` is a generator, but `tail` returns a `Tail`, a
  **single-use iterable** (not an iterator), because §3.1 forbids wrapping
  `Records` and a bare generator has nowhere to carry its events.
- **The macOS claim in this entry was false when written and is corrected by
  R5a.** The only macOS job ran `make conformance`, which is
  `tests/test_conformance.py` alone, so `tests/test_ingest.py` had never run on
  macOS at all. `check (macos-latest, 3.12)` is what made it true.

### R5a — the run-2 review's items (`c1e6946`, CI green, **7/7** — the job count is seven from here)

- F1–F10 plus T10/T11 closed. Tests 447 → 492. Red on the **derived** parent
  `33364b4` (`git rev-parse c1e6946^`; the commit body named `a4ce94b`, which is
  the previous *code* commit and two back — see **T7**) was meaningful:
  **43 failed, 449 passed** there, including the `records=7, every=2` fold, both
  `Router.flush` tests and the macOS-job assertion.
- **The decision in §3 named the wrong entry point.** The trailing delta ships as
  **`Router.flush(trace_id)`**, not `Subscriptions.flush(trace_id)`: producing a
  delta needs a builder and reporting a refusal needs an event, and by `SPEC.md`
  §6.1's layering both are the router's. `Subscriptions.flush(trace_id, version)`
  is the pure lower half. §6.1 records the divergence and why, so a reader of the
  decision alone is not misled — and the decision row above carries the
  strikethrough for the same reason.
- **One review premise of its own was false.** F9 assumed a negative
  `max_pending_bytes` behaves as `0`; it does not — it emits a
  `fragment_too_long` of length 0 on every push that ends on a line boundary and
  inflates the framer's line numbers (R2b's consequence, compounding). R5a took
  F9's second option: **a negative cap is a `ValueError`**, stated in `SPEC.md`
  §3.4.
- Three things a later reader must take fresh rather than from memory.
  `delta_unsent` **changed meaning**: it is now "the tail could not be
  produced", carrying `spanweave_code`, and `Subscriptions.released` is gone,
  replaced by `flush` + `forget` (`SPEC.md` §6.5). The SPEC-block test caught a
  second drift — `Routed.events` had `= ()` in code and no default in §4.1 — so
  adding a field to `Event` now fails unless §4.1 is edited in the same commit.
  And the import gate now bans `http`, `socketserver` and `urllib`, which made
  R5's standing challenge to R6 enforceable.
- **Two review items were not R5a's to close** (F11 and F12, both
  `WORKPLAN.md`, and a batch never edited that file). Their dispositions are in
  the review table below.

### R3a — forgetting (`baa32cb`, CI green, 7/7)

- The series' only unbounded cost is bounded: `Router(max_completed=None)`
  forgets the oldest-completed trace ids past the caller's count, one `forgotten`
  event per id. Tests 492 → 503.
- **The parent run, with the step the record left out.** The derived parent is
  `afc6a7a` (`git rev-parse baa32cb^`); the commit body named `c1e6946`, the
  previous *code* commit, two back (**T7**). The recorded figure is
  **11 failed / 492 passed** there, of which **two pass and are guards rather
  than new behaviour** (that `max_completed` appears in no other test file, and
  the `len(_books) - len(_builders)` identity, which already held) — so the real
  new-behaviour count is 9 and not 11. **That run is not reproducible as it was
  described.** R3a's tests import `FORGOTTEN` from `spanweave_live`, and no
  `FORGOTTEN` exists anywhere in the package at `afc6a7a` (`git show
  afc6a7a:spanweave_live/__init__.py` and `:spanweave_live/routing.py` both have
  none, against ten references in `baa32cb:tests/test_completion.py`), so
  carrying the tests onto the parent tree aborts collection with
  `ImportError: cannot import name 'FORGOTTEN'` and collects **0** tests. The
  11/492 is reachable only after first **adding the `FORGOTTEN` constant to the
  parent tree**, and with that step the 2026-10-07 review re-derived it exactly.
  This is recorded as an **undisclosed step** rather than as a slip in a number:
  a figure nobody can re-run from what was written is not evidence, and it is the
  worst of the six discrepancies that review found for exactly that reason.
- **The measurement, so the policy's number is a number.** It is in
  **`SPEC.md` §5.5**, which carries the table: ~**221 B/id**, unchanged by the
  bound — the bound simply stops the growth. 10⁵ completions at
  `max_completed=1000` hold 1 000 ids for 221 036 B with **RSS delta 0**. Two
  figures in this entry are **R3a's own measurement and are not in §5.5**, so
  they are attributed here rather than cited there: unbounded, the same 10⁵ is
  20.7 MB, and **10⁶ is 230.5 MB** — re-measured independently at
  **230 516 588 B** on 2026-10-07 by the same method §5.5 names (`route` →
  advance the clock → `tick()`, 32-character ids, a deep `getsizeof` over the
  book after `gc.collect()`, deduped by object identity), which reproduces
  §5.5's three rows to within one float object (24 B low on each). §5.5 has no
  10⁶ row and says **~210 MB** for it, which is R3's estimate and what that
  section should be read as saying; the 230.5 MB is the confirmation of it, not a
  quotation of it. The earlier wording sourced 230.5 MB to §5.5 and so pointed a
  reader at a section stating a different figure.
- **One figure here is a machine's and not the method's.** §5.5's "RSS delta …
  880 KB and **zero**" re-derives on a second machine as **888 832 B** at
  `max_completed=10000` and **exactly 0** at `1000` — so the load-bearing half,
  zero growth at the bound, is reproducible and the ~880 KB is right as written.
  A re-run reported 1 511 424 B for that delta; it did not reproduce, and RSS is
  an allocator's number rather than a determinate one. The deep-`getsizeof` rows
  are the re-derivable part of §5.5 and the RSS column is corroboration.
- **The decision's "at the next tick" was underspecified and R3a settled it.**
  Eviction happens in the tick whose completion pushes the book past the bound,
  and the `forgotten` rides on that `Completed`: a tick that completes nothing
  has no `Completed` to carry an event, and the alternative was changing
  `tick()`'s return type, which the decision does not state. Argued in `SPEC.md`
  §5.5 and in `_forget`'s docstring, not just chosen.
- **A consequence R7 inherited, and it is a file overwrite.** Forgetting an id
  loses its generation, so a later record for a forgotten id writes
  `<trace_id>.json` **over** the file the earlier completion wrote. §5.5's "the
  file already written is not rewritten" holds **only while the completion is
  remembered**. It follows from the decided policy rather than being invented, so
  R3a did not halt — and R7 put it in front of a human three ways (below).
- Routing's `Event` gained one optional field **`at`** (the completion tick),
  following `seconds` (R3), `version` (R4) and `offset` (R5); `SPEC.md` §4.1 says
  why it is `at` and not `seconds`.

### R6 — the OTLP/HTTP endpoint (`8ae7a5d`, CI green, 7/7)

- Tests 503 → 547. Red on the derived parent `e033f6c` (`git rev-parse
  8ae7a5d^`; the body named `baa32cb`, the previous code commit — **T7**) was
  **total rather than meaningful** — the new file is a collection `ImportError`
  there, so all 44 are red for one reason; the **mutation** is what carries this
  batch, and the parent's own 503 passing is the part worth having.
- **The seam allowlist was still `{}`, and that made three declined predictions
  in a row** (R0 predicted R3, R3 predicted R5/R6, R5 predicted R6). The listener
  is injected as two parameters with no defaults: `handler_class(base, endpoint, /)`
  takes `http.server.BaseHTTPRequestHandler` and builds the handler with
  `type(...)`, because a `class` statement would need the base **at import
  time** — the very import being avoided — and `serve(endpoint, *, listener=…)`
  takes the factory. `endpoint.py` passes the ambient, network and os rules
  unexempted.
- **R2's lesson repeated, and R6 said so instead of banking the green.** The
  `document` → `push` mutation took 10 of 44 tests down, but both `verbatim`
  cases of the central test stayed **green**: the corpus stores both container
  renderings newline-terminated, so a whole arrival reads identically through
  `push`. The 4 `trimmed`/`compact` cases are what bite (trimmed on the status,
  `400 != 200`; compact on the records), and a framer-level control test now
  asserts the three spellings really do differ — so the mutation cannot be made
  toothless again by a corpus that agrees with itself.
- Routing's `Event` gained **no** field, so §4.1 and R5a's SPEC-block test are
  untouched; §7.2's own `Request`/`Response`/`Exchange` are now held to the spec
  fence by that same test. Two facts stated in `SPEC.md` §7.2 rather than left to
  a reader: a **chunked** body is refused `415` rather than mis-read (R1's §3.3
  trap closed at the transport, not just the framer), and `gzip.decompress(b"")`
  is `b""`, so an empty gzipped body is a `200`.

### R7 — the CLI (`d21859d`, CI green, 7/7)

- Two commands, `SPEC.md` §8.1–§8.7 new. Tests 547 → 628, of which
  `tests/test_cli.py` has **81 collected items, 72 of them through
  `subprocess`** — measured, where this row and §8.7 both used to say all 81.
  The other **nine** read the package in-process, which is the only way to ask
  what they ask (the parser, `real.py`'s bindings and the allowlist, §8.3's codes
  and layers, the gate's rules over `cli.py`, and that no dataclass was
  reinvented); `tests/test_cli.py`'s own docstring always carried the exception,
  so the spec and this row overclaimed past a file that did not.
- The parent run: red on the derived parent `3f593a6` (`git rev-parse
  d21859d^`; the body named `8ae7a5d`, the previous code commit, and called it
  "the derived parent" — **T7**), **77 failed / 4 passed** (re-run at that parent
  in a clean worktree by the 2026-10-07 review, whose figure is taken here rather
  than the row's own; the correction commit made no worktree, having no new test
  to run). An earlier reading of this row said 76/3 and listed three passers meant
  to pass (usage exit 2, `real` not in `__all__`, no new dataclasses); the
  **fourth** is `test_version_and_help_both_say_nothing_is_frozen`, which exists
  at `tests/test_cli.py` and which the record left unnamed. The central test is
  gate A's own comparison **through a process** —
  51 `.jsonl` renderings via `tail -`, 2 OTLP documents via `serve --port 0`,
  gate A's loader, byte for byte.
- **The seam allowlist is no longer empty, and this is the one entry the series
  predicted three times and refused twice.**
  `SEAMS = {"real.py": frozenset({"time", "http.server"})}` — one file, two
  modules. It could not be avoided because R3/R5/R6 each declined on the same
  ground (the seam was a parameter with no default and the *caller* held the
  import) and **R7 is that caller**: a process has nobody to take
  `now`/`sleep`/listener from. Narrowed two ways worth keeping: it names
  `real.py` (fifty-odd lines of nothing but bindings) and **not** `cli.py`, with
  a test running the gate's rules over `cli.py` against an **empty** allowlist;
  and `http.server`, not `http`. `real.py` is not exported from `__init__`. The
  four tests that asserted `SEAMS == {}` were **narrowed to "my module is not in
  it"**, not deleted — so the gate still bites for every other file.
- **R3a's overwrite is in front of a human three ways**: `--max-completed`'s
  `--help` text, one `may_overwrite` stderr line at a run's first `forgotten`
  (once per run), and `SPEC.md` §8.5. Pinned by a pair of tests:
  `--cap 1 --max-completed 0` over two POSTs of one trace leaves only `t1.json`
  holding the **second** generation's graph, while the default leaves `t1.json`
  **and** `t1.2.json`.
- **The mutation was chosen against the corpus, not in spite of it.**
  `framer_line=event.line` → `line=event.line` is caught — re-run at this tip:
  **1 failed / 80 passed** in `tests/test_cli.py` and 1 failed / 650 passed
  across the suite, `KeyError: 'framer_line'` at `tests/test_cli.py:392`, so
  nothing else is touched (an earlier reading of this row said 1/79) — and the
  test **holds its own premise**: every corpus rendering's lines end in `\n`, so
  the cap never bites there, and the input that does bite is 70 000 newline-free
  bytes — zero input lines, two framer lines. R2b's line-number consequence
  honoured, and R2/R6's lesson applied before the fact rather than discovered
  after it.
- Two judgement calls the row did not settle, both in `SPEC.md` §8.5/§8.6.
  End-of-input finalisation **reassigns `router.completion`** to
  `Completion(policies=(Cap(0),), …)` and ticks once, so a replay always leaves
  files behind and reports `Cap(records=0)` rather than a CLI-invented code. And
  exit `1` is every `OSError` from the source, which §8.6 admits is one notch
  loose about the word "start".
- `make install-check` now runs a **command**, piping a corpus record to the
  installed console script from outside the repo, so the gate that proves what
  ships exercises the thing a user types.

### R8 — the showcase (`c3dcab0`, CI green, 7/7)

- **What the row predicted**, quoted because the row is gone and because a
  prediction nobody can read is a prediction nobody can check. R8's acceptance
  criterion, from `spanweave` `OPEN_QUESTIONS.md` §19, was: *"the
  `verify_identity → issue_refund` order rule fails at the version that absorbs
  the `llm.plan` span carrying the `issue_refund` request — one version before
  the `issue_refund` tool span arrives — which is the 'when it almost happened'
  the memo promised"*. The mechanism it offered is true: the request **is**
  absorbed first, and at version 5 the graph already reports `issue_refund` as
  an `unpaired_call`. The verdict it predicted is not.
- The showcase is in, and **the row's central claim was false.** Tests 628 → 651.
  Red on the derived parent `0acbed7` (`git rev-parse c3dcab0^`; the body named
  `d21859d`, the previous code commit — **T7**): `tests/test_showcase.py` alone
  is a collection error there (`No module named 'agentgolden'`), and with the new
  pins/gates files carried over, **5 failed / 634 passed** (re-run at that parent
  by the 2026-10-07 review; that figure is taken here rather than the row's own).
  An earlier reading of this row said 4/635 and named four; the **fifth** failure
  is
  `tests/test_pins.py::test_every_submodule_is_cloned_over_https_too`, which R8
  broadened to cover `showcase/` (**R0-3 / P-5**) and which therefore cannot pass
  on a tree with no `showcase/` submodule.
- **The actual first-failure table** (7 versions, 19 rules, 4 ever fail):
  `tools.required:verify_identity` **1**, `tools.required:issue_refund` **1**,
  `trajectory.all_calls_fulfilled` **2**, `order:verify_identity < issue_refund`
  **6**.
- **Why the row was wrong, and it is a model fact rather than a bug.**
  agentgolden's `OrderRule` reads `Signature.tool_calls`, which are tool
  **nodes**, and spanweave's `NodeKind` is **closed** — so a call requested by an
  `llm.plan` span with no tool span is an `unpaired_call` **diagnostic**, not a
  node. At version 5 the order rule has nothing to order and passes vacuously;
  it first fails at **6**, when the tool span itself arrives. That is the
  closed-enum invariant doing exactly what it promises, and the row assumed a
  graph shape the model does not produce.
- **The memo's "when it almost happened" survives, in a better rule than the one
  the row named.** `trajectory.all_calls_fulfilled` fails at version 2, passes,
  fails again at 5, and **passes at the last version** — so it is a verdict that
  exists only in the live stream and is **invisible in the batch graph of the
  same trace**. That is a sharper demonstration of why a receiver is worth
  having than the order rule would have been, because the order rule's final
  verdict is the same either way. This entry is the claim the series makes for
  R8; the original sentence is not.
- The honesty checks held. `rules.toml` and the trace are **untouched**, and a
  test compares both byte-for-byte against the pinned submodule's committed
  blobs, so "unchanged" is asserted rather than asserted *about*. **Nothing
  semantic landed under `spanweave_live/`**: zero package changes, a new gate
  `no-consumer-rules` with 4 planted violations watched failing, and a pin test
  holding the runtime dependencies to exactly `["spanweave"]`. The mutation
  (evaluate only the final graph) took **6 of 12** tests down and flattened the
  table to two rules, both at version 7 — which is precisely the showcase's own
  point failing when the per-delta loop is removed. It erases **two**
  first-failures, not one: re-measured off the replay's own observations, the
  final graph fails `order:verify_identity<issue_refund` and
  `tools.required:verify_identity` only, so **`trajectory.all_calls_fulfilled`
  *and* `tools.required:issue_refund`** both vanish from the table. An earlier
  reading of this row named only `all_calls_fulfilled`. The per-version verdicts
  of `all_calls_fulfilled` are `pass, FAIL, pass, pass, FAIL, pass, pass`.
- **Two facts for whoever moves the `spanweave` pin next.** agentgolden's
  `spanweave>=0.9.1,<1.0` does resolve against the pinned spanweave, but it meets
  the **lower** bound exactly (`0.9.1`), **so a future spanweave `1.0` pin breaks
  the showcase**; `tests/test_pins.py` asserts the resolution rather than
  trusting it. And agentgolden had to come in as a **`showcase/` submodule**, not
  just a wheel, because its wheel ships no `examples/` — `showcase/` is excluded
  from the sdist and the wheel ships no rule engine.

### R9 — the close (this commit)

- This registry, with §3 and §4 folded. `WORKPLAN.md` deleted.
- Both reviews archived byte-for-byte under `reviews/` with their sha256, and
  every finding dispositioned (below).
- `README.md` rewritten to cover the CLI and the API. Its "`Framer`, `Router`,
  … arrive in R1–R7" sentence had been stale **three times over** by R3, and no
  batch before R9 was allowed to patch it piecemeal, which is why it stood that
  long: the README was R9's, by the plan's own assignment, and R9 is the first
  batch at which every claim it could make is true.
- Every live citation of `WORKPLAN.md` in `SPEC.md`, `spanweave_live/`,
  `tests/`, `CONTRIBUTING.md` and `.github/workflows/ci.yml` re-pointed at this
  file. `CHANGELOG.md`'s **plan** citations are left as they stand: fourteen
  survive in tracked files, and **thirteen** of them sit inside a dated batch
  entry, so each is a statement about what was true when that batch landed and
  `git show b500342:WORKPLAN.md` resolves it. The **fourteenth** did not:
  `CHANGELOG.md:7` was in the preamble, two lines above the first heading and
  inside no entry, and read "the unit of change is a **batch**
  (`WORKPLAN.md`)" — present tense, in the library's own voice, pointing a
  reader at a file this commit had deleted. R9's exception as first stated did
  not cover it. It is re-pointed at this file, with the dated-history rule for
  the other thirteen said out loud in the same preamble (2026-10-07).
- Every citation of `patches/REVIEW-<date>.md` re-pointed at its `reviews/`
  archive — in `SPEC.md`, `spanweave_live/ingest.py`, eight modules under
  `tests/`,
  `.github/workflows/ci.yml` and `CHANGELOG.md`. Those had been dangling for
  anyone but the author since they were written, because `patches/` is
  `.gitignore`d; the archived bytes are identical, so the citations name the
  same text they always did.
- **One thing R9 did not do, and the orchestrator has since done:**
  `CLAUDE.md`'s second paragraph described `WORKPLAN.md` as live execution state
  ("which batch is next … edited only by the orchestrator"), which was false the
  moment R9 deleted it. `CLAUDE.md:45`'s "these are `WORKPLAN.md` §0.6, which is
  where they were first written" remains true as history, and the rules
  themselves are repeated in full in `CLAUDE.md` so nothing was lost. The
  paragraph was left for its owner rather than edited from inside a batch — which
  was the protocol working, since the paragraph's own rule and R9's brief both
  forbade a batch from editing the orchestrator's text. **Closed 2026-10-07**,
  outside the series, by the paragraph that now names **this file** as the
  registry between series and
  says that a `WORKPLAN.md` exists only while a series is open. The aggravator
  that fix was really for: before it, `grep -n "TASKS.md" CLAUDE.md` returned
  nothing, so `CLAUDE.md:6`'s "a cold session should be able to work here from
  this file alone" sent a cold reader to a deleted file and never named the one
  that replaced it.

---

## The reviews, archived and dispositioned

**Three** cold reviews were run, each by an aux session that **edited no tracked
file and committed nothing** — by design, so that a finding is made by the
builder from the review file and never by the reviewer. All three are here
**byte for byte**, under the names they were written with recorded beside their
archive paths:

| archived as | written as | sha256 |
|---|---|---|
| `reviews/2026-10-04-run1.md` | `patches/REVIEW-2026-10-04.md` | `6d1a20e6c3527cb287ff3d32d13787958212084670c4a5dfb7e338afe830df39` |
| `reviews/2026-10-06-run2.md` | `patches/REVIEW-2026-10-06.md` | `0de625ddb817a0217f487bc87f5e9a39586445865422501500a93480e9f365f0` |
| `reviews/2026-10-07-close.md` | `patches/REVIEW-2026-10-07.md` | `f6678782069d7d13adc74167e48551fafab3f345357397e74c60443da3e9d8ae` |

The third is the scoped review of the close itself, run over
`63cbcca..86183b0`; it is archived by the same commit that closed its findings
(*The record made true*, below), for the reason the first two were — a tracked
citation must resolve in a stranger's checkout.

`patches/` is gitignored and holds the `git format-patch` output of the runs, so
the reviews lived there untracked until they were archived. The copies are
unedited: they contain their own errors, their own stale premises, and their
citations of a `WORKPLAN.md` that no longer exists at the tip. That is the point
of an archive. Three things to know before reading them:

- **Review 2's header miscounts its own body.** Its preamble says "Eight
  findings are `next batch`, thirteen are `thread`"; §1 lists **twelve**
  (F1–F12) and thirteen. Twelve is right, and it is the number the decisions log
  and R5a's row use.
- **Review 1 withdraws one of its own clean lines** (§5, "Reviewer error,
  marked"): a plan-hygiene sub-agent had treated the false "`make check` runs
  `install-check`" sentence as correct, two other reviewers reported it false,
  and the review verified it independently and sided with them rather than with
  the majority. The finding stands as **R0-1**.
- **Review 3 has four figures of its own that did not re-derive**, found while
  closing its findings and recorded here because it audited this registry for
  exactly this. Its `tests/gates.py:209` for the `SEAMS` literal is `:237`; its
  re-measured RSS delta of 1 511 424 B did not reproduce (888 832 B here, which
  is `SPEC.md` §5.5's ~880 KB as written); it attributes that RSS figure to
  `TASKS.md`, where it has never appeared — it is `SPEC.md:1156`; and its "twice
  the body uses the word *derived*" is four times (**T7**). Its §5.5 book figures
  and its `230 516 612 B` re-derive to within one float object (24 B, the same
  offset on every row, which is a difference in the walk and not in the finding),
  and its `9 of 81`, its six derived parents and its first-failure tables
  re-derived exactly. An archive keeps its errors.

### Run 1 — `reviews/2026-10-04-run1.md`, eight `next batch` findings

Nothing blocked run 2.

| # | Finding | Disposition |
|---|---|---|
| R0-1 | `WORKPLAN.md` §4's "`make check` runs `install-check` as a step" is false — it is a second step of the CI `check` job, and the `Makefile` keeps it out of `check`'s prerequisites on purpose | **closed by the plan commit `9a2e40f`**, which had already corrected it when R2a reached the item. R2a confirmed nothing else stated it wrongly and made no commit for it. Recorded as closed, never as skipped |
| R0-2 | Nothing held the import gate to **walking** the tree: `package_files()` reduced to a two-name list left `make check` green with a planted `time` import | **closed by R2a** (`7fdbff3`): the tripwire now compares `package_files()` against an `rglob` computed independently in the test, and a three-level nested module is caught with no gate edit |
| R1-2 | `push`'s `skipped_records` was asserted nowhere — a `Framer.push` returning `0` unconditionally passed the whole suite | **closed by R2a**: one test asserts it directly, and the two-form sweep makes 52 tests fail on it |
| R1-3 | `SPEC.md` §3.5's "re-sorted by the library's own order" was unguarded, and the test was green because of its own fixture choice (9 lines, where the renumbering does not invert) | **closed by R2a**: the fixture crosses the 9 → 10 digit boundary, where sorted order reverses arrival order, and the docstring says that is the point |
| R1-4 | `SPEC.md` §3.2's "no dedup cache of its own" was untested — a `self._seen` set inside `Framer` passed 92/92 and made a `duplicate_record` diagnostic vanish | **closed by R2a**: a two-part test, the halves each other's control (same line twice in one push → one record plus `duplicate_record`; across two pushes → two records, no diagnostic) |
| R2-1 | `SPEC.md` §4.1's declared `Router` surface was narrower than the code's: `routed` undeclared, and `Router(1, 'openinference', False)` constructed despite the spec's `*` | **closed by R2a**: `kw_only=True` on the dataclass, and §4.1 declares `routed`. The SPEC-block test that holds §4.1 equal to the dataclass arrived with R5a |
| P-1 | The `py.typed` and `trace_id_of` threads survived nowhere: both lived in `WORKPLAN.md` §4, which R9 deletes, and §0.6 then folded only §3 | **closed by R2a** for substance (both threads moved into `SPEC.md` §0.2 and §4.2, which outlive the plan) **and by `9a2e40f`** for the fold clause (§0.6 became "§3 and §4"). The R9 row itself lagged until F12 |
| P-2 | `SPEC.md` §4.2 still carried the premise R2 falsified — an upstream `trace_id_of` "would halve it" — and cited a plan section that series close deletes | **closed by R2a**: §4.2 carries the 15.5–17.1 % measurement in place of "would halve it", and `routing.py`'s citation points at §4.2. The remaining "`WORKPLAN.md` §3 while the series runs, `TASKS.md` once it closes" clause is re-pointed by **this commit** |

### Run 1 — ten `thread` findings, registered

| # | Thread | Disposition |
|---|---|---|
| R0-3 / P-5 | The submodule's HTTPS URL was held by no test (a re-added SSH URL passed `make check` and failed only at CI checkout) | **closed by R2a**, which added the `.gitmodules` assertion; **broadened by R8** to `test_every_submodule_is_cloned_over_https_too`, covering `showcase/` as well |
| R0-4 | `CLAUDE.md` standing rule 9 (no `eval`, `exec`, `pickle`, `yaml.load` on trace content) is gated nowhere, and there was no network-import gate either | **half closed, half open.** The network half is closed by **R5a** (`c1e6946`), from F8: `tests/gates.py` has a `no-network` rule banning `urllib`, `http`, `socketserver`, `ssl`, `requests`, `httpx` and `aiohttp` among fourteen modules in all. The `eval`/`exec`/`pickle`/`yaml.load` half is **still review-only** — an AST rule would close it and conflicts with nothing |
| R0-5 | A vacuous CI job was green and named like a real one: `make conformance` asserted nothing before R2, while the check surface read `conformance (ubuntu-latest) ✓` | **moot from R2** (`d762484`), which made the target assert; `make showcase` arrived already asserting. Registered because the shape recurs: when a target is deliberately vacuous, that belongs in the **job name**, not only in the log |
| R1-1 | The framing sweep's diagnostic and `skipped_records` equality was vacuous — a `push` swallowing every diagnostic passed 51/51 | **closed by R2a**: the sweep gained a second, corrupted form of every rendering, generated from corpus bytes at test time |
| R1-5 | `SPEC.md` §3.4's "no cap" was prose with no guard — nothing would fail if a later batch quietly capped or truncated the remainder | **superseded by R2b** (`d152c3b`): §3.4 is now the cap policy, with the boundary tested, and **R5a** added the `0` and the negative-cap cases (F9) |
| R1-6 | The BOM-split consequence of §3.2 is untested (`BOM` appears only in prose) | **open.** `MULTI_BYTE_STREAM` still carries no BOM prefix. The claim was verified true by the review; the fix is one prefix, after which the existing two-way split sweep covers the BOM boundaries for free |
| R2-2 | Gate A's interleaving is **line-atomic**: `replay()` drains each arrival's chunks before the next arrival's, so the framer's remainder never holds one trace's partial line while the other trace's bytes arrive (instrumented: 0 arrivals) | **open.** §4.7's prose suggests a cross-trace framing state the test never reaches. Extra coverage, not a bug — R1 already tests the remainder within one stream. The fix is to chunk the concatenated interleaved stream, or add one test that does |
| R2-3 | An unclaimed record is accounted for only by `no_trace.version`: a stream of nothing but unclaimed records yields no event and no count, and `no_trace.graph()` then refuses, so R7 — which writes every event to stderr — has nothing to write for them | **open**, and bounded: nothing is dropped (the records are in the builder), and `SPEC.md` §4.3 names the library's own `missing_trace_id`/`unclaimed_record` diagnostics as the account. Surfacing an unclaimed **count** is a spec sentence; a new event **code** would be a decision, not a patch |
| P-3 | `WORKPLAN.md` §4's gate-A arithmetic omitted a factor of two: "1354 pairs × 10 seeds = 27 080" is 13 540; the real figure is `2 × 1354 × 10`, two graphs compared per pair | **closed by this commit**: the R2 entry above writes the equation out with the factor. Every input number checked out independently (53 renderings, 29 scenarios, 1354 cross-scenario pairs), and `CHANGELOG.md` gave the total with no equation and was correct as written |
| P-4 | Finding 3 (`push` is not a second way to read a document) was understated in the surviving documents: §3.3 asserted the chunked-loss direction only, and the whole-body direction lived in a test docstring | **closed by R2a**: §3.3 states the trap in full and asserts both directions, which is how R6 met it in the spec rather than in a docstring |

### Run 2 — `reviews/2026-10-06-run2.md`, twelve `next batch` findings

Nothing blocked run 3.

| # | Finding | Disposition |
|---|---|---|
| F1 | `SPEC.md` §5.5 miscounted `_Book`'s fields ("four floats, an int and a flag" for five slots) and gave no number where one now existed — and "a small record per trace id" reads as ~40 B to anyone doing the arithmetic, against a measured ~220 B | **closed by R5a**; the measured figure and the 10⁵/10⁶ rows are in §5.5, and **R3a** replaced the estimate with its own measurement at ~221 B/id |
| F2 | §6.6's fold claim was false at `every=N` unless the final version was an exact multiple of N, and the test was green because of a choice it made about its own fixture | **closed by R5a**, with the trailing delta decided first (2026-10-06, above): the fold holds after completion or flush, and the test runs at `records=7, every=2` |
| F3 | The `every=N` fold test did not use its first delta, contrary to §6.6's claim that it does | **closed by R5a**: one assertion mirroring the `every=1` test's cross-check |
| F4 | §6.5's "the way to reach it" over-narrowed `delta_unavailable`: a consumer joining mid-stream with a coarser `every` reaches it without any caller touching retention | **closed by R5a**: the sentence fixed and the path fixtured. The behaviour was already correct and self-reporting |
| F5 | `Event.offset` was added by R5 to the code but not to §4.1, which claims to declare the type **exactly** | **closed by R5a**, and closed structurally: the SPEC-block test now holds §4.1's block equal to `dataclasses.fields(Event)`, which is why **R3a's `at`** could not land without the spec edit |
| F6 | Either run the ingest tests on macOS or stop citing macOS for them — the only macOS job ran `make conformance`, i.e. `tests/test_conformance.py` alone | **closed by R5a** by the stronger of the two options: `check (macos-latest, 3.12)` runs `make check`, and a test in `tests/test_ingest.py` asserts that job is still in the workflow, so the claim and its evidence fail together |
| F7 | `AMBIENT_MODULES` was narrower than the invariant it was advertised as proving: `os`, `secrets`, `uuid`, `concurrent.futures`, `selectors`, `select`, `subprocess`, `sched` all passed — and `os` was already in use for `fstat` | **closed by R5a**: `tests/gates.py` gained the `no-ambient-os` rule over the dangerous `os` attributes, and the gate's written claim and its enforcement were brought back level |
| F8 | There was no network-import gate in this repo at all: `import urllib.request` under `spanweave_live/` passed, and R6 was about to open an HTTP endpoint | **closed by R5a**: the `no-network` rule. It also made R5's challenge to R6 enforceable — and R6 met it with an injected listener and no allowlist entry |
| F9 | `max_pending_bytes=0` was stated legal in two places and tested in none, and a negative cap was spec-silent | **closed by R5a**, whose **own premise was false**: a negative cap does not behave as `0` (it emits a zero-length `fragment_too_long` on every push ending on a line boundary and inflates the framer's line numbers). R5a took F9's second option — a negative cap is a `ValueError`, stated in §3.4 |
| F10 | `reopen_failed` was specified, exported and completely untested: deleting the whole `except OSError` body left 444 passing | **closed by R5a**, including the streak question the finding raised |
| F11 | R2c's blocking premise was false (PR #4 had merged) and R2c was in no run's execution order, so a cold builder prompted for run 3 would never reach it — while R9 had to register R0–R9 with shas | **closed by the plan commits `63cbcca`** (R2c written into run 3, first, because it is a pin move and everything after it compiles against the new pin) **and `33364b4`** (status, sha, "Last updated"). Not R5a's to close: a batch never edited `WORKPLAN.md` |
| F12 | R9's row still said "§3 folded" while §0.6 and §3 had said "§3 and §4" since `9a2e40f` — leaving the corrected decision in the two places nobody reads at close and out of the one instruction an agent executes | **closed by the plan commit `afc6a7a`**. Both are folded above, which is what the correction was for |

### Run 2 — thirteen `thread` findings, registered

| # | Thread | Disposition |
|---|---|---|
| T1 | `Router.completion` is a mutable public field, and a completion attached **after** records have been routed measures `Quiet` from the tick rather than from the records: `route` creates a `_Book` only when `now is not None`, so `tick` builds it with `first_record_at = last_record_at = now` and `Completed.seconds` reports 0 for a trace open for an hour | **reached, and harmless where it is reached — but not for the reason first recorded here.** R7's CLI **does** reassign `router.completion` at end-of-input finalisation, to `Completion(policies=(Cap(0),), …)`, before one final tick (`spanweave_live/cli.py:274`, `SPEC.md` §8.5). An earlier reading of this disposition said "`Cap(0)` completes immediately and reads no accumulated silence, **so** nothing is mismeasured". That is a **non-sequitur**, and three fake-clock probes separate the cause from the claim: (A) the CLI's own shape — router built with its policy, one record, clock +3600 s, `completion` reassigned to `Cap(0)`, tick — reports `seconds=3600.0`; (B) the thread's own precondition, routing with `completion=None` and attaching `Quiet(1.0)` afterwards, does not fire at +3600 and reports `seconds=1.0` one second later; (C) **the same `Cap(0)` reassignment onto B's router reports `seconds=0.0`**. So the reassignment *does* mismeasure when the router was routed without a policy. What makes the CLI safe is the other half of the thread's sentence: **the CLI constructs the router with its policy**, so `route` opens a `_Book` on the first record and the books carry a true `first_record_at` for the final tick to subtract from. The thread's *prediction* was right about the fact, and this disposition had credited the wrong cause. **Still open** as the thread states it, which was never in doubt: no §5 sentence says what happens when a policy is added mid-stream, and no test covers the `Quiet` case. Either state it in §5.2 or make `completion` constructor-only |
| T2 | §5.4's "unreachable today" claim rests on spanweave's current refusal set, and R2c is a pin move | **open, and the claim survived the move.** The review probed the one live-looking route (`Router(adapter="otel_genai")` against an OpenInference record) and the pinned `Builder` **absorbs** it as a `NodeKind.UNKNOWN` node rather than refusing. Nothing fails if a future pin move adds a refusal that makes the branch reachable; a synthetic `Builder` stub whose `graph()` raises would close it for one test |
| T3 | The forgetting policy is due **before** R7, not after it: R7's `tail`/`serve` is the first caller that runs unbounded in wall-clock time and has no window to build | **closed: decided and built as R3a** (`baa32cb`), before R7 (`d21859d`). The decision is the 2026-10-06 `forgetting` row above; the measurement is in `SPEC.md` §5.5; and the thread's second requirement — that a late arrival after the horizon be distinguishable from a first sighting — is why a record for a forgotten id emits **no** `late_arrival` and opens generation 1, stated in §5.5 rather than left to be discovered |
| T4 | The cursor's advance on `delta_unavailable` is unspecified: `due()` advances before the consumer is called, so a window lost to a refusal is never retried and never re-reported | **open**, and benign: §6.2 states this explicitly for the *raising* case ("a subscriber that raised still advances") and §6.5 is silent for the *unavailable* case. The behaviour looks right — the consumer's first received update starts its own fold from `builder.graph()`. One sentence in §6.5, not a defect |
| T5 | R3's `released` still carries its version in `detail` only, now that `Event.version` exists | **open.** §4.1 and §6.1 both say so and both say it is §5's edit to make. Registered so it is not lost. An earlier reading of this disposition said `released` "has since been joined by `flush`/`forget` (R5a, §6.5)", which names two things that are not event codes: `released` **is** a code (`spanweave_live/completion.py:56`, `RELEASED: Final = "released"`), while `flush` and `forget` are **`Subscriptions` methods** (`spanweave_live/subscriptions.py:222` and `:251`) — neither appears as a code literal anywhere under `spanweave_live/`. What R5a actually did is replace R4's `released` *on `Subscriptions`* with those two methods, declared in **§6.1** and not §6.5 (§6.5 is the three codes, `consumer_error`/`delta_unavailable`/`delta_unsent`), and §6.1 is also where "R3's `released` keeps its version in `detail`; moving it is §5's edit" is written down. So the edit this thread asks for is **one code**, `released`, moving its version out of `detail` into `Event.version`; the two method names were never part of it, and the instruction to "take all of them together" was unfollowable as written |
| T6 | The R2b row's mutation criterion named the wrong assertion (the drop-mutation is caught by the diagnostic-code and byte-reconstruction assertions before `skipped_records`), the second run in which a row's criterion was imprecise — so: **a row should name the mutation, not predict which assertion fires** | **moot as a row, kept as a convention.** There are no rows left: `WORKPLAN.md` is deleted and the batch-row form went with it. `CONTRIBUTING.md`'s bar already asks for a named *mutation* ("a framer that hands partial lines over") and never for a predicted assertion, which is the convention the thread asked for. Recorded because the next series inherits the shape, not the file |
| T7 | R2b's commit body stated a parent sha that is not the parent (`7fdbff3`, which is `d152c3b~2`); harmless only by luck, since the two trees differed solely in `WORKPLAN.md` | **closed about the rule, not about the history.** The rule *is* fixed going forward, in the place that outlives the plan: `CONTRIBUTING.md`'s "confirmed red on the parent" bullet asks for the sha `<sha>^` **resolved to**, recorded in the commit body (§0.3 of the deleted plan was the other home). But this row recorded **once** what happened **six times of the seven code commits of run 3**, every one of the six landing after the review that named T7 (`63cbcca`, the run-2 review decision, is their common ancestor) — and **four** of the six bodies use the word "**derived**" for a sha that is not. Commit bodies are immutable, so the history cannot be repaired; it is written out here instead. Each parent below was re-resolved with `git rev-parse <sha>^` on 2026-10-07: `a4ce94b`→**`63cbcca`** (R2c; body says "red on the derived parent (704ce6a"), `c1e6946`→**`33364b4`** (R5a; body says "the derived parent `33364b4^` = `a4ce94b`" — right arithmetic, wrong subject: `33364b4^` *is* `a4ce94b`, but `33364b4` is the `plan:` commit that *follows* R5a, so it is R5a's own parent and not something to take `^` of), `baa32cb`→**`afc6a7a`** (R3a; "the derived parent `c1e6946`", repeated in `CHANGELOG.md`), `8ae7a5d`→**`e033f6c`** (R6; "the code parent `baa32cb`", disclosed as such), `d21859d`→**`3f593a6`** (R7; "the derived parent `8ae7a5d`"), `c3dcab0`→**`0acbed7`** (R8; "red on parent (`d21859d`"). In every case the cited sha is `^^` — the previous **code** commit, with a `plan:` commit in between — and harmless only because the two trees differed in `WORKPLAN.md` alone; only `86183b0`, which cites no parent at all, is clean. The R5a, R3a, R6, R7 and R8 entries above printed the uncorrected sha and now print the derived one |
| T8 | `WORKPLAN.md:213` still read "§3.4 records that the remainder has no cap", correct as dated history but a reversed claim with no forward pointer for a reader hitting it first | **moot at close** — the file is deleted — and answered here: the R1 entry above states the "no cap" position *and* the decision that replaced it, in that order, in one place |
| T9 | R2a's commit body said "69/69 green with R2a's tests deselected", which is not reproducible: the parent tree under the same mutation is 125 passed, and deselecting R2a's framing additions gives 68 | **open as a correction of the record.** The claim's substance was confirmed by a stronger run; only the number is off. Registered because run 1 raised the same class of thing (P-3, the factor of two) and the series' credibility rests on its numbers being re-derivable |
| T10 | "a `Tail` … *is* the iterator" is literally false in four places; and §7.1's "the asymmetry is **forced**" is *chosen*, not forced — a caller-supplied event sink would let `tail` stay a generator | **closed**, and the overclaiming word corrected, with §3.1's reason kept. Not "all four by R5a", which is what this disposition used to say and is wrong twice over. **Three** places carry the corrected wording at the tip, and R5a (`c1e6946`) is the commit that wrote all three: `SPEC.md:1629`, `spanweave_live/ingest.py:431` and `CHANGELOG.md:519` (measured, `grep -n "single-use iterable"`). The **fourth** was the `WORKPLAN.md` row, and R5a did not touch it: `git show --name-only c1e6946` does not list that file, and `git log -S"single-use iterable" -- WORKPLAN.md` returns `63cbcca` and `86183b0` only. So the fourth was changed by a `plan:` commit, to words that do not contain the phrase, and then deleted with the file by `86183b0`. This thread is the finding that a *correction* contained a precision defect — "the one place a project that strikes through its own premises cannot afford one" — so a disposition repeating the defect it closes was the worst available place for one. Corrected 2026-10-07 |
| T11 | Dynamic import escapes the gate: `importlib.import_module("time")` and `__import__("time")` both pass, so the gate's claim should be stated as "no **static** ambient import" | **closed by R5a**, as the finding's first option: the claim is stated as static. Nothing in the package imports `importlib`, and either form is conspicuous in review |
| T12 | §4.2's measurement is load-bearing spec text with no artifact: no benchmark script or test exists, so no later reader can re-derive it, and the quoted µs ranges taken as independent bounds give a wider interval than the stated one | **open.** §4.2's conclusion — optimisation, not necessity, no batch — does not depend on the precision, so this is provenance rather than correctness. A re-runnable benchmark under `tests/` would close it; the series did not add one |
| T13 | Three protocol-text lags: §0.1 step 6's stop list did not authorize the `awaiting PR #4` stop that §3 and the R2c row did; `awaiting <batch>` bookkeeping was applied inconsistently; and one plan subject read alone misleads about which commit closed an item | **moot at close**, and none of the three affected behaviour. The status is right; "all three are text in a deleted file" was not. It holds for (i) and (ii), both `WORKPLAN.md` text. Item (iii) is an **immutable commit subject** — `7a6e6a6 plan: R2a done, and one of its items was closed by the plan commit` — which reads alone as though `7a6e6a6` closed the item, where the commit that did is `9a2e40f` (**R0-1**). A subject cannot be edited, so that one is moot because it is unreachable, not because its text was deleted; `7a6e6a6` itself changed `WORKPLAN.md` and nothing else. Recorded because the next series inherits the protocol: a stop list should name every stop its decisions authorize, a status convention should say which convention it follows, and a `plan:` subject should name the commit that closed the item |

### The record made true — the close review's eight blocking findings (2026-10-07)

**Not a batch of the series.** The series closed at `86183b0`; this is one
follow-up commit on `receiver`, derived parent `86183b0`, made by the
orchestrator after the scoped review of the close
(`reviews/2026-10-07-close.md`). It changed **no behaviour and no test**, so the
bar's *red on the parent* and *named mutation* lines do not apply to it and no
worktree or parent run was made; its evidence is the measurements below.

The review found the code merge-ready and the **record** untrue in eight places,
none of them a code defect. All eight are closed above, in place, where the false
sentence was:

| # | what was false | where it is now true |
|---|---|---|
| B1 | T10's "all four, closed by R5a" | **T10** — three places, R5a wrote all three; the fourth was the `WORKPLAN.md` row a `plan:` commit changed and `86183b0` deleted |
| B2 | T5 naming `flush`/`forget` as event codes, and §6.5 | **T5** — they are `Subscriptions` methods; the surface is §6.1 |
| B3 | "Thirteen rows" in the decisions log, twice | *Decisions taken*, and `CHANGELOG.md` — **twelve**, counted |
| B4 | "each [plan citation] sits inside a dated batch entry" | **R9** — fourteen survive, thirteen are dated, and the fourteenth (`CHANGELOG.md:7`) is re-pointed at this file |
| B5 | five present-tense "the seam allowlist is empty" claims | `CLAUDE.md` rule 4, `SPEC.md` §5.2, `spanweave_live/ingest.py`, `endpoint.py` ×2 — each states the one entry, and `CLAUDE.md`'s module list gains `http.server` |
| B6 | §8.7's "every test in it runs the CLI as a process" | `SPEC.md` §8.7 and the **R7** entry — 72 of 81 collected items spawn a process, nine read the package |
| B7 | six recorded figures that did not re-derive | **R5a**, **R3a**, **R6**, **R7**, **R8** entries, each with the derived parent and the corrected number |
| B8 | "10⁶ is 230.5 MB" sourced to `SPEC.md` §5.5 | **R3a** — attributed to R3a's own measurement; §5.5 is cited only for what it says |

**Every figure that could be taken at the tip was re-measured for this commit
rather than copied from the review**, and four of the review's own figures did
not re-derive (listed with the archives above). Three could not be: R7's
`77 / 4`, R8's `5 / 634` and R3a's `11 / 492` are parent runs, and a parent run
needs a worktree this commit had no reason to make, so those three are the
review's re-derivation and are attributed as such where they appear. What was
measured here, and how:

- **81 collected items in `tests/test_cli.py`, 72 spawning a process, 9 not** —
  `subprocess.Popen`/`run` wrapped by a pytest plugin that records the running
  item's nodeid, so the count is of what each test *did* and not of what its
  source looks like.
- **The R7 mutation** (`framer_line=event.line` → `line=event.line`) —
  re-planted at the tip: **1 failed / 80 passed** in the file,
  **1 failed / 650 passed** across the suite, `KeyError: 'framer_line'`, then
  reverted.
- **The R8 mutation's effect** — computed from the replay's own observations: the
  final graph fails two rules, so the mutation erases **two** first-failures.
- **`SPEC.md` §5.5's book figures and the 10⁶ extrapolation** — re-run by the
  method §5.5 names, reproducing all three rows to within one float object and
  giving **230 516 588 B** at 10⁶.
- **T1's three probes** — A `seconds=3600.0`, B `seconds=1.0` one second late,
  C `seconds=0.0`, on a fake clock.
- **The six derived parents** — `git rev-parse <sha>^`, each against the sha its
  own commit body names.
- **`FORGOTTEN`'s absence at `afc6a7a`** — `git show`, no worktree needed.

**What this commit did not close, and why.** Its scope was prose, and three
files under `spanweave_live/` plus no test at all. So four more sentences of
B5's shape are still standing, disclosed here rather than left to be found:
`spanweave_live/completion.py:19` still says the allowlist "stays empty" in the
present tense, which is the same defect as the three that were fixed and was
missed by the review's own table of five; and `tests/test_completion.py:166`,
`tests/test_ingest.py:764` and `tests/test_gates.py:263` each carry a looser
version of it in a docstring or comment, two of them dated to their own batch and
one not. `CHANGELOG.md:511`, `:607` and `:766` say it too, and so do
`SPEC.md:1672` and `:1676`; all five of those are **correct**, because each sits
inside a dated entry or a section dated to its own batch. The two behaviour
threads the review raised (`serve` re-yielding the previous request's `Records`;
a client that aborts before reading leaking an uncounted `socketserver`
traceback) are **`SPEC.md` §7.2 decisions, not patches**, and are left for the
maintainer under `CONTRIBUTING.md`'s "Halt, do not improvise".

---

## Origins

| ID | Origin |
|---|---|
| R0–R7, R9 | spanweave `OPEN_QUESTIONS.md` §19 (receiver project items 1–5) and its decision of 2026-09-29; spanweave `SPEC.md` §7 (the reader's three properties) and §10.10. |
| R8 | §19 "The live consumer, and why it needs no new rules". |

The inserted batches have their own origins, all of them findings rather than
plans: **R2a** and **R5a** are the first two cold reviews archived above; **R2b**,
**R2c** and **R3a** are the three decisions those reviews forced (the framer's
cap, the upstream `py.typed`, and the forgetting policy), each taken by the
maintainer in the decisions log and built by one batch afterwards.
