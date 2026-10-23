# REVIEW-2026-10-22 — backlog series, run 1 (cold read)

Range: `11a1452..72d60e8` on `backlog`: B1 `3ceb8df`, `plan:` `c4ec4a4`,
B2 `57ad222`, `plan:` `29b2996`, B3 `303f50f`, `plan:` `72d60e8`.
Rules: `WORKPLAN.md` §0.2 at `72d60e8`, `CONTRIBUTING.md`, `CLAUDE.md`.
Graded under `WORKPLAN.md` §2's merge rule: **blocking** only if this series
introduces the defect or a claim it makes depends on it. Anything older is a
**thread**, with its measurements. "Non-blocking" marks a defect this series
introduced that no claim depends on.

Method: detached worktrees by absolute path under the aux scratchpad, at
`72d60e8` and at each commit and its derived parent (`3ceb8df^` = `11a1452`,
`57ad222^` = `c4ec4a4`, `303f50f^` = `29b2996`). Each has `corpus/` at
`17edf61` and `showcase/` at `aa1847f`, cloned from the repo's module store,
and a venv from `uv sync --extra dev --frozen` (offline). One sub-agent per
code commit. The re-derivations below were done separately, with scripts that
import none of the tests' helpers.

## Verdict

**No blocking finding.** Every number the series states that this review
re-derived came out the same. Six findings: three non-blocking (introduced
here, no claim depends on them) and three threads or notes.

## Per-commit checks

| Check | B1 `3ceb8df` | B2 `57ad222` | B3 `303f50f` |
|---|---|---|---|
| Spec in the same commit | pass (§2.3, §4.1/§6.1, §4.3, §4.5, §5.5, §6.2, §6.4, §8.1, §8.7) | pass (§1.1, §4.1, §4.2, §4.3, §4.5, §4.7, §4.8, §8.3); every sentence naming §4.3's exception is gone or now history | pass (§7.2) |
| New tests red on the derived parent | 10 failed / 136 passed on `11a1452` (one of the 10 is red only on the missing keyword; `test_no_unclaimed_bound_is_the_default` is green there, as CHANGELOG says) | 14 failed on `c4ec4a4`; the pins (gate A named ×2, the sweep-count test, the zoo gate named ×24) are green there and call themselves pins | 46 failed / 113 passed on `29b2996`, matching the body's "46" |
| Parent sha recorded in the body | **no** (R-1) | `c4ec4a4`, correct | `29b2996`, correct |
| Named mutation caught | all three of the row's (e.g. `_unclaimed = len(_builders)` is red in `…absorbs_a_claimed_record_frees_its_place`) | classify across adapters under a name: 14 red; envelope asked under a name: 4 red | length off by one: 19 red |
| Two more mutations | `>=`→`>` caught; `not identity.claimed` dropped caught; `_counted` dropped caught; CLI not passing the field caught | fallback to unnamed routing on no id caught (2); still refusing a both-claim record caught (6); sole classifier's parse instead of X's **survived**, equivalent at the pin (R-4) | varint high group first caught; varint threshold `0xFF` caught; `len(message)` for `len(data)` survived, equivalent today (R-6) |
| Ambient runtime outside `SEAMS` | none added; gates green | none added | no protobuf or other import under `spanweave_live/`; gates green |
| Pins | spanweave = corpus = lock `17edf61`; agentgolden = showcase = lock `aa1847f`; untouched by all six commits; `test_pins.py` green at each |
| One concern | yes (the `subscriptions.py` change is a docstring the bound made false) | yes (the CLAUDE.md rule 5 edit closes the exception B2 removes) | yes |
| `make check` | 925 passed (§4 says 925) | 965 passed (§4 says 965) | 996 passed (§4 says 996; also re-run at `72d60e8`: 996) |

`plan:` commits: each touches `WORKPLAN.md` alone. The three row corrections
(B1's 90 traces / 180 events, B2's gate A as a pin, B3's test-declared
`Status`) each match what was measured here. CI: GitHub ran on `11a1452` and
`72d60e8` only, and all seven jobs at `72d60e8` are green (R-3).

## Independent re-derivations (at `72d60e8`)

**B1, the bound as the row states it.** Exports were hand-built as OTLP/JSON
and read through `spanweave.read_records`. Health checks are unpacked and
`classify` gives `()`; one OpenInference span is claimed.
- The cap_bound shape, `Router(max_traces=1, max_unclaimed_traces=10)` with
  one claimed trace and 100 two-span health checks, plus one subscriber:
  **11 builders, 11 cursors** (`Subscriptions._cursors`), and
  `counts == {'refused_at_cap': 180}` over **90 distinct traces**. Each
  detail names `max_unclaimed_traces`.
