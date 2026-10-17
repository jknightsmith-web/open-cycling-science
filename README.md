# Open Cycling Science

Local first cycling performance analysis. Every number is either a sensor observation, a deterministic transform with a documented equation, or a model with documented assumptions, limitations and validation evidence. The rider owns all data.

**Status:** Phase One in development. No release yet. Specification: [`docs/spec/`](docs/spec/README.md).

## Development

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```
make setup   # once, fetches dependencies
make test    # runs offline
make oracle  # standard library only arithmetic reference
```

Rider data lives outside this repository, by default in `~/Library/Application Support/OpenCyclingScience/` on macOS (override with `OCS_DATA_ROOT`). Never commit activity files.

## Licence

MIT. Dependencies keep their own licences; see `DEPENDENCIES.md`.
