"""The showcase: agentgolden's rules per delta (`SPEC.md` §9).

What this file asserts, and what it refuses to assert:

- **The first-failure version table, exactly.** Four rules of nineteen ever
  fail on this trace, and the version each one first failed at is a fact about
  the trace and the rules file — not a range, not a subset. A table asserted
  loosely would pass for a consumer that evaluated the final graph seven times.
- **The `TASKS.md` R8 premise is false, and this file says so rather than
  bending to it.** The row (and `spanweave` `OPEN_QUESTIONS.md` §19, which it
  comes from) predicts that the `verify_identity → issue_refund` **order** rule
  fails at the version absorbing the `llm.plan` span that carries the
  `issue_refund` request — one version before the tool span. It does not: it
  fails at version 6, the version the `tool.issue_refund` span arrives, because
  `agentgolden`'s `OrderRule` reads `Signature.tool_calls`, which is tool
  **nodes**, and `spanweave`'s `NodeKind` is closed — a requested call with no
  span of its own is an `unpaired_call` *diagnostic*, not a node. The memo's
  mechanism ("the LLM span ends before the tool span starts") is true of the
  telemetry and false of the rule that was supposed to read it.
- **"When it almost happened" is real, and it is a different rule.**
  `trajectory.all_calls_fulfilled` fails at version 5 — the request absorbed,
  the tool not yet run — and **passes again at version 6**. It is a verdict
  that exists only live: the batch graph of the whole trace never shows it.
  That is what the live consumer buys, stated as the thing actually measured.
- **Batch and live are one model.** The same rules file over
  `spanweave.build` of the whole trace gives verdict for verdict what the last
  live version gives, and the live final graph serializes byte for byte to the
  batch graph, compared with gate A's own normalization (§4.7).
- **Nothing semantic reached the library.** No module under `spanweave_live/`
  imports `agentgolden`, held by a gate with a planted violation in
  `tests/test_gates.py`.

No clock, no network, no randomness: the rules file and the trace are read from
`showcase/`, the pinned `agentgolden` submodule, and the replay is `Framer` +
`Router` over bytes.
"""

from __future__ import annotations

import subprocess

import pytest
import spanweave
from agentgolden.rules import evaluate, load_rules
from agentgolden.signature import signature

from tests import gates, showcase
from tests.test_conformance import undigested

# --------------------------------------------------------------------------
# The table. Four rules of nineteen, and the version each first failed at.
# --------------------------------------------------------------------------

#: Every rule the file enables, in `agentgolden.rules.evaluate`'s fixed order.
RULES_EVALUATED = 19

#: The claim of this batch, as a number per rule. Versions are 1-based: version
#: `n` is the graph after the `n`-th record of the trace was absorbed.
FIRST_FAILURES = {
    "order:verify_identity<issue_refund": 6,
    "tools.required:issue_refund": 1,
    "tools.required:verify_identity": 1,
    "trajectory.all_calls_fulfilled": 2,
}

#: The version the `llm.plan` span carrying the `issue_refund` request lands.
REQUEST_VERSION = 5

#: The version the `tool.issue_refund` span lands, one later.
TOOL_VERSION = 6

#: The whole trace: seven records, so seven versions.
RECORDS = 7


@pytest.fixture(scope="module")
def run() -> showcase.Replay:
    """One replay of the trace through `Framer` + `Router`, reused."""
    return showcase.replay()


# --------------------------------------------------------------------------
# The rules file is agentgolden's own, unchanged.
# --------------------------------------------------------------------------


def test_the_rules_file_and_the_trace_are_the_pinned_submodule_s_own_bytes():
    """`unchanged` is the whole point of the showcase, so it is asserted.

    Compared against the submodule's committed blobs rather than against a
    copy in this repository: a copy would be a second thing to keep at the pin
    (`CLAUDE.md`), and a rules file edited to make a verdict come out right
    would void the demonstration entirely (`TASKS.md` R8).
    """
    for path in (showcase.RULES, showcase.TRACE):
        committed = subprocess.run(
            ["git", "show", f"HEAD:{path.relative_to(showcase.SUBMODULE).as_posix()}"],
            cwd=showcase.SUBMODULE,
            capture_output=True,
            check=True,
        ).stdout
        assert path.read_bytes() == committed, (
            f"{path.name} differs from the blob the pinned agentgolden commit "
            f"holds; the showcase evaluates agentgolden's rules UNCHANGED"
        )


def test_the_rules_file_is_the_support_agent_policy_the_row_names():
    rules = load_rules(showcase.RULES)
    assert rules.name == "support-agent refund policy"
    assert rules.required_tools == ("verify_identity", "issue_refund")
    assert [(rule.before, rule.after) for rule in rules.order] == [
        ("verify_identity", "issue_refund"),
        ("lookup_order", "issue_refund"),
    ]


# --------------------------------------------------------------------------
# The table, exactly.
# --------------------------------------------------------------------------


