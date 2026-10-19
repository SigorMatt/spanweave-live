# WORKPLAN.md — spanweave-live, the zoo series

Status file for the series that answers the zoo's four receiver probes
(`PROBES.md` L1–L4 at `SigorMatt/spanweave-zoo` `7eb5b69`): the receiver
answered 415 to every export a stock exporter sent (L1); a record it routed
reached no graph and no event said where it went (L2); a trace whose root
arrives last completes once per body under `--quiet 0` (L3); a trace with no
root is never completed by `RootEnded` (L4). The twelve captures become
this repository's corpus through the `corpus/` submodule, and the audit's
"live, batch and incremental are equal" becomes a gate. One batch = one
sub-agent = one commit = one concern. This file plus git is the only state;
any session can resume cold from it.

Last updated: 2026-10-19 (run 1 done: V0, V1, V2; run 2 not started.)

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
8. `git push origin zoo`. A run is not finished until the push succeeds
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
`patches/REVIEW-<date>.md` (untracked) and print them. **Aux never edits
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
cap, a late arrival, a consumer error — and from V2, a record that reaches
no trace — is an event with a code, counted and reported. `spanweave` is
pinned to one commit in `pyproject.toml` and the `corpus/` submodule is at
the same commit; a test holds the two equal, and the `agentgolden` pin and
`showcase/` likewise.

The corpus is read in place through `corpus/`, never copied: from V0 that
includes `corpus/fixtures/zoo/` — the twelve captures (JSON and raw bodies,
manifests) at the zoo's pin. The receiver's own gate over them, the **zoo
gate** (V0), holds for every capture that the graph the receiver writes at
end of input equals `spanweave.build` of the same records byte for byte;
every batch keeps it green or moves it with the reason.

TASKS.md is the item registry (one line per batch, written at series
close); this file is execution state only and is deleted at series close
with §3 and §4 folded into TASKS.md. The opening commit of the series makes
whatever the doc-truth gates need for WORKPLAN.md to exist, as the receiver
series' opener did, and nothing else.

---

## 1. Batch list

