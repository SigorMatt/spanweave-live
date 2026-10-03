# The acceptance harness. `make check` is THE gate a batch must pass before it
# counts as done (CONTRIBUTING.md, "The bar"): it wraps the exact toolchain
# commands plus the invariant gate as runnable checks.

.PHONY: check lint types test gates conformance install-check clean

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

# Conformance gate A (WORKPLAN.md R2, SPEC.md section 4): interleave two
# scenarios' records from the corpus, push them through Framer + Router, and
# assert each trace's graph serializes byte for byte to `spanweave.build` of
# its own rendering. R0 is the repository skeleton and has neither a Framer nor
# a Router, so there is nothing to compare yet and this target says so rather
# than printing a reassuring nothing. It becomes real in R2 and is green or red
# from then on.
conformance:
	@echo "conformance: NO GATE YET -- R0 is the repository skeleton."
	@echo "  Gate A (tests/test_conformance.py) arrives in R2: the corpus'"
	@echo "  renderings interleaved through Framer + Router, each trace's graph"
	@echo "  compared byte for byte against spanweave.build of its own rendering."
	@echo "  Until R2 this target asserts NOTHING. It is not a pass."
	@test -d corpus/fixtures/conformance || { \
	  echo "  corpus/ is not checked out: run 'git submodule update --init'"; \
	  exit 1; }
	@echo "  corpus/fixtures/conformance is present, so R2 has its scenarios."

# Prove that what SHIPS works: builds the wheel, installs it into a throwaway
# venv, and runs it from a working directory outside the repo -- the only gate
# that can catch a packaging break. Needs the network once, to resolve the
# pinned spanweave. Deliberately not a prerequisite of `check`; CI runs both.
install-check:
	uv run python -m tests.install_check

clean:
	rm -rf .mypy_cache .ruff_cache .pytest_cache dist/ out/
	find . -type d -name __pycache__ -not -path './corpus/*' -prune -exec rm -rf {} +
