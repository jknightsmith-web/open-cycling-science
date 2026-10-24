# All targets run offline once `make setup` has fetched dependencies.
.PHONY: setup test test-backend test-frontend types types-check frontend e2e perf oracle run

setup:
	uv sync
	cd frontend && npm ci

test: test-backend test-frontend

test-backend:
	uv run --offline pytest

test-frontend: types-check
	cd frontend && npm test && npm run build

# Regenerate the TypeScript API types from the FastAPI schema.
types:
	uv run --offline python -m backend.api.openapi_export build/openapi.json
	cd frontend && npm run types

# Fails if the committed API types differ from the current backend schema.
types-check:
	uv run --offline python -m backend.api.openapi_export build/openapi.json
	cd frontend && npx openapi-typescript ../build/openapi.json -o ../build/schema.check.d.ts >/dev/null
	diff -q frontend/src/api/schema.d.ts build/schema.check.d.ts

frontend/dist/index.html: $(shell find frontend/src -type f) frontend/index.html frontend/package-lock.json
	cd frontend && npm run build

frontend: frontend/dist/index.html

# End to end tests in Chromium against a freshly seeded synthetic data root (UI-01 to UI-19).
e2e: frontend
	cd frontend && npx playwright test

# Performance run: 1,000 activities and a 3 h, 1 Hz ride. Results in frontend/perf-results/perf.json.
perf: frontend
	cd frontend && npx playwright test --config playwright.perf.config.ts

oracle:
	cd reference && python3 -m unittest -v test_metric_oracle

run: frontend
	uv run --offline python -m backend.api
