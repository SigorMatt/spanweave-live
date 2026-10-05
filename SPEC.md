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
`tests/gates.py`, and the gate fails the build when one does. The allowlist was
empty at R0 and is **still empty**: R3 needed no entry for the clock (§5.2) and
R5 needed none for sleeping (§7.1), because a seam with no default is a seam the
caller binds and there is then no import to exempt. R6's listener is the last
candidate.

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
FRAGMENT_TOO_LONG = "fragment_too_long"

@dataclass(frozen=True, slots=True)
class FramingEvent:
    code: str
    line: int      # the fragment's 1-based line number in the stream
    length: int    # how many bytes were handed over as that one line
    detail: str

class Framer:
    def __init__(self, *, max_pending_bytes: int | None = None) -> None: ...
    def push(self, chunk: bytes) -> spanweave.Records: ...
    def document(self, body: bytes) -> spanweave.Records: ...
    def flush(self) -> spanweave.Records: ...
    @property
    def pending_bytes(self) -> int: ...
    @property
    def max_pending_bytes(self) -> int | None: ...
    @property
    def events(self) -> tuple[FramingEvent, ...]: ...
    @property
    def counts(self) -> Mapping[str, int]: ...
```

That block is the whole public surface, declared **exactly** as the code accepts
it — including the `*`, which is real: `max_pending_bytes` is keyword-only, for
the reason §4.1 gives for `Router`'s settings. It is a policy the caller sets,
not a reading order, and a positional slot would be a contract this document
never offered (a test constructs `Framer(64)` and requires a `TypeError`).

`spanweave.Records` is the return type, not a type of the receiver's own: it
already carries exactly the three things a read produced — the records, the
diagnostics, and `skipped_records` — and a wrapper would add a second name for
each. That is also why the framer's own events are **beside** the return value
rather than in it: `events` is the events of the most recent call, reset by
every call, and `counts` is the running total per code, bounded by the number of
codes rather than by the length of the stream (§4.6 made the same choice for the
router). A `FramingEvent` is not a routing `Event` (§4.1) because the two layers
have different facts: a routing event names a record's arrival index, a trace id
and the library's refusal code, none of which the framer has, and a length,
which the router has no field for. One dataclass for both would be four fields
that are `None` wherever they are not the emitter's.

One `Framer` per byte stream; the remainder, the line count, the cap and the
counts are that stream's, so two streams are two framers. There is no lock and
no concurrency (§1.4): a framer is a pure function of the bytes it has been
handed, in the order it was handed them.

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

### 3.4 `flush`, `pending_bytes` and the cap — the remainder is never dropped

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

**The cap is `max_pending_bytes`, and it is the caller's number.** A stream that
never sends a `\n` would otherwise grow the remainder without bound.
`max_pending_bytes=None` — the **default** — is no cap, exactly as R1 shipped,
and the default is the receiver's whole position on the question: how many bytes
of an unterminated line are too many is a policy, and a default number here
would be the receiver carrying a policy of its own (§1.2). `pending_bytes` is
what makes the growth visible to a caller that would rather watch than cap.

What the receiver owns is the mechanism, and it has one rule: **the cap is the
most the framer will keep.** When a push leaves more than `max_pending_bytes` in
the remainder, the remainder is not kept — it is handed to `read_records` as one
line, in the same push, together with whatever complete lines that push also
completed. Three consequences, each of them the point rather than a side effect:

- The bytes are **reported, not dropped** (§1.5). A fragment of a line is a
  `malformed_record` carrying its text, which is the only place those bytes
  survive, and it is counted in `skipped_records`. A fragment that happens to be
  a whole record is a record. Truncating, or discarding the remainder and
  carrying on, are both the one thing this project does not do.
- The framer **emits a `FramingEvent`** with code `fragment_too_long` and the
  fragment's `length`, counted in `counts`. The `malformed_record` says the line
  could not be read; the event says the receiver is why it was read when it was.
  Both, because either alone is a half-truth.
- The framer is then **holding nothing**, so the next chunk reads as an ordinary
  chunk. A cap that wedged the stream it capped would be worse than no cap, and
  a stream whose line never ends is reported fragment by fragment rather than
  once: the caller's number is how often.

The boundary is strict — `>`, not `>=` — because a remainder exactly at the cap
is a remainder the caller allowed. `max_pending_bytes=0` is therefore legal and
means every remainder is read the moment it exists.

**What the cap costs, said rather than hidden.** Once a line is cut into
fragments, the framer no longer knows where that line ended: each fragment is
numbered as a line of its own, and the rest of the real line — when its `\n`
finally arrives — is numbered as the line after it. So line numbers downstream
of a `fragment_too_long` are the framer's count of what it handed over, not the
input's count of its own lines (§3.5 is about the other case, where they agree).
The event is what tells a reader which one they are looking at.

Neither `document` nor `flush` is capped. A body is not a remainder — it arrives
whole or not at all, so there is nothing for a cap to bound and capping it would
truncate an export the caller handed over complete. And `flush` reads whatever is
left whatever its length, because that is what `flush` is for; under a cap there
is never more than the cap left for it to read.

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
    seconds: float | None = None # the duration the event is about, if any (§5.1)
    version: int | None = None   # the version the event is about, if any (§6.1)

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
        completion: Completion | None = None,   # §5
        subscriptions: Subscriptions | None = None,  # §6
    ) -> None: ...
    def route(self, record: Record) -> Routed: ...
    def tick(self) -> tuple[Completed, ...]: ...   # §5.4
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

R3 added two names to that block and one field. `completion` and `tick` are
§5's and are specified there. `Event.seconds` is the one field a completion
event needs that a routing event never had: a `late_arrival` is defined by a
**gap**, and a number a caller can only read out of a sentence is a number the
caller cannot match on (§1.5). It is one optional field shared by the codes
that are about a duration and `None` for `refused` and `refused_at_cap`, which
is why §5 follows this `Event` rather than declaring a type of its own — and
why §3.1's `FramingEvent` still does: a framing event has a length and *none*
of `index`, `trace_id` or `spanweave_code`, so merging that one would be four
fields that are `None` wherever they are not the emitter's, not one.

R4 added `subscriptions` and, for the same reason `seconds` exists,
`Event.version`: §6's three codes are each about a **version**, and §1.5 is only
true where the caller can match on the number instead of reading it out of a
sentence. It is `None` for every code that is not about one. R3's `released`
still states its version in `detail` only; moving it is §5's edit to make and
nothing in R4 needed it.

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

`trace_ids` is the traces the router **holds a builder for**, which is the same
thing until completion (§5): a completed trace's builder is released and its id
leaves the list, and if a late record re-opens it, it rejoins at the end,
because that new builder is the newest one the router made. That is still
arrival order — of builders, which is what the router has — and §5.5 says so
where it can be read next to the event that causes it.

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
retention policy nobody asked for. The two meet in one direction only —
completion releases a builder, which frees a slot, so the next new trace is not
refused — and never in the other: reaching the cap completes nothing and
hurries nothing. A router at its cap with no completion policy stays there, and
`refused_at_cap` is the honest report of that rather than a reason to drop
somebody's live trace.

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

## 5. Completion — when is a trace finished?

Nothing in a live stream says a trace is over. A span is not announced as the
last one, an exporter that has gone quiet may be about to send ten more, and a
trace whose root ended at 12:00:01 can gain a tool span at 12:00:09 under
at-least-once export. So "finished" is **not a fact the receiver can know**, and
a receiver that claimed to know it would be wrong on exactly the traces that
matter.

What the receiver can do is stop holding a builder, and that is all completion
is: **a policy the caller chose about when to stop**, evaluated against a clock
the caller supplied. Three consequences, each of them this section's shape:

- A policy is a **value** the caller constructed, not a rule the receiver
  believes in (§1.2). The receiver evaluates it; it has no opinion about whether
  the trace is really over, and it says `completed` rather than `finished` or
  `complete` for that reason.
- Completion **enforces nothing** (§1.3). It does not hold a record, delay one,
  refuse one or gate anything. A record for a trace the caller's policy already
  completed is absorbed, into a new builder, and reported (§5.5).
- Completion is **bookkeeping and observation**: materialize, optionally write,
  release, count. Every one of those four is an event with a code (§1.5),
  because a builder that vanished from a router with nothing said about it is
  the silence this project does not do.

### 5.1 The surface

```python
QUIET = "quiet"
ROOT_ENDED = "root_ended"
CAP = "cap"

