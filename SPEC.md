# SPEC.md — technical specification

**Status: nothing here is frozen.** The version is `0.0.x` and says so on
purpose (`CLAUDE.md`). No name, no event code, no CLI flag and no file layout in
this document is a contract yet. When something freezes, this line changes and
the version changes with it.

`SPEC.md` is the source of truth for *what* to build; `CLAUDE.md` is the source
of truth for *how*, and for the lines that must never be crossed. Where the two
disagree, that is a bug in one of them and a commit of its own.

## 0. What this is

`spanweave-live` is a **receiver**. It takes telemetry in flight — bytes off a
tailed file, a chunk off an exporter, an OTLP/HTTP request body — and keeps a
live [`spanweave`](https://github.com/SigorMatt/spanweave) graph per trace,
handing graphs and deltas to consumers as records arrive.

It is made of four pieces and a transport, each specified in its own section as
its batch lands:

| § | Piece | Question it answers |
|---|---|---|
| 3 | `Framer` | Where does a record end, when the bytes arrive in arbitrary chunks? |
| 4 | `Router` | Which builder does this record belong to? |
| 5 | `Completion` | When is a trace finished? |
| 6 | `Subscriptions` | Who gets told, and what do they get? |
| 7 | Ingest | Where do the bytes come from? |
| 8 | CLI | What does a person type? |

Sections 3 onward are written by the batch that builds them (`WORKPLAN.md`
R1–R7). This document begins with the two sections that constrain all of them:
what the receiver will never do, and the three properties of the library
underneath it that it has to be designed around.

### 0.1 The pin is one pin, and both halves of it are HTTPS

`spanweave` is a dependency pinned to **one commit** in `pyproject.toml`, and
`corpus/` is a git submodule of **that same repository at that same commit**,
read-only, which is where `fixtures/conformance/` is read from. `uv.lock`
records the sha a third time. `tests/test_pins.py` holds all three equal,
because a drift makes the conformance gate compare live graphs against
expectations from a different version of the library than the one it imports,
and the failure that produces points at the code under test instead of at the
pin.

Both halves are fetched over **HTTPS**, not SSH, and that is a requirement
rather than a preference:

- the dependency is `spanweave @ git+https://github.com/SigorMatt/spanweave@<sha>`,
  so an unauthenticated resolve — CI's, a stranger's — works;
- the submodule URL in `.gitmodules` is `https://github.com/SigorMatt/spanweave.git`,
  because CI checks submodules out with the Actions token over HTTPS. An SSH
  URL there fails at **checkout**, on every job, with a message about a missing
  key rather than about a pin.

Both are held by a test (`tests/test_pins.py`), the submodule half included:
until R2a it was stated only in a comment in `.github/workflows/ci.yml`, so a
re-added SSH submodule passed `make check` and failed only at CI.

### 0.2 One typing override, and why it is temporary

`pyproject.toml` carries exactly one mypy override:
`follow_untyped_imports = true` for `module = ["spanweave.*"]`. It is here
because the pinned `spanweave` ships **no `py.typed` marker**, so `mypy
--strict` refuses to analyse it as soon as a receiver module imports it, even
though every line of it is annotated.

The two ways out are not equivalent, which is why the narrow one was chosen.
`ignore_missing_imports` would make `Records`, `Diagnostic` and `read_records`
all `Any`, and then every annotation in this package would type-check
vacuously — a green gate that has stopped asking the question.
`follow_untyped_imports` instead analyses the installed source, so the receiver
is checked against the library's real signatures: a planted
`x: int = read_records(b"")` still errors, as it should.

The marker belongs upstream, and it is on its way there:
`SigorMatt/spanweave` **PR #4**, *"packaging: the package ships py.typed"*
(commit `bea9d44`), open and green at the time of writing and **not yet
merged**. When it merges, the pins of §0.1 move to the new `main` sha and this
override is **deleted** (`WORKPLAN.md` R2c), with a test asserting that no
`follow_untyped_imports` remains. Until then the override is a current fact
stated here rather than a suppression hidden in a config file.

## 1. Non-goals — permanent, not parked

These are not a backlog. Each one is a thing a receiver is *tempted* to grow,
and each one, grown here, would make this project the wrong dependency for
somebody.

### 1.1 No dialect

The receiver never reads a telemetry dialect. A record's trace id, its span id
and its kind come from `spanweave`'s adapters — `spanweave.adapters.classify`
and the claiming adapter's `parse` — and never from a key the receiver looks up
itself. There is no `record["trace_id"]`, no `resourceSpans` walk, no
`"gen_ai."` prefix test, anywhere under `spanweave_live/`.

This is the sharpest of the non-goals because it is the easiest to violate by
accident and the cheapest-looking at the time: one `record.get("trace_id")` in
the router "just for partitioning" works on every JSONL fixture and is silently
wrong for an OTLP container, where the trace id lives on a resource and the
record that carries it is shaped nothing like a span. A second dialect reader,
disagreeing subtly with the first, is a defect no fixture of the receiver's own
can find — the library would be right and the receiver would be wrong, about
the same bytes.

If a record's trace id cannot be had through the adapter surface, the answer is
"no trace id" and a counted event, not a key lookup.

### 1.2 No rules, no semantics

The receiver computes nothing *about* a graph. No roles, no severity, no risk,
no cost, no quality judgement, no scoring, no pass/fail. It hands graphs and
deltas over; a consumer evaluates them. `spanweave`'s neutrality invariant
(`CLAUDE.md` 1 there) is inherited whole: a receiver that scored traces would
have an opinion, and the two reasons not to have one are the same reasons the
library gives.

The consumer side of this is demonstrated rather than asserted: R8 runs
`agentgolden`'s rules, **unchanged**, over per-record deltas, and gets the same
verdicts as the same rules over the batch graph. Live and batch are one model,
and no rule had to move into the receiver for that to be true.

### 1.3 No enforcement

Detection is observation. The receiver never holds a call, never blocks, never
refuses, never injects, never mutates telemetry, and never calls back into the
system it is watching. A gate that acts on what a rule found is a different
component, with a different failure mode and a different safety argument, and
the receiver does not know it exists.

The practical form of this: the receiver's output is files, stdout and
callbacks. It has no side effect that reaches the observed system.

### 1.4 No clock of its own

The receiver has no ambient runtime. The clock, sleeping and listening are
**injected seams** — `now: Callable[[], float]`, `sleep: Callable[[float], None]`,
and a listener factory — bound once by the caller (the CLI binds the real ones)
and fake in every test.

No module under `spanweave_live/` imports `time`, `datetime`, `random`,
`socket`, `threading` or `asyncio`, except a seam file named in the allowlist in
`tests/gates.py`, and the gate fails the build when one does. The allowlist is
empty at R0.

Why a gate and not a convention: completion is a timeout policy (§5), and a
timeout policy tested against the real clock is a test that passes on a fast
machine and flakes on a loaded one. Every such test would be rewritten until it
asserted nothing. One `time.monotonic()` reached for directly is enough to put
the project on that path, and it is invisible in review because it is one line
and it works.

### 1.5 Nothing dropped silently

Not strictly a non-goal — it is the shape every other answer takes. A refusal,
a cap, a late arrival, a truncation, a malformed body, a consumer that raised:
each is an **event with a code**, counted and reported. The receiver's honest
answer to "what did you not handle?" is a number per code, never silence.

This is `spanweave`'s losslessness invariant one layer up. The library's rule is
that no input record vanishes; the receiver's is that no *decision* vanishes.

## 2. The three properties the receiver designs around

`spanweave.read_records` is the seam the receiver sits on, and `SPEC.md` §7
there states three things about it that are not incidental — they are the reason
the receiver's own pieces are shaped the way they are. Quoted, because a
paraphrase would drift:

### 2.1 The reader does not buffer across calls

> **The reader neither buffers nor rejoins across calls**, so a multi-byte
> character split between two chunks is half a character in each — a receiver
> reading bytes in flight splits them on `\n` and keeps the remainder for its
> next call, rather than handing over an arbitrary boundary.
>
> — spanweave `SPEC.md` §7, Inputs

**What it makes ours.** Framing is the receiver's job, not the library's, and
the library will not quietly cover for getting it wrong — it will decode half a
character into `U+FFFD`, report `undecodable_bytes`, and hand back a record that
is subtly not the one that was sent. So `Framer` (§3) owns a remainder buffer,
splits on `\n` itself, hands over complete lines only, and exposes
`pending_bytes` so a caller can see that it is holding something. The whole-body
form (`document`) exists for the same reason from the other side: an OTLP JSON
document must *not* be split, so it is a different method rather than a flag.

### 2.2 Deduplication is per call

> It **raises nothing an unreadable input can cause**: a line that is not JSON
> is a `malformed_record` on the result, a record sent twice is one
> `duplicate_record` and one record, exactly as on a file.
>
> — spanweave `SPEC.md` §7, `read_records`

Read with §2.1: the collapse happens **within one call**, because that is the
only thing the reader can see. Two copies in one chunk are one record and one
`duplicate_record`; two copies in two chunks are two records, and the second
reaches the builder, where it is a node-id collision and a **refusal** —
spanweave `SPEC.md` §10.5, "an exporter resending one span is refused and costs
nothing else".

**What it makes ours.** A re-sent span is normal under at-least-once export, so
the receiver treats a builder refusal as routine and *loud*: `Router` (§4)
records it as a `refused` event carrying the record's index and the library's own
code, counts it, and routes on. It does not retry, does not suppress, and above
all does not grow a dedup cache of its own — a second deduplicator, with a
different window and a different notion of sameness, would disagree with the
library about the same bytes for reasons no fixture could pin.

### 2.3 Reading is cheap; absorbing is not

> **Cheap to read is not cheap to absorb.** A whole export read in one call is
> still one `feed` per span, and a `feed` pays for every key the record touches
> — most of them restated in full (§10.6). Reading is where the container form
> stops mattering; it is not where absorbing becomes free.
>
> — spanweave `SPEC.md` §7, `read_records`

**What it makes ours.** The receiver's cost is in `feed` and in materialization,
not in framing, so that is where its policies live: completion (§5) releases a
builder so a finished trace stops costing memory, `max_traces` (§4) is a cap
with a counted event rather than unbounded growth, and retention (§6) is set
from the longest window a subscriber actually asked for rather than kept "just
in case". A delta is handed out per record because that is what a live consumer
wants; it is not handed out per record *because it is free*.

## 3. Framing — where a record ends

`Framer` answers one question: **the bytes arrived in a chunk nobody chose, so
where does a record end?** It owns a remainder buffer, splits on `\n`, and hands
complete lines to `spanweave.read_records`. It parses nothing, classifies
nothing, and looks inside no line — a record's identity, its trace id and its
kind are the library's (§1.1).

It is the one piece whose failure mode is silent. Framing wrongly does not
raise: the reader decodes half a multi-byte character to U+FFFD, reports
`undecodable_bytes`, and hands back a record that is *subtly not the one that
was sent* (§2.1). That is why this is a module with a corpus-wide test rather
than three lines in an ingest loop.

### 3.1 The surface

```python
class Framer:
    def push(self, chunk: bytes) -> spanweave.Records: ...
    def document(self, body: bytes) -> spanweave.Records: ...
    def flush(self) -> spanweave.Records: ...
    @property
    def pending_bytes(self) -> int: ...
```

`spanweave.Records` is the return type, not a type of the receiver's own: it
already carries exactly the three things a read produced — the records, the
diagnostics, and `skipped_records` — and a wrapper would add a second name for
each. One `Framer` per byte stream; the remainder and the line count are that
stream's, so two streams are two framers. There is no lock and no concurrency
(§1.4): a framer is a pure function of the bytes it has been handed, in the
order it was handed them.

### 3.2 `push` — a chunk of a line-delimited stream

Everything up to and including the **last** `\n` in the buffer goes to
`read_records` as one call; everything after it is kept. A chunk that completes
no line reads nothing and reports nothing — the bytes are in the remainder, not
gone, and `pending_bytes` is where that is visible.

The terminator travels with the lines rather than being stripped, so the reader
is given exactly the bytes a file would have given it; the final empty piece is
a blank line, which it ignores.

Two consequences worth stating because they are the reason the remainder exists
rather than side effects of it:

- A **multi-byte character split across chunks** is never handed over in halves.
  The two halves meet in the remainder before any line containing them is
  complete, so `undecodable_bytes` reports only bytes the input actually holds,
  never the receiver's own chunking.
- A **BOM split across chunks** is likewise whole by the time the reader sees
  it, which is what lets the reader apply its head-of-stream tolerance (§2.1) to
  a stream the receiver is reading in pieces.

The reader's **container detection and deduplication are per call** (§2.1,
§2.2), and a push is one call. So a chunk's complete lines are read as one
input: two identical lines in one chunk are one record and one
`duplicate_record`, and the same two lines split across two chunks are two
records — the second of which is the `Builder`'s refusal (§4), not the framer's
problem. The receiver grows no dedup cache of its own.

