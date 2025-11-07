.PHONY: default
default: help

.PHONY: help
help:
	@echo "Available targets:"
	@echo "  help                   Show this help message"
	@echo "  fix                    Format source code"
	@echo "  check                  Run checks"
	@echo "  test                   Run tests"
	@echo "  test-snapshot          Run tests, udpating snapshots"

.PHONY: fix
fix:
	uv run hatch run quality:format

.PHONY: check
check:
	uv run hatch run quality:check
	uv run hatch run quality:typecheck

.PHONY: test
test:
	uv run hatch run tests:run

.PHONY: test-snapshot
test-snapshot:
	uv run hatch run tests:run-snapshot
