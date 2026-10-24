# Open Cycling Science

Local first cycling performance analysis. Every number is either a sensor observation, a deterministic transform with a documented equation, or a model with documented assumptions, limitations and validation evidence. The rider owns all data.

**Status:** Phase One in development. No release yet. Specification: [`docs/spec/`](docs/spec/README.md).

## Development

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/) and Node.js 22 (or 20.19+) with npm.

```
make setup   # once, fetches Python and npm dependencies
make test    # backend and frontend unit tests, offline
make e2e     # end to end tests in Chromium on synthetic data
make perf    # load time, memory and chart timings with 1,000 synthetic activities
make oracle  # standard library only arithmetic reference
make run     # builds the interface if needed and serves it on http://127.0.0.1:8765 (OCS_PORT to change)
```

`make e2e` and `make perf` need a Chromium for Playwright (`cd frontend && npx playwright install chromium`, once).

The interface has five screens: Overview, Library, Activity (one recording, or a confirmed ride), Science and Settings. The API is under `/api`; the server rendered catalogue is at `/catalogue`. Interface design: `docs/spec/06_INTERFACE_DESIGN.md`.

Rider data lives outside this repository, by default in `~/Library/Application Support/OpenCyclingScience/` on macOS (override with `OCS_DATA_ROOT`). Never commit activity files.

## Licence

MIT. Dependencies keep their own licences; see `DEPENDENCIES.md`.