Both halves of that are asserted, as each other's control: a cache inside the
`Framer` would make the two-chunk half pass by passing nothing on, and the
`duplicate_record` of the one-chunk half would simply disappear — a diagnostic
lost, which is §1.5 and not only prose. No corpus rendering holds a
byte-identical duplicate line, so the corpus sweep cannot be what holds this.

### 3.3 `document` — a whole body, handed over unsplit

A JSON document is not a record until its closing brace, so a body is read in
one call or not at all. `document(body)` is `read_records(body)`: a **method
rather than a flag on `push`**, because the caller knows which of the two it is
holding and the bytes do not say.

The honest statement of why it is needed: a pretty-printed export pushed in
chunks is lost. Each push hands over a run of lines that are not records, and
every one becomes a `malformed_record` — loudly, which is the point, but the
export is gone. A framer that buffered until something parsed would be the
reader's §2.1 rule reimplemented here, differently, and it would hold a tail
forever on the ordinary line-delimited input it was given.

**Why that is a trap and not merely a rule.** The other half of it is the half
that bites: a body that happens to arrive **whole** reads *identically* to
`document(body)` — the same records, no diagnostic, byte for byte — because the
reader's container detection runs per call and a whole arrival is one call. So
`push` is not "the wrong method for bodies, which fails"; it is the wrong method
for bodies, which **works** on every body small enough to arrive in one piece,
and then loses a whole export the first time one does not. Both halves are
asserted over the corpus' two document renderings
(`tests/test_framing.py::test_a_document_pushed_in_chunks_is_lost_which_is_why_document_exists`),
and the consequence is a standing instruction for the transport batch: **R6
hands POST bodies to `document`, never to `push`** (§7.2).

