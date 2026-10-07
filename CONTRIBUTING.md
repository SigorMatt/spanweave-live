# Contributing to spanweave-live

Work here arrives in **batches**: one batch is one concern, one commit, and one
agent or person's sitting. The bar below is what every batch must clear. It
began as the receiver series' batch brief written out, with the reason for each
line, because a bar whose reasons are not written gets negotiated away one batch
at a time — and it is now the only copy: the series' execution state
(`WORKPLAN.md`) was deleted at its close, and `TASKS.md` registers what that
series did.

Read first: `CLAUDE.md` (the invariants — the standing rules are not style
preferences), then the part of `SPEC.md` you are touching.

**Nothing in this project is frozen.** Pre-1.0, by `0.0.x`. No API name, no event
code and no CLI flag is a contract yet, so a batch that renames something is
cheap today and will not be later. Say what you changed in `CHANGELOG.md`.

## The bar

A batch is done when all of these hold.

- [ ] **Spec first.** If behaviour changed, `SPEC.md` changed **in the same
      commit**. Not a follow-up: a spec that lags the code is a spec a reader
      cannot trust, and the first time it is wrong nobody reads it again.

- [ ] **The new test was confirmed red on the parent.** Write the failing test
      before the fix, then run it against the **derived** parent — `<sha>^` of the
      commit you are making, never a sha a brief happens to name, because plan
      commits interleave and a brief's sha may be two commits back. Check it out
      in a worktree created by **absolute path under the scratchpad**:

      ```bash
      git worktree add /abs/path/under/scratchpad/parent <sha>^
      ```

      Never a relative path, and never inside the repo: a worktree under the
      working tree gets picked up by `rglob`, by pytest collection and by the
      gates, and then the parent run is measuring both trees at once.

      **Record the sha `<sha>^` resolved to** in the commit body, not the sha
      you started from. One commit in the receiver series claimed a parent that
      was two commits back and was right only by luck, because the two trees
      differed solely in the series' plan file; the next time the intervening
      commit touches code or tests, the same mistake makes the evidence worthless
      (`TASKS.md`, thread T7).

- [ ] **A named mutation, shown caught.** Name one specific wrong
      implementation — "a framer that hands partial lines over", "a `Quiet` that
      fires one tick early" — make it, watch the new test fail, revert it. This is
      required for **every** code batch, not only where the parent run is
      informative: a tests-only batch's derived parent is often a `plan:` commit,
      which makes the parent run vacuous, and a test that has only ever been
      watched passing is indistinguishable from a test that cannot fail.

- [ ] **`make check` green.** ruff, `ruff format --check`, `mypy --strict`,
      pytest, and the invariant gate. Also run `make conformance`, and
      `make install-check` when packaging or dependencies moved — it is the only
      gate that can catch a packaging break, because everything else runs under
      `uv run` with the source tree on the path.

- [ ] **A `CHANGELOG.md` entry**, under the batch's heading, in the same commit.

- [ ] **One concern per commit.** `<area>: <one line>`, with a body naming the
      batch and the `SPEC.md` sections touched. A commit that does two things
      cannot be reverted, reviewed or cited as one.

- [ ] **No test whose result depends on what is installed on the machine running
      it**, and none that is green because of a choice it made about its own
      fixture. Both failure modes pass everywhere they cannot catch anything.

- [ ] **No test that reads the real clock, opens a real socket, or shuffles
      unseeded.** Drive the injected seams. A timeout test against the real clock
      is a flake, and a flake gets tuned until it asserts nothing.

## Halt, do not improvise

Stop, write the options to `OPEN_QUESTIONS.md` under a heading naming the batch,
commit that alone, and say `awaiting decision`, if finishing would need:

- a change in `spanweave` itself;
- a dialect read outside `spanweave`'s adapters;
- a rule or policy `SPEC.md` does not already state;
- a `NodeKind`, `EdgeKind` or graph-shape change;
- a new entry in `tests/gates.py`'s seam allowlist for something that is not a
  seam.

Guessing at any of these produces a plausible answer that is expensive to
unpick. A written question costs one commit.

## The pins

`spanweave` is pinned by git sha in `pyproject.toml`; `corpus/` is a submodule of
the same repository at the same sha; `uv.lock` records it a third time.
`tests/test_pins.py` holds all three equal. Moving the pin is therefore one edit
in three places and one commit — and `make install-check` afterwards, because a
pin move is a dependency move.

Since R8 there is a **second pin of the same shape**: `agentgolden` by git sha in
the `dev` extra, `showcase/` a submodule of that repository at that sha, and
`uv.lock` again. It is a *dev* pin and its consumer is a test, because the
receiver carries no rules (`SPEC.md` §1.2, §9.4); a gate fails the build if any
module under `spanweave_live/` imports it. Moving it moves the first-failure
table the showcase asserts, so the new table belongs in the same commit.

## Reporting a bug

The best report is a **failing fixture**: the smallest byte stream that
reproduces it, the graphs you got, and the graphs you expected. If the receiver
and `spanweave.build` disagree about the same records, say so in those words —
that is this project's central claim failing, and it outranks everything else.

## License

Contributions are accepted under the MIT license (`LICENSE`).
