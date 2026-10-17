# Open Cycling Science: Technical Architecture

| Field | Value |
|---|---|
| Document | 03 Technical architecture (authoritative) |
| Version | 1.0 PHASE ONE FROZEN (approved by Jimmy 2026-10-17) |
| Date | 2026-10-17 |
| Normative source for behaviour | `01_SPECIFICATION.md`. This document says how; where it seems to disagree, the specification wins and the conflict is logged. |

## 1. Shape

Local Mac application: a Python process (import, normalisation, calculation, API) and a React/TypeScript browser UI served by the same process. One SQLite database and one content addressed file vault, both under the data root.

```
FIT / TCX / ZIP (rider owned)
  -> import adapter (per format)          backend/importers/
  -> vault (sha256, read only)             <data_root>/vault/
  -> canonical samples + timer segments    backend/canonical/
  -> pure metric functions                 backend/metrics/
  -> metric runs + values + provenance     SQLite
  -> local API (127.0.0.1)                 backend/api/
  -> React UI                              frontend/
```

## 2. Stack

| Layer | Choice | Reason | Status |
|---|---|---|---|
| Language (backend) | Python 3.12+ | Scientific ecosystem, readable reference code | Agreed in pack |
| API | FastAPI + Pydantic v2 | Typed schemas, generated OpenAPI | Agreed |
| Storage | SQLite (WAL), SQLAlchemy 2 Core, Alembic | Single file, no server, migrations | Agreed |
| Numerics | Python stdlib for Phase One metrics; NumPy only if a benchmark shows need | Fewer dependencies, exact float behaviour easier to audit | Proposed |
| FIT decoding | `fitdecode` 0.11.0, pinned `[D8]` | MIT, pure Python, no runtime dependencies | Licence verified (MIT, LICENSE.txt in wheel). Embedded FIT profile from Garmin SDK 21.171 (Aug 2025); current SDK is 21.218. Unknown newer messages arrive as raw fields and are kept in `original_field_json` |
| FIT test files | Small FIT encoder written in `tests/` for synthetic fixtures (record, event, session, device_info messages, with CRC) | Lets tests create files with gaps, sentinels, pauses and compressed timestamps without a proprietary SDK | Proposed |
| TCX | `defusedxml` + stdlib ElementTree, namespace aware | Safe XML parsing | Proposed |
| Frontend | React, TypeScript, Vite; charting library chosen at WP7 after licence check | Agreed in pack | Charting library open |
| Tests | pytest, hypothesis (property tests against oracle), Vitest + Playwright smoke | | Proposed |
| Packaging | `uv` lock file; single `make run` / `./run.sh`; frontend built to static assets served by FastAPI | Offline install after first fetch | Proposed |

## 3. Repository layout

```
backend/
  importers/   fit.py, tcx.py, archive.py      -> RawActivity
  canonical/   timeline.py (sec 5.3 to 5.5 of spec), validity.py
  metrics/     m001_duration.py ... m004_mmp.py, registry.py
  science/     register loader, completeness validator
  storage/     models, migrations, vault.py
  api/
frontend/
reference/     metric_oracle.py (independent oracle, kept stdlib only)
registry/      metrics/*.yaml (machine readable register entries)
fixtures/      synthetic/ (committed), real/ (gitignored, local only)
tests/
docs/          spec set copied from /spec on approval
```

Data root is never inside the repository. `fixtures/real/` and any `*.fit`, `*.tcx` outside `fixtures/synthetic/` are gitignored, and a test asserts this.

## 4. Canonical model

`RawActivity` (adapter output): source format, device identity list, records with raw field dict, events, laps, session summary. No unit conversion beyond what the format defines.

`Timeline` (canonical): ordered list of `Interval(start_s, end_s, channels{name: (value, state)}, timer_running)` built by the rules in spec 5.3 and 5.4. Both production metrics and the oracle consume this same structure, so the oracle check covers the metric code and the timeline builder is tested separately.

