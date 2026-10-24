# Phase One progress

Updated 2026-10-24. Specification v1.0 (frozen). Repository: https://github.com/jknightsmith-web/open-cycling-science (full history pushed 2026-10-24); CI green on Linux (run 40079281341).

Test run 2026-10-24 after WP9, Linux container: backend `uv run --offline pytest` **186 passed, 0 failed** (WP8 had 135; WP9 adds 51: export and restore 24, deletion 14, interrupted operations 6, running server network 2, API 5); frontend `npm test` **15 passed, 0 failed**; end to end `npx playwright test` **16 passed, 0 failed** (WP8 had 11; WP9 adds 5); `make types-check` clean. Network access is blocked for the backend suite, the running server is audited for every socket call (below), and every end to end test aborts and fails on any request that is not to 127.0.0.1. Every test uses synthetic files; no real device compatibility is claimed (P10).

## Work packages

| WP | Content | Status | Evidence | Remaining |
|---|---|---|---|---|
| 1 | Repo, licence, dependency register, offline run, CI | Done | MIT `LICENSE`, `DEPENDENCIES.md` with licences from package metadata, `make test`, `.github/workflows/ci.yml` | CI passed on GitHub Actions, run 40079281341 |
| 2 | Data root, vault, migrations, storage benchmark | Done in container; Mac benchmark pending | `backend/config.py`, `backend/storage/vault.py`, schema with 14 tables and P6 CHECK constraints, migration 0001; `tests/test_storage.py`. Benchmark (`tests/bench_storage.py`, Linux container, not a Mac): 2,016,000 sample rows inserted at 55,344 rows/s, 97.6 bytes per row including the primary key index, one 2 h activity read in 4.7 ms | Run at 20M rows on the Mac. Linear extrapolation (inference, not measured): about 2 GB and 6 minutes for 20M rows, above the 60 bytes per row the architecture estimated |
| 3 | FIT and TCX importers | Done on synthetic files; real file verification pending | `backend/importers/` (fit via fitdecode, tcx via defusedxml, zip with traversal and bomb limits, content sniffing); `tests/fit_encoder.py` writes FIT files with sentinels, absent fields, pauses, compressed timestamps and CRCs; `tests/test_importers.py` (16 tests) | Field mapping must be confirmed on a real Fenix 8 FIT, Hub TCX and MyWhoosh FIT. Pending until Jimmy supplies recordings (his instruction, 2026-10-24) |
| 4 | Timeline builder, validity, suspect zero, recording statistics | Done on synthetic data | `backend/canonical/timeline.py`; `tests/test_timeline.py` (17 tests) | Real file check after WP3 |
| 5 | M001 to M004, oracle agreement | Done | `backend/metrics/`; oracle updated to D1; `tests/test_metrics.py`, `tests/test_oracle_agreement.py` | None for synthetic scope |
| 6 | Idempotent import, duplicate proposals, decisions, rides, per channel selection, overcount | Done on synthetic data | `backend/library/` (ingest, duplicates, rides, aggregates, metric_store); migration 0002; `tests/test_ingest.py`, `tests/test_rides.py`, `tests/test_api.py` | Real three source ride for Gate 1 |
| 7 | Registry for M001 to M004, completeness validator, Science catalogue | Done | `registry/metrics/*.yaml`, `registry/bibliography.yaml`, `registry/states.yaml`, `backend/science/registry.py`, `/catalogue` pages and `/api/science`; `tests/test_registry.py` | None |
| 8 | Interface: Overview, Library, Activity (recording and ride modes), Science, Settings | Done on Linux, awaiting review; macOS measurement pending | Design `docs/spec/06_INTERFACE_DESIGN.md` v0.2; API additions B1 to B8 in `backend/api/`, `backend/library/series.py`, migration 0003; `frontend/` (React, uPlot); `frontend/e2e/screens.spec.ts`, `frontend/e2e/perf.spec.ts`; acceptance table below | macOS run of `make run` and `make perf`; Jimmy's review |
| 9 | Export, archive restoration, deletion | Done on synthetic data, awaiting review | `backend/library/exports.py`, `restore.py`, `deletion.py`, `backend/storage/maintenance.py`, `backend/importers/location.py`; migration 0004; endpoints under `/api/exports`, `/api/export/archive`, `/api/restore`, `/api/activities/{id}` and `/api/imports/{id}` (DELETE and `/deletion` preview), `/api/data/delete-all`, `/api/rides-needing-review`; tests `test_export_restore.py`, `test_deletion.py`, `test_interruptions.py`, `test_running_app_network.py`, `test_api_wp9.py`, `frontend/e2e/wp9.spec.ts` | Jimmy's review of the choices below |
| 10 | Benchmark | Not started | | Waits for WP9 review |

