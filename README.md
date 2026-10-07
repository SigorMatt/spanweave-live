# spanweave-live

A receiver that turns agentic-system telemetry **in flight** into live
[`spanweave`](https://github.com/SigorMatt/spanweave) graphs: it frames bytes
arriving in arbitrary chunks from a tailed file, stdin or an OTLP/HTTP POST into
complete records, routes each record — through `spanweave`'s own adapters, never
through a key of its own — to one `spanweave.Builder` per trace, decides with an
injected clock when a trace is complete, and hands graphs and per-record deltas
to consumers, so that a rule a consumer already runs over a finished trace runs
unchanged while the trace is still happening.

It owns plumbing and policy and nothing else: it reads no dialect, carries no
rules and no semantics, enforces nothing, has no clock of its own, and drops
nothing silently — every refusal, cap, late arrival and consumer error is an
event with a code, counted and reported.

**Pre-1.0 (`0.0.x`): nothing is frozen** — not the API, not the event codes, not
the CLI. See `SPEC.md` for what it does, `CLAUDE.md` for the lines that must not
be crossed, `CONTRIBUTING.md` for the bar a change must clear, and `TASKS.md`
for how it was built and what its reviews found.

## Install

`spanweave` is pinned to one commit (`pyproject.toml`), so an install resolves
it from git:

```bash
uv pip install git+https://github.com/SigorMatt/spanweave-live
```

From a clone, for development — `corpus/` and `showcase/` are submodules of the
pinned `spanweave` and `agentgolden` repositories, and the test suite reads them
in place:

```bash
git clone https://github.com/SigorMatt/spanweave-live
cd spanweave-live
git submodule update --init
uv sync --extra dev
make check
```

## The CLI

Two commands. Both write each completed trace's final graph to `--out` as
`<trace_id>.json` with `spanweave.dump`, write every event to **stderr** as one
JSON line carrying its code, and keep **stdout** for deltas and nothing else.

```bash
# Follow a growing file. --once reads what is there now and stops (a replay).
spanweave-live tail /var/log/agent/traces.jsonl --out graphs/ --quiet 30

# Replay a file and exit, writing each per-record delta to stdout as one line.
spanweave-live tail trace.jsonl --out graphs/ --once --deltas

# Read a pipe to EOF. `-` is stdin.
cat trace.jsonl | spanweave-live tail - --out graphs/

# Receive OTLP/HTTP JSON: POST /v1/traces, application/json, gzip accepted.
spanweave-live serve --port 4318 --out graphs/ --root-grace 5
```

A trace is complete when a policy the caller chose says so, and the caller
chooses by flag: `--quiet S` (no record for S seconds), `--root-grace S` (S
seconds after an ended root was first seen), `--cap N` (N records absorbed).
Give several and they compose as any-of; give none and only end of input
completes a trace. The other flags are bounds, each of them the caller's number
rather than a default this library invented: `--max-traces`, `--max-completed`,
`--max-pending-bytes`. `--poll-seconds` and `--once` apply to a file,
`--host` and `--requests` to the socket. `spanweave-live <command> --help`
prints every flag, each policy and bound with the `SPEC.md` section that
specifies it, including the two traps worth knowing before you rely on them:

- **`--max-completed` can overwrite a graph.** Forgetting a completed trace id
  loses its generation, so a later record for a forgotten id writes
  `<trace_id>.json` **over** the earlier completion's file instead of beside it
  as `<trace_id>.2.json`. The default forgets nothing and overwrites nothing
  (`SPEC.md` §5.5, §8.5).
- **Line numbers after a `fragment_too_long` are the framer's, not the
  input's**, because each fragment of a cut line is numbered as a line. Events
  call that field `framer_line` for exactly this reason (`SPEC.md` §3.4).

Exit codes (`SPEC.md` §8.6): `0` the input ended and everything was delivered ·
`1` it could not start · `2` usage · `3` it ran to the end but something it had
could not be delivered (`not_written`, `delta_unsent`, `consumer_error`) ·
`130` interrupted. A refusal, a cap, a late arrival, a `415`, a `400` and a
client that aborted before reading its answer are **observations** and leave
the code at `0`.

## The API

The CLI is a caller of the library and adds nothing to it. The library is
synchronous, importable, and free of ambient runtime: the clock, sleeping and
the listening socket are parameters with no defaults, so there is exactly one
module in the package that imports `time` or `http.server`
(`spanweave_live/real.py`, which the CLI binds and `__init__` does not export).

```python
from pathlib import Path

from spanweave_live import Cap, Completion, Framer, Quiet, Router

clock = [0.0]                       # your clock, injected: the library owns none
router = Router(
    completion=Completion(
        policies=(Quiet(30.0), Cap(10_000)),   # any-of
        now=lambda: clock[0],
        out_dir=Path("graphs"),     # where a completed trace's graph is written
    )
)
framer = Framer()                   # bytes in arbitrary chunks -> whole records

for chunk in incoming_bytes:        # a socket, a file, anything
    clock[0] = my_clock()           # you advance it; tick() reads it, never time
    for record in framer.push(chunk).records:
        routed = router.route(record)
        for event in routed.events:
            report(event.code)      # refused, refused_at_cap, late_arrival, ...
    for completed in router.tick():
        print(completed.trace_id, completed.version, completed.path)

for record in framer.flush().records:   # the remainder is read, never dropped
    router.route(record)

# End of input. The CLI finalises exactly this way (SPEC.md 8.5): a Cap(0)
# completes every held trace at once, so a replay always leaves files behind.
router.completion = Completion(policies=(Cap(0),), now=lambda: clock[0],
                               out_dir=Path("graphs"))
for completed in router.tick():
    print(completed.trace_id, completed.version, completed.path)
```

The five pieces, each specified in the section named:

| | | |
|---|---|---|
| **`Framer`** | §3 | `push(chunk)` hands the reader complete lines only and keeps the remainder; `document(body)` hands a whole OTLP-JSON body over unsplit; `flush()` reads the remainder as a final line and reports it; `pending_bytes` is what it still holds. Diagnostics come back with the line's absolute offset in the stream. `max_pending_bytes` caps the remainder, and the oversize fragment is reported rather than dropped |
| **`Router`** | §4 | One `spanweave.Builder` per trace, created on first sight, the trace id read through `spanweave.adapters.classify` and the claiming adapter's `parse`. A record with no trace id or no claimant goes to the no-trace builder; a `Builder` refusal is a counted `refused` event and routing continues; `max_traces` is a cap and the cap is counted |
| **`Completion`** | §5 | Three policies, each a value — `Quiet(seconds)`, `RootEnded(grace_seconds)`, `Cap(records)` — composable as any-of over a `now` the caller supplies. `Router.tick()` returns the traces completed, materializes each final graph, writes it, and releases the builder. A record for a completed trace opens a new generation and emits `late_arrival` with the gap |
| **`Subscriptions`** | §6 | A consumer registers a callback for one trace or for all, per record or `every=N`, and is handed `Update`s carrying a `spanweave` delta. Retention is set to the hungriest subscriber's window and no more. A callback that raises is isolated as `consumer_error`: the other subscribers are still called and the record is still absorbed |
| **`tail` / `stdin` / `serve`** | §7 | `tail(path, *, now, sleep, poll_seconds)` follows a growing file, detects truncation and rotation by the platform's own `(st_dev, st_ino)` and reports both as events; `stdin()` reads a pipe to EOF; `serve(endpoint, *, listener=…)` answers `POST /v1/traces` over a socket the caller's factory owns |

`spanweave_live.__all__` is the whole public surface, event-code constants
included. Every code the receiver can emit is a module-level `Final` string, so
a consumer matches on `spanweave_live.LATE_ARRIVAL` rather than on a literal.

## The claim this project is tested against

Records of two traces, shuffled together and framed in arbitrary chunks,
produce each trace's graph **byte for byte** identical to `spanweave.build` of
that trace alone. That is conformance gate A (`SPEC.md` §4.7,
`tests/test_conformance.py`), run over every pair of renderings from the pinned
corpus' scenarios — 1354 cross-scenario pairs × 10 seeds × 2 graphs per pair =
27 080 byte-for-byte comparisons. Live and batch are one model, or this library
is not worth having.

```bash
make check          # ruff, ruff format --check, mypy --strict, pytest, the gates
make conformance    # gate A alone
make showcase       # agentgolden's rules, unchanged, evaluated per delta
make install-check  # build the wheel, install it, run it from outside the repo
```

What live buys over batch is demonstrated rather than asserted (`SPEC.md` §9):
`agentgolden`'s support-agent rules are evaluated **unchanged** on every
per-record delta of its own `skipped_verification` trace, and one rule —
`trajectory.all_calls_fulfilled` — fails at version 2, fails again at 5 and
**passes at the last version**, so it is a verdict that exists only in the live
stream and is invisible in the batch graph of the same trace. The receiver
carries no rules to make that happen: a gate fails the build if any module under
`spanweave_live/` imports the rule engine.

## License

MIT (`LICENSE`).