`document` carries no line offset (§3.5): the body is the whole input as far as
its caller is concerned. It neither reads nor clears the remainder — a body and
a tail are different transports, and neither may eat the other's bytes.

### 3.4 `flush` and `pending_bytes` — the remainder is reported, never dropped

`pending_bytes` is the remainder's length. Non-zero is the **ordinary** state of
a growing file read at an instant: a tail that stops mid-record has not failed,
it has not finished, and calling it `malformed_record` would produce one per
poll on a file that is merely still being written. So a truncated final line is
`pending_bytes > 0` and nothing else until `flush`.

`flush` reads the remainder as the stream's final line and hands back what that
was — a complete record that simply arrived without a `\n` becomes a record; a
truncated one becomes the `malformed_record` carrying its text, which is the
only place that text survives (§1.5). Either way the remainder is read exactly
once and the framer is then holding nothing. An empty remainder reads nothing
and reports nothing: there was no final line, and saying there was would invent
a fact.

**No cap, and that is a gap stated rather than a decision made.** A stream that
never sends a `\n` grows the remainder without bound. `pending_bytes` is what
makes that visible to a caller who wants to act on it; which bytes to refuse and
what to call the event is a policy, and inventing one here is a halt point
(`CONTRIBUTING.md`). The receiver reports; it does not decide.

