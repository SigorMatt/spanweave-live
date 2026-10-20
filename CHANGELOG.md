# Changelog

All notable changes to this project. **Nothing here is frozen**: the version is
`0.0.x`, and until that changes any entry below may be undone by the next one.

The format is loosely [Keep a Changelog](https://keepachangelog.com/); the unit
of change is a **batch**, each entry names the batch, and `TASKS.md` is the
registry that lists them one line apiece. A batch entry may cite its series'
`WORKPLAN.md`, which was deleted at that series' close; each such citation is
dated history, resolvable at `git show 3077bec:WORKPLAN.md` for the zoo
series' entries (V0–V4) and at `git show b500342:WORKPLAN.md` for the receiver
series' (R0–R9).

## Unreleased

## 0.0.2 — the zoo series (2026-10-19)

The version moved from `0.0.1` at the series' close (V4): nothing is frozen,
and the event-code set grew (`no_trace`, V2; `no_graph`, after the close). Under
this heading are the zoo series' batches V0–V4 and, above them, the commits made
after its close, newest first.

### An unpacked record two adapters claim is refused, and the envelope is not asked (2026-10-20)

Derived parent `d52669c`. The third commit after the series' close, answering
R-2 of the first half of its cold review (run 1, archived under `reviews/` by
a later commit of these). A pin, not a fix: **no behaviour changed**. Only
`tests/test_routing.py` and this file moved, and `SPEC.md` is untouched,
because §4.2 already says what the test holds (a record more than one adapter
claims goes to the no-trace builder and stays `refused` and nothing else), and
no sentence anywhere says the case is untested. Until now it was, for an
unpacked record: the suite's only ambiguous record was flat, and the review's
mutation xi, the envelope asked for an unpacked record more than one adapter
claims, passed every test and completed a phantom trace.

Added

- **One test**, `test_an_unpacked_record_two_adapters_claim_is_refused_and_its_envelope_not_asked`,
  in `tests/test_routing.py` beside the flat ambiguous test it is the twin of,
  built from the file's hand-made export helpers: one OTLP/JSON span carrying
  `openinference.span.kind` and two `gen_ai.*` attributes, through
  `Framer().document`. It asserts its premises first: the record is
  `spanweave.read.Unpacked`, `classify` gives two adapters, and the envelope
  states the export's trace id. Then, under a default `Router()`: `trace_id`
  `None`, the record at the no-trace builder and absorbed by nothing (version
  `0`), one `refused` event with no trace id and `adapter_ambiguous`, no
  builder for the export's trace, `trace_ids ()`, `counts {'refused': 1}`; and
  `spanweave.build` of the same export refuses with the same code.

Green on the parent (`d52669c`, worktree under the scratchpad), with the test
file overlaid: the whole suite gives 0 failed, 910 passed. It is green there
because nothing moved, as V3's pins and V1a's guards were: the code was right,
and the test holds it. The mutation is what shows it can fail. Mutations, each
of `_identify` in `spanweave_live/routing.py`, run against the whole suite (910
tests):
- xi, the envelope asked when more than one adapter claims an `Unpacked`
  record: 1 failed, 909 passed (the new test, at `trace_id` `None`: the record
  was routed to the export's trace). Against the parent's own 909 tests, without
  the new one, xi passes all 909;
- the envelope branch's guard widened from no claimant to not exactly one
  (`len(claimants) != 1`): 4 failed, 906 passed (the new test and three flat
  ambiguous tests, the flat record now announced as `unclaimed`);
- the ambiguity branch removed, so the first claimant's `parse` routes: 4
  failed, 906 passed (the new test and three flat ambiguous tests);
- the ambiguous record announced as `no_trace` (`unclaimed`) before its
  refusal: 4 failed, 906 passed (the same four as the widened guard).

### A trace no adapter can read is announced as no_graph, and stays off the cap until it holds a claimed record (2026-10-20)

Derived parent `1df7a35`. The second commit after the series' close, and the
one behaviour change among them, answering R-1 of the first half of its cold
review (run 1, archived under `reviews/` by a later commit of these). Since V2
an export no adapter claims, a plain HTTP health check, is an identified trace
whose graph the library refuses (`adapter_unconfident`), as a batch build of
the same records refuses. Live still equalled batch; what followed had been
chosen by nobody: exit 3 for ordinary traffic, and a cap slot only end of input
released. This decides it.

Changed

- **The event.** At completion, a refusal of `graph()` whose code is
  `adapter_unconfident` is one counted **`no_graph`** event carrying that code,
  made at materialization whether or not a directory was named, and no
  `not_written` follows it. It is a fact about the input, as `no_trace` is, so
  §8.6's exit 3 does not count it: the CLI exits `0` on such a trace, and
  `finished` counts it. A refusal with any other code is still `not_written`
  and exit 3. New public name: `NO_GRAPH`.
- **The cap.** A trace counts against `max_traces` from the first claimed record
  it absorbs, and not before: a record no adapter claims is never refused at the
  cap, whichever trace it names, and the builder of a trace holding only such
  records takes no slot. At the cap, the claimed record that would make such a
  trace count is `refused_at_cap`, as a new trace's first record is; the trace
  keeps its builder and its records. The cost is stated in §4.5: `max_traces`
  does not bound those builders, and completion is what releases them.
- **`RootEnded`.** A trace with no graph has no root the receiver can see, so
  `RootEnded` alone never completes it; `Quiet`, `Cap` and end of input do, as
  `no_graph`. §5.3 says so beside the rootless trap, and README's third trap
  gains it. No code moved for this: the tick already read a refused graph as "no
  root seen yet".
- **The record.** The "unreachable" sentences go: §5.4's step 2, `routing.py`'s
  `_write` and `_root_ended`, and a fourth the decision did not count, §5.7's
  parenthetical, which cited step 2's. `SPEC.md` §4.5, §5.1 (the code list),
  §5.3, §5.4, §5.5 (the one case that does not re-open), §5.7, §8.3 and §8.6
  amended; §5.4's step 3 said "refused in step 1" of step 2, and says step 2.
  README's exit-code line, its `Router` row and the comment on its end-of-input
  `Cap(0)`, which said a replay always leaves files behind, say what is true.

Added

- **One hand-made export no adapter can read**, `unread_export()` in
  `tests/test_routing.py` beside the other hand-made exports: two spans, root
  and child, both ended, no attribute any adapter reads, one valid trace id.
  Fourteen test items are new, the guards below among them. The routing tests
  hold the cap: the
  unread trace is held and not counted, its records are never refused at a full
  cap, and the claimed record that would make it count is `refused_at_cap`.
  Under `Quiet(0.5)` and `Cap(2)`, each with and without a directory, the
  completion's events are `completed`, `no_graph` (`adapter_unconfident`),
  `released`. Under `RootEnded(0.0)` alone nothing completes it up to
  `now = 10^6`; the end-of-input `Cap(0)` does, as `no_graph`.
  `Router(max_traces=1, completion=RootEnded(0.0))` fed the export and then
  `zoo/z1/2026-10-13-recorded` completes z1 with none of its 31 records
  `refused_at_cap` (31 re-derived from the zoo README). The CLI test runs
  `tail --once --root-grace 0` on the export and requires exit `0`, `no_graph`
  on stderr and in `finished`, no `not_written`, and no file.
- **Three guards**, green on the parent: a trace holding one claimed record (Z4's
  shape, an unclaimed root and a claimed child) still counts at the cap from that
  record; uncapped, an unread trace a claimed record joins is one trace whose
  graph is the batch graph; and a refusal of `graph()` with any other code is
  still `not_written`, with a stub `Builder` whose `graph()` refuses with
  another code.

Red on the parent (`1df7a35`, worktree under the scratchpad), with the three
test files overlaid: the whole suite gives 11 failed, 898 passed. The failures
are the three routing cap tests (the export refused at the cap, or holding the
slot), the constant, the four completion parametrizations (`not_written` or
nothing where `no_graph` is required), the `RootEnded` test (its end-of-input
completion has no `no_graph`), the z1 test (`refused_at_cap` on z1's records),
and the CLI test (exit 3). The three guards passed there.
Mutations, each run against the whole suite (909 tests):
- `no_graph` counted toward exit 3: 1 failed, 908 passed (the CLI test);
- an unclaimed-only trace counted against the cap: 3 failed, 906 passed (two
  routing cap tests and the z1 test);
- the claimed record that joins an unclaimed-only trace at the cap admitted:
  1 failed, 908 passed (the routing test of that record);
- `no_graph` said only where a directory was named: 3 failed, 906 passed (the
  two parametrizations with no directory, and the `RootEnded` test);
- a released trace not dropped from the counted set: 1 failed, 908 passed (R3's
  `test_completing_frees_a_slot_at_the_cap`, which already held the slot);
- every refusal of `graph()` reported as `no_graph`: 1 failed, 908 passed (the
  guard with the stub `Builder`).

### The record test gives the review's fixes a place, and says what holds the registry (2026-10-20)

Derived parent `e883fa3`. The first commit after the series' close, answering
two findings of the second half of its cold review (run 2 and the close,
archived under `reviews/` by a later commit of these): R-17 and R-6. No
behaviour changed: only `tests/test_record.py` and this file moved, and
`SPEC.md` is untouched, because it states no rule about this file's headings.

Changed

- **`tests/test_record.py` gives the commits after the close a place** (R-17).
  The newest version's entries had to be the registry's batches and nothing
  else, so this entry, and each later fix for the review's findings, had no truthful
  place: under `## Unreleased` it would say it is not in `0.0.2`, which it
  ships in. The test now accepts, above the batches and only there, entries
  whose heading names no batch, each ending in its date, the dates newest
  first down to the close's (V4's). That is how `## 0.0.1` carries the receiver
  series' follow-ups above R9. An entry of that kind below the batches is
  still red. This file's sentence under `## 0.0.2` says the same.
- **The commit check's docstring says what holds the registry** (R-6). It said
  the body match tells `V1` from `V1a`'s body; it does not: `\bV1\b` matches
  `a856ec2`'s body ("V1's §4 thread", "(V1 served"), and V0's `024fc66` names
  V1 ("(V1-V3)"), V2 and V3. What holds the registry is that match **and** the
  shas' uniqueness, the check's last assert, and the docstring now says so.

Red on the parent (`e883fa3`, worktree under the scratchpad), with this
file overlaid: `tests/test_record.py` gives 1 failed, 9 passed. The failure is
the entries test refusing this entry ("an entry names no batch"). The new
test file there is 10 passed, both with this file and with the parent's.
Mutations, each run against the whole suite (895 tests):
- this entry moved below V0: 1 failed, 894 passed (the entries test);
- this entry moved between V4 and V3: 1 failed, 894 passed (the same);
- V1 registered as V0's `024fc66` (the review's X1): 1 failed, 894 passed,
  on the uniqueness assert alone; with that assert removed, 895 passed;
- this entry dated 2026-10-18, before the close: 1 failed, 894 passed; with
  the newest-first assert removed, 895 passed;
- the entries test setting aside the headings that name no batch wherever
  they stand, rather than only above the batches: with it, this entry below
  V0, and between V4 and V3, are each 895 passed;
- this entry's date dropped: 1 failed, 894 passed.

### V4 — the zoo series closes, and its plan is deleted (2026-10-19)

Derived parent `3077bec`. The zoo series' last batch (V4). No behaviour
changed but the version `--version` prints: nothing under `spanweave_live/`
moved but `__version__` and one comment.
This is the close. The series' plan is deleted, and what outlives it is folded
into tracked files.

Added

- **`TASKS.md` registers the zoo series**, above the receiver series. It has
  the six batches with the commit that closed each, the plan's decisions log
  (§3) and resume note (§4) folded in, L1–L4 dispositioned, and V2's four
  threads. L1's reader half is spanweave's W1 `4ecf414`. It also has the order
  of what remains before the merge (the plan's §2), and the origins (§5).
  Where a number lives in `SPEC.md` or `README.md` and a test re-derives it
  there, the registry points at it rather than copying it. One sentence of the
  2026-10-19 V2 decision row moved, as V4's row directs (thread V2(c)): the
  event carries the library's code; which field failed is the library's
  sentence, which the receiver does not carry.
- **`tests/test_record.py`** holds that record to what it says. The version
  must be one number in `pyproject.toml`, the package, `uv.lock` and this
  file's newest versioned heading. The heading's entries must be the
  registry's batches, newest first. The registry must list V0–V4 in the order
  they ran, each sha a non-`plan:` ancestor of the tip whose body names its
  batch. The decisions log must be as long as it says, and L1's W1 sha must be
  the one spanweave's own registry gives at the pin. Every
  `git show <sha>:WORKPLAN.md` citation must resolve. `CLAUDE.md` must say a
  series is open exactly while a plan exists, and rule 1 must name every
  source of a trace id `SPEC.md` §1.1 names. CI's `check` job must keep the
  history the file reads.

Changed

- **The version is `0.0.2`** (`pyproject.toml`, `spanweave_live.__version__`,
  `uv.lock`). Nothing is frozen, and the event-code set grew. This file now
  groups its entries under `0.0.2` and `0.0.1`. V0's entry had lost its
  `### V0 — ` heading prefix, and the new test found it.
- **`CLAUDE.md`** says no series is open and where the zoo series' plan is.
  Standing rule 1 names spanweave's public `envelope()` as a source of trace
  ids, in the plan's §0.6 words (thread V2(d)).
- **Thread V2(a), the sentences.** Each sentence this series wrote saying that
  a record reaching the no-trace builder is announced now names the one
  exception: a router given `adapter=` absorbs a record two adapters claim
  with no event. These are `SPEC.md` §4.2's sentence on an ambiguous record,
  the `NO_TRACE` comment in `spanweave_live/routing.py`, a section comment in
  `tests/test_routing.py` and README's `Router` row. §4.3 already named it,
  and now says where it is registered. The V2 entry below names it in its own
  bullet and is left as it stands.
- `CONTRIBUTING.md`'s sentence about the deleted plan covers every series, and
  `tests/test_pins.py`'s citation of the plan's §3 points at `TASKS.md`. This
  file's preamble says where each series' `WORKPLAN.md` citations resolve.
  `SPEC.md` §0 names the zoo series beside R1–R8.
- CI's `check` job checks out with `fetch-depth: 0`, because the new test reads
  history. No job is added or renamed, so the ruleset's required checks are
  the same names.

Removed

- **`WORKPLAN.md`**, as its §0.6 said from the series' first commit. It is
  at `git show 3077bec:WORKPLAN.md`. No `plan:` commit follows this one.

Not here: `reviews/` is unchanged. No review of this series had been archived
when this commit was made. The cold review runs after it, in two halves
(`TASKS.md`, *What remains before the merge*).

Tests red on the parent (`3077bec`, worktree under the scratchpad): 8 of the
new file's 10. The two green there are guards: the plan citations resolve, and
`CLAUDE.md` said a series was open while its plan existed. Mutations shown
caught, each red on exactly one test:
- `spanweave_live.__version__` left at `0.0.1`: red (the version);
- V2 registered as its `plan:` commit `b01c945`: red (the commits);
- V0's heading prefix lost again: red (the changelog's entries);
- the decisions log said to be seven rows: red (its length);
- `CLAUDE.md` still saying the series is open: red (the open-series test);
- rule 1 without the envelope clause: red (rule 1);
- W1 cited as its decision commit `898e9f5`: red (L1's W1);
- run 2 written V3 → V1a → V4: red (the order);
- `fetch-depth: 0` dropped from CI: red (the history).

### V3 — what a generation is, and what the policies do at values the audit never ran (2026-10-19)

Derived parent `5369cac`. The zoo series' fifth batch (`WORKPLAN.md` V3), the
zoo's `PROBES.md` L3 and L4, and the maintainer's 2026-10-16 decision that
generations are not merged and early completion is not a defect. **No
behaviour changed**: no test showed a policy firing at the wrong instant.
Docs and pins.

Added

- `tests/test_zoo_policies.py` pins the three policies over the zoo's
  captures on one fake-clock schedule (body *k* fed at `now = k`, ticked at
  `k` and `k + 0.5`). On Z3, Z1, Z2 and Z6 real: `Quiet(0.5)` completes once
  per body and each generation's file is `spanweave.build` of **its own
  body** byte for byte, every one before the last carrying `orphan_parent`,
  the last holding the ended root, each after the first opened by
  `late_arrival`; `Quiet(2.0)`, `RootEnded(1.0)` and `Cap(N)` each complete
  once at the instant §5.3 states, with the end-of-input graph; `RootEnded`'s
  grace runs from the tick that first saw the root. On Z5 real and recorded,
  which has no root: `RootEnded(S)` for S in {0, 1, 3600} completes nothing up
  to `now = 10^6`; `Quiet(S)` completes once at `last + S`; `Cap(4)` at the
  fourth record; `Cap(5)` never, and end of input does. These pins are green
  on the parent; the three tests that re-derive the documents' numbers are
  red there, because the documents are what this batch adds.
- `SPEC.md` §5.3: the policies' readings on the zoo, and `RootEnded` alone
  never completing a trace whose root never ends. §5.5: what a generation
  is — the batch graph of what its builder absorbed when the policy fired,
  never merged — with the generation table the test reads. §4.8 points there.
- `README.md`: the third trap, beside the two `--help` prints.

Mutations shown caught (by the new file alone):
- `Quiet`'s `>=` as `>`: red (15);
- `Cap`'s `>=` as `>`: red (6);
- an orphan read as a root in `root_ended`: red (17);
- a late arrival that does not number its generation: red (4);
- `RootEnded`'s grace measured from the last record: red (4).

### V1a — a protobuf request is answered in its own encoding (2026-10-19)

Derived parent `fef26e0`. The zoo series' fourth batch (`WORKPLAN.md` V1a), the
thread V1 left for the close and the maintainer's 2026-10-19 decision. It
finishes the zoo's `PROBES.md` L1 for the answer: V1 read what a stock exporter
sends, and answered it in JSON, which that exporter cannot decode.

Changed

- **An accepted `application/x-protobuf` request is answered `200` with
  `Content-Type: application/x-protobuf` and an empty body.** That is the
  empty `ExportTraceServiceResponse`, which encodes as zero bytes, so no
  encoder is needed and nothing under `spanweave_live/` imports a protobuf
  runtime. It is the same message `{}` is in OTLP/JSON, so it claims nothing
  `{}` does not, and §7.2's `partialSuccess` reasoning is unchanged. The
  answer's type is the request's declared media type as §7.2 matches it,
  never a type guessed from the bytes.
- **A refusal stays `{"code": ...}` as `application/json` for either media
  type.** OTLP asks for an encoded `google.rpc.Status` there, which would need
  an encoder. §7.2 states the deviation and its reason.
- JSON requests are unchanged: `{}` as `application/json`. `README.md` names
  the request and not the answer, so it did not move. `SPEC.md` §7.2 amended:
  the sentence whose premise this corrects, the deviation, and what the
  section is tested against.

Added

- **The zero bytes are re-derived, not asserted.** A test encodes
  `ExportTraceServiceResponse()` with the `otlp` extra's runtime, which a test
  may import and the package may not, and holds the endpoint's answer to it.
  It reads the bytes back as that message with no `partial_success`, and holds
  its OTLP/JSON rendering equal to the `{}` a JSON request gets.
- A table of requests at the pure layer holds the answer's type to the
  declared one under HTTP's matching, and every refusal of a protobuf request
  to JSON. `respond` is shown writing the type and a `Content-Length` of `0`.
  The socket test over every zoo raw body now checks the type and `b""`, and
  the JSON and truncated-protobuf socket tests check theirs.

Mutations shown caught:
- the answer's type always `application/json`, as on the parent: red;
- the answer's type taken from the header verbatim (case and parameters): red;
- the answer's type guessed from the body's first byte: red;
- a non-empty protobuf success body (`{}` under the protobuf type): red;
- a refusal (`415`, or the `400` cases) answered in the request's type: red.

### V2 — every record the receiver routes reaches a trace or an event says why not (2026-10-19)

Derived parent `2ef0231`. The zoo series' third batch (`WORKPLAN.md` V2),
answering the zoo's `PROBES.md` L2. Before it, a record the receiver routed
could reach no graph and no event said where it went. This is the receiver's
half of spanweave's T1 decision.

Changed

- **An unpacked OTLP record that no adapter claims is routed by its envelope.**
  `trace_id_of` asks the claimant's `parse`, as before. When no adapter claims
  a record the reader unpacked from an export, it now asks
  `spanweave.envelope(record).trace_id`, which is the transport's id read
  through the library's public function. "Unpacked" is the reader's mark, the
  record's type `spanweave.read.Unpacked`, and never a key. A flat record's
  envelope is never asked for. A refused envelope is the answer, and nothing
  is read past it to a key.
- **Every record that reaches the no-trace builder is announced.** Each one
  gets one event, new code `no_trace`, counted, with the arrival index. Its
  `detail` is exactly `unclaimed` (a flat record no adapter claims),
  `no_envelope` (an unpacked one whose envelope the library refused, with
  `spanweave_code` `not_an_envelope`), or `no_id` (the claimant reported no
  single id). The event comes before the feed. A `refused` follows it if the
  builder will not take the record. An ambiguous record is still `refused`
  and nothing else. `finished` counts `no_trace`. The exit code ignores it,
  because it is an observation. New public names: `NO_TRACE`, `UNCLAIMED`,
  `NO_ENVELOPE`, `NO_ID`.
- **The zoo gate's Z4 rows move from 4 of 5 to 5 of 5.** Z4's unclaimed root
  now reaches its trace. The written graph is the batch graph byte for byte:
  five nodes, four `parent` edges, no `orphan_parent`. All twelve captures are
  equal, and nothing reaches the no-trace builder on any of them. §4.8's table
  marks the two rows `yes (L2)`. README says all twelve.
- `SPEC.md` §1.1, §4.1, §4.2, §4.3, §4.7, §4.8, §8.3 and §8.6 amended. §4.3
  now says in one sentence what its three said and contradicted §1.1 and
  §1.5 with.

Added

- **The measurement V2 would have stopped on.** Over every unpacked record
  that exactly one adapter claims, in the corpus and the zoo, the claimant's
  trace id and the envelope's were compared on 748 records: 8 from the
  corpus' renderings, 370 from the zoo's JSON bodies and 370 from its raw
  bodies. They are equal on 748, differ on 0, and one side states no id on 0.
  `tests/test_zoo_gate.py` derives every number, and §4.2 cites them.
- **Gate A pairs an export with an unclaimed root against every rendering.**
  No conformance scenario has such a span, and a test asserts that. So gate A
  borrows the corpus' `zoo/z4/2026-10-12-recorded`, read in place, and pairs
  it with each of the 55 renderings at each of the ten seeds.
- **An older gap, found and pinned rather than fixed.** Under a router given
  `adapter=`, a record two adapters claim reaches the no-trace builder, which
  absorbs it, and no event says so. §4.3 states this, a test pins it, and it
  is registered for the close.

Tests red on the parent (`2ef0231`, worktree under the scratchpad): 25. These
are eight routing tests (envelope routing, `unclaimed`, `no_id`,
`no_envelope` over a protobuf body with a zero trace id, a refused envelope
not read past, announced-then-refused, the cap test now expecting
`no_trace`, the constants), four zoo-gate tests on Z4 (byte for byte and
5 of 5, ×2), the README sentence, the §4.2 citation, gate A's new test at all
ten seeds, and the CLI's `no_trace` line and `finished` count. Mutations shown
caught:
- the envelope fallback applied to a flat record: red (`unclaimed` test, CLI);
- a refused envelope read past to the record's `trace_id` key: red (the
  read-past test);
- a `no_trace` event not counted: red (six tests, the CLI's `finished` among
  them);
- an ambiguous record also announced as `no_trace`: red (two tests);
- the announcement dropped: red (seven tests).

### V1 — the endpoint serves what a stock exporter sends (2026-10-19)

Derived parent `28fb029`. The zoo series' second batch (`WORKPLAN.md` V1),
answering the zoo's `PROBES.md` L1: before it, the receiver answered `415` to
every export a stock exporter sent.

Changed

- **`POST /v1/traces` with `Content-Type: application/x-protobuf` is served.**
  The body, inflated if `gzip`, goes whole to `spanweave.read_protobuf` (the
  reader's half, spanweave W1), and its records are routed exactly as a JSON
  body's are. `application/json` is unchanged and still goes to
  `Framer.document`. The `Content-Type` names the reader; the bytes are never
  sniffed. Nothing under `spanweave_live/` imports a protobuf runtime, and a
  test holds that. New public name: `PROTOBUF_MEDIA_TYPE`.
- **§7.2's five checks are five, with two media types.** The
  `unsupported_media_type` detail names both. A protobuf body that does not
  parse is a `400` with `unreadable_body` by §7.2's existing second case, and
  no new one: `read_protobuf` answers it as one `malformed_record` and no
  record. An empty protobuf body is an empty request and a `200`. Every answer
  is still `{}` or `{"code": ...}` as `application/json`, whatever the
  request's media type.
- `spanweave-live serve --help` and `README.md`'s `serve` line name both media
  types. `SPEC.md` §7.2, §8.1 and §4.8 amended.

Added

- **The zoo gate replays every capture a second time, from its raw bodies**:
  the exporter's own protobuf, in `forwards` order, through `Endpoint.handle`
  as the manifest records each request. Every body is answered `200` with the
  zoo's count for its JSON pair. The graph written equals the JSON replay's
  byte for byte on all twelve, Z4's two included.
- `tests/test_endpoint.py`: each of the zoo's 29 raw bodies is POSTed over the
  socket and answered `200`, and routes as many records as its JSON pair. Each
  truncated by one byte is `400`. Also covered: gzip over protobuf, both media
  types matched as HTTP matches a header, and the header choosing the reader.
  `tests/test_cli.py`: Z1's real run, posted as protobuf to
  `spanweave-live serve`, is written as the batch graph. A test reads the
  number 29 back from §7.2 and recounts it.
- `tests/test_cli.py`'s `serving` helper now takes an optional `timeout` on a
  post, and it kills the process when its block fails. Without these, a
  mutation that floods stderr deadlocked the new CLI test on the unread pipe
  instead of failing it.

Tests red on the parent (`28fb029`, worktree under the scratchpad): 92. These
are the 29 socket posts, the 29 truncations, both zoo-gate raw tests on all
twelve, the §7.2 citation, the CLI test, and eight endpoint test cases
(415 detail ×3, media type, gzip, truncated, header-names-the-reader, the
constant). Mutations shown caught:
- the protobuf body handed to `Framer.document` instead of `read_protobuf`:
  red on the zoo gate's raw replay (24) and on the 29 socket posts;
- a protobuf body answered `200` without being read: red on `routed` in the
  same places;
- the gzip body handed to `read_protobuf` un-inflated: red (gzip test);
- the reader chosen by the raw header instead of the normalized media type:
  red (media-type test);
- the refusal detail naming JSON alone: red (415 detail ×3).

### V0 — the pins move to the wire series' merge, and the zoo is a gate (2026-10-19)

Derived parent `0de9f55`. The zoo series' first batch (`WORKPLAN.md` V0).

Changed

- **Both pins move to spanweave `17edf6165c724bea996cbd29af74d7fe77adf267`**,
  the wire series' merge (PR #6): `pyproject.toml`, the `corpus/` submodule and
  `uv.lock`. spanweave's version there is `0.9.1`, as at the pin before, so
  `agentgolden`'s `spanweave>=0.9.1,<1.0` still resolves; `tests/test_pins.py`
  asserts both. The dependency is now written **`spanweave[otlp]`**, so the
  extra `spanweave.read_protobuf` needs (`protobuf`, `opentelemetry-proto`)
  ships with every install of the receiver. Nothing under `spanweave_live/`
  imports either. `SPEC.md` §0.1 and §0.2 name the new pin.
- **Gate A grows with the corpus**: 30 scenarios, 55 renderings (53 `.jsonl`,
  2 OTLP documents), 1460 cross-scenario pairs. The new scenario is
  `orphan_siblings`. Every pair still produces each trace's batch graph byte
  for byte, on all ten seeds. `README.md`'s sentence is now 1460 × 10 × 2 =
  29 200. A new test reads that sentence back and checks it against the
  sweep's own constants.
- **The showcase's first-failure table did not move** at the new pin. The
  expectation was "unchanged", because the stranger series changed
  diagnostics and times and not edges. `make showcase` asserts the same table
  as before, with `tests/test_showcase.py` untouched.

Added

- **The zoo gate**, `tests/test_zoo_gate.py`, run by `make conformance`
  (`SPEC.md` §4.8). It covers each of the twelve captures under
  `corpus/fixtures/zoo/`. The JSON bodies go through `Framer.document`, then
  `Router.route`, then the end-of-input `Cap(0)` tick. Two things are then
  checked. The written graph must equal `spanweave.dumps(spanweave.build(...))`
  of the same records byte for byte, with the batch side built from the bodies
  joined into one line-delimited stream (the test asserts the join is
  faithful). And `routed` must equal the zoo's own per-body record counts,
  read from the corpus README. **Ten rows are equal. Z4's two are short:
  4 records of 5 reach the trace's graph.** Z4's root span is claimed by no
  adapter, so it goes to the no-trace builder (L2). The test pins exactly that:
  version 4, one record in the no-trace builder, the batch graph less its one
  `unknown` node, and 4 `orphan_parent` live against 0 in batch. §4.8's table
  holds those rows, the test reads that table back, and V2 is the batch that
  moves them. The four L3 captures (Z3, Z1, Z2, Z6 real) complete once, at
  the last index, with no `orphan_parent`.
- `make install-check` reads one zoo raw body (Z4 recorded, five records) with
  the *installed* `spanweave`, which proves that the `otlp` extra ships.

Tests red on the parent (`0de9f55`, worktree under the scratchpad): every
zoo-gate test, because the zoo is absent from the old pin (0 captures of 12).
Also red there: the three new pin tests and the corpus-size and README
sentence tests of gate A. Mutations shown caught:
- a router that reads `record["trace_id"]` for a record no adapter claims
  turns Z4's rows into 5 of 5 and is red (the Z4 test and §4.8's table);
- an unclaimed record dropped instead of fed to the no-trace builder is red;
- in the test itself, keeping `source_digest` on the batch side is red on 12,
  and feeding the raw bodies where the JSON bodies belong is red on 42.

`make check` green (716 passed), `make conformance` green (57),
`make showcase` green with the table unchanged, `make install-check` green.

## 0.0.1 — the receiver series

The version from R0 to the receiver series' merge: its batches R0–R9 and the
follow-up commits of 2026-10-07 after its close, newest first.

### The sixth sentence, and three in the tests (2026-10-07)

**Prose only.** No behaviour changed, and **no test's logic or assertions
changed** — only docstring and comment text — so the bar's *confirmed red on the
parent* and *named mutation* lines do not apply to this entry, and no worktree
and no parent run were made. Derived parent `1b69c2b`. This closes the residue
`7ca6e91` disclosed when it closed **B5** of `reviews/2026-10-07-close.md` at
five sites: the sixth site it found and left, and the three looser instances
under `tests/`. The literal they are all held against is `tests/gates.py:237`,
`SEAMS = {"real.py": frozenset({"time", "http.server"})}` — one file, two
modules — read there for this entry rather than copied from the last one.

Fixed

- **The sixth present-tense "the seam allowlist stays empty" claim**, and the
  only one of the four in a **shipped** module:
  `spanweave_live/completion.py`'s module docstring, which is the only one of the
  four a library user reads. Its local point is unchanged — `now` has no default,
  so *this* module imports no clock — and the clause that was false now says what
  is true: `completion.py` needs **no** entry in the allowlist, whose one entry
  is `real.py`, for `time` and `http.server` (§8.2).
- **Three looser instances in test prose**, each now stating the true shape and
  each keeping its own argument. `tests/test_completion.py`'s rationale for
  requiring `now` is about keeping `completion.py` out of the allowlist, which is
  now what it says instead of "keeps the allowlist empty".
  `tests/test_ingest.py`'s "after this batch" claim is dated to **R5**, its own
  batch, with R7 named as where the one entry finally arrived; and
  `tests/test_gates.py`'s "still empty after the batch that was supposed to grow
  it" is dated to **R3**, which is the batch that paragraph is about, with R7
  named as what grew it. Dating them is what makes each one's point about a
  declined prediction land rather than read as false — the same fix `7ca6e91`
  made at the two sentences of that shape it reached.
- **`TASKS.md`'s disclosure of the four**, which said they were still standing.
  It now says they are closed by **this commit**: a commit cannot contain its own
  sha, so the record says "this commit" and a reader resolves it with `git log`
  or `git blame` on that line rather than being handed a sha that would be wrong.
  The same passage's `CHANGELOG.md` citations were **stale** — `:511`, `:607` and
  `:766`, moved by the entries added above them — and now name the four dated
  entries they sit in, measured at this tip, with a fifth (R0's, "empty at R0")
  and `SPEC.md:2017` added. Those, `SPEC.md:1672` and `:1676` are all **correct**
  and all untouched, because each sits inside a dated entry or a section dated to
  its own batch; §7.2's names R7's entry two sentences later.

Nothing under `spanweave_live/` moved but `completion.py`'s module docstring, and
`SPEC.md` is untouched, because no behaviour changed and every sentence there
that says the allowlist is empty is dated to the batch it is about. `make check`
green (ruff, `ruff format --check`, mypy --strict on 9 source files, **657
passed**, gates/pins 68). `make conformance` and `make install-check` were not
run and are not needed: no behaviour, no packaging, no dependency and no pin
moved.

### The endpoint's two behaviour threads, decided and closed (2026-10-07)

**The first change of behaviour since the series closed.** The close review
(`reviews/2026-10-07-close.md`) found exactly two things in seven commits that
were about behaviour rather than prose, both in `spanweave_live/endpoint.py`, and
binned both as `SPEC.md` §7.2 **decisions** rather than patches under
`CONTRIBUTING.md`'s "Halt, do not improvise". The maintainer decided them on
2026-10-07; this is them. Derived parent `7ca6e91`; both behaviours have a test
confirmed red there and a named mutation shown caught.

Fixed

- **A connection that carried no request now yields nothing** (**T-R6-4**).
  `serve` yielded `endpoint.last.records` after every `handle_request()`, so one
  that handled nothing re-yielded the **previous** request's object — reachable
  from outside by a bare TCP connect-and-close, with `Endpoint.requests` not
  moving, nothing counted, and the consumer handed the prior trace's records a
  second time. Nothing visible broke only because routing the same records twice
  happens to be graph-idempotent, which is luck and not design. "Was a request
  handled" is now read from `Endpoint.requests` **moving**, and there are
  **three** answers where §7.2 described two: a request handled yields its
  records; a **refusal** is a request handled and still yields `Records` that is
  empty rather than absent (§1.5, unchanged); a connection that carried no
  request yields nothing at all — not a stale object, and not an empty
  placeholder, because there is nothing for one to be empty about. `until` is
  still asked before each `handle_request()`, which is what keeps a skipped
  yield from being a loop with no exit.
- **A client that aborts before reading is a counted event** (**T-R6-5**). The
  response write raised, the exception escaped `respond`,
  `socketserver.BaseServer.handle_error` printed a **traceback to stderr**, and
  `Endpoint.counts` recorded nothing. The records still reached the consumer, so
  nothing was dropped in substance — but an uncounted traceback on the error
  stream is the shape standing rule 5 exists to prevent, and this module's own
  `400` path already did it correctly. `respond` now catches `ConnectionError`
  around the **write-back only**, never around `endpoint.handle`.

Added

- **`CLIENT_ABORTED`** (`"client_aborted"`), the endpoint's third code and the
  first addition to `spanweave_live.__all__` since R6. There is no status for it
  — nobody is listening for one — and the exit code stays `0`, because a poster
  that went away is an observation and not a graph the run failed to hand over
  (`SPEC.md` §8.6).
- **`Endpoint.aborted(exchange, error)`**, which counts the event and puts it on
  the exchange that becomes `last`, so `Endpoint.counts` and
  `Endpoint.last.events` stay consistent with each other as they are for every
  other code. A method rather than a branch in `respond`, because `Exchange` is
  frozen and the event has to reach both surfaces.
- **Seven tests in `tests/test_endpoint.py`**, and one **rewritten**:
  `test_a_listener_that_handled_nothing_still_yields` asserted "the yield is
  empty rather than absent", which was the defect rather than the rule — the
  empty placeholder only ever appeared before the *first* request. It is now
  `test_a_listener_that_handled_nothing_yields_nothing`, keeping its point that
  `Endpoint.last` is `None` before the first request. The bare connection is held
  by a **real socket**; the abort is held by a handler whose `wfile.write`
  raises, because whether an RST discards the bytes already queued for the
  server's read is the operating system's answer — a real abort gives
  `counts == {"client_aborted": 1}` 200 runs out of 200 on Linux, and that is
  recorded as a measurement rather than shipped as a test that would decide
  differently on the macOS job. §7.2 says which fact is held by which kind of
  test.

### The record made true — the close review's eight blocking findings (2026-10-07)

**Prose only.** No behaviour changed, no test changed, and nothing was added to
or removed from the library's surface — so the bar's *confirmed red on the
parent* and *named mutation* lines do not apply to this entry, and no worktree or
parent run was made. The scoped cold review of the series' close
(`reviews/2026-10-07-close.md`, archived here byte for byte with its sha256 in
`TASKS.md`) found the code merge-ready and the **record** untrue in eight places.
All eight are closed where the false sentence was.

Fixed

- **`TASKS.md`'s dispositions of T1, T5, T7, T10 and T13**, each of which said
  something that does not hold. T10 claimed R5a closed "all four" places that
  called a `Tail` the iterator: there are **three** at this tip and R5a wrote all
  three, while the fourth was the `WORKPLAN.md` row a `plan:` commit changed and
  `86183b0` deleted. T5 named `flush` and `forget` as event codes: they are
  `Subscriptions` **methods**, and the surface they are declared in is `SPEC.md`
  §6.1, not §6.5. T13 called all three of its items "text in a deleted file":
  item (iii) is an immutable commit subject. T1's reasoning was a non-sequitur —
  what makes the CLI's `Cap(0)` reassignment safe is that the CLI **constructs**
  the router with its policy, not that `Cap(0)` reads no silence; the same
  reassignment reports `seconds: 0.0` on a router routed without one. T1's status
  (**open**) and T13's (**moot**) were right and are unchanged.
- **Five present-tense claims that the seam allowlist is empty**, false since R7
  put its one entry in: `CLAUDE.md`'s standing rule 4, `SPEC.md` §5.2, and
  docstrings in `spanweave_live/ingest.py` and `spanweave_live/endpoint.py`
  (two). Each now states the true shape —
  `SEAMS = {"real.py": frozenset({"time", "http.server"})}`, one file and two
  modules — and the two that were "after this batch" claims are dated to R3 and
  R6 as history, the way `SPEC.md` §7.1's already were. `CLAUDE.md`'s
  banned-module list gains **`http.server`**, the second module that entry
  exempts. Four looser instances remain under `tests/` and in
  `spanweave_live/completion.py`; they are disclosed in `TASKS.md` rather than
  silently left, because this entry's scope was three docstrings.
- **`SPEC.md` §8.7** claimed every test in `tests/test_cli.py` runs the CLI as a
  process. Measured: **72 of 81 collected items** spawn one; **nine** read the
  package in-process, and the file's own docstring always said so. The
  `TASKS.md` R7 row repeated the overclaim as "81, all through `subprocess`" and
  now carries the measured split.
- **Six recorded figures** in `TASKS.md` that did not re-derive as written: R7's
  parent run (**77 failed / 4 passed**, and the fourth passer,
  `test_version_and_help_both_say_nothing_is_frozen`, is now named), R7's
  mutation (**1 failed / 80 passed**), R8's parent run (**5 failed / 634
  passed**, with `test_every_submodule_is_cloned_over_https_too` named as the
  fifth failure), R8's mutation (it erases **two** first-failures —
  `trajectory.all_calls_fulfilled` *and* `tools.required:issue_refund`), and —
  the one that is not a slip in a number — **R3a's parent run is not reproducible
  as described**: it aborts with `ImportError: cannot import name 'FORGOTTEN'`
  and collects 0 tests unless the `FORGOTTEN` constant is first added to the
  parent tree, a step no record mentioned. It is now recorded as part of the
  evidence.
- **The citation of "10⁶ is 230.5 MB"**, which `TASKS.md` sourced to `SPEC.md`
  §5.5 — a section with no 10⁶ row that says ~210 MB. The figure is real
  (re-measured at **230 516 588 B**) and is now attributed to R3a's own
  measurement, with §5.5 cited only for what §5.5 says. No spec measurement
  changed.
- **The decisions log's count**: twelve rows, not thirteen, here and in
  `TASKS.md`.
- **`CHANGELOG.md`'s preamble**, which named `WORKPLAN.md` in the present tense,
  in no dated entry, as the unit of change. It names `TASKS.md` instead and says
  how to read the dated citations below it. `TASKS.md`'s claim that every
  surviving plan citation sits inside a dated batch entry is corrected to the
  measured fourteen-of-which-thirteen.
- **`CLAUDE.md:8–10`**, which still described `WORKPLAN.md` as live execution
  state four lines under a promise that a cold session can work from that file
  alone. It now names **`TASKS.md`** as the registry between series — `grep -n
  "TASKS.md" CLAUDE.md` returned nothing before this — and keeps the rule it was
  carrying: a `WORKPLAN.md` exists only while a series is open, is the
  orchestrator's, and is never edited by a batch.

Added

- **`reviews/2026-10-07-close.md`**, the third cold review, archived byte for
  byte with its sha256 in `TASKS.md`'s table, so that the citations this entry
  and `TASKS.md` make resolve in a stranger's checkout. `patches/` is
  `.gitignore`d; the archive is the same practice R9 established for the first
  two.
- **A `TASKS.md` section recording this commit**, with every number in it
  re-measured rather than copied from the review, the method for each, and the
  four of the review's own figures that did not re-derive.

### R9 — the receiver series closes, and its execution state is deleted (2026-10-06)

No change under `spanweave_live/` except two re-pointed citations. This is the
close: the series' plan is deleted, everything in it that a later reader needs
is folded into tracked files, and the README finally describes what the library
does rather than what it is going to do.

Added

- **`TASKS.md`**, the item registry: one line per batch for R0–R9 with the
  commit that closed it, the series' **decisions log** (twelve rows, the
  deleted plan's §3) and its **resume note** (the deleted plan's §4) folded in
  per batch, the disposition of every finding of both reviews, and the origins
  table. The fold is both sections and not one, which was itself a review
  finding (**F12**): the decision to fold both had been taken on 2026-10-05 and
  reached the plan's §0.6 and §3 but never the R9 row that an agent executes.
  Where a measurement already lives in `SPEC.md` — the `trace_id_of` share of
  routing (§4.2), the per-id cost of the completed-trace book (§5.5) — the
  registry points at the spec instead of copying the number, because two copies
  of a number drift.