- Five one-span checks at `max_unclaimed_traces=2`: 2 builders, 3 counted
  `refused_at_cap`, all naming the bound.
- A further record for a held trace is absorbed (version 2, no event).
- When that trace absorbs a claimed record (version 3), the next check is
  admitted and the one after it is refused.
- Five new claimed traces at a full unclaimed bound are all admitted.
- A claimed record joining a held unclaimed trace at a full `max_traces` is
  `refused_at_cap` naming `max_traces`. That trace stays in the unclaimed
  count, so the next check is refused.
- Completion (`Quiet(1.0)`, fake clock) releases an unclaimed trace
  (`completed`, `no_graph`, `released`), and the next check is admitted.
- A late arrival for that completed trace at a full bound is
  `refused_at_cap`, as §5.5 says (R-2).
- **The no-trace builder is bounded by neither.** At
  `max_traces=0, max_unclaimed_traces=0`, 50 flat unclaimed records and 3
  unpacked spans with an empty `traceId` give 53 `no_trace` events and 0
  `refused_at_cap`. The no-trace builder ends at version 50 after the flat
  records.

**B2, the measurement.**
- **82 inputs**: 55 renderings (`corpus/fixtures/conformance/*/dialects/*`),
  3 `corpus/fixtures/captured/*.jsonl`, the 12 zoo captures' JSON bodies in
  order, and their raw bodies through `read_protobuf`.
- Each input ran under `Router(adapter=X)` for X in both registered adapters:
  **164 pairs, 1822 records, 164 traces, 164 of 164 equal** to
  `graph_from_records` of that trace's records under X, digest dropped.
- 0 records went to the no-trace builder. The router's grouping matched an
  independent grouping by X's `parse` in every pair.
- **140 of 164** also equal the public `spanweave.build(bytes, adapter=X)`.
  The 24 raw pairs have no bytes `build` reads.
- The same script at `c4ec4a4` gives the same 164/164 and 140, so the corpus
  and the zoo do not reach the defect, as §4 says.

**B2, run 1's R-9, both shapes.** One ordinary record of X plus an odd record
in trace `t1`:

| At | Shape | Under each name |
|---|---|---|
| `72d60e8` | both adapters claim the record (`classify` → both) | routed `[t1, t1]`, no event, live 2 nodes = batch 2, byte-equal |
| `72d60e8` | flat record, `classify` → `()` | routed `[t1, t1]`, no event, live 2 nodes = batch 2, byte-equal |
| `c4ec4a4` | both adapters claim the record | routed `[t1, None]`, **no event**, live 1 node vs batch 2 |
| `c4ec4a4` | flat record | routed `[t1, None]` with `no_trace`, live 1 node vs batch 2 |

**B3, every refusal row in both encodings.** Every request went through
`endpoint.respond` with a fake handler (no socket). The checks were the status,
the `Content-Type` and `Content-Length` written, and the body decoded with a
`google.rpc.Status` I declared from `status.proto`'s three fields.

The rows are 8 refusal shapes (GET, PUT, wrong target, `Transfer-Encoding:
chunked`, `Content-Encoding: deflate`, bad gzip, truncated gzip, unreadable
bytes). Each was sent under 4 declared spellings (`application/json`,
`application/x-protobuf`, ` APPLICATION/JSON ;charset=UTF-8` and
`application/x-protobuf; proto=foo`).

**32 of 32 answered correctly:**
- the status was 415 or 400 as the code decides, and the type was the
  declared one;
- the JSON bodies parse with `json_format.Parse`;
- the protobuf bodies parse and re-serialize to the same bytes (field 2
  alone, e.g. `\x12\x16unsupported_media_type`);
- in each, `message` was the event's code, `code` was 0 and `details` was
  empty.

**A request declaring neither type is answered JSON.** No header, `""`,
`text/plain`, `application/protobuf`, `application/grpc` and
`application/x-protobuf+json`: 6 of 6 got 415 `application/json`
`{"message":"unsupported_media_type"}`.

**§8.7's "78 of 87".** `tests/test_cli.py` was run with a pytest plugin of my
own that records every `subprocess.Popen` per test item: **87 collected, 78
spawn a process, 9 do not**. The 9 are exactly the nine §8.7 names.

## Findings

