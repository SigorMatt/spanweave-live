"""The showcase's consumer: agentgolden's rules, evaluated per delta.

This module is in `tests/`, not in `spanweave_live/`, and that is the point of
it rather than an accident of layout. The receiver carries **no rules and no
semantics** (`CLAUDE.md` standing rule 2, `SPEC.md` §1.2): it hands a consumer
a `Delta`, the version it belongs to and the builder it came from, and what the
consumer concludes is the consumer's. So the thing that loads a rules file,
computes a signature and decides that a verdict is a failure lives here, beside
the test that measures it, and `agentgolden` is a **dev** dependency. A gate
holds that: `tests/gates.py`'s `no_consumer_rules` fails the build if any
module under `spanweave_live/` imports it (`SPEC.md` §9.4).

What it does, in the order `SPEC.md` §9.2 states it:

1. replay the trace -- `showcase/examples/support_agent/candidates/` holds
   `skipped_verification.openinference.jsonl` -- through one `Framer` and one
   `Router`, one line at a time, as a tail would deliver it;
2. on every per-record `Update`, ask the builder for `graph()` — the `Update`
   carries no graph, by §6.1's design, and the builder is right there;
3. compute `agentgolden.signature.signature(graph)` and evaluate
   `showcase/examples/support_agent/rules.toml`, **unchanged**, with
   `agentgolden.rules.evaluate`;
4. keep every version's verdicts, so the first version at which each rule
   failed is a lookup rather than a second replay.

The delta itself is not what the rules read: `agentgolden`'s rules read a whole
graph, and the memo's refinement — evaluate "only the rules whose inputs the
delta names" (`spanweave` `OPEN_QUESTIONS.md` §19) — is **not implemented
here**, because it would require knowing which rule reads which part of the
graph, and that is a consumer's optimisation and not the claim under test. What
the delta provides is the *trigger* and the *version*: it says that something
changed and which version it is, which is exactly what a first-failure table is
indexed by.

Run it: `make showcase`, or `python -m tests.showcase`, which prints the table.
No clock, no network, no randomness.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass

import spanweave
from agentgolden.rules import FAIL, RuleSet, Verdict, evaluate, load_rules
from agentgolden.signature import Signature, Step, signature

from spanweave_live import Event, Framer, Router, Subscriptions, Update

REPO = pathlib.Path(__file__).resolve().parent.parent

#: The pinned `agentgolden` repository, a submodule at the sha the dev
#: dependency names (`tests/test_pins.py`). The rules file and the trace live
#: under its `examples/`, which the wheel does not ship -- so the submodule is
#: how the showcase reads agentgolden's own bytes instead of a copy of them.
SUBMODULE = REPO / "showcase"
EXAMPLE = SUBMODULE / "examples" / "support_agent"
RULES = EXAMPLE / "rules.toml"
TRACE = EXAMPLE / "candidates" / "skipped_verification.openinference.jsonl"

MISSING = (
    "showcase/ is not checked out: run `git submodule update --init`. It is the "
    "pinned agentgolden repository, and the showcase reads its rules file and "
    "its trace from it rather than from a copy (CLAUDE.md)."
)


@dataclass(frozen=True, slots=True)
class Observation:
    """One version of one trace, and what the rules said about it."""

    version: int
    #: The window the delta covered: `version - 1` in per-record mode (§6.2).
    since: int
    verdicts: tuple[Verdict, ...]
    signature: Signature

    @property
    def failed(self) -> tuple[str, ...]:
        return tuple(v.rule for v in self.verdicts if v.outcome == FAIL)


class LiveRules:
    """A consumer. It evaluates; the receiver that fed it does not.

    Deliberately stateful and deliberately dumb: it keeps every version's
    verdicts and concludes nothing beyond "this rule said fail". A consumer
    that kept only the last version's verdicts would report a first-failure
    table of the finished trace, which is the mutation `SPEC.md` §9.5 names.
    """

    def __init__(self, rules: RuleSet) -> None:
        self.rules = rules
        self.observations: list[Observation] = []

    def __call__(self, update: Update) -> None:
        graph = update.builder.graph()
        sig = signature(graph)
        self.observations.append(
            Observation(
                version=update.version,
                since=update.since,
                verdicts=evaluate(self.rules, graph, sig),
                signature=sig,
            )
        )


@dataclass(frozen=True, slots=True)
class Replay:
    """One replay of the showcase trace, and the questions a test asks of it."""

    trace_id: str
    observations: tuple[Observation, ...]
    final_graph: spanweave.Graph
    events: tuple[Event, ...] = ()

    def at(self, version: int) -> Observation:
        found = [obs for obs in self.observations if obs.version == version]
        assert len(found) == 1, f"version {version} observed {len(found)} times"
        return found[0]

    @property
    def versions(self) -> tuple[int, ...]:
        return tuple(obs.version for obs in self.observations)

    @property
    def windows(self) -> tuple[tuple[int, int], ...]:
        return tuple((obs.version, obs.since) for obs in self.observations)

    @property
    def rule_ids(self) -> tuple[str, ...]:
        """Every rule the file enables, in `evaluate`'s fixed order."""
        return tuple(v.rule for v in self.observations[0].verdicts)

    @property
    def first_failures(self) -> dict[str, int]:
        """Rule id -> the first version at which it failed. The claim of R8."""
        found: dict[str, int] = {}
        for obs in self.observations:
            for rule in obs.failed:
                if rule not in found:
                    found[rule] = obs.version
        return found

    def verdicts(self, version: int) -> tuple[Verdict, ...]:
        return self.at(version).verdicts

    def verdict(self, version: int, rule: str) -> Verdict:
        found = [v for v in self.verdicts(version) if v.rule == rule]
        assert len(found) == 1, f"{rule!r} appears {len(found)} times at v{version}"
        return found[0]

    def outcome(self, version: int, rule: str) -> str:
        return self.verdict(version, rule).outcome

    def unfulfilled(self, version: int) -> tuple[str | None, ...]:
        return self.at(version).signature.unfulfilled

    def tool_calls(self, version: int, operation: str) -> tuple[Step, ...]:
        return self.at(version).signature.tool_calls(operation)