COMPLETED = "completed"
WRITTEN = "written"
NOT_WRITTEN = "not_written"
RELEASED = "released"
LATE_ARRIVAL = "late_arrival"

@dataclass(frozen=True, slots=True)
class TraceState:
    trace_id: str
    now: float                   # the tick's one clock reading
    records: int                 # the builder's version: records absorbed
    first_record_at: float       # when this builder's first record arrived
    last_record_at: float        # when its most recent record arrived
    root_ended_at: float | None  # when an ended root was FIRST seen, if ever

class Policy(Protocol):
    code: ClassVar[str]
    watches_root: ClassVar[bool]
    def fires(self, state: TraceState) -> bool: ...

@dataclass(frozen=True, slots=True)
class Quiet:
    seconds: float

@dataclass(frozen=True, slots=True)
class RootEnded:
    grace_seconds: float

@dataclass(frozen=True, slots=True)
class Cap:
    records: int

def root_ended(graph: spanweave.Graph) -> bool: ...

@dataclass(frozen=True, slots=True)
class Completion:
    def __init__(
        self,
        *,
        policies: tuple[Policy, ...] = (),
        now: Callable[[], float],
        out_dir: pathlib.Path | None = None,
    ) -> None: ...
    def fired(self, state: TraceState) -> Policy | None: ...
    @property
    def watches_root(self) -> bool: ...

# in `routing.py`, beside `Routed`:
@dataclass(frozen=True, slots=True)
class Completed:
    trace_id: str
    policy: Policy
    version: int
    graph: spanweave.Graph | None   # None only where the library refused it
    path: pathlib.Path | None       # where it was written, if it was
    events: tuple[Event, ...]
