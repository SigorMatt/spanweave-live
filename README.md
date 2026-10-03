# spanweave-live

A receiver that turns agentic-system telemetry **in flight** into live
[`spanweave`](https://github.com/SigorMatt/spanweave) graphs: it frames bytes
arriving in arbitrary chunks from a tailed file, stdin or an OTLP/HTTP POST into
complete records, routes each record — through `spanweave`'s own adapters, never
through a key of its own — to one `spanweave.Builder` per trace, decides with an
injected clock when a trace is complete, and hands graphs and per-record deltas
to consumers, so that a rule a consumer already runs over a finished trace runs
unchanged while the trace is still happening. It owns plumbing and policy and
nothing else: it reads no dialect, carries no rules and no semantics, enforces
nothing, has no clock of its own, and drops nothing silently — every refusal,
cap, late arrival and consumer error is an event with a code, counted and
reported. **Pre-1.0 (`0.0.x`): nothing is frozen** — not the API, not the event
codes, not the CLI. See `SPEC.md` for what it does, `CLAUDE.md` for the lines
that must not be crossed, and `CONTRIBUTING.md` for the bar a change must clear.
At R0 the repository is a skeleton: the gates, the pins and the contract are
here; `Framer`, `Router`, `Completion`, `Subscriptions`, the ingest paths and the
CLI arrive in R1–R7 (`WORKPLAN.md`).