| ID | Batch | Status | Calls |
|---|---|---|---|
| V0 | **The pins move to the wire series' merge, and the zoo is a gate.** Both pins (`pyproject.toml`, `corpus/`) to spanweave `main` at the wire series' merge commit, `17edf6165c724bea996cbd29af74d7fe77adf267` (PR #6; §4), the dependency written as `spanweave[otlp]` so the extra ships with the receiver; `uv.lock` with them; `tests/test_pins.py` green; `agentgolden`'s `spanweave>=0.9.1,<1.0` still resolves (the batch states spanweave's version at the pin). Gate A green at the new pin, every pair. The showcase's first-failure table re-measured at the new pin: if a version moved, the batch says which and why (the stranger series changed diagnostics and times, not edges, so the expectation is "unchanged" — stated as an expectation, not a number). `tests/test_zoo_gate.py`: for each of the twelve captures under `corpus/fixtures/zoo/`, the JSON bodies in order through `Framer.document` → `Router.route` → the end-of-input `Cap(0)` tick, and the written graph equals `spanweave.dumps(spanweave.build(records))` byte for byte — except Z4 real and recorded, whose root no adapter claims, which the gate pins at 4 of 5 nodes as `no (L2)` until V2 (§4); `routed` equals the capture's record count as the manifest's bodies state it; the four L3 captures (Z3, Z1, Z2, Z6 real) complete once, at the last index, and their graphs carry no `orphan_parent` — the audit's observation, now asserted. `make conformance` runs it. Tests red on the parent: the zoo is absent from the old pin. | done (024fc66) | 5 |
| V1 | **The endpoint serves what a stock exporter sends.** L1. `POST /v1/traces` with `Content-Type: application/x-protobuf` is a served request: the body (inflated if `gzip`) goes to `spanweave.read_protobuf` (W1) and its records are routed exactly as a JSON body's are; `application/json` unchanged; the five checks of SPEC §7.2 become five with two media types, the `unsupported_media_type` detail names both. No transcoding, no proto import under `spanweave_live/` — the reader's extra does it (standing rule 1). SPEC §7.2 and §8.1 amended; README's `serve` line says both. Tests red on the parent: all 29 raw bodies from `corpus/fixtures/zoo/` answered 200 with `routed` equal to the JSON body's; the zoo gate extended — each capture replayed from its **raw** bodies writes a graph byte-identical to the JSON replay's; a body declaring `application/x-protobuf` that does not parse is `400` with `unreadable_body`, counted, as a malformed JSON body is — by §7.2's existing second case and no new one: `read_protobuf` raises nothing an unreadable body can cause and answers it as one `malformed_record` with no record, so `records == ()` and `skipped_records > 0` hold as they do for JSON (the batch shows it on a truncated zoo raw body). Mutation: the raw path routed through the JSON reader is red (the zoo gate); a 200 answered without routing is red (`routed`). | done (9641d75) | 5 |
| V2 | **Every record the receiver routes reaches a trace or an event says why not.** L2; the receiver's half of spanweave's T1 decision. (1) `trace_id_of`: the claimant's `parse` as today; when no adapter claims an **unpacked OTLP record**, `spanweave.envelope(record).trace_id` — the transport's id, read through the public envelope, never a key. "No trace id" stays the answer for a flat record no adapter claims and for a claimant that reports no single id, and is the answer for an unpacked record no adapter claims whose envelope `spanweave.envelope` refuses (`EnvelopeError`, `not_an_envelope`: no trace or span id, or a field of a type the envelope cannot hold). The wire series made the first of those reachable from a stock exporter, because on the wire an all-zero id is no id. The receiver never reads past a refused envelope to a key. The batch measures, over every unpacked record a claimant claims in the corpus and the zoo, that the claimant's trace id equals the envelope's, and states the count; if any differs it stops (`awaiting decision`), because which one routes would then be a rule. Routing reads ids only through the library, so the reader's malformed-input rules that spanweave's next series decides (a member stated twice among them) move routing and the batch build together; the zoo gate holds them equal, and nothing here decides them. (2) A record that reaches the no-trace builder emits one event, code `no_trace`, counted, carrying the record's arrival index and a `detail` naming which answer it was (`unclaimed`, `no_envelope`, `no_id`), and, where the library refused, the library's code as `spanweave_code` (`not_an_envelope`); the ambiguous case is already `refused` and stays so. `finished` reports the count. The no-trace builder is still never written — each of its records was announced — and SPEC §4.3 says so in one sentence instead of the three that contradicted §1.1 and §1.5. (3) The audit's Z4 end-of-input run: one trace, 5 records routed to it, graph of 5 nodes with 4 `parent` edges and 0 `orphan_parent`, equal byte for byte to `spanweave.build` of the five — the zoo gate holds it, and the gate's Z4 row changes from "4 of 5" to "5 of 5" with L2 as the reason. Gate A: a conformance pair in which one rendering is an OTLP container with an unclaimed span among claimed ones still produces each trace's batch graph (the batch names the corpus scenario it uses, or adds the hand-made export to the receiver's own fixtures if none fits). SPEC §1.1, §4.2, §4.3, §8.3 amended. Tests red on the parent: Z4 real and recorded through the zoo gate (5 nodes, not 4); a hand-made export with one claimed and one unclaimed span routes both to one trace; a flat unclaimed record yields `no_trace` with `detail: unclaimed` and reaches the no-trace builder; a claimed record whose spans carry no trace id yields `no_trace` with `detail: no_id`; an unclaimed span whose `traceId` is sixteen zero bytes in a protobuf body yields `no_trace` with `detail: no_envelope` and `spanweave_code: not_an_envelope`, and the no-trace builder's account of it is the batch build's (`missing_trace_id`, `unclaimed_record`). Mutations: the envelope fallback applied to a flat record is red; a refused envelope read past to the record's `trace_id` key is red; a `no_trace` event not counted in `finished` is red. | done (6d78ad9) | 6 |
| V3 | **What a generation is, and what the policies do at values the audit never ran.** L3, L4. No behaviour change unless a test shows a policy fires at the wrong instant; this batch is readings pinned by tests on the zoo captures under the fake clock. Tests (new, red on the parent only where they import a new name — none expected; they are pins and say so): over Z3 real (4 bodies), Z1 real (2), Z2 real (3), Z6 real (11), bodies fed at `now = k` seconds for body k, then ticks: `Quiet(0.5)` ticked after each body completes **once per body** (generations as the audit counted under `--quiet 0`: Z3 4, Z1 2, Z2 3, Z6 11), the last generation holding the root and every earlier one carrying `orphan_parent` exactly as `spanweave.build` of that body prefix does (asserted byte for byte per generation); `Quiet(2.0)` ticked after each body completes nothing, and a tick at `now = last + 2.0` completes once with a graph equal to the end-of-input graph; `RootEnded(1.0)` ticked after each body completes nothing until the last body, and a tick at `last + 1.0` completes once, same graph; `Cap(N)` with N the capture's record count completes at the last record, same graph. Over Z5 real and recorded (no root): `RootEnded(S)` for S in {0, 1, 3600} completes nothing at any tick up to `now = 10^6`; `Quiet(S)` completes once at `last + S`; `Cap(4)` completes at the fourth record; `Cap(5)` never, and the end-of-input `Cap(0)` completes it. SPEC §5.3 and §5.5 gain the reading: a generation is the batch graph of what was absorbed when the caller's policy fired, so a policy that fires before a trace's parents arrive yields the `orphan_parent` diagnostics a batch build of that prefix yields — the caller's policy showing, not a defect — the next generation opens on the next record as `late_arrival`, generations are never merged, and `RootEnded` alone never completes a trace whose root never ends. README gains that as its third trap, beside the two it has. Docs and tests. | todo | 4 |
| V4 | **The series closes.** TASKS.md: registry V0–V4 with shas, §3 and §4 folded, L1–L4 dispositioned (L1 with W1's sha for the reader's half); `reviews/`; CHANGELOG; version to `0.0.2` (nothing is frozen, and the event-code set grew); WORKPLAN.md deleted. No `plan:` commit follows. The series reaches `main` only through the PR `zoo` → `main` (§2), a merge commit through `main`'s ruleset: its required checks are `check (macos-latest, 3.12)`, `check (ubuntu-latest, 3.11)` to `check (ubuntu-latest, 3.14)`, `conformance (macos-latest)` and `conformance (ubuntu-latest)`. A CI job this series adds or renames is added to the ruleset after the merge, once it has run on `main`. | awaiting V3 | 4 |