### 3.5 Diagnostics carry the line's position in the stream

The reader numbers lines **within the call it was given**, which for a push is
the chunk. A diagnostic whose number was 1 because its line happened to open a
chunk is useless: it points at a line of a buffer nobody kept. So each push's
diagnostics are **re-issued with the absolute line offset added** — the number
is the line's position in the whole stream — and `flush`'s remainder is numbered
as the line after every line `push` handed over.

Three rules make that precise:

- The chunk-local number is **replaced, not kept alongside**. How the bytes were
  chunked is the receiver's own doing and says nothing about the input;
  publishing both would leave a reader guessing which to act on.
- A diagnostic that names no line comes back untouched. A `duplicate_record`,
  and a container form's "the input …", have no number to fix, and inventing one
  would be worse than leaving it.
- The re-issued tuple is **re-sorted** by the library's own order
  (`spanweave` `SPEC.md` §5.2 — `(code, node_id, message)`). Renumbering changes
  the message, so a tuple sorted by the old numbers would quietly break a
  property the caller is entitled to. The test for it crosses the **9 → 10**
  digit boundary on purpose: `"line 10 …"` sorts before `"line 9 …"`, so the
  sorted tuple is the reverse of the order the lines arrived in, and a fixture
  that stayed below ten would pass with the sort removed.