```

That block is the whole public surface, declared **exactly** as the code accepts
it, `*` included: `Completion`'s three settings are keyword-only for §4.1's
reason, and `now` has **no default**, which is §5.2.

`Completed` lives in `routing.py` next to `Routed` rather than in
`completion.py`, and the reason is layering rather than taste. It carries
routing `Event`s, so putting it in `completion.py` would make completion import
routing while routing imports completion. `completion.py` is therefore the
lower layer and holds only values and pure functions — the policies, the state
they see, `root_ended`, and the codes — and the router is what keeps books,
emits events, writes files and releases builders.

### 5.2 The clock is the caller's, and no module here reads one

`now: Callable[[], float]` is handed to `Completion` by whoever constructs it,
and **nothing under `spanweave_live/` imports `time`** (§1.4). The seam
allowlist in `tests/gates.py` is still empty after this batch, which was the
design goal rather than an accident: a module holding `time.monotonic` as a
default would have earned an allowlist entry, and `now` with no default costs
the caller one argument and costs the test suite nothing. R7's CLI is where the
real clock is bound.

Three rules make the reading deterministic:

- A tick takes **one** clock reading and evaluates every trace against it. Two
  readings inside one tick could complete one trace and not the next for a
  reason no caller could see.
- `route` reads the clock **once per record**, and only when the router has a
  completion policy. A router without one reads no clock at all, which is why
  R2's behaviour — and gate A — is untouched by this batch.
- Every duration here is measured on **that** clock, never on a span's
  timestamps. `Node.started_at` and `Node.ended_at` are the observed system's
  clock as its exporter reported it; comparing them against `now()` would make
  a receiver decision depend on two clocks agreeing, and clock skew would then
  complete traces early or never. The receiver's claim is about what it saw and
  when **it** saw it, which is the only claim it is in a position to make.

### 5.3 The three policies, and the instant each fires

Each is a value, each answers one question about `TraceState`, and the boundary
of each is stated here because "fires at the right time" is the whole of what a
timeout policy is. All three boundaries are **inclusive** — the policy fires at
the first tick at which its condition holds, not the one after.

| Policy | Fires when | `watches_root` |
|---|---|---|
| `Quiet(seconds)` | `now - last_record_at >= seconds` | no |
| `RootEnded(grace_seconds)` | an ended root has been seen, and `now - root_ended_at >= grace_seconds` | yes |
| `Cap(records)` | `records >= self.records` | no |

- **`Quiet(seconds)`** is "no record for this trace for this long". Any record
  the router routed to that trace is activity, **absorbed or refused**: a
  re-sent span is the exporter still talking about this trace, and treating a
  refusal as silence would complete a trace that is plainly still arriving.
  `Quiet(0)` completes a trace on the first tick after any record, which is
  legal and is what "no cap on the caller's policy" means (§1.2).
- **`Cap(records)`** is "this trace has absorbed this many records". The count
  is the builder's own `version`, so there is no second counter to drift from
  it, and a refused record does not count because it was not absorbed
  (`spanweave` §10.5) — it is already reported as `refused` (§4.4).
- **`RootEnded(grace_seconds)`** is the only one that looks at the graph, and
  §5.6 is what it is allowed to look at.

### 5.4 `tick()` — evaluate, then materialize, write and release

`Router.tick()` takes one clock reading, evaluates the policies against every
trace the router holds — in `trace_ids` order, so the result is deterministic —
and returns the traces this tick completed, as `Completed` values. With no
completion policy it returns `()` and reads no clock.

The policies compose as **any-of**: the first policy in the caller's tuple whose
`fires` is true is the one that completed the trace, and it is carried on
`Completed.policy` so a caller can tell `Quiet` from `Cap` without parsing a
sentence. The caller's order is the order, because "first that fires" over a
tuple is a fact the caller can predict and "the strictest" would be the receiver
ranking somebody's policies.

Completing one trace is four steps, in this order, and the events come back on
`Completed.events` in that order:

1. **Say so.** `COMPLETED` names the policy that fired and carries `seconds` =
   how long the trace was open on the receiver's clock (`now -
   first_record_at`). It is first because it is the decision; the three steps
   after it are what the decision caused.
2. **Materialize.** `builder.graph()`, which is the batch graph of what was
   absorbed (`spanweave` §10). It can refuse — a builder holding only records no
   adapter claimed refuses rather than returning a graph of `unknown` nodes
   (§4.3) — and then `Completed.graph` is `None` and the refusal is reported by
   step 3 rather than raised. `tick()` raises nothing a record can cause, for
   `route`'s reason (§4.4). That refusal is, today, **unreachable** through this
   surface and the handling is deliberately kept anyway: a builder refuses a
   graph only when nothing in it was claimed (§4.3), and a trace the router
   identified has at least one claimed record by construction — the trace id came
   from a claiming adapter (§4.2). So no test covers it, which is said here
   rather than left for a reader to discover: `graph()`'s refusals are the
   library's to define, a pin move can add one, and the receiver's answer to a
   new one should be a `not_written` event and not a traceback that loses every
   other trace it was holding.
3. **Write, if the caller named a directory.** `spanweave.dump(graph, path)`
   into `out_dir`, and `WRITTEN` with the path. Three things stop a write, and
   each is `NOT_WRITTEN` with a `detail` saying which: the graph was refused in
   step 1 (`spanweave_code` carries the library's code); the trace id is not
   usable as **one** path component — it is empty, it is `.` or `..`, or it
   contains a separator or a NUL — because a trace id is untrusted input
   (`CLAUDE.md` 9) and a file named from it must not be able to leave the
   directory the caller named; or the write itself failed (`OSError`, reported
   verbatim). A receiver that died on one unwritable file would lose every other
   trace it was holding, and a receiver that wrote outside the named directory
   would be doing something the caller never asked for. `out_dir` is created if
   it does not exist, with its parents.
4. **Release.** The builder is dropped — that is the point of the whole section
   (§2.3: a finished trace should stop costing memory) — and `RELEASED` carries
   the version released. `router.builder(trace_id)` is `None` afterwards and the
   id leaves `trace_ids` (§4.3).

A router holding subscriptions (§6) has a **fifth** step after those four, and it
is bookkeeping rather than a decision: the released trace's subscriber cursors are
forgotten, and each subscriber whose cursor was behind the released version gets
one `delta_unsent` on the same `Completed` (§6.5). A router without
subscriptions has exactly the four steps above.

`Event.index` on all of these is the router's arrival count at the tick — how
many records had been routed when the tick ran. A tick is not caused by a record
and there is no record index to report; the arrival count is the honest nearest
thing and it is what lets a caller place the tick in the stream.

The **no-trace builder is never completed**, for §4.5's reason: it is not a
trace. Releasing it would throw away the library's own account of the records
that identified none (§4.3) on a timeout that was about something else.

### 5.5 A late arrival is an event, and the written file is never touched again

A record for a trace that was completed opens a **new builder** and is absorbed
into it, and `route` reports `LATE_ARRIVAL` with the trace id and `seconds` =
the gap between the completion and this arrival on the receiver's clock. The
record is not refused, not dropped and not held: the caller's policy said stop
holding a builder, and it did not say stop receiving telemetry (§1.3).

One case does not re-open: a router **at `max_traces`** has no room for the new
builder, so the record is `refused_at_cap` (§4.5) and there is no late arrival to
report, because nothing was re-opened. The cap's event is the report, the trace
stays completed, and a later record that *is* admitted carries the gap from the
original completion — which is still the true gap.

The new builder starts at version 0 and is the newest builder the router holds,
so the id rejoins `trace_ids` at the end (§4.3). Its `Cap` and `Quiet` are its
own: this generation's records, this generation's silence.

**The file already written is not rewritten and not appended to.** If this
second generation completes too, it is written beside the first, not over it:
generation 1 is `<trace_id>.json` — the name §8's CLI documents — and generation
*n* > 1 is `<trace_id>.<n>.json`. The reason is §1.5 read the other way round:
the first file is a report the receiver already made about records it had, and
editing it would make the receiver's output depend on what arrived *after* it
said that. Two files are two honest statements; one overwritten file is a lost
one. A reader who wants the whole trace folds them, and the gap in the
`late_arrival` event is what tells them there is something to fold.

**What remembering a completion costs, stated rather than hidden.** The gap and
the generation are facts about a trace whose builder is gone, so the router keeps
a small record per trace id it has ever held — four floats, an int and a flag,
and never a graph or a builder. Releasing therefore returns the materialization
and the absorbed records, which is where this project's cost is (§2.3), and not
quite everything: that record is **unbounded in the number of distinct trace ids
a stream completes**. A receiver running for a month would hold one per trace it
ever saw. That is said here because `max_traces` (§4.5) does *not* bound it — it
bounds builders — and because the fix is a policy for **forgetting** a completed
trace, which is a number somebody has to choose and so is a decision rather than
this section's to invent (§1.2, and the same reasoning R1 applied to the framer's
cap before §3 decided it). A caller that cannot afford it today builds a new
`Router` per window; what it loses by doing that is the `late_arrival` gap, which
is the thing the record is for.

### 5.6 What a policy may look at, and what it may not

`TraceState` has six fields and they are a trace id, a clock reading and four
numbers. There is deliberately **no span, no node, no name and no kind** on it:
a policy may not consult what a record meant, what a tool was called or what a
graph came to say, because that would be the receiver holding a rule (§1.2) and
a completion policy that fired on `name == "final_answer"` would be a detector
with a timeout. A test holds `TraceState`'s field set to exactly those six.

`RootEnded` is the one policy that needs the graph, and it reads **structure the
graph already states**, through `spanweave`'s public surface, never a dialect
(§1.1) and never a definition of its own:

- A **root** is a node with no incoming `parent` edge and no `orphan_parent`
  diagnostic naming it. Both halves are the library's: "a record that names no
  parent at all is a **root**, and a root is not a truncated trace" and
  "`orphan_parent` reports a parent the record **named** and this input does not
  carry" (`spanweave` §4.0). The second half is what makes this usable live,
  where a trace's root arriving after its children is the ordinary case
  (`spanweave` §10.6): a child whose parent has not arrived yet has no `parent`
  edge either, and counting it as a root would complete traces whose real root
  is still in flight. Only `parent` edges are read — `call_result`, `data`,
  `link` and `temporal` assert something else, and `temporal` is derived.
- **Ended** is `node.ended_at is not None`: the span reported an end. A dialect
  that reports no end time therefore never satisfies `RootEnded`, and that is
  the honest answer rather than a guess — such a caller wants `Quiet`.
- `root_ended(graph)` is true when the graph has **at least one** root and
  **every** root has ended. A trace can have several roots (nodes with no parent
  are siblings at trace root, `spanweave` §4.3), so "any" and "all" are a real
  choice and this is the conservative one: with "any", one finished sibling would
  complete a trace whose other top-level operation was still running. A graph
  with no root at all — every node an orphan — is **not** ended, because there is
  nothing there whose end could mean the trace's end.

`root_ended_at` is recorded at the **first tick that sees it**, and then never
recomputed: the grace runs from when the receiver saw the root end, not from the
span's own `ended_at` (§5.2), and not from the second tick that noticed the same
thing.

### 5.7 What `RootEnded` costs, said rather than hidden

Deciding from the graph means materializing the graph, and §2.3 is that
materialization is where this project's cost is. Three things keep it bounded,
and they are the reason this is affordable rather than an argument that it is
free:

- The pinned `Builder` **caches** its graph until the next `feed`
  (`spanweave/api.py`, `Builder.graph`), so a tick on a trace that has absorbed
  nothing since the last tick materializes nothing. Stated as a property of the
  pin rather than of the contract, deliberately: `spanweave` §10.2 promises the
  opposite — "`graph()` sorts the nodes and indexes them afresh every time it is
  asked" — so this is a cost the pin happens to spare us and not a guarantee to
  build a policy on. Nothing here is *correct* because of it.
- The graph is materialized only while `root_ended_at` is `None`. Once an ended
  root has been seen, the grace is arithmetic on two floats.
- It happens only when a `RootEnded` is in the caller's tuple. `Completion`
  exposes that as `watches_root`, and a router with only `Quiet` and `Cap` never
  calls `graph()` until it completes something.

A graph the library **refuses** while a tick is evaluating `RootEnded` is "no
root seen yet", and it is not an event. (Unreachable today, for step 2's reason,
and handled for step 2's reason.) The alternative is one event per tick for
the life of the stream, which is the unbounded accumulation §4.6 exists to avoid,
and the condition is not hidden by leaving it out: it is permanent, it is the
library's own answer, and the caller meets it the moment it asks that builder for
a graph. Nothing was dropped — a decision was not made, and the trace stays open.

## 6. Subscriptions — the deltas go out, and nothing is concluded about them

A consumer registers a callback; after every **absorbed** record the router hands
it what changed. That is the whole of this section, and the three things it is
careful not to be follow from §1:

- It is a **fan-out, not an evaluation** (§1.2). The receiver hands over a
  `Delta` and the builder it came from. What the consumer concludes — a rule, a
  score, a verdict, a cost — is the consumer's, and nothing here looks at the
  delta's contents. There is no filter by meaning: a subscriber narrows by
  **trace id** and by **how often**, which are facts about the stream, and by
  nothing else.
- It **enforces nothing** (§1.3). A consumer that raises does not stop the
  record, does not stop the other consumers and does not stop the stream.
- It is **not silent** (§1.5). A callback that raised, a delta the journal could
  no longer produce, and a window a released builder took with it are each an
  `Event` with a code, counted on the router.

### 6.1 The surface

```python
CONSUMER_ERROR = "consumer_error"
DELTA_UNAVAILABLE = "delta_unavailable"
DELTA_UNSENT = "delta_unsent"