## 2. Execution order

Run 1 = V0 → V1 → V2. Run 2 = V3 → V4. Then, in order: the aux cold review
of the series; its fix commits; the PR `zoo` → `main`; then together, one
bounded review of those fix commits and Qodo's review of the PR (first
fetch archived), dispositioned as one set; that set's commits, CI green and
Qodo's post-push diff; and the merge. Every batch: CI green on the pushed
tip before `done`. The branch is `zoo`, from `main` at its tip when the
series opens (§4 records it). V0 cannot start before the wire series has
merged to spanweave `main` (it has: §4).

The merge rule is spanweave's decisions log D39 and D40, adopted here from
the start (§3): only a defect this series introduces, or one a claim it
makes depends on, blocks the merge; an older defect is registered in
TASKS.md with its measurements. A review of fix commits is bounded: the
standard per-commit rules (§0.2) plus the previous review's own survivors
and probes, and no new search. If it finds a blocking defect, that fix is
made and goes to the merge on green CI without a further review: the loop
ends there.

## 3. Decisions log

| Date | Batch | Decision | By |
|---|---|---|---|
| 2026-10-16 | series | The zoo's probes are answered one by one, and the twelve captures become the receiver's corpus through the submodule it already has, never a copy: the pin moves, the zoo comes with it, and the audit's "live equals batch" claim becomes a gate the receiver runs on every `make conformance`. | maintainer |
| 2026-10-16 | V1 | The protobuf path is the reader's (spanweave's wire series), and the receiver only hands bytes to it: a transcoder here would be a second reader of the envelope, which standing rule 1 forbids for exactly the reason §1.1 gives. `spanweave[otlp]` is the receiver's dependency unconditionally — a receiver exists to receive what stock exporters send, and they send protobuf. | maintainer |
| 2026-10-16 | V2 | Routing by the envelope is not reading a dialect: spanweave's T1 decided the transport's ids are the transport's, read by the reader before any adapter is asked and exposed through a public function; the receiver asking that function for a record no adapter claims is the receiver's half of that decision. The no-trace builder keeps its job for records that have neither a claimant nor an envelope, and every record that reaches it is announced — §1.5 wins over §4.3's "invents no event code", because the diagnostics are the library's and the routing decision is the receiver's. | maintainer |
| 2026-10-19 | V2 | An unpacked record no adapter claims whose envelope spanweave refuses (`not_an_envelope`) is "no trace id", with its own detail, `no_envelope`, and the library's code on the event. The receiver never reads past a refused envelope to a key it can use, and never says which field failed: the library's message does. Which id routes when a claimant's and the envelope's differ is not decided here; V2 measures that they never do in the corpus, and stops if they do. | maintainer |
| 2026-10-19 | series | The review loop is bounded from the start, as spanweave's decisions log D39 and D40 bounded its PR #6 (§2): one cold review, its fixes, one bounded review of them read together with Qodo's review, and the merge on green CI. An older defect is a thread, never a blocker. | maintainer |
| 2026-10-16 | V3 | Generations are not merged and early completion is not a defect: the caller chose the policy, the receiver says what it absorbed when it fired, and a batch build of the same prefix says the same. The receiver's job is to make that plain in SPEC and README, and to pin the policies' behaviour at values the audit never ran, not to second-guess a policy. | maintainer |

