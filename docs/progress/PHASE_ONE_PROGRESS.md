# Phase One progress

Updated 2026-10-24. Specification v1.0 (frozen). Repository: https://github.com/jknightsmith-web/open-cycling-science (full history pushed 2026-10-24); CI green on Linux (run 40079281341).

Test run 2026-10-24 (`uv sync --locked`, `uv run --offline pytest`): **122 passed, 0 failed**, including 8 oracle unit tests, a 300 example property test against the oracle, 17 importer tests, 10 import tests, 21 ride and duplicate tests, 10 registry tests, 6 API tests and a migration consistency test. Network access is blocked for the whole suite. Every test uses synthetic files; no real device compatibility is claimed (P10).

## Work packages

| WP | Content | Status | Evidence | Remaining |
|---|---|---|---|---|
| 1 | Repo, licence, dependency register, offline run, CI | Done | MIT `LICENSE`, `DEPENDENCIES.md` with licences from package metadata, `make test`, `.github/workflows/ci.yml` | CI passed on GitHub Actions, run 40079281341 |
| 2 | Data root, vault, migrations, storage benchmark | Done in container; Mac benchmark pending | `backend/config.py`, `backend/storage/vault.py`, schema with 14 tables and P6 CHECK constraints, migration 0001; `tests/test_storage.py`. Benchmark (`tests/bench_storage.py`, Linux container, not a Mac): 2,016,000 sample rows inserted at 55,344 rows/s, 97.6 bytes per row including the primary key index, one 2 h activity read in 4.7 ms | Run at 20M rows on the Mac. Linear extrapolation (inference, not measured): about 2 GB and 6 minutes for 20M rows, above the 60 bytes per row the architecture estimated |
| 3 | FIT and TCX importers | Done on synthetic files; real file verification pending | `backend/importers/` (fit via fitdecode, tcx via defusedxml, zip with traversal and bomb limits, content sniffing); `tests/fit_encoder.py` writes FIT files with sentinels, absent fields, pauses, compressed timestamps and CRCs; `tests/test_importers.py` (16 tests) | Field mapping must be confirmed on a real Fenix 8 FIT, Hub TCX and MyWhoosh FIT. Pending until Jimmy supplies recordings (his instruction, 2026-10-24) |
| 4 | Timeline builder, validity, suspect zero, recording statistics | Done on synthetic data | `backend/canonical/timeline.py`; `tests/test_timeline.py` (17 tests) | Real file check after WP3 |
| 5 | M001 to M004, oracle agreement | Done | `backend/metrics/`; oracle updated to D1; `tests/test_metrics.py`, `tests/test_oracle_agreement.py` | None for synthetic scope |
| 6 | Idempotent import, duplicate proposals, decisions, rides, per channel selection, overcount | Done on synthetic data | `backend/library/` (ingest, duplicates, rides, aggregates, metric_store); migration 0002; `tests/test_ingest.py`, `tests/test_rides.py`, `tests/test_api.py` | Real three source ride for Gate 1 |
| 7 | Registry for M001 to M004, completeness validator, Science catalogue | Done | `registry/metrics/*.yaml`, `registry/bibliography.yaml`, `registry/states.yaml`, `backend/science/registry.py`, `/science` pages and `/api/science`; `tests/test_registry.py` | WP8 Science screen will read `/api/science` |
| 8 to 10 | UI, export and deletion, benchmark | Not started | API used by WP8 exists (`backend/api/`) | |

## Acceptance criteria (spec 9)

| # | Criterion | Status |
|---|---|---|
| 1 | Launches on macOS, 127.0.0.1 | Partial: `make run` serves the API and catalogue on 127.0.0.1 (tested on Linux); macOS run and UI pending (WP8) |
| 2 | Real Fenix 8, Hub and MyWhoosh files import | Importers built and pass on synthetic files; needs your real files |
| 3 | Identical bytes create no activity | **Pass** (synthetic): reimport reports the existing activity, including for zip members and failed files |
| 4, 4a | Duplicate proposal, confirmation, per channel selection | **Pass** on synthetic Fenix, Hub and MyWhoosh style files; real files pending |
| 5 | Vault SHA256 equals original | **Pass** |
| 6 | Zero, missing, invalid distinct | **Pass** from FIT and TCX parsing through timeline and database (sentinel becomes invalid, absent field becomes missing, CHECK constraints reject zero standing in for missing); export and display parts pending |
| 7 | 200 W and 100/300 W results | **Pass** |
| 8 | 3 s gap invalidates crossing MMP windows | **Pass** |
| 9 | Timer stop changes timer, not elapsed | **Pass** |
| 10 | Time zone changes nothing | **Pass** for calculations; UI part pending |
| 11 | Low coverage: M002 unavailable, M003 lower bound | **Pass** |
| 12 | Every metric opens its register entry | **Pass** in the API and catalogue pages; WP8 UI pending |
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

## WP6 and WP7 decisions within the spec (2026-10-24)

- Duplicate rule 1.1 adds recording identity to the 80% overlap rule, at Jimmy's request. Logged as spec amendment 1, C28.
- A recording matching an already confirmed ride joins it as pending and counts separately until accepted or excluded (C29).
- The override for "count confirmed duplicates as one ride" is reopen, then optionally reject (C30).
- Confirmation needs every field stated explicitly (timer, power, heart rate, cadence, speed, distance, temperature). Saved preferences and a coverage based suggestion only prefill the form.
- Ride level values are copies of the selected activity's values with new ride scope runs, because Phase One never combines files within a metric (spec 5.8, C25).
- Aggregates are computed on request from stored runs, so they cannot be stale. Weekly bucketing by display time zone is left to the WP8 Overview.
- The potential overcount assumes the earliest member stays the source. The rider's selection can change the real difference.
- Every metric value states uncertainty as "not quantified" (spec 6.4 item 5).
- The science catalogue is server rendered with no scripts or network assets, so it works before the WP8 frontend.

## Outstanding issues

1. WP3 real file verification is pending until Jimmy supplies Fenix 8, Wattbike Hub and MyWhoosh recordings. Nothing here verifies real device compatibility.
2. WP9 deletion must remove ride scope runs and selection history that reference a deleted activity, so no hash survives (spec 8.4, acceptance 15). The cascades cover samples, channels, members, events and history rows; ride runs carry hashes in `provenance_json` and need explicit removal.
3. R12 (Pinot and Grappe 2011) is still an unconfirmed DOI. It does not block M004, whose status is IDENTITY, but it stays visible in the catalogue.
4. The register document's `software_test_status` fields (02, frozen 2026-10-17) still say "production not built". The in app registry carries the current status. The document will be updated at the next spec revision.
5. FastAPI pulls in `opentelemetry-api`. It sends nothing without an SDK, and the offline test covers the suite, but WP9's network test should run against the live server too.
6. The test client prints a deprecation warning from Starlette about httpx. It does not affect results.