**R-1 — `3ceb8df` (B1). Rule: `CONTRIBUTING.md`, "Record the sha `<sha>^`
resolved to in the commit body". Grade: non-blocking.**
The body names no parent: `git log -1 --format=%B 3ceb8df | grep -c 11a1452`
gives 0. Only the CHANGELOG entry says "Derived parent `11a1452`". The sha is
right (`3ceb8df^` = `11a1452909136d6662b3636b2fc95814c8b84545`), and the red
run reproduces there (10 failed), so no claim depends on the omission. The
body cannot be amended, since §0.1 forbids a force-push. The fix is a record
line in `TASKS.md` at B10, as B9(d) does for T9.

**R-2 — `3ceb8df` (B1). Rule: §0.3, "A number you state … is a citation with
a test"; behaviour stated in SPEC and held by none. Grade: non-blocking.**
B1 added a clause to SPEC §5.5: a late unclaimed arrival at a full
`max_unclaimed_traces` is `refused_at_cap`, the trace stays completed, and no
`late_arrival` is emitted. Measured true here and by the B1 sub-agent, but no
test pins it. With a free place, the same record is admitted with
`late_arrival`. A test belongs beside B5's completion pins.

**R-3 — `c4ec4a4`, `29b2996` (plan). Rule: `WORKPLAN.md` §2, "Every batch: CI
green on the pushed tip before `done`". Grade: non-blocking.**
B1 and B2 were marked `done` with no push and no CI run on their tips. GitHub
shows runs on `backlog` only at `11a1452` and `72d60e8`. §0.1 step 8 pushes
once per run, which contradicts §2's per-batch wording. The `done` claims now
stand: all seven jobs at `72d60e8` are green, including the ruleset's six
required ones. The plan's two rules should agree before run 2 marks B4 done.

**R-4 — `57ad222` (B2). Rule: §0.2, two more mutations of added code. Grade:
thread (note).**
One mutation survives all 184 tests in the three touched files: under a name,
use the parse of the sole adapter `classify` names instead of X's. It is
equivalent at pin `17edf61`, because the two adapters' parses disagree on the
trace id of 0 of 588 corpus records, and of no hand-made probe. No test can tell the two apart until an adapter reads trace ids
differently. Recorded so a pin move that adds such an adapter adds the test.

**R-5 — `57ad222` (B2). Rule: a stated reason that is incomplete (SPEC §4.8
"And every capture again under each named adapter"; `tests/test_zoo_gate.py`
`test_under_a_named_adapter_each_capture_is_its_named_batch_graph`'s
docstring). Grade: non-blocking.**
Both explain why the named zoo pin was green on the parent with "no capture
holds a record two adapters claim". That is one of two reasons. Z4's root is
claimed by no adapter, and on `c4ec4a4` it was routed by its envelope to the
same trace id X's parse gives. So the parent's other defect shape, a *flat*
unclaimed record, cannot occur in the zoo, whose records are all unpacked.

The claim "held before B2 too" is true: 164/164 on `c4ec4a4`, above. Only the
"because" is short. §4.7's companion sentence for gate A is complete, because
its renderings are each claimed by their own adapter alone (146 records, 77 OI
and 69 GenAI, measured by the B2 sub-agent).

**R-6 — `303f50f` (B3). Rule: SPEC §1.5 / §7.2 scope of "A refusal answers
OTLP's `google.rpc.Status`". Grade: thread.**
The new sentence does not say which refusals it covers. Two answers come from
`http.server` itself, never reach `respond`, and are neither a `Status` nor
counted:
- a method outside `_METHODS`, e.g. `TRACE`, gets `501` with an HTML body;
- a malformed request line gets an HTML `400` with no status line.

Measured over loopback by the B3 sub-agent: counts after three requests were
`{'unreadable_body': 1}`, from the third alone. This is older than the series.
SPEC §7.2 already names `http.server`'s uncounted `501`, and §1.5's "each is
an event" was false for both before B3. B3's unscoped sentence makes the gap
wider in wording only.

Two more observations, neither a defect:
- B3 adds one more loopback-socket test
  (`test_a_protobuf_refusal_over_the_socket_is_a_status_with_its_type`) to
  the registered R-10 thread that B9 takes.
- The `len(message)` mutation is equivalent today, because every refusal
  code is an ASCII constant (the longest is 22 bytes). The varint's
  multi-byte branch is held only by the direct `_status` test at lengths 127,
  128, 300 and 20000.

## Process note

At the start of this review, one command read `.gitmodules` from the main
checkout's working tree (`cat ~/git/spanweave-live/.gitmodules`) instead of
from a worktree. It changed nothing. No command moved the main checkout's
HEAD, index or files. `git worktree add` registered seven worktrees under the
scratchpad, which `git worktree prune` clears once the scratchpad is gone.