## Acceptance criteria (spec 9)

| # | Criterion | Status |
|---|---|---|
| 1 | Launches on macOS, 127.0.0.1 | Partial: `make run` builds the interface and serves it on 127.0.0.1 (tested on Linux); macOS run pending |
| 2 | Real Fenix 8, Hub and MyWhoosh files import | Importers built and pass on synthetic files; needs your real files |
| 3 | Identical bytes create no activity | **Pass** (synthetic): reimport reports the existing activity, including for zip members and failed files |
| 4, 4a | Duplicate proposal, confirmation, per channel selection | **Pass** on synthetic Fenix, Hub and MyWhoosh style files; real files pending |
| 5 | Vault SHA256 equals original | **Pass** |
| 6 | Zero, missing, invalid distinct | **Pass** from FIT and TCX parsing through timeline and database (sentinel becomes invalid, absent field becomes missing, CHECK constraints reject zero standing in for missing); display **Pass** (UI-07, end to end); export **Pass**: in the derived CSV an observed zero is written `0.0`, missing and invalid are empty and told apart by the `power_validity` column, JSON Lines writes `null`; the archive restores every row equal (`test_export_restore.py`: `test_derived_csv_follows_rfc4180_with_empty_for_missing_and_no_rounding`, `test_full_archive_round_trip_reproduces_every_row_hash_and_value`) |
| 7 | 200 W and 100/300 W results | **Pass** |
| 8 | 3 s gap invalidates crossing MMP windows | **Pass** |
| 9 | Timer stop changes timer, not elapsed | **Pass** |
| 10 | Time zone changes nothing | **Pass** for calculations and display (UI-10, end to end) |
| 11 | Low coverage: M002 unavailable, M003 lower bound | **Pass** |
| 12 | Every metric opens its register entry | **Pass** (UI-08, end to end) |
| 13 | Production agrees with oracle | **Pass** (fixtures plus 300 generated activities with gaps, pauses, fractional intervals) |
| 14 | Archive round trip | **Pass** on synthetic data. Export, delete everything, restore into an empty install: every row of every table equal, every vault object rehashed equal, metric values and states equal, and each original re-parsed and recomputed to the archived timeline digest and values (`test_export_restore.py`; end to end in `wp9.spec.ts`). Tampered, truncated, extra member, wrong schema and non empty target archives are refused before anything is written |
| 15 | Deletion marker scan | **Pass** on synthetic data. Every deletion test ends with a byte scan of every file and path under the data root (database, WAL, SHM, vault, exports) for the deleted file's SHA256 (hex in either case, and raw bytes) and its filename (UTF-8 and UTF-16), and checks the WAL is truncated; no VACUUM is run (`test_deletion.py`, 14 tests). Cases: a solo recording whose filename is a marker, the power source of a confirmed ride, the timer source, a confirmed group dissolving, a proposed pair, a pending member, an export holding the file, every recording deleted one by one, delete everything. A control test shows the scan finds the hash and marker before deletion. Also passes after a crash between commit and file removal (`test_interruptions.py`). GPS positions are not in the database at all (scan for the latitude value) |
| 16 | Offline import, calculation, export | **Pass**. Backend suite with networking blocked; the running server (uvicorn, `python -m backend.api`) run under a PEP 578 audit hook (`tests/netwatch.py`) through import, confirmation, every screen's API, all three exports, deletion, delete everything and restore records only the bind on 127.0.0.1 (`test_running_app_network.py`); the same hook wraps the end to end server and the last e2e test checks its log. A positive control proves the hook catches a call to 192.0.2.1 |
| 17 | Data root outside source tree, rider files ignored | **Pass** |
| 17a | Recording statistics, no rejection on recording mode | **Pass** (UI-11, end to end) |
| 18 | Large history benchmark | Not started (WP10). Indicative only: 3 h at 1 Hz builds in 0.06 s, five MMP durations in 0.13 s |
| 19 | Backend and frontend suites offline | **Pass** locally (Linux): backend, Vitest and Playwright run with no network; CI runs all three |

