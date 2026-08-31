# Every Python tool runs from the environment `uv` syncs out of `uv.lock`, so the lockfile
# governs what `make check` and `make test` actually execute. This is the same guarantee pixi
# gave (#17) and, before it, the one `uv run hatch run <env>:<script>` did not: hatch built
# its own `quality` and `tests` environments and resolved them fresh against the index, so
# the lockfile's only contribution was the `hatch` binary itself (#9). `--locked` additionally
# fails rather than re-resolving if `uv.lock` has gone stale against `pyproject.toml`.
#
# uv replaced pixi in #38, once #37 removed pycairo and left no dependency that needs conda.
# It is a replacement and not an addition: there is one lockfile, and `pixi.lock` is gone.
# The interpreter comes from `.python-version`, which is what `[tool.pixi.feature.py313]`
# used to pin.
UV_RUN := uv run --locked

# Shared by `test` and `test-snapshot` so the two cannot drift into running different
# suites -- the snapshot update has to be the same run, or it records snapshots for
# something `make test` does not execute. `src/mgm_muc1_vntr` is a collection path, not a
# typo: `[tool.pytest.ini_options] addopts = "--doctest-modules"` collects the doctests in
# the package itself.
PYTEST := $(UV_RUN) pytest --cov=src/mgm_muc1_vntr --cov-report=term-missing \
	--durations 5 -s tests/ src/mgm_muc1_vntr

.PHONY: default
default: help

.PHONY: help
help:
	@echo "Available targets:"
	@echo "  help                   Show this help message"
	@echo "  check                  Run all checks (format, lint, types)"
	@echo "  check-format           Check formatting with black"
	@echo "  check-lint             Lint with ruff"
	@echo "  check-types            Type check with pyright"
	@echo "  fix                    Format source code and apply ruff fixes"
	@echo "  test                   Run tests with coverage"
	@echo "  test-snapshot          Run tests, updating snapshots"
	@echo "  build                  Build the sdist and wheel"
	@echo "  lock                   Upgrade the lock file"

# `check` is the composition; the pieces are separate targets so CI can name the gate that
# failed and still run byte-identical commands to a local run.
.PHONY: check
check:
	$(MAKE) check-format
	$(MAKE) check-lint
	$(MAKE) check-types

.PHONY: check-format
check-format:
	$(UV_RUN) black --check --diff --preview src tests

.PHONY: check-lint
check-lint:
	$(UV_RUN) ruff check src tests

# No `--pythonpath` needed. Under `uv run` there is exactly one environment for pyright to
# analyse, so the nested `uv run --active hatch run quality:python -c ...` that used to
# discover which of the two venvs to point at is gone (#9).
.PHONY: check-types
check-types:
	$(UV_RUN) pyright src/ tests/

.PHONY: fix
fix:
	$(UV_RUN) black --preview src tests
	$(UV_RUN) ruff check --fix --unsafe-fixes src tests
	$(MAKE) check-lint

.PHONY: test
test:
	$(PYTEST)

.PHONY: test-snapshot
test-snapshot:
	$(PYTEST) --snapshot-update

# `python -m build` rather than `uv build`, which is what the pixi switch (#17) left behind
# and what replaced the `[tool.hatch.envs.build]` environment whose only script was
# `hatch build`. All three drive the same `hatchling` backend from `[build-system]`; keeping
# the PEP 517 frontend means `make build` is not tied to uv's own build path.
.PHONY: build
build:
	$(UV_RUN) python -m build

# `uv lock` alone only refreshes the lockfile against the manifest. `--upgrade` is what moves
# every package to the newest version the constraints allow, which is what `pixi update` did.
.PHONY: lock
lock:
	uv lock --upgrade