FIT mapping (to be confirmed against real Fenix 8 and MyWhoosh files in WP3):

| Canonical | FIT message.field | Units | Invalid |
|---|---|---|---|
| timestamp | record.timestamp | s since 1989-12-31 UTC | |
| power_w | record.power | W | 0xFFFF |
| heart_rate_bpm | record.heart_rate | bpm | 0xFF |
| cadence_rpm | record.cadence (+ fractional_cadence) | rpm | 0xFF |
| speed_mps | record.enhanced_speed, else record.speed | m/s | |
| distance_m | record.distance | m | |
| temperature_c | record.temperature | °C | 0x7F |
| timer | event.event = timer, event_type start/stop/stop_all | | |
| device_timer_s | session.total_timer_time | s | |

The decoder's scaled outputs are used; tests assert that sentinel values arrive as invalid, not as numbers.

TCX mapping: `Trackpoint/Time`, `HeartRateBpm/Value`, `Cadence`, `Extensions/TPX/Watts` (namespace `http://www.garmin.com/xmlschemas/ActivityExtension/v2`), `Lap/TotalTimeSeconds`. Absent `Watts` = missing, never 0.

## 5. Database

Tables from the pack, with these changes (each logged in `05_CONFLICTS_AND_RESOLUTIONS.md`):

- `source_files`: add `refcount` view or query; `relative_storage_path` is relative to the data root.
- `activities`: add `timer_source`, `device_timer_s`, `nominal_interval_s`, `recording_flags`.
- `activity_channels` (new): `activity_id, channel, present, sensor_identity_json, origin (measured/simulated), observed_s, invalid_count, suspect_zero_s`. Sensor identity is stored as found in the file; the `devices` table arrives in Phase Two.
- `duplicate_groups` (new): `id, proposed_at_utc, rule_version, overlap_json, status (proposed/confirmed/rejected), decided_at_utc`.
- `duplicate_group_members` (new): `group_id, activity_id`.
- `rides` (new): `id, kind (single/group), activity_id_nullable, group_id_nullable`. Every activity not in a confirmed group is its own ride; a rejected or proposed group leaves each member as its own ride.
- `ride_channel_sources` (new): `ride_id, channel, activity_id_nullable, selected_at_utc, selection_revision`. Null activity means no member recorded that channel.
- `channel_preferences` (new): ordered rules per channel used only to prefill the confirmation form.
- `samples`: add `cadence_validity`, `speed_validity`, `distance_validity`, `temp_validity`, `suspect_zero` flag; keep `original_field_json`. No position columns in Phase One. Unique key `(activity_id, sample_index)`.
- `timer_segments` (new, derived): `activity_id, start_utc, end_utc, source`.
- `metric_runs`: `scope_type` is `activity`, `ride` or `aggregate`. `input_revision` = SHA256 of the canonical timeline serialisation plus, for ride and aggregate scope, the ride composition and channel selection revision, so any change is detectable.
- `metric_values`: `numeric_value` nullable, `state` enum (`valid`, `lower_bound`, `insufficient_coverage`, `no_power`, `not_applicable`, `unconfirmed_duplicates_included`), `units`, `uncertainty_json` (null = not quantified).
- `devices`, `threshold_history`, `test_efforts`, `model_fits`: created in Phase Two migrations, not Phase One.

Storage estimate (inference, to benchmark in WP2): about 60 bytes per sample row before indexes, so 20 million samples is roughly 1.2 to 2 GB. If benchmarks exceed tolerable size, store samples per activity as compressed columnar blobs keyed by activity; the canonical model does not change.

## 6. Algorithms

