# CLAUDE.md — operating contract

This file governs how Claude Code works in this repo. Read it at the start of
every session, in full. `SPEC.md` is the source of truth for *what* to build;
this file is the source of truth for *how*, and for the lines that must never be
crossed. A cold session should be able to work here from this file alone.

`TASKS.md` is the registry **between** series and the second file a cold session
reads: one line per batch with the commit that closed it, the decisions the
maintainer took, the facts the batches measured, and the disposition of every
finding of every review. While a series is open there is also a `WORKPLAN.md` —
the orchestrator's execution state, which batch is next and what it must
contain. **It is edited only by the orchestrator**, and a sub-agent executing a
batch never edits it. It exists only for the life of a series and is deleted at
the close, with what outlives it folded into `TASKS.md`; the receiver series'
last state is at `git show b500342:WORKPLAN.md`. No series is open at this tip,
so there is no `WORKPLAN.md` here.

## What this project is

A **receiver**: it turns telemetry in flight into live
[`spanweave`](https://github.com/SigorMatt/spanweave) graphs. Bytes arrive in
arbitrary chunks from a tailed file, stdin or an OTLP/HTTP POST; records come out
through `spanweave.read_records`; each record is routed to one
`spanweave.Builder` per trace; graphs and deltas go to consumers.

It is not an analyzer, not a rule engine, not a gate, not a service with a
policy. **The receiver owns plumbing and policy and nothing else.**

`spanweave` is a dependency pinned to one commit, and `corpus/` is a submodule of
that same repository at the same commit, read-only, used only to build
`fixtures/conformance/`. Nothing in this repo changes `spanweave`; if a batch
seems to need a change there, that is a halt point (below).

The showcase (`SPEC.md` §9) has the same shape one directory over: `agentgolden`
is a **dev** dependency pinned to one commit, and `showcase/` is a submodule of
that repository at the same commit, read-only, where the rules file and the
trace are read from. It is a dev dependency and its consumer is a **test**
because the receiver carries no rules; a gate fails the build if any module
under `spanweave_live/` imports it. Nothing in this repo changes `agentgolden`
either, and that too is a halt point.

## Standing rules — non-negotiable

These are `WORKPLAN.md` §0.6, which is where they were first written, repeated
here because they are the contract and a session must not have to read the plan
to find them. A change that violates one is wrong even if it passes tests.

1. **It never reads a dialect.** A record's trace id, span id or kind comes from
   `spanweave`'s adapters (`spanweave.adapters.classify` and the claiming
   adapter's `parse`), never from a key the receiver looks up itself. No
   `record["trace_id"]`, no container walk, no dialect test under
   `spanweave_live/`. (`SPEC.md` §1.1.)

2. **It carries no rules and no semantics.** A consumer evaluates graphs; the
   receiver hands them over. No roles, no severity, no risk, no cost, no scoring,
   no verdicts. (`SPEC.md` §1.2.)

3. **It enforces nothing.** Detection is observation. Holding or refusing a call
   belongs to a gate the receiver does not know exists. (`SPEC.md` §1.3.)

4. **The clock, sleeping and sockets are injected seams** — `now`, `sleep`, a
   listener factory — so every test runs on a fake clock and the conformance gate
   is deterministic. No module under `spanweave_live/` imports `time`,
   `datetime`, `random`, `socket`, `threading`, `asyncio` or `http.server`
   (`tests/gates.py` bans a longer list than those seven) outside a seam file
   named in that file's `SEAMS` allowlist. The allowlist has **one** entry,
   added by R7 and still the only one —
   `SEAMS = {"real.py": frozenset({"time", "http.server"})}`, one file and two
   modules — because `real.py` is where a process binds the real world and
   nothing else does. The gate fails the build. (`SPEC.md` §1.4, §8.2.)

5. **Nothing is dropped silently.** A refusal, a cap, a late arrival or a
   consumer error is an **event with a code**, counted and reported.
   (`SPEC.md` §1.5.)

6. **The two pins are one pin.** `spanweave` is pinned to one commit in
   `pyproject.toml`, the `corpus/` submodule is at the same commit, and
   `tests/test_pins.py` holds the two equal (and `uv.lock` with them). Moving one
   without the others is the failure that test exists to catch. Since R8 there is
   a second pair of the same shape: the `agentgolden` dev pin and the `showcase/`
   submodule, held equal by the same file.

7. **Nothing is frozen.** Pre-1.0, by `0.0.x`, said out loud in the version
   number, in `--help`, in `README.md` and at the top of `SPEC.md`. Publishing is
   reversible; freezing is not. Say so often until something actually freezes.

8. **Determinism.** Same input bytes → byte-identical graphs, on any machine, in
   any process. No clock reads, no unseeded randomness, no `hash()` in an
   identity or ordering path, no reliance on set or dict iteration order. Chunk
   boundaries and arrival interleavings are seeded in the test, never ambient.

9. **Read-only toward the observed system.** The receiver reads bytes and writes
   files, stdout and callbacks. It never calls back into the system it watches.
   Trace payloads are untrusted input: never `eval`, `exec`, `pickle` or
   `yaml.load` anything that came out of a trace.

## Architecture

```
bytes ──► Framer ──► spanweave.read_records ──► Router ──► Builder per trace
          (§3)                                   (§4)      │
                                      Completion (§5) ─────┤
                                   Subscriptions (§6) ◄────┘
```

- `spanweave_live/` is the library. Everything in it is importable, synchronous,
  and free of ambient runtime (rule 4).
- `tests/gates.py` holds the invariant gate as reusable checks over source text;
  `tests/test_gates.py` watches it fail against planted violations. A gate nobody
  has watched fail is a gate nobody knows works.
- `corpus/` is the pinned `spanweave` repository. Read it; never write it.
- The corpus' own `fixtures/conformance/` is read in place, through `corpus/`,
  rather than copied into a `fixtures/` of this repo's own: a copy is a second
  thing to keep at the pin. The cross-interleaving equivalence test (gate A,
  `tests/test_conformance.py`, R2) is this project's central claim: records of
  two traces, shuffled together and framed in arbitrary chunks, produce each
  trace's graph **byte for byte** as `spanweave.build` of that trace alone.

## Commands

Tooling is `uv`. The `Makefile` is the source of truth for the gates.

```bash
make check            # THE gate: ruff, ruff format --check, mypy --strict, pytest, gates
make gates            # the invariant gate and the pin test alone
make conformance      # gate A (real from R2: tests/test_conformance.py, ~25s)
make showcase         # the showcase: prints the first-failure table, then asserts it
make install-check    # wheel into a throwaway venv, run from OUTSIDE the repo (needs network once)
uv run pytest tests/test_gates.py::test_the_package_reaches_for_no_ambient_runtime
```

`make check` runs everything under `uv run`, with the source tree on the path, so
it only ever answers questions about the repository. `make install-check` is the
only gate that can catch a packaging break. CI runs both, on 3.11–3.14, plus
`make conformance` on ubuntu and macos. Run both locally before calling a change
done.

First time in a fresh clone: `git submodule update --init` (both `corpus/` and
`showcase/`) then `uv sync --extra dev`.

## Definition of done (per change)

- [ ] `SPEC.md` reflects the behaviour, edited in the same commit.
- [ ] The new test was confirmed **red** on the derived parent (`<sha>^`), in a
      worktree created by absolute path under the scratchpad.
- [ ] One named mutation shown caught by the new test.
- [ ] `make check` green; `make conformance` run; `make install-check` run when
      packaging or dependencies moved.
- [ ] `CHANGELOG.md` entry.
- [ ] One concern per commit.

`CONTRIBUTING.md` states that bar in full, including why each line is there.

## Halt points — stop and ask, do not improvise

Write the options to `OPEN_QUESTIONS.md` under a heading naming the batch,
commit that alone, and report `awaiting decision`:

- A change in `spanweave` itself would be needed.
- A dialect would have to be read outside `spanweave`'s adapters.
- A rule or a policy the spec does not already state would have to be invented.
- A `NodeKind`, an `EdgeKind` or a graph shape would have to change.
- The seam allowlist would have to grow for something that is not a seam.
