# Changelog

All notable changes to this project. **Nothing here is frozen**: the version is
`0.0.x`, and until that changes any entry below may be undone by the next one.

The format is loosely [Keep a Changelog](https://keepachangelog.com/); the unit
of change is a **batch** (`WORKPLAN.md`), and each entry names the batch.

## Unreleased

### R8 — the showcase: agentgolden's rules per delta, and a premise corrected (2026-10-06)

No change under `spanweave_live/`. The receiver already had everything a live
rules consumer needs, and that is the finding rather than a shortfall of it
(`SPEC.md` §9, new in this commit).

Added

- **`tests/showcase.py`**, a consumer that on every per-record `Update` asks
  `update.builder.graph()`, computes `agentgolden.signature.signature`, and
  evaluates `showcase/examples/support_agent/rules.toml` — **unchanged** —
  with `agentgolden.rules.evaluate`, keeping every version's verdicts so the
  first version at which each rule failed is a lookup. It lives in `tests/`,
  not in the package: the receiver carries no rules (`SPEC.md` §1.2), and
  `make showcase` / `python -m tests.showcase` prints the table.
- **`agentgolden` as a pinned *dev* dependency** (`aa1847f`) plus **`showcase/`,
  a submodule of that repository at the same sha**, because the rules file and
  the trace live under its `examples/`, which its wheel does not ship, and a
  copy here would be a second thing to keep at the pin. `tests/test_pins.py`
  holds the pair equal the way it holds the `spanweave` pair, asserts the
  receiver's runtime dependency list is exactly `["spanweave"]` so an installed
  receiver carries no rule engine, and asserts the resolution the row only
  claimed: `agentgolden` needs `spanweave>=0.9.1,<1.0` and the pinned
  `spanweave` is `0.9.1`, so it is the **lower** bound that is met exactly.
- **`tests/gates.py`'s fourth rule, `no-consumer-rules`**: no module under
  `spanweave_live/` may statically import `agentgolden`, with **no seam** —
  the package evaluates nothing, so no file at the edge has to bind a rule
  engine. Watched failing against four planted imports, and its limit stated:
  it bans a module, not a vocabulary.
- **`tests/test_showcase.py`**, 12 tests, asserting the first-failure version
  table exactly, the complement (fifteen rules passing at every version),
  verdict-for-verdict equality against `spanweave.build` of the whole trace,
  byte equality of the live final graph against the batch graph through gate
  A's own `undigested`, and that the rules file and the trace are the pinned
  submodule's own committed blobs.

Corrected

- **`WORKPLAN.md` R8's premise is false, and the test asserts the measurement
  rather than the row.** The row — from `spanweave` `OPEN_QUESTIONS.md` §19 —
  predicted the `verify_identity → issue_refund` **order** rule failing at the
  version that absorbs the `llm.plan` span carrying the `issue_refund` request,
  one version before the tool span. It fails at version **6**, when
  `tool.issue_refund` arrives. The mechanism the memo named is true (the
  request *is* absorbed first: at version 5 the graph already reports
  `issue_refund` as an `unpaired_call`), but `agentgolden`'s `OrderRule` reads
  `Signature.tool_calls` — tool **nodes** — and `spanweave`'s `NodeKind` is
  closed, so a requested call with no span is a *diagnostic* and not a node.
  At version 5 the order rule is a **vacuous pass**.
- **"When it almost happened" is real and it is a different rule.**
  `trajectory.all_calls_fulfilled` fails at version 2 and version 5 and passes
  at every other version including the last — a verdict that exists only live,
  because the batch graph of the finished trace shows it passing. The live
  reading does not make the *ordering* violation visible earlier; it makes the
  *window between a request and its fulfilment* visible, which the finished
  graph closes.

The first-failure table, in full: `tools.required:verify_identity` 1,
`tools.required:issue_refund` 1, `trajectory.all_calls_fulfilled` 2,
`order:verify_identity<issue_refund` 6; the other fifteen rules never fail.

The named mutation: a consumer that evaluates only the **final** graph
(`LiveRules.__call__` keeping the latest `Observation` instead of appending it)
reports every failure at version 7 and loses `trajectory.all_calls_fulfilled`
entirely — 6 of 12 tests fail. A showcase whose table survived that mutation
would not be showing anything live.

### R7 — the CLI, and the first entry in the seam allowlist (2026-10-06)

Two commands, no new mechanism, and the one module in the package that imports
`time` and `http.server` (`SPEC.md` §8, new in this commit).

Added

- **`spanweave-live tail <path> --out <dir>`** and **`spanweave-live serve
  --port P --out <dir>`**. `<path>` is a file or `-` for stdin. Every other flag
  sets a value an earlier section already declared — `--quiet`/`--root-grace`/
  `--cap` are §5.3's three policies, `--max-traces` is §4.5, `--max-completed`
  is §5.5, `--max-pending-bytes` is §3.4, `--deltas` is one §6.1 subscription,
  `--poll-seconds`/`--once` are §7.1's and `--host`/`--port`/`--requests` are
  §7.2's. §8.1's usage block is parsed out of `SPEC.md` by a test and held
  against the parser **in both directions**, so a flag in one and not the other
  fails the build. The policies compose in the order §8.1's table lists them,
  because a command line has no tuple order of its own and §5.4's any-of needs
  one; picking an order was unavoidable, hiding which one would not have been.
- **Final graphs as `<trace_id>.json`** in `--out`, which is §5.4's write under
  §5.5's name. The CLI ticks **once per yield** from its ingest and not once per
  record (per record would re-materialize the graph for every `RootEnded`
  evaluation, which is exactly what §5.7's cache spares), and when the input
  ends it replaces its completion with one whose only policy is `Cap(0)` and
  ticks once more — so a replay leaves every trace's graph behind, and
  `Completed.policy` says `Cap(records=0)` rather than the CLI inventing a code
  for "the input ended".
- **Events to stderr, one JSON line each**, sorted keys and ASCII-escaped so a
  line is one line whatever a trace payload held, flushed as written, with
  `code` and `layer` on every line and a `None` field left out rather than
  written as `null`. stdout carries **deltas and nothing else** — one
  `spanweave.delta_dumps` document per line, the library's own canonical bytes,
  which already end in one `\n` and hold no other, so there is no second
  encoder here.
- **Exit codes, documented in `--help` and in §8.6**: `0` the input ended and
  everything was delivered; `1` it could not start; `2` usage; `3` it ran to the
  end but something it had could not be delivered (`not_written`,
  `delta_unsent` or `consumer_error`); `130` interrupted. The code is about
  **what the receiver could not do**, never about what the telemetry said: a
  `refused`, a cap, a late arrival, a `415` and a `400` are observations and
  leave the code at `0`, because a receiver that exited non-zero on a re-sent
  span would be a gate (§1.3).
- **`tests/test_cli.py`**, 81 tests, every one of them through `subprocess`.
  Its central test is gate A's comparison reached through a **process**: all 51
  line-delimited corpus renderings piped to `tail -`, and the two OTLP
  documents POSTed to `serve --port 0`, each compared byte for byte against
  `spanweave.dumps` of `spanweave.build` of that rendering with gate A's own
  loader. Nothing in the file waits on a clock: stdin's EOF is a stop,
  `--poll-seconds 0` leaves the one trailing poll nothing to wait out, `--port 0`
  plus the `listening` line means no port is written down, and every barrier is
  a **read** (the `listening` line before a POST, a delta line before a signal).
- **`make install-check` now runs a command, not just `--version`**: one corpus
  record piped to the *installed* console script from outside the repo, with
  `t1.json` required to land. `--version` proved the script existed; this proves
  the thing a human runs works in what ships.

Changed — the seam allowlist is no longer empty, and this is the entry worth reading

- **`tests/gates.py`'s `SEAMS` is `{"real.py": {"time", "http.server"}}`** — the
  project's first entry, after R3 (`now`), R5 (`sleep`) and R6 (the listener)
  were each predicted to need one and each declined it. All three declined for
  the same reason: the seam was a parameter with no default, so the caller held
  the import. **R7 is that caller.** `Completion.now`, `tail`'s `now` and
  `sleep` and `serve`'s listener factory are those parameters, and something has
  to hand them the real `time.monotonic`, the real `time.sleep` and a real
  `HTTPServer`: a process has nobody to take them from. The entry is not a
  weakening of the three refusals; it is the place all three were deferring to,
  and §1.4, §5.2, §7.1 and §7.2 each say so now.
  - It names **`real.py`, not `cli.py`**, because an entry exempts a whole file:
    the exempted file is fifty-odd lines that do nothing but hand back the real
    thing,
    and the several hundred lines of `cli.py` — where a stray `time.monotonic()`
    could actually hide — stay under the gate. A test runs the gate's rules over
    `cli.py` with an **empty** allowlist to prove it.
  - It names **`http.server`, not `http`**, because the matcher matches a module
    or anything under it and `http` would have exempted `http.client` too.
  - `real.py` is deliberately **not** exported from `spanweave_live/__init__.py`.
    Publishing it would publish a clock this library is built not to own.
- **`tests/test_completion.py::test_no_other_test_in_the_suite_sets_a_bound`**
  now names `tests/test_cli.py` as its one exception, and holds that the file
  contains no `max_completed=` — the bound is set as a CLI flag in a child
  process, never in a router of this suite's, so every router the rest of the
  suite builds (gate A's included) still forgets nothing.

Surfaced — R3a's overwrite reaches a human for the first time

- `--out` is the first caller in this project that can **lose a graph**.
  Forgetting a completed trace id loses its generation, so a later record for a
  forgotten id writes `<trace_id>.json` **over** the file the earlier completion
  wrote: §5.5's "the file already written is not rewritten" holds only while the
  completion is remembered. The CLI says it in three places and none of them is
  a footnote — in `--max-completed`'s own `--help` text, in one `may_overwrite`
  line on stderr the first time a `forgotten` appears, and in §8.5. A test POSTs
  two records of one trace with `--cap 1 --max-completed 0` and asserts the file
  left behind is the **second** generation's graph and not the first's, with its
  twin asserting that the default writes `t1.json` and `t1.2.json` side by side.

Honoured — R2b's line numbers, where a human reads them

- A framing event's `line` is written to stderr as **`framer_line`**. Once a
  line has been cut by `--max-pending-bytes`, each fragment is numbered as a
  line, so the number is the framer's count of lines *handed over* and not the
  input's count of lines *written* (§3.4, §7.1) — and a key spelled `line` would
  have been read as the second. The `line N` that opens a reader diagnostic's
  message carries the same divergence and cannot be renamed, so the run's first
  `fragment_too_long` is followed by one `cli` line of code
  `line_numbers_diverged`, once per run and not once per fragment (§4.6).
- The named mutation is that renaming: `framer_line` written as `line` takes
  exactly one test down and leaves every graph, every exit code and every other
  event untouched. R2's and R6's lesson applies twice over here and the test
  **holds the premise rather than assuming it**: every corpus rendering's lines
  end in `\n`, so the remainder after a push is empty and the cap never bites —
  a suite whose only inputs were the corpus' own bytes would have left the
  renaming untested and green. The input that bites is 70,000 bytes with no
  newline in it at all, which holds **zero** lines while the framer reports two.

### R6 — the OTLP/HTTP endpoint, with the socket in the caller's hands (2026-10-06)

The second of the two ingests (`SPEC.md` §7.2): an exporter POSTs a body instead
of writing a file. Stdlib `http.server` only, and no dependency.

Added

- **`Endpoint`**, which serves exactly one request — `POST /v1/traces` with
  `Content-Type: application/json`, `Content-Encoding: gzip` inflated — and
  hands the body to **`Framer.document`**, never to `Framer.push`. That has been
  a standing instruction since R1 (`SPEC.md` §3.3) and it is a trap rather than a
  rule: the corpus' two container renderings end in a newline, so a POST of one
  of those bytes-for-bytes reads *identically* through `push`. The same export
  with its trailing newline trimmed — the ordinary shape of an HTTP body — loses
  its closing brace to the remainder, and compacted onto one line it reads as
  nothing at all. So `tests/test_endpoint.py` posts every document rendering in
  **three spellings** and compares each against gate A's own batch graph; the
  `push` mutation leaves both verbatim cases green and takes ten tests down.
- **`415` for every request that is not the one served** — wrong method, wrong
  target, wrong media type, a `Content-Encoding` it cannot undo, or a
  `Transfer-Encoding` it cannot unframe — counted, with the check named in the
  event's `detail`. One status and not three, argued in §7.2 rather than
  defaulted. `Transfer-Encoding` is **refused rather than ignored**, which is the
  one check that exists for §1.5 and not for HTTP: `respond` reads
  `Content-Length` bytes, so accepting a chunked body would mean answering `200`
  to a body nobody read.
- **`400` for a body that cannot be read**: a gzip that will not inflate, or a
  read that skipped every line and produced no record. The reader's own
  diagnostics ride out in the exchange's `records`, which is the only place
  those bytes survive, and `Event.spanweave_code` carries the first diagnostic's
  code. An **empty** body and an empty container are a `200`: calling them a
  `400` would be the receiver deciding a body should have held spans, which is a
  dialect read (§1.1). An accepted body answers `{}` and **not** OTLP's
  `partialSuccess` envelope, for the same reason — a truthful `rejectedSpans`
  needs a span count.
- **`serve(endpoint, listener=…)`**, one yield per request handled, refusals
  included and empty rather than absent (§7.1's rule for a poll that read
  nothing), with the listener closed however the iteration ends and `until` the
  caller's stop.

Unchanged, and this is the entry's one real finding

- **The seam allowlist in `tests/gates.py` is still `{}`.** R0 predicted that
  R6's listener would be the first entry, as it predicted R3's clock and R5's
  sleep, and all three predictions were wrong for the same reason: a parameter
  with no default. Here the seam turned out to be **two** parameters, not one —
  `handler_class(base, endpoint)` takes the handler's base class and builds the
  class with `type(...)` because a `class` statement would need the base at
  import time, and `serve` takes the listener factory. So nothing under
  `spanweave_live/` imports `http`, `socketserver` or `socket`, the gate passes
  the new module unexempted, and `import http.server` waits for R7's CLI beside
  the real `time.monotonic` and `time.sleep`. `gates.py` and §1.4 record the
  third declined prediction; nothing R0 named is left to want a line.
- **Routing's `Event` gained no field**, unlike R3 (`seconds`), R4 (`version`),
  R5 (`offset`) and R3a (`at`): a `415` and a `400` are about a request, and
  `index`, `spanweave_code` and `detail` are the three facts they have. The HTTP
  status lives on the `Response` beside the event, where it is not `None` for
  every other code in the project.
- **§7.2's surface is held to the code** from the day it exists, by §4.1's own
  block test (R5a, F5) reused for `Request`, `Response` and `Exchange` —
  `declared_fields` now also finds the last subsection of a part, which §7.2 is.

Tests 503 → 547. Red on the code parent (`baa32cb`): its own 503 pass there and
the whole new file is a collection error, because `spanweave_live.endpoint` does
not exist on it.

### R3a — completed trace ids are forgotten by the caller's bound (2026-10-06)

R5a's §5.5 stated the cost and said the fix was a decision rather than a
section's to invent. The decision was made (`WORKPLAN.md` §3, 2026-10-06) and
this is it: the book that outlives the builders gets a **caller-set bound**, and
forgetting is an event like everything else here.

Added

- **`Router(max_completed=None)`.** `None` is the default and forgets nothing,
  which is R3's behaviour unchanged — a caller that upgrades gets no new silence
  it did not ask for. At `max_completed=N` a `tick` that pushes the number of
  remembered completions past `N` evicts the oldest ones, **oldest by the order
  this router completed them in** and not by a sort on the caller's clock, so a
  clock that steps backwards evicts nothing out of turn. It is a **count, not a
  horizon**: memory is what the bound buys, and a horizon of ten minutes bounds
  nothing on a stream that completes ten thousand traces a minute.
- **The `forgotten` event**, one per evicted id, carrying the trace id and — in
  `Event.at`, R3a's one new field — the clock reading at which that trace was
  completed. `at` is an **instant** and `seconds` is a duration, and one field
  meaning both is a field a caller cannot match on, so §4.1 declares a second
  one. The event rides on the `Completed` whose completion pushed the book over,
  which is also why the eviction is evaluated there and not at the top of the
  next tick: a tick that completes nothing has no `Completed` to report on, and
  an eviction nobody was told about is the silence `SPEC.md` §1.5 refuses.
- **`SPEC.md` §5.5 is rewritten from "unbounded"** to this policy, including the
  consequence, which is the whole of the trade: a record for a **forgotten** id
  is a new trace at **generation 1** and emits **no `late_arrival`**, because the
  gap it would carry is the fact that was evicted. A bound on the book is a bound
  on how long a late arrival stays recognizable. The second half of that trade is
  the one place a bound costs more than memory and it is stated too: generation 1
  is `<trace_id>.json`, so where the caller named an `out_dir` the new generation
  is written **over** the forgotten one's file — §5.5's "the file already written
  is not rewritten" holds while the completion is *remembered*, and the receiver
  cannot number a generation it does not remember. Stated in the spec, asserted
  in `tests/test_completion.py`, never discovered live.
- Ten tests on the fake clock, eight of them red on the derived parent
  (`c1e6946`): the eviction and its event, the forgotten id's first sighting, a
  remembered id's `late_arrival` still carrying its gap, eviction order across
  ticks and within one, an **open** trace never being forgotten however small
  the bound, `max_completed=0`, and `None` forgetting nothing — that last one
  across the whole suite, by reading the rest of the suite's source for a bound
  no other test sets.

### R5a — the run-2 review's `next batch` items, closed (2026-10-06)

One commit for the twelve findings `patches/REVIEW-2026-10-06.md` marks
`next batch`. Three of them were behaviour, three were a gate, one was CI, and
the rest were documents that claimed more than the code did. The two that are
the orchestrator's file (`WORKPLAN.md` F11, F12) are not touched here.

Changed

- **A subscriber with `every=N` now receives its tail.** A completing trace
  hands every behind subscriber `delta(since=cursor)` before it forgets the
  cursors (`SPEC.md` §5.4's fifth step), and `Router.flush(trace_id)` is the
  caller's way to ask for the same thing mid-stream. It was a `delta_unsent`
  *report* and nothing else, which meant a coarse subscriber silently never saw
  the end of any trace whose length was not a multiple of its window — a dropped
  delta, not a policy the caller had not asked for (`WORKPLAN.md` §3,
  2026-10-06; F2). `delta_unsent` is kept for the one case where the tail cannot
  be produced at all, and it now carries the library's own code.
- **`SPEC.md` §6.6's fold claim is restated** as holding at the last delivered
  version mid-stream and at the final version **after completion or flush**, and
  the `every=N` fold test runs at `records=7, every=2` — a count that is *not* a
  multiple of `N`. At `records=6` the claim was true of the fixture rather than
  of the mechanism (F2), and that test is red on the parent at 7.
- **`Subscriptions.released` is now `flush` + `forget`**, split because the two
  halves happen at different moments: the tail goes out while the released
  builder is still in hand, and the cursors are dropped after it.
- **`Framer(max_pending_bytes=0)` is tested** — the boundary §3.4 stated and
  nothing held (F9) — and a **negative** cap is now a `ValueError` rather than
  "behaves as `0`": `len(remainder) <= -1` is false for the empty remainder too,
  so it reported a `fragment_too_long` of length 0 on every push that ended on a
  line boundary and burned a line number doing it.
- **`reopen_failed`'s "once per failure" means once per rotation.** The streak
  flag is cleared by a poll that finds the path naming the file the tail still
  holds, as well as by a successful reopen, so a path that reverts and is then
  rotated away again reports a second time instead of nothing. It was also
  entirely untested — deleting its `except OSError` body left the suite green
  (F10) — and now has the event, its offset, and the old handle still being read
  after the failure.
- **The invariant gate enforces what it is advertised as proving.**
  `no_ambient_runtime` also bans `secrets`, `uuid`, `concurrent.futures`,
  `selectors`, `select`, `subprocess` and `sched` (F7); a new `no_network` rule
  bans `urllib`, `http`, `requests`, `httpx` and their kin, which this
  repository had nothing stopping, unlike its parent (F8); and a new
  `no_ambient_os` rule bans `os.times`, `os.urandom`, `os.fork`, `os.pipe` and
  their kin without banning `os`, which `SPEC.md` §7.1's tail needs for
  `os.fstat`. All three are **static**, which the rule's docstring and a test
  now say out loud: a dynamic `importlib.import_module("time")` escapes an AST
  walk. The seam allowlist is still empty, and R6's `http.server` is the first
  import that must be injected away or earn one narrow line in it.
- **CI gains `check (macos-latest, 3.12)`**, running `make check` — the whole
  suite. The only macOS job ran `make conformance`, i.e.
  `tests/test_conformance.py` alone, so `tests/test_ingest.py` had **never run
  on macOS** while the series cited macOS for rotation and truncation being
  platform facts (F6). Seven jobs now, not six. A test in `tests/test_ingest.py`
  holds the job in the workflow, so the claim and its evidence fail together.
- **A `Tail` is a single-use iterable, not an iterator.** Four places said it
  "**is** the iterator" and the object has no `__next__`: `iter(t) is not t` and
  `next(t)` raises (T10). The §3.1 reason is unchanged and is why the object
  exists — the yielded value is `spanweave.Records` and a bare generator has
  nowhere to carry a tail's events — but that asymmetry is **chosen**, not
  "forced": a caller-supplied event sink would have let `tail` stay a generator.
- **`SPEC.md` §4.1 declares `Event.offset`**, which R5 added to the code while
  its commit message and CHANGELOG entry both said §4.1 was amended (F5). "The
  block is declared exactly as the code accepts it" is now a test that parses
  this section's own fence — and it caught a second drift immediately:
  `Routed.events` carries `= ()` in the code and carried no default in the spec.
- **`SPEC.md` §5.5 counts `_Book` correctly** — five fields, not six: there is
  no flag, because `completed_at` being `None`-or-set *is* the flag and is one
  of the four floats (F1). The measured cost is in the section now too: **≈ 220
  B per completed trace id**, ~22 MB at 10^5 and ~210 MB at 10^6, which is about
  5.5× what the field list reads like and is the number the forgetting decision
  is made against.
- **`SPEC.md` §6.5 names both ways to `delta_unavailable`.** The second one
  touches no caller's retention: a consumer joining a trace already in flight
  with a window coarser than the journal is kept at, since retention is widened
  only after a fan-out (F4). The behaviour was already right and is now fixtured.

### R2c — the pins move to a typed spanweave, and the override goes (2026-10-06)

A batch with no new behaviour in it: it makes a fact true that two documents and
a config comment had been calling temporary. `spanweave` PR #4 is merged, so the
pinned library now ships `py.typed` and the one mypy override this repository
carried has nothing left to stand in for.

Changed

- **Both halves of the pin move to `fec7da27af517ad8b58ae3ec57827916aae60674`**
  (spanweave `main` after PR #4): the `pyproject.toml` dependency, the `corpus/`
  submodule and `uv.lock`, in one commit, as `tests/test_pins.py` requires.
  Still HTTPS on both halves — CI's own `submodules: true` checkout
  authenticates over HTTPS and an SSH URL fails at checkout rather than at a
  pin (`SPEC.md` §0.1). The sha carries no API change: PR #4 is one commit and
  it adds a marker file.

Removed

- **The `[[tool.mypy.overrides]]` entry for `spanweave.*`**, and with it
  `follow_untyped_imports = true`. `mypy --strict` now reads `spanweave` as the
  typed package it is: 20 of its modules enter the build from site-packages,
  `read_records` reveals as `def (data: bytes | bytearray | memoryview[int]) ->
  spanweave.read.Records`, and nothing resolves to `Any`. The `pyproject.toml`
  comment that explained the override is replaced by one that explains its
  absence, because "there is deliberately no override here" is the thing a
  reader needs told.

Added

- `tests/test_typing.py` — three tests, because the claim has three parts: the
  installed `spanweave` carries `py.typed`; no mypy configuration anywhere sets
  `follow_untyped_imports` or `ignore_missing_imports` (`[tool.mypy]` and every
  override entry parsed, not grepped, so the file is still free to *name* the
  deleted setting in a comment; plus `mypy.ini`/`setup.cfg` and the mypy command
  lines in the `Makefile` and CI); and `mypy --strict`, under this repository's
  own configuration, really reports a planted `int = read_records(b"")` against
  the real return type. The third is the one that matters most: deleting the
  override while the dependency were untyped fails **loudly**, but
  `ignore_missing_imports` would fail **quietly**, by making every annotation in
  this package vacuous while the gate stayed green.
- `SPEC.md` §0.2 rewritten from *"one typing override, and why it is temporary"*
  to *"no typing override: the dependency is a typed package"*, keeping the
  history — including why `ignore_missing_imports` was refused — because that
  reasoning is what stops the override coming back under a worse name.

### R5 — ingest: a growing file, and a pipe (2026-10-05)

The fifth piece (`SPEC.md` §7, new; §7.1 written, §7.2 reserved for R6). The
first piece that touches the outside world, and it touches as little of it as the
job allows: it opens a file, reads chunks, hands them to `Framer.push`, and hands
back what the framer said. It looks inside no chunk and routes nothing.

Added

- `spanweave_live.ingest`, with `tail(path, *, now, sleep, poll_seconds, …)` and
  `stdin(stream=None, …)`. `tail` returns a `Tail`, a **single-use iterable of
  `spanweave.Records`, not an iterator** (corrected in R5a: it has no
  `__next__`, and this entry said "is the iterator"); `stdin` is a generator.
  The asymmetry is the framer's own
  (`SPEC.md` §3.1): the yielded value is `spanweave.Records` and stays that way,
  so a tail's events ride **beside** the yields and a bare generator has nowhere
  to put them — and a pipe, which cannot be truncated or rotated, has no events
  to carry. A `Tail` is iterated once and a second iteration raises, because an
  "again" would resume the first one's stream while looking like a fresh start.
- **`sleep` is injected and has no default, so the seam allowlist in
  `tests/gates.py` is still empty.** R0 predicted R5 would need the first entry
  and R5 does not, for the reason R3 did not: a seam with no default is a seam the
  caller binds, and there is then no `time` import under `spanweave_live/` to
  exempt. The real `time.sleep` and `time.monotonic` are R7's CLI's to bind. The
  gate's note now records two wrong predictions rather than one, and says R6's
  listener should be made to prove it needs a line.
- `truncated`, `rotated`, `vanished` and `reopen_failed`, as the router's `Event`
  (`SPEC.md` §4.1) rather than a type of their own: R2b split `FramingEvent` off
  because framing is *below* routing, and ingest is *above* it. Truncation is
  `os.fstat` of the open handle against the offset; rotation is `(st_dev, st_ino)`
  of the path against the open handle — the platform's own answer to "the same
  file", read and not chosen, so no policy was invented and nothing halted.
- `Event.offset: int | None` — one more optional field, as R3 added `seconds` and
  R4 added `version`, because §1.5 is only true where a caller can match on the
  number instead of reading it out of a sentence.
- One yield per read, **including a read that completed no line**: "nothing
  arrived" and "nothing was completed" are different answers and `pending_bytes`
  is where the second is visible. A poll with an event to report yields too, so
  no event is invisible to a caller that only looks between yields.

Stated, because the honest answer was not an event

- A **short read** is not an event: `read(n)` returning fewer than `n` bytes is
  how a file says "that is all for now", and a code for it would be a code per
  poll on a file that is merely still being written.
- A file **truncated and regrown past the old offset between two polls** is
  indistinguishable from growth, and `SPEC.md` §7.1 says so rather than offering a
  heuristic that would be wrong differently. `poll_seconds` is how narrow that
  window is, and it is the caller's number.
- An open that fails **at the start** raises; it is not an event. The first open is
  the caller's claim that there is a file there, and waiting for one to appear is a
  retry policy the receiver does not carry (`SPEC.md` §1.2).
- A tail **does not flush** when it stops: its stop is the caller's `until`, which
  is not end of input, so the remainder stays visible as `pending_bytes`. `stdin`
  does flush, because EOF **is** end of input and a pipe's last line without a
  `\n` is a record only the flush can produce.

Tested

- **A corpus rendering appended in random chunks is the graph gate A asserts.**
  Every line-delimited rendering, written to a real file in seeded chunks while
  the tail is asleep, compared byte for byte against `spanweave.build` with gate
  A's own loader, chunker and comparison imported — not a weaker one of this
  file's own (`SPEC.md` §4.7, §7.1). Ten seeds; the file is 34 tests in ~1.2 s.
- **Truncation and rotation are two contents in one file**, the second relabelled
  onto a second trace id, and **both** graphs must come out exactly. The named
  mutation — a tail that treats truncation as ordinary growth — fails on the
  missing event, on the offset, and on the second trace's graph, because it reads
  at an offset the new content never had.
- The remainder held at a truncation comes back as **one `malformed_record` with
  its text**, never joined to the head of the new content: a line made of two
  files would be §3's failure mode reached through the back door.
- Rotation is claimed only on a poll that read nothing, so the bytes written to
  the old inode in the same breath as the rename are handed over first; a vanished
  path is **one** event however many polls find it gone; every wait is the
  caller's `sleep`, called with `poll_seconds`, and the clock moves only because
  the test's driver moved it.

### R4 — the deltas go out, and nothing is concluded about them (2026-10-05)

The fourth piece (`SPEC.md` §6, new). A consumer registers a callback and, after
every **absorbed** record, is handed what changed. The receiver hands over a
`spanweave.Delta` and the builder it came from and looks at neither: a subscriber
narrows by **trace id** and by **how often**, which are facts about the stream,
and by nothing else. A filter by meaning would be a rule the receiver carries
(`SPEC.md` §1.2).

Added

- `spanweave_live.subscriptions`, the lower of the two layers as `completion.py`
  is: values, the registry, the cursors, and the two pure questions "who is due?"
  and "how much journal does this trace need?". It emits no events and imports
  nothing from `routing.py` — calling a consumer, catching what it raises and
  keeping the books are the router's.
- `Subscriptions.subscribe(consumer, *, trace_id=None, every=1)` and
  `Router(subscriptions=...)`. `trace_id=None` is every builder the router feeds,
  the **no-trace builder included** — not §5.4's answer for completion, and
  deliberately: completing that builder would throw the library's own account of
  those records away, while reporting on it throws nothing away, and leaving it
  out would mean a record was absorbed, the graph changed, and a consumer that
  asked for everything was told nothing.
- `Update(trace_id, version, since, delta, builder)`, with **no graph on it**:
  materializing one per record per subscriber is the cost `SPEC.md` §2.3 is
  about, and the builder is right there to ask. A test holds that field set, as
  one holds `TraceState`'s, because an `Update` that grew a severity or a score
  would be the receiver evaluating on a consumer's behalf.
- **Per-record and `every=N` are one mechanism.** A subscriber is due when
  `version - cursor >= every` and gets `delta(since=cursor)`, so per-record mode
  is `every=1` — where the cursor is always `version - 1` and
  `delta(since=version - 1)` falls out of the general rule instead of sitting
  beside it. A delta is computed **once per distinct `since`** and shared, because
  a `Delta` is a frozen value.
- **Retention is the longest window any covering subscriber asked for, and no
  more** (`SPEC.md` §6.4): `builder.retain(max(every))`, per trace, applied after
  the fan-out and only when the window changes. A builder **nobody** subscribed
  to is left at the library's own default rather than narrowed to 0, because
  `Routed.builder` is public and a caller may be folding its own deltas off it.
  This adds no unbounded growth and **bounds one that was already there**: a
  `Builder` retains `"all"` by default, so every router since R2 has held one
  journal entry per absorbed record.
- `consumer_error`: a callback that raises is isolated — recorded with the trace
  id and the version, counted, **the remaining subscribers still called**, and the
  record still absorbed. Isolation is not suppression. Only `Exception` is caught:
  a `KeyboardInterrupt` is not a consumer's failure to isolate.
- `delta_unavailable`: `delta(since=...)` refused because retention no longer
  holds that version — unreachable for a builder whose retention the router sets,
  and reachable by a caller narrowing a `Routed.builder`'s own, which is legal.
  The event carries the library's own code; nothing approximate is handed over.
- `delta_unsent`: a trace completed while a subscriber's cursor was behind its
  final version, so there is a window it could have asked for and now never can.
  One event per such subscriber on the `Completed` — a report and **not** a
  delivery, because flushing a final partial window would be a policy the caller
  never asked for. Completion therefore has a fifth, conditional step
  (`SPEC.md` §5.4).
- `Event.version: int | None` — one more optional field on the router's `Event`,
  for `seconds`' reason (`SPEC.md` §4.1): §6's three codes are each about a
  version, and §1.5 is only true where the caller can match on the number.

Tested

- **Folding every delta a subscriber received onto its first graph gives the
  final `graph()`, byte for byte**, at `every=1` and at `every=2`. That is
  `spanweave` §10.6's promise read through the receiver — asserted per
  *subscriber*, over the deltas a fan-out actually chose to send. No delta is
  skipped by the claim: the first one is `since=0` with no graph beneath it (an
  empty builder refuses), so the test asserts that what it adds **is** the whole
  of the graph it produced.
- **A raising subscriber never stalls another**: three subscribers, the middle
  one raising, both others called with the same update, the record absorbed, and
  the failure an event with its trace id and version. The mutation — a fan-out
  that skips the subscriber after the raising one — fails it.
- A refused record and a record refused at the cap fan nothing out; a subscriber
  that raised is not re-sent to (its cursor advanced like everybody else's,
  because a retry queue is a policy nobody asked for); the fan-out order is
  **registration order**, which is the order the caller controls and the only one
  stable across processes.

### R3 — completion is a policy, with the caller's clock (2026-10-05)

The third piece (`SPEC.md` §5, new). Nothing in a live stream says a trace is
over, so the receiver does not claim to know: completion is **when the caller's
policy says to stop holding a builder**, evaluated against a clock the caller
supplied. It enforces nothing, holds nothing and refuses nothing — a record for a
trace already completed is absorbed, into a new builder, and reported.

Added

- `spanweave_live.completion`, the lower of the two layers: values and pure
  functions only, importing nothing from `routing.py`.
- Three policies, each a **value**, composable as **any-of** in the caller's
  order: `Quiet(seconds)`, `RootEnded(grace_seconds)`, `Cap(records)`. Every
  boundary is **inclusive** and tested from both sides — the tick before must not
  fire and the tick at it must — because "fires at the right time" is the whole of
  what a timeout policy is. `Quiet(0)` and `Cap(1)` are legal: the number is the
  caller's and the receiver holds no opinion about it (`SPEC.md` §1.2).
- `Completion(*, policies, now, out_dir)` — keyword-only, and **`now` has no
  default**. That is the batch's one design decision worth stating twice: a
  module holding `time.monotonic` as a default would have earned the first entry
  in `tests/gates.py`'s seam allowlist, and requiring the argument instead keeps
  **the allowlist empty** after the batch R0 predicted would grow it. No module
  under `spanweave_live/` imports `time`. R7's CLI binds the real clock.
- `Router(completion=...)` and `Router.tick() -> tuple[Completed, ...]`: one
  clock reading per tick, traces evaluated in `trace_ids` order, and the traces
  this tick completed returned. A router with no completion policy reads no clock
  and completes nothing, which is exactly what R2 was — gate A is untouched.
- Completing a trace is four reported steps: `completed` (naming the policy, with
  the trace's open lifetime), materialize, `written` / `not_written`, `released`.
  The builder is **dropped**, which is the point (`SPEC.md` §2.3), and that frees
  a slot at `max_traces`. The no-trace builder is never completed: it is not a
  trace.
- `late_arrival`: a record for a completed trace opens a **new builder**, is
  absorbed into it, and reports the **gap** on the receiver's clock. The graph
  already written is never rewritten or appended to — generation 1 is
  `<trace_id>.json` and generation *n* is `<trace_id>.<n>.json`, beside it, because
  editing a report the receiver already made would make its output depend on what
  arrived after it made it.
- `Event.seconds: float | None` — one optional field on the router's `Event`
  (`SPEC.md` §4.1), for the durations §5's codes are about. A number a caller can
  only read out of a sentence is a number it cannot match on, and §1.5 is only
  true if it can. `FramingEvent` stays separate for R2b's reason: merging *that*
  one would be four fields that are `None` wherever they are not the emitter's.
- `RootEnded` decides "root" and "ended" from **structure the graph already
  states**, through `spanweave`'s public surface and never a dialect: a root is a
  node with no incoming `parent` edge **and no `orphan_parent` diagnostic naming
  it** (both halves `spanweave` §4.0), and ended is `ended_at is not None`. The
  orphan half is what makes it usable live, where a trace's root arriving after
  its children is ordinary: an orphan has no `parent` edge either, and reading one
  as a root would complete traces whose real root is still in flight. **At least
  one root and every root ended** — the conservative reading, because with "any"
  one finished sibling would complete a trace whose other top-level operation was
  still running.
- A trace id is **untrusted input**, so no file is named from one that is not a
  single path component (empty, `.`, `..`, or carrying a separator or a NUL):
  `not_written` with the reason, and nothing written outside the directory the
  caller named. A failed write is an event too, not a traceback that would lose
  every other trace the receiver was holding.
- `tests/test_completion.py`: 45 tests, all on a **fake clock the test owns**.
  340 → 385 tests.

Known cost, stated rather than hidden

- The router remembers, per trace id it has ever completed, four numbers and a
  flag — what the `late_arrival` gap and a second generation's file name need. It
  is not a builder and not a graph, but it **is** unbounded in the number of
  distinct trace ids a stream completes, and `max_traces` does not bound it
  (`SPEC.md` §5.5). The fix is a policy for *forgetting* a completed trace, which
  is a number somebody has to choose, so this batch names it rather than invents
  it — as R1 did with the framer's cap before it was decided.

### R2b — the framer's remainder has a caller-set cap (2026-10-05)

R1 left the remainder uncapped and said so in `SPEC.md` §3.4, as a gap named
rather than a policy invented: which bytes to refuse is a decision, and a batch
does not make one. The decision is made (`WORKPLAN.md` §3, *framer cap*,
2026-10-05) and this batch implements it and nothing else.

Added

- `Framer(max_pending_bytes=None)` — a cap on the remainder, **keyword-only**,
  and `None` by **default**, which is unbounded exactly as R1 shipped. The
  default is the receiver's whole position: how many bytes of an unterminated
  line are too many is the caller's policy, and a number chosen here would be
  the receiver carrying one of its own (`SPEC.md` §1.2). Readable back as
  `Framer.max_pending_bytes`.
- When a push leaves more than the cap in the remainder, the remainder is handed
  to `read_records` as one line — alongside whatever complete lines that push
  also completed — so it comes back as a `malformed_record` carrying its text,
  counted in `skipped_records`, and **never dropped** (`SPEC.md` §1.5). The
  framer is then holding nothing, so the next chunk reads as an ordinary chunk:
  a cap that wedged the stream it capped would be worse than no cap.
- `FRAGMENT_TOO_LONG` (`"fragment_too_long"`) and `FramingEvent(code, line,
  length, detail)`, exported from `spanweave_live`: the event the framer emits
  when the cap is reached, carrying the **length** of the fragment. Read back as
  `Framer.events` (the most recent call's, reset by every call, never a log) and
  `Framer.counts` (per code, for the life of the framer — bounded by the number
  of codes, which is §4.6's choice for the router). A type of its own rather
  than the router's `Event`: a framer has no record index, no trace id and no
  library refusal code, and the router has no field for a length.
- `SPEC.md` §3.4 **rewritten** from "no cap, and that is a gap stated rather
  than a decision made" to the policy: the cap is the most the framer will keep,
  the boundary is strict (`>`, so a remainder exactly at the cap is one the
  caller allowed, and `0` is legal), neither `document` nor `flush` is capped,
  and the cost is named — once a line is cut into fragments each fragment is
  numbered as a line of its own, so line numbers downstream of a
  `fragment_too_long` are the framer's count of what it handed over rather than
  the input's count of its own lines. §3.1's surface block now declares the
  constructor, `events` and `counts`, and says why the events sit beside the
  return value instead of in it (a wrapper would be the second name for records,
  diagnostics and skips that §3.1 refuses).
- `tests/test_framing.py`: six new tests plus one new sweep. The cap tests assert
  the strict boundary at the byte, one `malformed_record` with
  `skipped_records == 1` and one `fragment_too_long` carrying the length, that
  the framer **continues on the next chunk**, that a chunk hands over its
  complete lines *before* its over-cap tail (one push, two reads, one result),
  that `document` and `flush` are uncapped, and — the assertion the design exists
  to make true — that concatenating the text of every `malformed_record` from a
  stream that never sends a `\n` **reproduces the input byte for byte**. The new
  sweep re-runs all 51 renderings × 2 forms × 12 framings = **1224** framings
  against `Framer(max_pending_bytes=None)` and requires R1's behaviour unchanged
  *and* that no event is emitted and no count kept anywhere in it, so a cap that
  fired on a `>=`, or that replaced `None` with a number of its own, fails over
  the whole corpus rather than in a sample of it. 340 tests.

### R2a — the run-1 review's findings, closed (2026-10-05)

A fix batch: no new piece, no new behaviour the receiver did not already have.
It makes the documents true where they were not, and makes five tests able to
fail where they were passing over empty sequences. Every item is from
`patches/REVIEW-2026-10-04.md`, which is the cold review of run 1.

Added

- `SPEC.md` §0.1 — **the pin is one pin, and both halves of it are HTTPS**: the
  sha-pinned dependency, the `corpus/` submodule at the same sha, `uv.lock` as
  the third copy, and why SSH breaks CI's own submodule checkout rather than a
  pin. `tests/test_pins.py` now holds the submodule half too, reading
  `.gitmodules` and requiring `https://` — until now a re-added SSH submodule
  passed `make check` and failed only at CI checkout (R0-3 / P-5).
- `SPEC.md` §0.2 — **the one mypy override, and why it is temporary**:
  `follow_untyped_imports` for `spanweave.*` exists because the pinned
  `spanweave` ships no `py.typed`, and `ignore_missing_imports` was rejected
  because it would make `Records`, `Diagnostic` and `read_records` all `Any` and
  every annotation here vacuous. The marker is upstream in `SigorMatt/spanweave`
  **PR #4** ("packaging: the package ships py.typed", commit `bea9d44`), open
  and green and **not yet merged**; when it merges the pins move and this
  override is deleted (`WORKPLAN.md` R2c). Stated in the spec and here because
  it lived in a `pyproject.toml` comment and in the plan's resume note, and the
  plan is deleted at series close (P-1). *(PR #4 has since merged and R2c
  deleted the override; this entry is left as it read, and §0.2 now describes
  the typed dependency.)*
- `SPEC.md` §3.3 states the `push`-vs-`document` **trap** in full: a body that
  happens to arrive whole reads *identically* to `document(body)`, which is
  exactly why the same body arriving in chunks being lost to one
  `malformed_record` per line is a trap and not a rule. The whole-arrival half
  was in a test docstring only (P-4), and is now asserted as well.
- `tests/test_framing.py` sweeps every line rendering in **two forms**: as
  captured, and with one line corrupted — the corrupted form **derived from the
  corpus bytes at test time**, never a copied fixture, so it cannot read clean
  the day the corpus moves. The sweep's `diagnostics` and `skipped_records`
  assertions compared two empty sequences before this, because not one of the 51
  renderings produces a diagnostic at the pinned sha: a `push` that swallowed
  every diagnostic passed it 51/51, and one that reported `skipped_records=0`
  unconditionally passed the entire suite (R1-1, R1-2). 51 renderings × 2 forms
  × 12 framings = **1224**, and one further test asserts `push`'s
  `skipped_records == 1` directly.
- `tests/test_framing.py` holds §3.2's "the receiver grows no dedup cache of its
  own" as a two-part test — the same line twice in one push is one record plus
  `duplicate_record`; the same line across two pushes is two records and no
  diagnostic. A `self._seen` set inside `Framer` passed the whole suite and made
  the `duplicate_record` disappear (R1-4).
- `tests/test_gates.py` holds the import gate **to walking the tree**: the gate's
  file set is compared against an `rglob` computed independently in the test, and
  a planted three-level module importing `time` is caught with no edit to the
  gate. `package_files()` mutated to a two-name list, plus a
  `spanweave_live/completion.py` importing `time`, left `make check` green
  before this (R0-2).
- `tests/test_routing.py` holds the `Router` surface to what `SPEC.md` §4.1
  declares (R2-1).

Changed

- `Router`'s three settings are **keyword-only** (`kw_only=True`), as §4.1's
  signature always said; `Router(1, 'openinference', False)` used to construct.
  §4.1 now also declares `routed`, which was public and in the prose only.
- `SPEC.md` §4.2 carries the **measurement** instead of the premise R2
  falsified: the second parse is 15.5–17.1 % of `trace_id_of + feed`, not the
  "would halve it" this section claimed, so an upstream `trace_id_of` is an
  optimisation and not a necessity. The number is in the spec rather than only
  in the plan, and `spanweave_live/routing.py`'s citation points at §4.2 instead
  of at a plan section that is deleted at series close (P-2).
- `tests/test_framing.py`'s diagnostic-order fixture crosses the **9 → 10**
  digit boundary (eight good lines, not nine), where the sorted order is the
  reverse of the arrival order. Below ten it passed with the re-sort removed
  (R1-3); §3.5 says why the boundary is the point.

Not changed, and why

- **R0-1** — `WORKPLAN.md` §4's false "`make check` runs `install-check` as a
  step" was already corrected by the plan commit `9a2e40f`, which this batch
  cannot edit (the plan is the orchestrator's file). Nothing was left to do.

### R2 — partition: one `Builder` per trace, and conformance gate A (2026-10-04)

Added

- `spanweave_live/routing.py`: `Router`, the second piece of the receiver
  (`SPEC.md` §4). `route(record) -> Routed` finds the record's trace id through
  `spanweave.adapters.classify` and the claiming adapter's `parse` — and through
  nothing else — then hands the record to that trace's `spanweave.Builder`,
  created on first sight. `Event`, `Routed`, `trace_id_of`, and the codes
  `refused` and `refused_at_cap`, all exported from `spanweave_live`.
- A record with no trace id — nobody claimed it, more than one adapter claimed
  it, or the claimant reported no single id — goes to the **no-trace builder**,
  which is a `Builder` and therefore carries `spanweave`'s own
  `missing_trace_id` and `unclaimed_record`. The receiver invents no code for
  either, and does not paper over `spanweave` refusing `graph()` for a builder
  holding only unclaimed records.
- A `Builder` refusal (a span re-sent under at-least-once export) is an `Event`
  with code `refused` carrying the record's arrival index and the library's own
  `code`, counted, and routing continues. `max_traces` is a cap: a new trace at
  the cap is `refused_at_cap`, counted, with no builder made — refused in the
  open rather than dropped. The router keeps **counts**, not an event log, so
  nothing it holds grows with the stream.
- `SPEC.md` §4: the surface, why the trace id may only come from the adapter
  surface and what the second parse costs, one builder per trace and the
  no-trace builder, refusals, the cap, counts-not-a-log, and §4.7 on gate A.
- `tests/test_conformance.py` — **gate A**: all 1354 pairs of renderings from
  two of the corpus' 29 scenarios (53 renderings, two of them whole OTLP
  documents), one side relabelled onto a second trace id, interleaved by a
  seeded shuffle that preserves each rendering's own order, framed in seeded
  chunks through one `Framer`, routed through one `Router` — and each trace's
  `graph()` compared byte for byte against `spanweave.dumps` of
  `spanweave.build` of its own rendering. Ten written-down seeds; 27 080 graph
  comparisons; about 25 s.
- `tests/test_routing.py`: 20 tests, including the one that tells a dialect read
  apart from the adapter surface — a record **no adapter claims** that
  nonetheless carries a `trace_id` key.

Changed

- `make conformance` runs gate A instead of printing "NO GATE YET". A green
  `conformance` job now means something.

Fixed (in the plan's premises, not in code)

- `WORKPLAN.md` R2 expected `otlp_container` to catch a router keyed by
  `record["trace_id"]`. It does not: `spanweave.read_records` normalizes a
  container's `traceId` to `trace_id` while unpacking it, so by the time a
  router sees a record **every** corpus rendering answers a dialect read with
  exactly what the adapter surface would have said. Gate A cannot catch that
  mutation; `SPEC.md` §4.7 says so, and `tests/test_routing.py` catches it with
  a hand-authored unclaimed record instead.

### R1 — framing: bytes in, complete records out (2026-10-04)

Added

- `spanweave_live/framing.py`: `Framer`, the first piece of the receiver
  (`SPEC.md` §3). `push(chunk)` splits on `\n`, keeps the remainder and hands
  **complete lines only** to `spanweave.read_records`; `document(body)` hands a
  whole OTLP-JSON body over unsplit; `flush()` reads the remainder as the
  stream's final line and reports what it was; `pending_bytes` is the
  remainder's length. Exported from `spanweave_live`.
- Diagnostics from a push are re-issued with the **absolute line offset added**,
  so a diagnostic's line number is the line's position in the whole stream
  rather than in the chunk. The chunk-local number is replaced rather than kept
  beside it, a diagnostic that names no line is untouched, and the tuple is
  re-sorted into the library's own order because renumbering changes the message.
- `SPEC.md` §3: the surface, `push` and the two consequences of the remainder (a
  multi-byte character and a BOM split across chunks are never handed over in
  halves), why `document` is a method and not a flag, `flush` and the remainder
  as a reported outcome, and the absolute-line-number rule. §3.4 states that
  there is **no cap** on the remainder and that this is a gap named rather than
  a policy invented.
- `tests/test_framing.py`: 68 tests. The central one sweeps all 51
  line-delimited renderings of the pinned corpus, framing each one twelve ways
  — ten written-down seeds plus one byte at a time and the whole input in one
  chunk — and asserts the records, the diagnostics and `skipped_records` equal
  `read_records` of the whole input exactly. Also: every two-way split of a
  hand-authored stream carrying 2-, 3- and 4-byte UTF-8 sequences yields no
  `undecodable_bytes` (the corpus is pure ASCII at the pinned sha, so this one
  fixture is hand-authored and a test asserts it has not quietly become ASCII);
  a truncated final line is `pending_bytes > 0` and not a `malformed_record`
  until `flush`; a malformed line is numbered by its position in the stream
  under every seeded chunking; and both OTLP-container renderings read through
  `document` exactly as `read_records` reads them, while the same bytes pushed in
  chunks are lost to `malformed_record`s — which is why `document` exists.
- `pyproject.toml` gained one mypy override — `follow_untyped_imports = true`
  for `module = ["spanweave.*"]` — because the pinned `spanweave` ships no
  `py.typed` and `mypy --strict` therefore refuses to analyse it as soon as a
  receiver module imports it. Named here retroactively by R2a, which states the
  override and its upstream fix in `SPEC.md` §0.2: this entry said nothing about
  `pyproject.toml` changing at all. *(Deleted again by R2c, which moved the
  pin to a `spanweave` that ships the marker.)*

### R0 — repository skeleton (2026-10-04)

Added

- `SPEC.md`: §0 what the receiver is, §1 the four permanent non-goals (no
  dialect, no rules or semantics, no enforcement, no clock of its own, and
  nothing dropped silently), §2 the three properties of `spanweave.read_records`
  the receiver is designed around, quoted from `spanweave` `SPEC.md` §7 — the
  reader does not buffer across calls, deduplication is per call, and reading is
  cheap while absorbing is not. §3 onward are reserved for the batches that build
  them.
- `CLAUDE.md`: the operating contract — the standing rules, the architecture, the
  commands, the definition of done, and the halt points.
- `CONTRIBUTING.md`: the batch bar, with the reason for each line.
- `pyproject.toml`: package `spanweave_live`, console script `spanweave-live`,
  Python 3.11–3.14, and `spanweave` pinned at
  `e42f257b91be1bd9c7be6bcdbd31313947401288` over HTTPS so an unauthenticated
  clone resolves it. `uv.lock` committed.
- `corpus/`: the `spanweave` repository as a submodule at that same sha,
  read-only, used only to build `fixtures/conformance/`.
- `tests/test_pins.py`: the dependency sha, the submodule sha and `uv.lock` are
  held equal, and the pin is required to be a full 40-character sha.
- `tests/gates.py` + `tests/test_gates.py`: the one invariant gate — no module
  under `spanweave_live/` imports `time`, `datetime`, `random`, `socket`,
  `threading` or `asyncio` outside a file named in the `SEAMS` allowlist, which is
  empty at R0. Watched failing against thirteen planted violations, in both import
  forms, and watched *not* firing on prose and identifiers that merely look alike.
- `Makefile`: `check` (ruff, `ruff format --check`, `mypy --strict`, pytest,
  gates, and the console script), `gates`, `conformance`, `install-check`, `clean`.
  `make conformance` asserts nothing until gate A arrives in R2 and says so in its
  output rather than printing a reassuring pass.
- `tests/install_check.py`: builds the sdist and wheel, audits the wheel for
  leaked `corpus/`, `tests/` or `WORKPLAN.md`, installs the wheel into a throwaway
  venv and runs it from a working directory outside the repo — asserting that it
  is outside, rather than assuming it.
- `.github/workflows/ci.yml`: `make check` + `make install-check` on 3.11–3.14,
  and `make conformance` on ubuntu and macos, with `submodules: true`.
- `spanweave_live/`: the importable package — `__version__` and a `--version`
  CLI. No behaviour; R7 builds the real commands.
- `README.md`, `LICENSE` (MIT), `.gitignore`.