## 4. Resume note

- 2026-10-16: series drafted; opens on `zoo` once spanweave's wire series
  (W0–W2) has merged.
- 2026-10-19: spanweave's wire series merged as
  `17edf6165c724bea996cbd29af74d7fe77adf267` (PR #6), the sha V0 pins
  both pins to; spanweave's version there is `0.9.1`. The series opens on
  `zoo` from `main` at `cddc694`. `main` is protected since 2026-10-19
  (ruleset 25363236: a pull request, and the required CI checks V4 names),
  so the opening commit lands on `zoo`, not on `main` as the receiver
  series' opener `f5f5ce2` did, and the series reaches `main` only through
  its PR.
- 2026-10-19, V0 (`024fc66`): the row said every capture's graph equals the
  batch build; Z4 real and recorded do not — their root span is claimed by
  no adapter and reaches the no-trace builder (L2), so the gate pins them at
  4 of 5 (`no (L2)` in SPEC §4.8), the "4 of 5" V2's row already moves to
  5 of 5. Row corrected. The other ten are equal byte for byte. spanweave is
  `0.9.1` at the pin; the showcase table did not move; the new pin grew gate
  A to 30 scenarios, 55 renderings, 1460 pairs (`orphan_siblings`).
- 2026-10-19, V1 (`9641d75`): every answer stays `application/json`
  (`{}` / `{"code":…}`) for a protobuf request too, as §7.2 states; OTLP
  asks a server to answer in the request's encoding, which would mean
  encoding protobuf here, which V1's decision rules out — a thread for the
  close, not a defect of V1. A protobuf body declared `application/json` is
  not sniffed: Z5's body has one line that parses as JSON and is answered
  200 under the partial-read rule; a test pins it.
- 2026-10-19, V2 (`6d78ad9`): claimant vs envelope measured before any
  routing code — 748 unpacked claimed records (8 corpus, 370 zoo JSON, 370
  zoo raw), 748 equal, 0 differ, 0 with an id on one side only; the stop
  did not fire; `tests/test_zoo_gate.py` re-derives it and SPEC §4.2 cites
  it. Z4 is 5 of 5; all twelve captures equal the batch build. Gate A: no
  corpus scenario has an unclaimed span inside an export (a test asserts
  it), so the pair uses the zoo's Z4 recorded capture, read in place, with
  each of the 55 renderings. Threads for the review and the close: (a) the
  router given `adapter=` absorbs a record two adapters claim into the
  no-trace builder with no event — older than this series, pinned in §4.3
  and by a test, to register in TASKS.md; (b) routing tells an unpacked
  record by `isinstance(record, spanweave.read.Unpacked)`, a type spanweave
  SPEC §7 names but `spanweave/__init__` does not export; (c) the
  `no_trace` event carries the library's code, not its `EnvelopeError`
  message; (d) CLAUDE.md's standing rule 1 does not yet name the envelope
  as a source, as §0.6 does.

## 5. Origins

| ID | Origin |
|---|---|
| V0 | `PROBES.md` "The captures", L3's "live, batch and incremental are equal"; spanweave's T0 (the zoo as a fixture) and W0. |
| V1 | L1; spanweave W1. |
| V2 | L2; spanweave `OPEN_QUESTIONS.md` §20 (T1's decision: "the receiver's half is spanweave-live's series"); spanweave-live `SPEC.md` §1.1, §1.5, §4.2, §4.3. |
| V3 | L3, L4; spanweave-live `SPEC.md` §5.3, §5.5, §5.7. |
| V4 | Close. |