The number is read off the front of the reader's message, because a
`spanweave.Diagnostic` carries no line field. That is a limitation of this seam
and it is named here rather than worked around silently; the test asserts the
result against `read_records` of the whole stream rather than against a sentence,
so what is pinned is the rule — the number is absolute — and not the library's
prose.

## 4. Routing — which builder does this record belong to?

`Router` answers one question and holds one thing: **a `spanweave.Builder` per
trace id**, created the first time that trace is seen. A record arrives, the
router asks the library which trace it belongs to, and hands it to that trace's
builder. It does not evaluate the record, score it, hold it, or look at what the
graph came to say — it partitions, and the graphs are the caller's (§1.2, §1.3).

Partitioning is the receiver's job rather than the library's because
`spanweave.Builder` is documented as one builder per trace: "Records of two
traces in one builder are kept and reported exactly as a multi-trace file is,
and partitioning a live stream by trace is the caller's" (`spanweave`
`SPEC.md` §10, `OPEN_QUESTIONS.md` §19). This section is that caller.

### 4.1 The surface

```python
Record = Any  # whatever `spanweave.read_records` yielded

REFUSED = "refused"
REFUSED_AT_CAP = "refused_at_cap"

@dataclass(frozen=True, slots=True)
class Event:
    code: str                    # the receiver's own code, above
    index: int                   # the record's 1-based arrival index
    trace_id: str | None
    spanweave_code: str | None   # the library's code, where the library refused
    detail: str

@dataclass(frozen=True, slots=True)
class Routed:
    index: int
    trace_id: str | None         # None: no trace id, so the no-trace builder
    builder: spanweave.Builder | None  # None only when nothing absorbed it
    version: int | None          # the version the absorption produced
    events: tuple[Event, ...]

def trace_id_of(record: Record) -> str | None: ...

class Router:
    def __init__(
        self,
        *,
        max_traces: int | None = None,
        adapter: str | None = None,
        temporal: bool = True,
    ) -> None: ...
    def route(self, record: Record) -> Routed: ...
    @property
    def trace_ids(self) -> tuple[str, ...]: ...
    def builder(self, trace_id: str | None) -> spanweave.Builder | None: ...
    @property
    def no_trace(self) -> spanweave.Builder: ...
    @property
    def counts(self) -> Mapping[str, int]: ...
    @property
    def routed(self) -> int: ...
```

That block is the whole public surface, and it is declared **exactly** as the
code accepts it. Two things were out of step until R2a and are named here so
the next reader can hold the document to the code rather than the other way
round: `routed` — how many records have been handed to `route` — is public and
was in the prose only, and the `*` was decorative, because the dataclass also
accepted `Router(1, 'openinference', False)` positionally. The settings are
keyword-only now (a test constructs one positionally and requires a
`TypeError`): they are independent knobs with no reading order, and a
positional order would be a contract this document never offered.