@dataclass(frozen=True, slots=True)
class Update:
    trace_id: str | None            # None: the no-trace builder (§6.3)
    version: int                    # the version the absorbed record produced
    since: int                      # the window's lower end: `delta(since=...)`
    delta: spanweave.Delta
    builder: spanweave.Builder      # ask it for `graph()`; nothing here does

Consumer = Callable[[Update], None]

@dataclass(frozen=True, slots=True)
class Subscription:
    consumer: Consumer
    trace_id: str | None            # None: every builder this router feeds
    every: int                      # 1 is per-record; N is "every N versions"
    order: int                      # registration order, 0-based (§6.2)

@dataclass(frozen=True, slots=True)
class Delivery:
    subscription: Subscription
    since: int

class Subscriptions:
    def subscribe(
        self,
        consumer: Consumer,
        *,
        trace_id: str | None = None,
        every: int = 1,
    ) -> Subscription: ...
    @property
    def registered(self) -> tuple[Subscription, ...]: ...
    def covering(self, trace_id: str | None) -> tuple[Subscription, ...]: ...
    def window(self, trace_id: str | None) -> int | None: ...
    def seen(self, subscription: Subscription, trace_id: str | None) -> int: ...
    def due(self, trace_id: str | None, version: int) -> tuple[Delivery, ...]: ...
    def released(self, trace_id: str, version: int) -> tuple[Delivery, ...]: ...

