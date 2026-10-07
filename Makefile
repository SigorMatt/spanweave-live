# The acceptance harness. `make check` is THE gate a batch must pass before it
# counts as done (CONTRIBUTING.md, "The bar"): it wraps the exact toolchain
# commands plus the invariant gate as runnable checks.

.PHONY: check lint types test gates conformance showcase install-check clean

check: lint types test gates
	uv run spanweave-live --version

lint:
	uv run ruff check .
	uv run ruff format --check .

types:
	uv run mypy spanweave_live

test:
	uv run pytest

# The invariant gate. Its own target so a failure names the invariant that
# broke rather than "some test failed": no module under spanweave_live/ reaches
# for the clock, randomness, a socket or concurrency outside an injected seam
# (CLAUDE.md, standing rules). `check` runs it too, via `test`; this target is
# how you run it alone, and how CI names it in a log.
gates:
	uv run pytest tests/test_gates.py tests/test_pins.py -v

# Conformance gate A (SPEC.md section 4.7): every pair of renderings from two
# corpus scenarios, one of them relabelled onto a second trace id, interleaved
# by a seeded shuffle, framed in seeded chunks through one Framer, routed
# through one Router -- and each trace's graph compared BYTE FOR BYTE against
# spanweave.build of its own rendering. This is the project's central claim and
# from R2 onward this target is green or red; it no longer asserts nothing.
#
# It is also run by `check`, via `test`. This target is how you run it alone,
# and how CI names it in a log.
conformance:
	@test -d corpus/fixtures/conformance || { \
	  echo "corpus/ is not checked out: run 'git submodule update --init'"; \
	  exit 1; }
	uv run pytest tests/test_conformance.py -v

# The showcase (SPEC.md section 9): agentgolden's support-agent rules, UNCHANGED,
# evaluated on every per-record delta of agentgolden's own skipped_verification
# trace, with the first version at which each rule failed asserted exactly. It
# prints the table and then asserts it, because a table a human can read is
# what makes the claim checkable by someone who does not run pytest.
#
# It is also run by `check`, via `test`. This target is how you run it alone.
# The consumer lives in tests/, never in spanweave_live/: the receiver carries
# no rules (CLAUDE.md, standing rule 2), and a gate fails the build if the
# package imports the rule engine.
showcase:
	@test -d showcase/examples || { \
	  echo "showcase/ is not checked out: run 'git submodule update --init'"; \
	  exit 1; }
	uv run python -m tests.showcase
	uv run pytest tests/test_showcase.py -v

# Prove that what SHIPS works: builds the wheel, installs it into a throwaway
# venv, and runs it from a working directory outside the repo -- the only gate
# that can catch a packaging break. Needs the network once, to resolve the
# pinned spanweave. Deliberately not a prerequisite of `check`; CI runs both.
install-check:
	uv run python -m tests.install_check

clean:
	rm -rf .mypy_cache .ruff_cache .pytest_cache dist/ out/
	find . -type d -name __pycache__ -not -path './corpus/*' \
	  -not -path './showcase/*' -prune -exec rm -rf {} +