## WP8 acceptance (design 06, section 7)

Measured in the Linux container (4 core Xeon 2.1 GHz, headless Chromium 141). None of this is a macOS measurement.

| # | Criterion | Status | Evidence |
|---|---|---|---|
| UI-01 | `make run` on macOS, 127.0.0.1 only, works offline | Partial: Linux only | Server binds 127.0.0.1; every end to end test runs against it. macOS run pending |
| UI-02 | No request leaves 127.0.0.1; bundle holds no remote URLs except DOI links | **Pass** | Route guard in `e2e/fixtures.ts` aborts and fails on any other host; bundle scan test. The bundle also contains XML namespace strings and two library error message URLs, which are never fetched |
| UI-03 | Import outcomes: imported, identical bytes with a link, failed with the reason | **Pass** | `UI-03` test. A file that is not FIT, TCX or ZIP is reported at import time but not stored (WP2 behaviour), so it does not appear in the import log |
| UI-04 | Proposed group with evidence; Overview shows both rides and the overcount | **Pass** | `UI-04` test |
| UI-05 | Confirm gives one ride with named sources; totals drop; reopen and reject restore them | **Pass** | `UI-05 UI-06` test: 1:49:15 and 5 rides before, 49:30 and 3 rides after confirming, 1:49:15 and 5 rides after reopen and after reject |
| UI-06 | Power, heart rate and cadence from different members | **Pass** | Same test: power from the Hub file, heart rate from the Fenix file, cadence from the MyWhoosh file |
| UI-07 | Observed 0, missing, invalid and suspect zero distinct without colour; no absent value shown as 0 | **Pass** | `UI-07` test reads every sample row; chart legend names each band |
| UI-08 | Every metric shows its class and opens its register entry | **Pass** | `UI-08` test |
| UI-09 | Unavailable metrics name their state; lower bounds read "at least" | **Pass** | `UI-09` test |
| UI-10 | Display time zone changes labels and weeks only | **Pass** | `UI-10` test: all eight metric values identical, date labels change |
| UI-11 | Recording statistics and flags, no adequacy verdict | **Pass** | `UI-11` test |
| UI-12 | 1,000 activities: Library, Overview and Activity load without fetching all samples | **Pass** (Linux) | `perf.spec.ts`: largest sample request 60 rows; charts use the bounded envelope |
| UI-13 | No metric computed in the frontend | **Pass** | `src/noMetricComputation.test.ts`, with a planted case proving the scan is not vacuous |
| UI-14 | No training load, readiness, fitness, fatigue, FTP, zone or kcal value | **Pass** | `UI-14` test over every screen except the register text; register lists M001 to M004 only |
| UI-15 | Frontend tests offline in CI and locally | **Pass** | Locally, and GitHub Actions run 40085444723 (backend, Vitest, types check, build, Playwright) |
| UI-16 | Library with 1,000 activities in at most 2 s | **Pass** (Linux): median 145 ms, max 168 ms over 5 cold loads | macOS pending |
| UI-17 | Activity screen, 3 h at 1 Hz, in at most 2 s | **Pass** (Linux): median 319 ms, max 394 ms over 5 cold loads | macOS pending |
| UI-18 | Heap and chart responsiveness recorded | **Recorded** (Linux): JS heap after GC 3.0 MB Library, 2.8 MB Overview, 2.9 MB Activity; zoom redraw 4 to 17 ms (includes waiting for the next frame); channel switch 41 to 180 ms including the API request | macOS pending |
| UI-19 | Charts never connect observations across missing, invalid, gap or paused intervals | **Pass** | Unit tests (`chartData.test.ts`, 500 random trials), backend envelope property test (300 examples), and a pixel test in the browser that reads the canvas inside every break. A deliberately broken build that drops the separating nulls failed the pixel test for all four break kinds |