- **`reviews/`**, which makes the two cold reviews tracked content for the first
  time. `reviews/2026-10-04-run1.md` and `reviews/2026-10-06-run2.md` are
  **byte-identical** to the `patches/REVIEW-<date>.md` files they were written
  as — `patches/` is `.gitignore`d, so until now every citation of a review in
  `SPEC.md`, `tests/` and `.github/` pointed at a file a stranger's checkout
  does not contain. Their sha256 are recorded in `TASKS.md`; the copies are
  unedited and keep their own errors, including run 2's header miscounting its
  own body (eight `next batch` findings claimed, twelve listed — twelve is
  right) and run 1's withdrawal of one of its own clean lines.
- **`tests/install_check.py` audits the sdist**, not only the wheel. The sdist's
  `include` is an allowlist, so `reviews/` is absent from it by default — which
  is correct and is now asserted rather than assumed, together with `corpus/`
  and `showcase/` being absent and `TASKS.md` being present. The wheel's
  forbidden list gains `showcase/` and `reviews/` and drops `WORKPLAN.md`, which
  this commit makes vacuous.
- **`CONTRIBUTING.md` asks for the resolved parent sha** in the commit body, not
  the sha the author started from (thread **T7**): one commit in this series
  claimed a parent two commits back and was right only by luck. The deleted
  plan's batch brief was the other home for that line, so this is where it
  lives now.

