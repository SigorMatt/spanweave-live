# Changelog

All notable changes to this project. **Nothing here is frozen**: the version is
`0.0.x`, and until that changes any entry below may be undone by the next one.

The format is loosely [Keep a Changelog](https://keepachangelog.com/); the unit
of change is a **batch** (`WORKPLAN.md`), and each entry names the batch.

## Unreleased

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
