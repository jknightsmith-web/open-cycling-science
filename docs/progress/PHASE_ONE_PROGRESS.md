# Phase One progress

Updated 2026-10-17. Specification v1.0 (frozen). Repository: local Git at `/mnt/project-files/code/open-cycling-science`, 5 commits; no GitHub repository attached yet, so CI has not run.

Test run (fresh clone, `uv sync --locked`, `uv run --offline pytest`): **57 passed, 0 failed**, including 8 oracle unit tests and a 300 example property test against the oracle. Network access is blocked for the whole suite.

## Work packages

| WP | Content | Status | Evidence | Remaining |
|---|---|---|---|---|
| 1 | Repo, licence, dependency register, offline run, CI | Done, CI unverified | MIT `LICENSE`, `DEPENDENCIES.md` with licences from package metadata, `make test`, `.github/workflows/ci.yml` | CI runs only once a GitHub repository exists |
| 2 | Data root, vault, migrations, storage benchmark | Mostly done | `backend/config.py`, `backend/storage/vault.py`, schema with 14 tables and P6 CHECK constraints, migration 0001; `tests/test_storage.py` | 20M sample storage benchmark not run |
| 3 | FIT and TCX importers | Not started | | Next. Real file verification needs your files |
| 4 | Timeline builder, validity, suspect zero, recording statistics | Done on synthetic data | `backend/canonical/timeline.py`; `tests/test_timeline.py` (17 tests) | Real file check after WP3 |
| 5 | M001 to M004, oracle agreement | Done | `backend/metrics/`; oracle updated to D1; `tests/test_metrics.py`, `tests/test_oracle_agreement.py` | None for synthetic scope |
| 6 to 10 | Duplicates and rides, registry and catalogue, UI, export and deletion, benchmark | Not started | | |

## Acceptance criteria (spec 9)

| # | Criterion | Status |
|---|---|---|
| 1 | Launches on macOS, 127.0.0.1 | Not started (WP8) |
| 2 | Real Fenix 8, Hub and MyWhoosh files import | Not started (WP3, needs files) |
| 3 | Identical bytes create no activity | Partial: vault stores identical bytes once; activity level in WP6 |
| 4, 4a | Duplicate proposal, confirmation, per channel selection | Not started (WP6) |
| 5 | Vault SHA256 equals original | **Pass** |
| 6 | Zero, missing, invalid distinct | **Pass** in timeline and database (CHECK constraints reject zero standing in for missing); export and display parts pending |
| 7 | 200 W and 100/300 W results | **Pass** |
| 8 | 3 s gap invalidates crossing MMP windows | **Pass** |
| 9 | Timer stop changes timer, not elapsed | **Pass** |
| 10 | Time zone changes nothing | **Pass** for calculations; UI part pending |
| 11 | Low coverage: M002 unavailable, M003 lower bound | **Pass** |
| 12 | Every metric opens its register entry | Not started (WP7) |
| 13 | Production agrees with oracle | **Pass** (fixtures plus 300 generated activities with gaps, pauses, fractional intervals) |
| 14 | Archive round trip | Not started (WP9) |
| 15 | Deletion marker scan | Not started (WP9); `secure_delete` pragma and cascades in place |
| 16 | Offline import, calculation, export | Partial: test suite runs with networking blocked; import and export not built |
| 17 | Data root outside source tree, rider files ignored | **Pass** |
| 17a | Recording statistics, no rejection on recording mode | **Pass** in timeline; reporting in UI pending |
| 18 | Large history benchmark | Not started (WP10). Indicative only: 3 h at 1 Hz builds in 0.06 s, five MMP durations in 0.13 s |
| 19 | Backend and frontend suites offline | Partial: backend yes, no frontend yet |

## Implementation choices within the spec

- Time comparisons use a 1 microsecond tolerance. Float64 epoch seconds carry about 0.2 microsecond error, so a tighter tolerance misclassified fractional TCX style timestamps in testing.
- A file with fewer than two distinct timestamps gets the flag `insufficient_samples` and no metrics, because the nominal interval is undefined.
- M004 windows shorter than the available contiguous data report the existing state `insufficient_coverage`.
- WP4 was built before WP3 against the importer output structure (`RawActivity`), which the WP3 importers will produce.