# in `routing.py`:
class Router:
    def __init__(
        self,
        *,
        max_traces: int | None = None,
        adapter: str | None = None,
        temporal: bool = True,
        completion: Completion | None = None,      # §5
        subscriptions: Subscriptions | None = None,  # this section
    ) -> None: ...
```

That block is the whole public surface, declared **exactly** as the code accepts
it. `Event` gains one more optional field for it — `version: int | None` — for
§4.1's reason: the three codes above are all about a **version**, and a number a
caller can only read out of a sentence is a number it cannot match on. R3's
`released` keeps its version in `detail`; moving it is §5's edit and nothing
here needed it.

`subscriptions` is a mutable registry rather than a frozen value, which is what
makes it unlike `completion` (§5.1): a policy is a value the caller constructed,
while a subscription list is something consumers join. It is handed to the router
and the caller keeps its reference — `router.subscriptions.subscribe(...)` and
`subs.subscribe(...)` are the same call. A router with `subscriptions=None` fans
nothing out, computes no delta and touches no builder's retention, which is
exactly what R2 and R3 were: **gate A is untouched by this section**.

`Subscriptions` is the lower of the two layers, as `completion.py` is (§5.1): it
holds the values, the registry, the cursors, and the two pure questions "who is
due?" and "how much journal does this trace need?". It emits no events and
imports nothing from `routing.py`. The router is what calls a consumer, catches
what it raises, and keeps the books — because events are a router's to make.

### 6.2 Per-record and `every=N` are one mechanism

A subscription's cursor for a trace is the version it was last handed. A
subscriber is **due** when `version - cursor >= every`, and the delta it gets is
`delta(since=cursor)`. Per-record mode is therefore not a second code path: it is
`every=1`, where the cursor is always `version - 1`, so `delta(since=version - 1)`
— the per-record mode `spanweave` §10.6 names — falls out of the general rule
rather than sitting beside it. A version moves by exactly one per absorbed
record, so an `every=N` subscriber is delivered to at versions `N`, `2N`, … and
each window is exactly `N` wide.

**Only an absorbed record fans out.** A refused record is not absorbed and the
version does not move (§4.4), so there is nothing that changed to report, and
reporting `delta(since=version - 1)` anyway would hand the *previous* record's
difference over a second time. The refusal is already an event. A record refused
at `max_traces` (§4.5) has no builder at all.

**The iteration order is registration order**, 0-based on `Subscription.order`,
and it is the order consumers are called in, for every record, in every process.
It is a fact the caller controls and can predict, which is the same reason §5.4
gives for taking the caller's policy tuple in the caller's order. Every
alternative is worse: `id()` and `hash()` are not stable across processes (§1.8),
sorting on a callback's name or module would rank consumers by something nobody
chose, and a `set` has no order to speak of. A consumer that must run after
another registers after it.

A delta is computed **once per distinct `since`** in a fan-out and handed to
every subscriber due at that window. A `Delta` is a frozen value, so sharing one
is not sharing state, and two subscribers at the same window would otherwise pay
for the same fold twice (§2.3).

**A subscriber that raised still advances.** Its cursor moves to the delivered
version like everybody else's, and the receiver does not re-send on the next
record. Isolation is not a retry queue: re-sending would make one consumer's
failure change what another consumer sees, and a receiver that retried would be
holding a policy nobody asked it for (§1.2, and §2.2's reasoning about growing a
mechanism of our own beside the library's).

### 6.3 What "all traces" includes, and why it is not §5.4's answer

`trace_id=None` subscribes to **every builder the router feeds, the no-trace
builder included**, and such an `Update` carries `trace_id=None`. That is
deliberately *not* the answer §4.5 and §5.4 give for the cap and for completion,
where the no-trace builder "is not a trace", and the difference is that those two
are **destructive** and this one is not: counting it against the cap would evict
real traces, and completing it would throw away the library's own account of the
records that identified none (§4.3). Reporting it throws nothing away — and
leaving it out would mean the receiver absorbed a record, its graph changed, and
a consumer that asked for everything was told nothing, which is the silence §1.5
exists to refuse.

A subscription naming a trace id receives that trace's updates and no others.
There is no way to subscribe to the no-trace builder *alone*: a consumer that
wants only those reads `update.trace_id is None` itself, and inventing a sentinel
for it would be a surface nobody has asked for.

A late arrival (§5.5) opens a **new builder** whose versions start at 0, so every
cursor for that trace is back at 0 too — this generation's deltas, as §5.5 says
of this generation's records and silence. The first update of the new generation
is `since=0`, exactly as the first update of the first one was.

### 6.4 Retention is the hungriest subscriber's window, and no more

A builder's journal is what `delta` folds, and keeping it is what costs memory
(`spanweave` §10.8, which makes retention the caller's policy "because only the
caller knows how far behind its consumers run"). This section is that caller, and
it knows the answer exactly:
`builder.retain(max(subscription.every for subscription in covering(trace_id)))`,
applied after a fan-out. `window(trace_id)` is that number.

It is the **longest window any covering subscriber asked for**, so the oldest
`since` the journal can still answer is the oldest one that is still going to be
asked about, and one version older than that is dropped. An `every=1` subscriber
alone keeps one version; add an `every=50` subscriber and fifty are kept, because
that one is going to ask for fifty.

Three boundaries of that rule, each chosen rather than fallen into:

- **No covering subscriber means retention is not touched at all** — not set to
  `0`. `Routed.builder` is public, so a caller may be folding deltas off a
  builder the router knows nothing about, and narrowing a journal it never
  promised to narrow would break that caller silently. With
  `subscriptions=None`, or with every subscription naming other traces, a builder
  keeps the library's own default (`"all"`).
- **It is per trace, not per router.** A subscriber for `t1` does not make `t2`
  keep fifty versions, because "and no more" is half of the claim.
- **It is applied after the fan-out**, never before, so the window a subscriber
  is being handed right now cannot be trimmed out from under it; and it is
  applied when the window **changes** rather than once per record, which is both
  cheaper and the safer of the two. Retention is the router's or the caller's and
  not both: a caller that narrows a `Routed.builder`'s journal itself has taken
  the policy over, and a router that re-widened it every record would be
  claiming entries that caller has already dropped — the one way this could have
  produced a traceback rather than the `delta_unavailable` event of §6.5. A new
  generation after a late arrival (§5.5) is a different builder with a journal of
  its own, so the window is applied to it afresh.

**What this costs, stated rather than hidden.** This section adds **no**
unbounded growth, and bounds one that was already there: a `Builder` retains
`"all"` by default, so every router since R2 has held one journal entry per
absorbed record, and a trace with a subscriber on it now holds a fixed number
instead. The cursors are bounded too — one `int` per subscription per trace the
router **currently holds a builder for**, forgotten when the builder is released
(§6.5), so `max_traces` bounds them. The unbounded cost this receiver does have
is the one §5.5 names and does not pretend to have fixed: the per-trace-id book
that outlives completion, awaiting a forgetting policy. Nothing here makes it
worse, and nothing here depends on how it is settled.

### 6.5 The three codes, and what each refuses to be silent about

- **`consumer_error`** — a callback raised. The exception is caught, an `Event`
  with the trace id and the version is recorded and counted, **the remaining
  subscribers are called**, and the record stays absorbed. Isolation is not
  suppression: nothing swallows it, and `detail` carries the exception's type and
  text, because a consumer error that reached no report would be the receiver
  deciding on somebody's behalf that it did not matter. Only `Exception` is
  caught — a `KeyboardInterrupt` or a `SystemExit` is not a consumer's failure to
  isolate, and catching it would make the receiver un-interruptible.
- **`delta_unavailable`** — `builder.delta(since=...)` was refused, which is
  `spanweave`'s `delta_unavailable` for a version retention dropped. §6.4's rule
  makes this unreachable for a builder whose retention the router sets, so the
  way to reach it is for a caller to narrow the retention of a `Routed.builder`
  itself. That is a legal thing for a caller to do, and the honest answer is this
  event — carrying the library's own code — rather than a traceback that loses
  every other subscriber and every later record. The subscriber is not called,
  because there is nothing to call it with; nothing approximate is offered in its
  place, for the library's own reason.
- **`delta_unsent`** — a trace was completed (§5.4) while a subscriber's cursor
  was behind its final version, so there is a window that subscriber could have
  asked for and never will: the builder is released and the journal goes with it.
  One event per such subscriber, carrying the trace id and the version released,
  on `Completed.events`. It is a report and not a delivery: handing out a final
  partial window at completion would be a flush policy the caller never asked
  for (§1.2), and an `every=50` subscriber would then get one window of 50 and
  one of 3 with nothing saying which was which. An `every=1` subscriber is never
  behind, so this code only ever concerns a coarser one.

Completion therefore has a fifth step after §5.4's four, conditional on the
router holding subscriptions: the released trace's cursors are forgotten, and
each one that was behind is a `delta_unsent` on the same `Completed`.

### 6.6 The claim this section is tested against

**Folding every delta a subscriber received onto its first graph gives the final
graph, byte for byte.** That is `spanweave` §10.6's own promise read through the
receiver — the corpus asserts it per builder (`FIXTURES.md` §4) and here it is
asserted per *subscriber*, over the deltas a fan-out actually chose to send, at
`every=1` and at `every=N`.

It is stated as "its first graph" rather than "an empty graph" because there is
no graph at version 0 to fold onto: an empty builder refuses (`spanweave` §10.5),
so the first update of a generation is `since=0` and has nothing beneath it. The
first delta is therefore accounted for differently and not skipped: what it adds
**is** the whole of the graph it produced, and the test asserts that too, so
every delta a subscriber received is used by the claim.

The second test is isolation: three subscribers, the middle one raising, and both
others called with the same update — which is what a fan-out that stopped at the
first failure would fail, and what a fan-out that merely logged and continued
without an event would also fail, because the event is asserted with its trace id
and version.

## 7. Ingest — where the bytes come from

Everything above this section is given bytes or records by somebody. This is the
somebody. An ingest answers one question — **how do the bytes reach the
framer?** — and knows nothing else: it does not look inside a chunk, does not
know what a record is, and never routes one. `Framer` (§3) decides where a record
ends, `Router` (§4) decides where it goes, and an ingest hands over chunks and
hands back what the framer said about them.

§7.1 is the two sources that are files, and is R5's. §7.2 is the OTLP/HTTP
endpoint and is **R6's**, reserved here and written by that batch; §8 is the CLI
(R7), which is where the real `time.monotonic`, the real `time.sleep` and the
real listener are finally bound.

### 7.1 `tail` and `stdin` — a growing file, and a pipe

```python
TRUNCATED = "truncated"
ROTATED = "rotated"
VANISHED = "vanished"
REOPEN_FAILED = "reopen_failed"
DEFAULT_CHUNK_BYTES = 65_536

