# Changelog

All notable changes to this project. **Nothing here is frozen**: the version is
`0.0.x`, and until that changes any entry below may be undone by the next one.

The format is loosely [Keep a Changelog](https://keepachangelog.com/); the unit
of change is a **batch** (`WORKPLAN.md`), and each entry names the batch.

## Unreleased

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