Overview with 1,000 activities: median 284 ms, max 309 ms. Raw results: `frontend/perf-results/perf.json` after `make perf` (not committed).

## WP8 choices within the approved design

- The chart zooms within the envelope it was given (about 1,200 points for 3 h). Each bucket keeps its first, minimum, maximum and last value, so peaks stay visible, but zooming far in on a long ride shows bucket resolution, not every sample. The Samples table shows every sample.
- The Samples table is collapsed by default and pages 60 rows at a time.
- M004 cards on the Activity and Overview screens are titled by window (5 s, 1 min) under a "Highest observed power" heading; the full name stays in the information panel.

## WP9 choices within the spec (need Jimmy's review)

1. GPS positions are no longer stored. Spec 8.2 keeps positions out of the database; the WP4 importer still kept them in `original_field_json`. Migration 0004 strips them from existing rows and the importer drops any field named for position, latitude or longitude. Exported originals still contain GPS (the files are unchanged); Settings warns.
2. Exports are written to `exports/` in the data root (atomic, `.partial-` then rename) and listed in Settings for download. Deleting a recording also deletes every saved export that contains it, and the confirmation lists them.
3. The JSON form of the derived export is JSON Lines, one file per table, beside the CSV.
4. When a confirmed group falls below two members it dissolves: the ride, its runs and its selection history go, and the remaining recording counts on its own again. When it keeps two or more members, history rows keep their place with the activity id cleared and `source_deleted` set.
5. Ride scope runs whose provenance names the deleted file are deleted and recomputed from the remaining selection. Deletion refuses to commit if any remaining run's provenance still contains the hash.
6. A ride whose timer source was deleted has no values and is not counted until the rider chooses a new timer. Overview and the ride page show a notice; `/api/rides-needing-review` lists them.
7. Restore only goes into an empty install with the same schema revision, and checks the archive manifest, every member's size and hash, every original against its row, metric definitions, and a recompute of each recording before it writes anything.
8. `DELETE /api/imports/{id}` deletes a file that failed to parse (no activity), from the Library's failed list.
9. Delete everything removes only the folders the app created (`vault`, `db`, `exports`, `backups`, `logs`), lists anything else it keeps, and leaves an empty working install. It needs a token from the preview, so the confirmation shows exactly what goes.
10. Single deletions use `secure_delete` and a WAL checkpoint, not VACUUM; the marker scan passes without it. Delete everything removes the files outright.
11. Opening the library recovers from an interrupted operation: it removes orphan vault objects, half written vault and export files and any export that holds a file no longer in the library, then truncates the WAL.

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
2. Closed in WP9: ride scope runs, `provenance_json`, selection history and duplicate events are scrubbed on deletion (acceptance 15).
3. R12 (Pinot and Grappe 2011) is still an unconfirmed DOI. It does not block M004, whose status is IDENTITY, but it stays visible in the catalogue.
4. The register document's `software_test_status` fields (02, frozen 2026-10-17) still say "production not built". The in app registry carries the current status. The document will be updated at the next spec revision.
5. Closed in WP9: the running server was audited for socket calls and made none except the bind on 127.0.0.1. FastAPI still installs `opentelemetry-api`, which sends nothing without an SDK.
6. The test client prints a deprecation warning from Starlette about httpx. It does not affect results.
7. WP8 performance and the `make run` launch have been measured on Linux only. Run `make setup`, `make run` and `make perf` on the Mac to get macOS figures (UI-01, UI-16 to UI-18).
8. `make run` now builds the interface first, so the Mac needs Node.js 22 (or 20.19+) and npm as well as uv.
9. DOI links in the register open in the system browser when clicked. That is the only outbound action in the interface and only happens on a click.
10. What the app cannot delete, shown in Settings: copies outside the data folder (downloaded or moved exports), Time Machine backups and APFS local snapshots, old SSD blocks (FileVault is relied on to protect them), and recordings in vendor accounts.
11. WP9 restore and deletion are tested on Linux only. The Mac run (`make test`, `make e2e`) should repeat them, including the marker scan on APFS.