class Tail:
    def __init__(
        self,
        path: str | os.PathLike[str],
        *,
        now: Callable[[], float],
        sleep: Callable[[float], None],
        poll_seconds: float,
        start: int = 0,
        framer: Framer | None = None,
        chunk_bytes: int = DEFAULT_CHUNK_BYTES,
        until: Callable[[], bool] | None = None,
    ) -> None: ...
    def __iter__(self) -> Iterator[spanweave.Records]: ...
    @property
    def framer(self) -> Framer: ...
    @property
    def offset(self) -> int: ...
    @property
    def polls(self) -> int: ...
    @property
    def reads(self) -> int: ...
    @property
    def events(self) -> tuple[Event, ...]: ...
    @property
    def counts(self) -> Mapping[str, int]: ...

def tail(path, *, now, sleep, poll_seconds, start=0, framer=None,
         chunk_bytes=DEFAULT_CHUNK_BYTES, until=None) -> Tail: ...

def stdin(stream: BinaryIO | None = None, *, framer: Framer | None = None,
          chunk_bytes: int = DEFAULT_CHUNK_BYTES) -> Iterator[spanweave.Records]: ...
```

That block is the whole public surface, declared exactly as the code accepts it.
Everything after `path` is keyword-only, for §3.1's and §4.1's reason: these are
seams and policies the caller binds, not a reading order, and a positional slot
would be a contract this document never offered.

**`tail` returns a `Tail`, and `stdin` is a generator**, which is the one place
this section's shape is not symmetric. The asymmetry is forced and it is the
framer's own (§3.1): the yielded value is `spanweave.Records` and stays that way,
so a tail's events have to ride **beside** the yields — and a bare generator has
nowhere to put them. A pipe cannot be truncated or rotated, so `stdin` has no
events to carry and needs no object to carry them. Both are iterated **once**, and
a second iteration of a `Tail` **raises**: the framer, the offset and the line
count are that stream's, so an "again" would resume the first iteration while
looking like a fresh start. One `Tail` per file, as one `Framer` per byte stream
(§3.1). Reading one looks like this:
`for records in tail(path, now=…, sleep=…, poll_seconds=…)`.

**One yield per read, including a read that completed no line.** "Nothing
arrived" and "nothing was completed" are different answers, and
`Framer.pending_bytes` is where the second one is visible (§3.4). A tail that
swallowed the empty result would make a caller unable to tell a quiet file from
a file in the middle of a record.

`framer` is injected rather than built in, so the caller sets the remainder's cap
(§3.4) and keeps a handle on `pending_bytes`. `chunk_bytes` bounds one `bytes`
object per read and nothing else: it is not a policy about content, and a read
that returns fewer bytes than asked for is the ordinary way a file says "that is
all for now" — **not** an event, because an event there would be an event per
poll on a file that is merely still being written.

`start` is the offset to begin at, and `0` — the whole file, then everything
after it — is the default, because a receiver's first question about a file is
what is in it. A caller that wants only new bytes passes the file's current size.

`until` is the caller's stop condition, asked once before each poll; `None`
follows forever. It is the caller's because "stop after this long" is a policy
(§1.2) and because a test needs a stop that is not a timeout.

#### The clock and the sleeping are the caller's, and the allowlist stays empty

`now` and `sleep` have **no defaults**, exactly as `Completion.now` has none
(§5.2). So **no module under `spanweave_live/` imports `time`, and the seam
allowlist in `tests/gates.py` is still empty after this batch** — R5 was the
batch R0 expected to need the first entry for `sleep`, and it does not, for the
same reason R3 did not need one for the clock: a parameter with no default costs
the caller one argument and costs the test suite nothing, while a module holding
`time.sleep` as a default would have to be exempted from the gate forever. R7's
CLI binds the real pair.

What that buys is the only kind of tail test worth having. The file is written
**when the tail sleeps**, in the test's own scripted order, so "it read the bytes
appended between these two polls" is a fact the test states rather than a race it
hopes to win. A tail tested against the real clock asserts that the writer got
there in time, which is a property of the machine, and such a test gets tuned
until it asserts nothing.

#### Three things that are not growth, and how each is detected

Each is an `Event` (§4.1) — **routing's**, not a type of its own. R2b split
`FramingEvent` off because framing is *below* routing and a framing event has a
length and none of a routing event's facts; ingest is *above* routing, so there
is no upward import to avoid and the facts fit. `index` is how many chunks this
source had handed to its framer when the event happened (§4.1's reading, one
layer down), `seconds` is how long the tail had been reading the content it is
leaving, and `offset` — the one field this batch added, as R3 added `seconds` and
R4 added `version` — is where in that content it had read to.

- **`truncated`.** `os.fstat` of the **open handle** says the file is shorter
  than the offset the tail has reached. The content the tail was reading is gone,
  so it seeks to 0 and reads the new content from the start. The check is made
  **before** each poll's reads, not after them, so a file truncated and regrown
  to less than the old offset is still caught.
- **`rotated`.** `path.stat()` and `os.fstat` of the open handle disagree about
  `(st_dev, st_ino)`: the path now names a different file. The tail reopens **by
  path**, at 0. It is checked only on a poll that **read nothing**, so every byte
  written to the old file before the rename is handed over first — that honesty
  costs one poll and is what makes "a rotation loses nothing" true.
- **`vanished`.** `path.stat()` raises: the path names nothing. The open handle
  is **kept and still read**, because on a POSIX system an unlinked or renamed
  file is still the file the tail holds and the bytes already written to it are
  still owed. Reported **once per vanishing**, not once per poll: how many times
  the path disappeared is a fact about the file, while how many polls found it
  gone is a fact about the caller's `poll_seconds` and would grow without bound
  (§4.6).
- `reopen_failed` is the narrow fourth: a rotation was seen and the new path
  could not be opened. The replacement is opened **before** the old handle is
  closed, so the tail keeps following what it already had rather than following
  nothing, and the next poll tries again. Reported once per failure, for
  `vanished`'s reason.

**`(st_dev, st_ino)` is read, not chosen.** "The same file" is the operating
system's own answer, which is a platform fact of the kind this document may
state; a *policy* about what should count as the same file — a size heuristic, a
name pattern, a modification time — would be the receiver inventing a rule
(§1.2) and would have been a halt. None is invented here.

**What is not detectable, said rather than claimed away.** A file truncated and
then regrown **past** the old offset between two polls is indistinguishable from
growth: the size is larger than the offset and no byte of the evidence survives.
The tail will read from the middle of the new content and the records it reads
will be whatever is there. `poll_seconds` is how narrow that window is, and it is
the caller's number. The receiver's answer to this is the honest one — it is
written down — and not a heuristic that would be wrong in a different way.

#### The remainder at a restart is reported, never joined

A truncation or a rotation happens while the framer may be holding an incomplete
final line. Those bytes belong to content that no longer exists, so the restart
**flushes** the framer: the fragment comes back as the `malformed_record`
carrying its text, counted in `skipped_records`, which is the only place those
bytes survive (§1.5, §3.4). Keeping the remainder instead would hand the reader
one line made of two files, and the record it produced would be a record nobody
wrote — the §3 failure mode (a record that is *subtly not the one that was
sent*) reached through the back door.

Two consequences of there being one framer per tail rather than one per file,
both stated because they are the kind of thing a reader is entitled to find
written down:

- **Line numbers are the tail's count, not the file's.** The framer numbers the
  lines it has handed over (§3.4 made the same point about a cut line), so after
  a restart its numbers continue rather than going back to 1. The `truncated` or
  `rotated` event, with its offset, is what tells a reader where the file's own
  count began again.
- **A tail does not flush when it stops.** Its stop is the caller's `until`, and
  that is not end of input: a growing file read at an instant ordinarily ends
  mid-record (§3.4). So the remainder is left where it is visible —
  `Tail.framer.pending_bytes` — and a caller whose own stop *is* end of input
  calls `flush()`. `stdin` is the other way round and flushes itself, because
  **EOF is end of input**: the last line of a pipe that closed without a `\n` is
  a record only the flush can produce. That final yield is always made, even when
  the remainder was empty, because "the stream ended" is the one thing a caller
  cannot read off the chunks.

An open that fails **at the start** is not an event: it raises. The first open is
the caller's claim that there is a file at that path, and "wait for a file to
appear" is a retry policy the receiver does not carry (§1.2). Everything that
happens to the file *after* that is an event, which is the line this section
draws.

#### What this section is tested against

`tests/test_ingest.py`, and its central test is **gate A's comparison reached
through a file**: every line-delimited corpus rendering is written to a file in
seeded random chunks — appended only while the tail is asleep — and each trace's
`graph()` must serialize byte for byte to `spanweave.dumps` of `spanweave.build`
of that rendering, using gate A's own loader, chunker and comparison
(`SPEC.md` §4.7). A second loader or a second comparison here would be a weaker
gate wearing the same name, so there is neither.

Truncation and rotation are then asserted as **two contents in one file**: the
file holds one scenario's rendering, is emptied (or rotated away), and then holds
a second scenario's rendering relabelled onto a second trace id — and **both**
graphs must come out exactly, which is what a tail that treated truncation as
growth cannot do, because it would read at an offset the new content never had.
The named mutation for this section is that one: `truncated` never fires, and the
test fails on the missing event, on the second trace's graph, and on the offset.

### 7.2 The OTLP/HTTP endpoint

Reserved for R6, written by that batch: stdlib `http.server` only, one handler
for `POST /v1/traces`, bodies to `Framer.document` and **never** to `push`
(§3.3), and the listener factory injected so the tests bind a loopback socket on
port 0. Nothing under `spanweave_live/` opens a socket before that batch.

## 8 onward

Reserved: §8 CLI (R7). A batch adds its section here in the same commit as its
code, and nothing else edits them.