def replay(*, trace: pathlib.Path = TRACE, rules: pathlib.Path = RULES) -> Replay:
    """Replay `trace` through `Framer` + `Router`, evaluating `rules` per delta."""
    assert trace.exists() and rules.exists(), MISSING

    consumer = LiveRules(load_rules(rules))
    subscriptions = Subscriptions()
    subscriptions.subscribe(consumer)
    router = Router(subscriptions=subscriptions)
    framer = Framer()

    events: list[Event] = []
    # One line at a time, as a tail or a stdin pipe delivers it. The bytes are
    # the file's own, framed rather than parsed here: the receiver reads no
    # dialect and neither does this (`SPEC.md` §1.1).
    for line in trace.read_bytes().splitlines(keepends=True):
        for record in framer.push(line).records:
            events.extend(router.route(record).events)
    for record in framer.flush().records:
        events.extend(router.route(record).events)
    assert framer.pending_bytes == 0

    trace_ids = router.trace_ids
    assert len(trace_ids) == 1, f"the showcase trace is one trace, got {trace_ids}"
    builder = router.builder(trace_ids[0])
    assert builder is not None
    return Replay(
        trace_id=trace_ids[0],
        observations=tuple(consumer.observations),
        final_graph=builder.graph(),
        events=tuple(events),
    )


def main() -> None:
    """Print the first-failure version table. `make showcase` runs this."""
    run = replay()
    first = run.first_failures
    print(
        f"trace {run.trace_id}: {len(run.versions)} versions, "
        f"{len(run.rule_ids)} rules, {len(first)} ever failed\n"
    )
    width = max(len(rule) for rule in run.rule_ids)
    for rule in run.rule_ids:
        version = first.get(rule)
        at = f"first failed at version {version}" if version else "never failed"
        print(f"  {rule:<{width}}  {at}")


if __name__ == "__main__":  # pragma: no cover - `make showcase`
    main()