`Record` is `Any` and deliberately not a JSON type of the receiver's own:
`spanweave`'s `JsonValue` is itself `Any` and is not exported, and a second,
narrower definition here would be a shape the library never promised.

`adapter` and `temporal` are passed through to every `Builder` the router
makes, so a caller that names a dialect or turns temporal edges off gets the
same thing live as `spanweave.build` gives it in batch. The router reads
neither.

### 4.2 The trace id comes from the adapter surface, never from a key

`trace_id_of(record)` asks `spanweave.adapters.classify(record)` which adapters
claim the record, takes the single claimant, calls that adapter's
`parse([record])`, and reads `trace_id` off the spans it yields. That is the
whole of it. There is no key table, no dialect test, no `record["trace_id"]`,
and no fallback that reads one (§1.1).

Three answers are **no trace id**, and each is the same answer:

- **Nobody claimed the record.** The library's own treatment is an `unknown`
  node plus an `unclaimed_record` diagnostic, and that is what the no-trace
  builder produces, because the record is fed to a real `Builder`.
- **More than one adapter claimed it.** The library refuses an ambiguous
  record rather than guessing (`spanweave` `SPEC.md` §6.1), so there is nobody
  to ask for a trace id. The record goes to the no-trace builder, which raises
  the library's own refusal, and that becomes a `refused` event (§4.4).
- **The claimant reported no single trace id** — no `trace_id` on the spans it
  parsed, or more than one distinct id across them. §1.1 already fixes this
  answer: "If a record's trace id cannot be had through the adapter surface,
  the answer is 'no trace id' and a counted event, not a key lookup." Choosing
  among several would be a policy, and inventing one is a halt point.

A `spanweave.SpanweaveError` raised while classifying or parsing is also "no
trace id". It is **not** swallowed: the record goes to the no-trace builder,
whose `feed` reaches the same code and raises the same refusal, and the event
carries the library's `code` verbatim.

**The cost, stated, and measured.** `classify` runs every adapter's `detect`
over the record and `parse` then translates it a second time — the builder's own
`feed` does both again. So the question a reader asks is how much of routing
that second parse is, and the answer is **not** "half", which is what this
section said until R2a and what the thread that opened it assumed.

Measured twice, independently, on 2000 distinct OpenInference `CHAIN` spans
with `perf_counter` over three repeats: `trace_id_of` costs **20–24 µs** per
record against `Builder.feed`'s **97–131 µs**, i.e. **15.5–17.1 %** of
`trace_id_of + feed`, good to roughly ±3 points and no finer. An upstream
`spanweave.trace_id_of(record)` would remove most of *that*, not half of
routing: it is an **optimisation, not a necessity**, and it gets no batch until
a receiver workload makes routing the cost rather than `feed` and
materialization (§2.3). The thread is registered in `WORKPLAN.md` §3 while the
series runs and in `TASKS.md` once it closes; the number above is here so the
conclusion does not depend on either of them still existing.

It is in any case **not** worked around here, because the only workaround is a
dialect read, and §1.1 says what that costs.

### 4.3 One builder per trace, and the no-trace builder

The first record of a trace creates its `Builder`; every later record of that
trace reaches the same one. `trace_ids` lists the identified traces in **first
arrival order** — the order traces were seen is a fact about the stream, and
sorting it would throw that away; nothing in the graphs depends on it.

The **no-trace builder** is a `Builder` like any other and exists from the
start. It is the receiver's honest place for a record that identifies no trace,
and the point of using a builder rather than a counter is that it carries the
library's own account of what those records were: `missing_trace_id` once per
graph, and `unclaimed_record` per unclaimed record, exactly as a batch build of
the same records reports them (`spanweave` `SPEC.md` §6.1, §7). The receiver
invents no event code for either.

One consequence inherited rather than chosen: a no-trace builder holding
**only** unclaimed records refuses `graph()`, because `spanweave` refuses an
input no adapter can read rather than returning a graph of `unknown` nodes
(`spanweave` `SPEC.md` §6.1, §10.5). The receiver does not paper over that.

### 4.4 A refusal is an event, and routing continues

