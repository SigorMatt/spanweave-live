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
  property the caller is entitled to.

The number is read off the front of the reader's message, because a
`spanweave.Diagnostic` carries no line field. That is a limitation of this seam
and it is named here rather than worked around silently; the test asserts the
result against `read_records` of the whole stream rather than against a sentence,
so what is pinned is the rule — the number is absolute — and not the library's
prose.

## 4 onward

Reserved, each written by its batch: §4 routing (R2), §5 completion (R3), §6
subscriptions (R4), §7 ingest (R5 file and stdin, R6 OTLP/HTTP), §8 CLI (R7). A
batch adds its section here in the same commit as its code, and nothing else
edits them.
