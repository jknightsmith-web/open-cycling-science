# Phase One progress

Updated 2026-10-24. Specification v1.0 (frozen). Repository: https://github.com/jknightsmith-web/open-cycling-science (full history pushed 2026-10-24); CI green on Linux (run 40079281341).

Test run (fresh clone, `uv sync --locked`, `uv run --offline pytest`): **73 passed, 0 failed**, including 8 oracle unit tests, a 300 example property test against the oracle and 16 importer tests on synthetic FIT, TCX and zip files. Network access is blocked for the whole suite.

## Work packages

| WP | Content | Status | Evidence | Remaining |
|---|---|---|---|---|
| 1 | Repo, licence, dependency register, offline run, CI | Done | MIT `LICENSE`, `DEPENDENCIES.md` with licences from package metadata, `make test`, `.github/workflows/ci.yml` | CI passed on GitHub Actions, run 40079281341 |
| 2 | Data root, vault, migrations, storage benchmark | Done in container; Mac benchmark pending | `backend/config.py`, `backend/storage/vault.py`, schema with 14 tables and P6 CHECK constraints, migration 0001; `tests/test_storage.py`. Benchmark (`tests/bench_storage.py`, Linux container, not a Mac): 2,016,000 sample rows inserted at 55,344 rows/s, 97.6 bytes per row including the primary key index, one 2 h activity read in 4.7 ms | Run at 20M rows on the Mac. Linear extrapolation (inference, not measured): about 2 GB and 6 minutes for 20M rows, above the 60 bytes per row the architecture estimated |
| 3 | FIT and TCX importers | Done on synthetic files; real file verification pending | `backend/importers/` (fit via fitdecode, tcx via defusedxml, zip with traversal and bomb limits, content sniffing); `tests/fit_encoder.py` writes FIT files with sentinels, absent fields, pauses, compressed timestamps and CRCs; `tests/test_importers.py` (16 tests) | Field mapping must be confirmed on a real Fenix 8 FIT, Hub TCX and MyWhoosh FIT. Persistence into the database comes with WP6 idempotent import |
| 4 | Timeline builder, validity, suspect zero, recording statistics | Done on synthetic data | `backend/canonical/timeline.py`; `tests/test_timeline.py` (17 tests) | Real file check after WP3 |
| 5 | M001 to M004, oracle agreement | Done | `backend/metrics/`; oracle updated to D1; `tests/test_metrics.py`, `tests/test_oracle_agreement.py` | None for synthetic scope |
| 6 to 10 | Duplicates and rides, registry and catalogue, UI, export and deletion, benchmark | Not started | | |

## Acceptance criteria (spec 9)

| # | Criterion | Status |
|---|---|---|
| 1 | Launches on macOS, 127.0.0.1 | Not started (WP8) |
| 2 | Real Fenix 8, Hub and MyWhoosh files import | Importers built and pass on synthetic files; needs your real files |
| 3 | Identical bytes create no activity | Partial: vault stores identical bytes once; activity level in WP6 |
| 4, 4a | Duplicate proposal, confirmation, per channel selection | Not started (WP6) |
| 5 | Vault SHA256 equals original | **Pass** |
| 6 | Zero, missing, invalid distinct | **Pass** from FIT and TCX parsing through timeline and database (sentinel becomes invalid, absent field becomes missing, CHECK constraints reject zero standing in for missing); export and display parts pending |
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
- WP4 was built before WP3 against the importer output structure (`RawActivity`), which the WP3 importers now produce.
- MyWhoosh speed and distance are marked simulated when the FIT manufacturer is `mywhoosh` (id 331 in the FIT profile) or the session sub sport is `virtual_activity`. Unverified on a real MyWhoosh file.
- Per channel sensor identity is taken from FIT `device_info` only when exactly one device of a matching ANT+ type exists; otherwise it is recorded as unknown with the candidates listed.
