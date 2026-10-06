# Changelog

All notable changes to this project. **Nothing here is frozen**: the version is
`0.0.x`, and until that changes any entry below may be undone by the next one.

The format is loosely [Keep a Changelog](https://keepachangelog.com/); the unit
of change is a **batch** (`WORKPLAN.md`), and each entry names the batch.

## Unreleased

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
  `stdin(stream=None, …)`. `tail` returns a `Tail`, which **is** the iterator of
  `spanweave.Records`; `stdin` is a generator. The asymmetry is the framer's own
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