Changed

- **`README.md` rewritten.** It now documents the CLI — both commands, the
  policy and bound flags, the exit codes, and the two traps a user meets before
  anything else (`--max-completed` can overwrite a written graph; line numbers
  after a `fragment_too_long` are the framer's) — and the API, as a runnable
  example plus one row per piece with the `SPEC.md` section that specifies it.
  Its old closing sentence ("`Framer`, `Router`, … arrive in R1–R7") had been
  stale since R3 and was left alone on purpose: the plan assigned the README to
  this batch so that no batch would patch that line piecemeal while it was
  still partly true.
- **Every live citation of the deleted plan re-pointed** at `TASKS.md`:
  `SPEC.md` (eight sites), `spanweave_live/routing.py`,
  `spanweave_live/subscriptions.py`, six test modules,
  `.github/workflows/ci.yml` and `CONTRIBUTING.md`. The **plan** citations in
  this file are deliberately left as they stand: each sits inside a dated batch
  entry, so it records what was true when that batch landed, and
  `git show b500342:WORKPLAN.md` resolves it.
- **Every citation of `patches/REVIEW-<date>.md` re-pointed** at its
  `reviews/` archive, in this file too, because there the bytes are identical
  and the archive is tracked: a citation that resolves from a clean checkout
  beats one that names the path it was written at.

Removed

- **`WORKPLAN.md`.** It was the series' execution state — the operating
  protocol, the batch rows with their acceptance criteria, the decisions log and
  the resume note — and it was written to be deleted at close so that nobody
  looking for what this project *is* has two places to look. Its own §0.6 said
  so from the first commit. The file is still readable at
  `git show b500342:WORKPLAN.md`, and `TASKS.md` carries what outlives it.
- The series-close commit is also the one plan commit in the series that
  **cannot** say `plan:`, as the plan's §0.7 stated in advance: a `plan:` commit
  deleting the plan would have nothing left to be the plan of.

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

One commit for the twelve findings `reviews/2026-10-06-run2.md` marks
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
`reviews/2026-10-04-run1.md`, which is the cold review of run 1.

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
