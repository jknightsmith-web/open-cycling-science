# All targets run offline once `make setup` has fetched dependencies.
.PHONY: setup test oracle run

setup:
	uv sync

test:
	uv run --offline pytest

oracle:
	cd reference && python3 -m unittest -v test_metric_oracle

run:
	uv run --offline python -m backend.api