- **Mean power and work (M002, M003):** single pass sum over intervals. Float64; no intermediate rounding.
- **MMP (M004):** for each contiguous valid run, prefix sum of energy at interval boundaries; for window T use two pointers over boundaries and the candidate set {boundary, boundary − T}, evaluating energy by linear interpolation of the prefix sum (exact for step functions). O(n) per window per run. The oracle's O(n²) scan stays as the reference. Property tests (hypothesis) generate random step series with gaps and pauses and require agreement within 1e-9 relative.
- **Duplicate proposal:** interval overlap on timer segments; O(n log n) by start time. Proposals never change rides.
- **Aggregates:** computed over rides. Weekly totals report two numbers when unconfirmed groups exist: the total as counted, and the amount attributable to non first members of unconfirmed groups (the potential overcount).
- **Recomputation:** a run is stale when the metric version, parameters or `input_revision` change. Old runs are retained.

## 7. Dependency and licence policy

- Project licence: MIT, as intended in the starter pack, `LICENSE` file added at WP1. With D8 every planned runtime dependency is under an OSI licence compatible with MIT.
- Each dependency is recorded in `docs/DEPENDENCIES.md` with licence, version, purpose and review date before it is added.
- No GPL code copied into the tree. GPL tools (for example GoldenCheetah) may be used only as external comparison, not as source.
- FIT decoding uses `fitdecode` (MIT) `[D8]`. The Garmin FIT SDK (proprietary FIT SDK licence) is not a dependency in any form. Garmin's published protocol document (D01) remains the reference for field semantics.
- Risk: `fitdecode` releases are infrequent (0.10.0 in 2021, 0.11.0 in 2025). If a Fenix 8 file needs a field it cannot decode, options are a profile update contributed upstream or a project fork under MIT; either is logged before use.

## 8. API

As in the pack (`/api/imports`, `/api/activities`, `/api/activities/{id}`, `/samples`, `/metrics`, `/api/metrics/{id}`, `/api/overview`, `/api/export`) plus:

- `DELETE /api/activities/{id}` and `POST /api/data/delete-all` (confirmation token).
- `GET /api/duplicate-groups?status=proposed`; `POST /api/duplicate-groups/{id}/confirm` with a channel selection body; `POST /api/duplicate-groups/{id}/reject`; `POST /api/duplicate-groups/{id}/reopen`.
- `PUT /api/rides/{id}/channels` to change a confirmed ride's selection.
- `GET /api/export/archive` returns the full archive.

Every metric value response carries `metric_id, version, classification, units, state, coverage, parameters, input_revision, source_sha256[]`.

## 9. Security

127.0.0.1 binding; upload size cap; zip extraction with path traversal and zip bomb limits (entry count, total uncompressed size, ratio); accept only `.fit`, `.tcx`, `.zip` by content sniffing as well as extension; no shell calls on file names; no secrets exist to log.

## 10. Testing strategy

| Level | What it proves | Data |
|---|---|---|
| Oracle agreement | Production metric code equals independent arithmetic | Synthetic, hypothesis generated |
| Timeline builder | Spec 5.3 to 5.5 rules | Synthetic edge cases: jitter, duplicate timestamps, gaps, last sample, pauses |
| Importer | Field mapping, sentinels, compressed timestamps, events | Real anonymised files (local), plus synthetic FIT written in tests |
| Cross source | Same ride from Fenix 8, MyWhoosh and Hub: duration consistency, power agreement assessment (bias, limits of agreement over 5 s or longer averages, per R06), per channel selection produces the expected ride values | One real ride recorded by all three |
| Recording statistics | Interval distribution, gap counts and coverage reported for regular and irregular files | Synthetic 1 Hz and irregular interval files |
| Validity states | 0, missing, invalid and suspect zero survive import, storage, calculation, API, CSV and UI unchanged | Synthetic |
| Ownership | Round trip, deletion marker scan, offline run | Synthetic |
| UI smoke | Screens load, every metric links to its entry | Synthetic |

The cross source test reports agreement; it does not require equality and it is not an accuracy test, because no calibrated reference is involved (spec 6.3).