def test_the_replay_is_one_trace_of_seven_per_record_deltas(run: showcase.Replay):
    """The premise of every version number below, held rather than assumed."""
    assert run.trace_id == "run-0003"
    assert run.versions == tuple(range(1, RECORDS + 1))
    # `every=1`, so each window is one record wide (`SPEC.md` §6.2).
    assert run.windows == tuple((version, version - 1) for version in run.versions)
    assert run.events == ()


def test_the_first_failure_version_table_is_exactly_this(run: showcase.Replay):
    assert run.first_failures == FIRST_FAILURES


def test_the_rules_that_never_failed_are_the_other_fifteen(run: showcase.Replay):
    """A table of four is only a claim if the complement is one too."""
    assert len(run.rule_ids) == RULES_EVALUATED
    never = tuple(rule for rule in run.rule_ids if rule not in run.first_failures)
    assert len(never) == RULES_EVALUATED - len(FIRST_FAILURES)
    for rule in never:
        assert all(run.outcome(version, rule) == "pass" for version in run.versions)


# --------------------------------------------------------------------------
# The row's premise, measured. It is false, and the file says which way.
# --------------------------------------------------------------------------


def test_the_llm_plan_span_carrying_the_request_lands_one_version_early(
    run: showcase.Replay,
):
    """The memo's mechanism, which is true: the request is absorbed first.

    `spanweave` reports it as an `unpaired_call`, and `agentgolden`'s signature
    carries the operation name — so at version 5 the graph already *says*
    `issue_refund` was asked for, one version before anything ran it.
    """
    assert run.unfulfilled(REQUEST_VERSION) == ("issue_refund",)
    assert run.unfulfilled(TOOL_VERSION) == ()
    assert TOOL_VERSION == REQUEST_VERSION + 1


def test_the_order_rule_fails_at_the_tool_span_and_not_one_version_before(
    run: showcase.Replay,
):
    """`TASKS.md` R8's premise, falsified in the direction it is wrong.

    At version 5 the order rule is a *vacuous pass*: `tool_calls` is empty
    because a requested call that has not run is a diagnostic and not a node,
    and `spanweave`'s `NodeKind` is closed, so there is nothing for it to be.
    The rule first fails at version 6, when `tool.issue_refund` arrives.
    """
    order = "order:verify_identity<issue_refund"
    assert run.outcome(REQUEST_VERSION, order) == "pass"
    assert run.outcome(TOOL_VERSION, order) == "fail"
    assert run.first_failures[order] == TOOL_VERSION
    # And the reason, not just the outcome: nothing is an `issue_refund` tool
    # node at version 5, which is what the order rule looks for.
    assert run.tool_calls(REQUEST_VERSION, "issue_refund") == ()
    assert len(run.tool_calls(TOOL_VERSION, "issue_refund")) == 1
    assert run.verdict(REQUEST_VERSION, order).basis == "vacuous"


def test_the_almost_happened_verdict_is_all_calls_fulfilled_and_it_heals(
    run: showcase.Replay,
):
    """What the live consumer really buys, and the batch graph cannot show.

    `trajectory.all_calls_fulfilled` fails at version 2 (the `lookup_order`
    request) and at version 5 (the `issue_refund` request), and passes at every
    other version — including the last. A consumer that only ever saw the
    finished trace would never see either.
    """
    rule = "trajectory.all_calls_fulfilled"
    failing = tuple(
        version for version in run.versions if run.outcome(version, rule) == "fail"
    )
    assert failing == (2, REQUEST_VERSION)
    assert run.outcome(run.versions[-1], rule) == "pass"


# --------------------------------------------------------------------------
# Batch and live are one model.
# --------------------------------------------------------------------------


def test_the_same_rules_on_the_batch_graph_give_the_same_final_verdicts(
    run: showcase.Replay,
):
    batch = spanweave.build(showcase.TRACE.read_bytes())
    verdicts = evaluate(load_rules(showcase.RULES), batch, signature(batch))
    assert tuple(verdict.as_dict() for verdict in verdicts) == tuple(
        verdict.as_dict() for verdict in run.verdicts(run.versions[-1])
    )


def test_the_live_final_graph_is_the_batch_graph_byte_for_byte(run: showcase.Replay):
    """Gate A's comparison, on the showcase's own trace (`SPEC.md` §4.7).

    Reached through gate A's `undigested`, not a second normalization: the one
    field a builder cannot carry is `meta.source_digest`, and nothing else is
    touched on either side.
    """
    batch = spanweave.build(showcase.TRACE.read_bytes())
    assert spanweave.dumps(run.final_graph) == spanweave.dumps(undigested(batch))


# --------------------------------------------------------------------------
# And none of it reached the library.
# --------------------------------------------------------------------------


def test_no_module_of_the_library_imports_the_consumer_s_rule_engine():
    """Standing rule 2, as a gate rather than as a sentence (`SPEC.md` §9.4)."""
    assert gates.check_package((gates.no_consumer_rules,)) == []


def test_the_consumer_lives_in_tests_and_not_in_the_package():
    assert showcase.__file__.endswith("tests/showcase.py")
    assert not (gates.PACKAGE_ROOT / "showcase.py").exists()