A re-sent span is normal under at-least-once export (§2.2), so a `Builder`
refusal is routine and loud rather than exceptional: `route` catches
`spanweave.SpanweaveError` from `feed`, records an `Event` with code `refused`
carrying the record's arrival index and the library's `code`, counts it, and
**returns normally**. The next record is routed. Nothing is retried, nothing is
suppressed, and the receiver grows no deduplicator of its own (§2.2).

The refused record is not absorbed — `spanweave` `SPEC.md` §10.5 promises the
builder is left exactly as it was — so `Routed.version` is the builder's
unchanged version, not the version the record would have produced.

### 4.5 `max_traces` is a cap, and the cap is counted

`max_traces` bounds how many identified traces the router holds builders for,
because the receiver's cost is in `feed` and in materialization (§2.3) and an
unbounded stream of trace ids is unbounded memory. At the cap, a record for a
**new** trace produces an Event with code `refused_at_cap` carrying the record's
index and the trace id, counted, and `Routed.builder` is `None`: no builder is
created and the record is not absorbed. It is **refused, in the open** — the
count and the event are the receiver's answer to "what did you not handle?"
(§1.5), and silence would have been the alternative.

A record for a trace the router already holds is never refused at the cap, and
neither is a record with no trace id: the no-trace builder is not a trace, and
counting it against the cap would make "no trace id" the thing that evicts
real ones. `max_traces=None` is no cap.

Which traces to evict, and when, is **not** here: eviction is completion's
business (§5), and a cap that quietly released a live builder would be a
retention policy nobody asked for.

### 4.6 Counts, not a log

The router keeps a count per event code and nothing else. The events of one
record are on that record's `Routed`, where the caller can report them as it
likes (R7 writes each to stderr as one JSON line); the router does not
accumulate them, because an event list grows with the stream and §2.3 is about
exactly that. `counts` is bounded by the number of codes.

### 4.7 Gate A — the central claim

`tests/test_conformance.py` is the claim this project exists to make: **how
records of two traces were interleaved cannot be seen in either trace's
graph.** For every pair of renderings drawn from two different corpus
scenarios, with one of the two relabelled onto a second trace id, the pair's
arrivals are interleaved by a seeded shuffle that preserves each rendering's own
order, pushed through one `Framer` in seeded chunks, and routed; then each
trace's `graph()` must serialize **byte for byte** to `spanweave.dumps` of
`spanweave.build` of that rendering alone.

Two things about the comparison are stated rather than assumed:

- **`meta.source_digest` is dropped from the batch side.** A `Builder` carries
  no digest of an input it never saw (`spanweave` `SPEC.md` §10.4), so the
  digest is the one field that cannot match. It is removed from the *batch*
  graph, and nothing else is normalized on either side.
- **The relabelling is a trace id and nothing else.** Every corpus rendering
  identifies one trace, `t1`, so two renderings fed to one router would share a
  builder and the test would assert nothing. The relabelling is a byte
  substitution of the token `"t1"`, and the test first asserts that every
  occurrence of it in the rendering is a trace-id value — so a corpus where
  that stops being true fails loudly instead of quietly rewriting something
  else.

**What gate A does not catch, said plainly.** It does not catch a router that
reads `record["trace_id"]`. `spanweave.read_records` normalizes an OTLP
container's `traceId` to `trace_id` while unpacking it, so by the time a router
sees a record every corpus rendering — the `otlp_container` ones included —
answers a `trace_id` lookup with exactly what the adapter surface would have
said. The dialect read is caught instead by a record **no adapter claims** that
nonetheless carries a `trace_id` key (`tests/test_routing.py`): the adapter
surface says "no trace id" and the key says `t1`, so a dialect read puts an
`unknown` node in a trace's graph that belongs in the no-trace builder. §1.1's
warning is still right about why the read is wrong; the corpus is simply not
where it shows.

## 5 onward

Reserved, each written by its batch: §5 completion (R3), §6 subscriptions (R4),
§7 ingest (R5 file and stdin, R6 OTLP/HTTP), §8 CLI (R7). A batch adds its
section here in the same commit as its code, and nothing else edits them.
