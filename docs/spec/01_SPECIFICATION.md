# Open Cycling Science: Specification

| Field | Value |
|---|---|
| Document | 01 Specification (authoritative) |
| Version | 1.0 PHASE ONE FROZEN (approved by Jimmy 2026-10-17); amendment 1 (2026-10-24): duplicate rules in 5.7 from Jimmy's WP6 brief, logged as C28 to C30 |
| Date | 2026-10-17 |
| Status | Frozen for Phase One. Decisions D1 to D8 (section 10) and the conflicts register (`05`) approved by Jimmy 2026-10-17. Any change, including scope additions, needs Jimmy's approval through change control (roadmap) and a version increment. |
| Companion documents | `02_RESEARCH_REGISTER.md`, `03_TECHNICAL_ARCHITECTURE.md`, `04_DEVELOPMENT_ROADMAP.md`, `05_CONFLICTS_AND_RESOLUTIONS.md` |
| Supersedes | Starter pack `docs/01` to `docs/07`, `prompts/01_PHASE_ONE.md`, `design/08_DATA_OWNERSHIP.md`. Those files remain as history. Where they differ from this set, this set wins. |

Requirement keywords: **MUST**, **MUST NOT**, **SHOULD**, **MAY** as in RFC 2119. Items tagged `[Dn]` implement an approved decision recorded with its rationale in section 10.

## 1. Objective

An open source, local first cycling performance analysis and training platform. Every number shown is either a sensor observation, a deterministic transform with a documented equation, or a model with documented equations, assumptions, limitations and validation evidence. The rider owns all data.

The platform is independent. It does not reproduce Garmin, Strava or TrainingPeaks outputs and is not validated against them. Proprietary indices (for example Training Stress Score, Normalized Power, Body Battery, Training Readiness) are not implemented under those names. A comparable published method MAY be implemented only under its own register entry, published equation and evidence record.

## 2. Principles (non negotiable)

P1. The rider controls all original files, generated values and exports.
P2. No subscription, hosted server, account, AI service or vendor API is needed for routine operation.
P3. Every displayed value carries a class: OBSERVED, DERIVED, MODELLED or EXPERIMENTAL (definitions in section 6.1).
P4. Every metric and model has a complete register entry (section 6.2) before it can be displayed.
P5. No opaque readiness, fitness or fatigue score is presented as a fact.
P6. Missing, invalid, measured zero and measured non zero values stay distinct in storage, calculation, display and export. Missing data are never replaced by zero or interpolated, for any channel.
P11. No recording device is assumed authoritative for every measurement. Each channel of a ride can come from a different source, chosen by the rider (section 5.8).
P12. Every original recording is preserved. Duplicate handling and source selection never delete, merge or alter a recording.
P7. Source files are immutable. Every calculated value is reproducible from recorded input hashes, metric version and parameters.
P8. No physiological claim is inferred from a mathematical fit without the physiological evidence that supports it.
P9. A software test verifies implementation, not scientific validity. Both are recorded separately.
P10. No compatibility claim for a device or platform before an integration test with a real file or device.

## 3. Scope

### 3.1 Supported data sources

"Supported" means: the import path is implemented, it has passed tests against at least one real anonymised file from that source, and the field mapping is documented. Until then the source is "targeted". Current status of all three: **targeted, unverified** (no real file has been tested).

| Source | Import path | Format | Channels expected | Known constraints |
|---|---|---|---|---|
| Garmin Fenix 8 | Original FIT from the watch (USB) or Garmin Connect original export, single file or account export archive (D02) | FIT | timestamp, HR, cadence, power (only if a power meter or trainer is paired), speed, distance, temperature, position, timer events, laps, session summary, device info | Every Second recording is the recommended setting, not a precondition. Smart Recording files (D07) are imported and assessed on their measured recording statistics (section 5.3, item 7); they are not assumed inadequate. Whether a paired power meter forces 1 s recording is unverified (U1). |
| Wattbike Atom | Wattbike Hub per session TCX download (D03); Atom power also arrives inside Fenix 8 or MyWhoosh FIT files when paired | TCX (Hub); FIT (via other recorders) | timestamp, power (TCX extension), cadence, HR if paired | No documented bulk export (D03). TCX has no pause events. |
| MyWhoosh | FIT download from the MyWhoosh web profile, Activities page (reported by users, not yet verified by the project, D08) | FIT | timestamp, power, cadence, HR if paired, virtual speed and distance | Speed and distance are simulated, not observed road values. Device identity in the file may name the app rather than the trainer. |

Out of scope for import: scraping vendor accounts, unofficial APIs, credential storage, automatic cloud sync. Other FIT and TCX files MAY import through the same adapters but are not claimed as supported.

### 3.2 Phase One functional scope

1. Import FIT and TCX files and zip archives of them, preserving original bytes.
2. Normalise to the canonical time model (section 5).
3. Compute M001 to M004 (section 7).
4. Detect byte duplicates; flag possible cross source duplicates and let the rider confirm them and choose a source per channel (sections 5.7, 5.8).
5. Screens: Library (import, status, errors, duplicates), Overview (weekly duration and work with coverage, recent activities, best MMP), Activity detail (time series with pauses, gaps and validity, provenance, metric values), Science catalogue (every register entry), Settings and export.
6. Export (section 8.3) and deletion (section 8.4).
7. Runs offline on macOS, bound to 127.0.0.1.

### 3.3 Explicitly out of scope until a later phase approves them

Readiness, fatigue, form, CTL/ATL style scores; VO2max estimates; FTP; automatic threshold or zone inference; single value HRV interpretation; workout recommendations; live trainer control; cloud sync; AI assistant dependency. Each enters only through the roadmap gate for its phase.

## 4. Users and environment

Single rider, single Mac, multi year 1 Hz history (design load: 5,000 activities, about 20 million samples; to be benchmarked, not assumed). iPad viewing over the home network is Phase Two or later and requires authentication first. Code MUST remain cross platform Python and TypeScript so other contributors can run it on Linux; macOS is the acceptance platform.

## 5. Data semantics (normative)

### 5.1 Time

- All stored timestamps are UTC, as float seconds since the Unix epoch, plus the source UTC offset where the file provides it. FIT timestamps (seconds since 1989-12-31 00:00:00 UTC) are converted exactly.
- Elapsed seconds are computed from UTC only. Display time zone never changes any computed value.
- Intervals are half open, `[start, end)`.

### 5.2 Channel validity

Every channel value in every sample has one of these states, stored explicitly:

| State | Meaning | Example |
|---|---|---|
| `observed` | Sensor reported a value. Zero is an observed value | Power field = 0 W while coasting |
| `missing` | Field absent from the record, or no record covers this time | Record with no power field |
| `invalid` | Field present but invalid: FIT invalid sentinel, out of physical range, duplicate timestamp | FIT uint16 power 0xFFFF |
| `inferred` | Value produced by the application | Not permitted for any channel in Phase One |

Physical range rules (engineering limits for rejecting corrupt values, not physiological claims): power 0 to 3,000 W; HR 20 to 250 bpm; cadence 0 to 250 rpm. Values outside are `invalid` and reported. Consequence: HR 0 is `invalid` (not physically possible during a ride); power 0 and cadence 0 are `observed`.

Rules that keep the three cases apart:

- Storage: value column NULL plus a state column; NULL never means zero and zero never means absent.
- Calculation: only `observed` values enter sums; coverage counts only `observed` seconds.
- Display and export: missing and invalid are shown as gaps or empty cells with their state, never as 0.
- Suspect zeros: some recorders may write 0 W during a sensor dropout (unverified, U7). A run of 0 W lasting at least 3 s while the same file shows cadence above 0 is flagged `suspect_zero`. The flag is shown and counted; the value stays `observed` and is not altered or excluded.

### 5.3 Sample duration rule `[D2]`

Each sample is a step function value held over a defined interval.

1. Within one timer running segment, sort samples by timestamp. Equal timestamps: keep the first, mark the rest `invalid` and report.
2. Nominal interval `Δnom` = median of positive successive timestamp differences within the activity.
3. Gap tolerance `g = 1.5 × Δnom` (1.5 s for 1 Hz data). No value is ever held across a gap longer than `g`.
4. For sample `i` with successor at `t(i+1)`: if `t(i+1) − t(i) ≤ g`, the sample covers `[t(i), t(i+1))`. Otherwise it covers `[t(i), t(i) + Δnom)` and `[t(i) + Δnom, t(i+1))` is a gap where every channel is `missing`.
5. The last sample in a segment covers `[t(i), min(t(i) + Δnom, segment_end))`.
6. Assumption A1: a record's value applies forward from its timestamp. Whether a given device's power value represents the preceding or following second is unverified; this can shift a window position by up to `Δnom` but cannot change mean power or work on regular data.
7. Recording coverage is assessed from evidence in each file, not assumed from the recording mode. For every activity the app reports: `Δnom`, the distribution of successive intervals (count per interval bin and maximum), seconds covered and seconds in gaps under rule 4, per channel `observed` coverage, and the number and length of gaps. Activities where more than 10% of successive differences differ from `Δnom` by more than 0.1 s carry the descriptive flag `irregular_recording`. The flag is information, not a quality verdict: whether a file is adequate for a metric is decided only by that metric's own data quality rules applied to the measured coverage. Whether Smart Recording gaps mean "value unchanged" (which could justify a different rule) is evidence question U9; until answered, rule 4 applies to all files alike (D2).

### 5.4 Timer `[D3]`

Timer running segments are determined in this order:

1. FIT `event` messages with `event = timer` (start, stop, stop_all). Source recorded as `timer_source = device_events`.
2. If the file has no timer events (always the case for TCX), the timer is assumed to run from the first sample to the end of the last sample. Source recorded as `timer_source = assumed_continuous` and shown in the UI.
3. Independently, the device reported total timer time (FIT `session.total_timer_time`, TCX `Lap/TotalTimeSeconds` summed) is stored as an OBSERVED value `device_timer_s`. A difference from M001 greater than max(2 s, 1%) is flagged, never silently reconciled.

Pauses MUST NOT be inferred from low power, zero speed or gaps.

### 5.5 Eligibility and coverage

- Eligible time = timer running time (M001).
- Power coverage = observed power seconds within eligible time ÷ eligible time.
- Coverage threshold for mean power: 0.95 (engineering threshold, not a physiological one; stored in each run's parameters).

### 5.6 Multiple sources and sensors

- One activity = one source file. Each channel series always comes whole from one file; samples from different files are never spliced, averaged or merged within a channel.
- For each activity and channel the app records which sensor produced it where the file identifies it (FIT `device_info`, for example an ANT+ HR strap versus wrist optical HR), otherwise `unknown`.
- Commanded trainer power (ERG target) is never stored as measured power.
- Channels a source simulates rather than measures (MyWhoosh speed and distance) carry `origin = simulated` and are excluded from any metric that needs real world speed or distance.

### 5.7 Duplicates `[D7]`

- Byte duplicate: identical SHA256. The second import creates no new activity and reports the existing one. The bytes are already preserved, so nothing is lost.
- Possible duplicate: different bytes, timer running spans overlapping by at least 80% of the shorter activity (engineering parameter, stored). The app groups them as a *proposed* duplicate group automatically.
- Also a possible duplicate (amendment 1, 2026-10-24): different bytes with the same recording identity (FIT `file_id` manufacturer, product, serial number and creation time; TCX creator and activity `Id`), which a re-export keeps even when the bytes change. The evidence for each pair (overlap, start offset, timer durations, recording identity, device identity) is stored with the group. Rule version 1.1.
- A recording that matches a member of an already confirmed group joins it as *pending* (amendment 1). It counts as its own ride, and in the shown overcount, until the rider accepts it (with a new channel selection) or excludes it. At confirmation the rider may also exclude members; excluded members stay separate rides.
- A proposed group changes nothing until the rider acts. The rider can **confirm** it (the members become one ride, section 5.8) or **reject** it (the members stay separate rides and are not proposed again as that group).
- Once confirmed, the group counts as one ride in aggregates. The rider overrides this by reopening the group (it returns to proposed) and, if wanted, rejecting it (amendment 1).
- Until confirmed, every member counts in aggregates as its own ride. The Overview shows the number of unconfirmed groups and the duration and work that would be excluded if they were confirmed, so the possible overcount is visible.
- Confirming, rejecting or changing a group never deletes or alters a recording, is reversible, and marks dependent aggregates stale for recomputation.
- Activity level values are always computed for every member.

### 5.8 Rides and per channel source selection `[D7]`

- A **ride** is either a single activity, or a confirmed duplicate group.
- Selectable fields per ride: `timer` (duration source), `power`, `heart_rate`, `cadence`, `speed`, `distance`, `temperature`. Each is chosen independently from the members that recorded it. Example: power from the Wattbike Hub file, heart rate from the Fenix 8 file, cadence from MyWhoosh.
- Selection happens in the confirmation step. The rider MAY save per channel preferences (for example "heart rate: Fenix 8 strap first"); saved preferences only prefill the confirmation form and are applied when the rider confirms, never silently.
- A field no member recorded is `missing` for the ride, not zero.
- Ride level metrics use the selected source for each input channel. A metric whose inputs all come from one file is computed on that file alone with that file's own timer segments: M002 to M004 at ride level use the selected power file and its own timer and coverage. The selected `timer` source sets the ride's reported duration (M001) and weekly duration totals.
- Metrics that combine two channels from different files (for example HR at a given power, Phase Two) require a documented clock alignment method first (U8) and are not available in Phase One.
- The selection, who made it and when are stored; changing a selection creates a new input revision and marks dependent values stale.

## 6. Scientific governance

### 6.1 Classes

| Class | Definition | Display rule |
|---|---|---|
| OBSERVED | Directly reported by a device | Show device identity; note device measurement error from register |
| DERIVED | Deterministic transform of observations by an equation that is a mathematical identity given its input definitions | Show equation and coverage |
| MODELLED | Parameters estimated under assumptions that may not hold | Show fit quality, protocol status and validation status; never call it "measured" |
| EXPERIMENTAL | Hypothesis not approved for decision support | Hidden by default; labelled where shown |

Evidence labels (project labels, not GRADE): `Established mathematical identity`, `Model supported in controlled settings`, `Predictive evidence limited`, `Unverified`.

### 6.2 Register entry contract

Every metric has these machine readable fields, held in `02_RESEARCH_REGISTER.md` and the in app registry, with tests asserting completeness: `metric_id, version, display_name, classification, units, equation, variable_definitions, source_refs, population_scope, input_requirements, data_quality_rules, algorithm, parameter_set, assumptions, known_limitations, validation_protocol, software_test_status, scientific_validation_status, uncertainty_statement, last_reviewed`.

A metric MAY be displayed only if its entry is complete and its data quality rules pass for that input. Otherwise the UI shows a named unavailable state, never 0 or blank.

### 6.3 Agreement versus accuracy

- **Accuracy** is closeness to a true value. It can be claimed only from comparison with a calibrated reference of stated, traceable uncertainty (for example a motorised calibration rig or a calibrated laboratory ergometer).
- **Agreement** is how closely two instruments read relative to each other: bias, limits of agreement (Bland Altman) and dependence on power, cadence and conditions, following the recommendations in R06. A comparison between two power meters, trainers or recordings is an agreement assessment. It says nothing about which instrument is right unless one is a calibrated reference.
- All project documents, UI text and reports use these terms accordingly.

### 6.4 Validation gate (all metrics)

1. Source review: the cited passage supports the equation and use.
2. Implementation check: independent synthetic oracle (`reference/metric_oracle.py` or successor) agrees with production code.
3. Real file check: at least one real file per supported source.
4. Model predictions only: time ordered train and test split, comparison against a naive baseline, published error.
5. Uncertainty is stated only when produced by a stated statistical method; otherwise "not quantified".

## 7. Metrics

Phase One approves M001 to M004. M005 is approved for Phase Two only, subject to the protocol rules below. M006 to M011 are not approved. Evidence records are in `02_RESEARCH_REGISTER.md`.

### M001 Timer duration, elapsed duration and sample coverage (DERIVED, v1.0)

- `elapsed_s = t_end − t_start` where `t_start` is the first sample timestamp and `t_end` the end of the last sample interval (section 5.3).
- `timer_s = Σ length(timer running segments)` (section 5.4). At ride level, taken from the ride's selected `timer` source.
- `observed_s = Σ length(sample intervals within timer running segments)` (any channel).
- Outputs: `elapsed_s`, `timer_s`, `observed_s`, `timer_source`, `device_timer_s` (OBSERVED, separate).
- Tests: 10 × 1 s samples give `timer_s = 10`; a 5 s timer stop gives `timer_s` 5 s lower and `elapsed_s` unchanged; changing display time zone changes nothing; TCX with no events reports `assumed_continuous`.

### M002 Recorded mean power (DERIVED, v1.0)

- `P_mean = Σ(P_i × Δt_i) / Σ(Δt_i)` over intervals with `observed` power inside timer running segments.
- Unavailable (state `insufficient_coverage`) when power coverage < 0.95.
- Outputs: value (W), coverage, observed power seconds, eligible seconds.
- Tests: 200 W × 10 s gives 200 W; 100 W × 5 s then 300 W × 5 s gives 200 W; a 2 s missing gap is excluded, not counted as 0 W; explicit 0 W samples are included.

### M003 Recorded mechanical work (DERIVED, v1.0) `[D1]`

- `W_kJ = Σ(P_i × Δt_i) / 1000` over the same intervals as M002.
- Reported at any coverage above 0 with coverage alongside. Because mechanical power is non negative, recorded work is a strict lower bound on work done during eligible time; below 0.95 coverage it is labelled `lower_bound`.
- Mechanical kJ are not dietary kcal or metabolic energy. Phase One MUST NOT convert them; a conversion needs gross efficiency and is a separate MODELLED candidate (register M014).
- Tests: 200 W × 10 s gives 2 kJ; 250 W × 3600 s gives 900 kJ; 50% coverage reports the observed half and the `lower_bound` label.

### M004 Maximal mean power over duration T (DERIVED, v1.0)

- `MMP(T) = max over a of (1/T) ∫[a, a+T) P(t) dt`, over windows lying entirely inside one contiguous run of `observed` power within one timer running segment.
- Windows MUST NOT cross a gap, an invalid or missing sample, or a timer stop.
- Default durations: 5, 60, 300, 1200, 3600 s; user durations allowed from `Δnom` up to the longest contiguous valid run.
- Outputs per T: value (W), source activity, window start, recording interval, device. All history MMP takes the maximum over rides, using each ride's selected power source, and links the source file.
- Label: "highest observed", not "maximal capability".
- Tests: 200 W × 10 s gives MMP(5) = 200 W; 100 W × 5 s then 300 W × 5 s gives MMP(5) = 300 W; a 3 s gap in 10 s makes every window crossing it invalid; MMP(10) is unavailable with fewer than 10 contiguous valid seconds.

### M005 Critical Power and W′, two parameter model (MODELLED, Phase Two only)

- `P(t) = CP + W′/t`; work form `W(t) = CP·t + W′`. CP in W, W′ in J, t in s.
- Inputs: at least 3 rider marked exhaustive efforts from separate sessions, durations spanning approximately 2 to 15 minutes, protocol recorded per effort.
- Efforts not marked as protocol tests produce a fit labelled `protocol_unverified`, never "your CP".
- Fitting method, transform comparison (P vs 1/t, W vs t, P vs t hyperbolic), residuals, parameter standard errors and a leave one out sensitivity check are reported. Physically invalid fits (CP ≤ 0, W′ ≤ 0) are rejected.
- Test: (180 s, 350 W), (360 s, 300 W), (720 s, 275 W) recover CP = 250 W and W′ = 18,000 J within 1e-6 relative.

### M006 to M011 (not approved)

Heart rate at controlled workload, impulse response training load model, HRV, VO2max, intensity distribution and workout planning. Each needs a complete register entry and a roadmap gate. See register for current evidence status and the conditions for promotion.

## 8. Data ownership

### 8.1 Storage

- One data root, default `~/Library/Application Support/OpenCyclingScience/`, configurable. It MUST NOT default inside the source tree. `[D4]`
- Layout: `vault/sha256/ab/cd/<sha256>`, `db/cycling.db`, `exports/`, `backups/`, `logs/`.
- Vault files are written once, set read only, verified by rehash on import and before export.
- Logs contain no telemetry values, file contents or locations.
- Encryption at rest relies on macOS FileVault, stated in the README.

### 8.2 Location data `[D5]`

- Phase One does not normalise GPS position. Derived exports contain no location.
- Original files in the vault and in original exports keep their GPS bytes unchanged (provenance requires byte identity). The export UI warns that originals may reveal home location.
- A GPS stripped copy for sharing is a Phase Two candidate, produced as a new file with its own hash, never replacing the original.

### 8.3 Export `[D6]`

Phase One delivers all three types:

| Export | Contents | Format |
|---|---|---|
| Original files | Vault objects with original filenames | Byte identical FIT/TCX |
| Derived data | Activities, samples, timer events, duplicate groups and their decisions, ride channel selections, metric definitions, runs, values | One CSV per table (UTF-8, RFC 4180, units in column names, empty = missing, validity columns included, no rounding) plus JSON |
| Full archive | Both plus `manifest.json` (app version, schema version, timestamp, row counts, SHA256 of every file, metric versions) | ZIP |

Importing a full archive into an empty install MUST reproduce identical vault hashes, row counts and metric values.

### 8.4 Deletion

- Deleting an activity removes its samples, events, runs and values; aggregates that used it are recomputed or marked stale.
- Its vault object is removed when no other activity references it.
- If the activity belongs to a duplicate group it is removed from the group. Any ride channel selection that pointed to it becomes unselected and the ride is flagged for the rider to review; a group left with one member dissolves into a single activity ride. No other member is altered.
- SQLite residue is removed (`secure_delete`, WAL checkpoint truncate, `VACUUM` on full deletion).
- "Delete everything" removes the data root including internal backups and exports, after one confirmation listing what will go.
- No tombstone keeps hashes, filenames or timestamps of deleted content.
- The app documents what it cannot delete: external copies, Time Machine and APFS snapshots, SSD physical blocks, vendor accounts.

### 8.5 Network

- Bound to 127.0.0.1 by default. No outbound connections in any workflow. Fonts and assets bundled.
- LAN mode (Phase Two or later) requires authentication and TLS or an explicit unencrypted warning; holds nothing beyond the Mac's data.
- Project infrastructure (repository, releases) never receives rider data, crash reports or usage metrics.

## 9. Phase One acceptance criteria

All MUST pass, executed offline, with results recorded.

1. Launches on macOS with documented commands; binds to 127.0.0.1.
2. Imports real FIT from Fenix 8, real TCX from Wattbike Hub and real FIT from MyWhoosh (anonymised files supplied by the rider, kept local, never committed).
3. Re-importing identical bytes creates no activity.
4. Two files of the same ride from different sources are proposed as a duplicate group, not merged. Before confirmation both count in aggregates and the possible overcount is shown; after confirmation the ride counts once; rejecting or undoing restores the previous totals; no original file changes in any step.
4a. In a confirmed group, power, heart rate and cadence can each be selected from a different member, and ride level values use the selected sources.
5. Vault object SHA256 equals the original file's.
6. 0 W and 0 rpm are `observed`; HR 0 is `invalid`; absent fields are `missing`; FIT invalid sentinels are `invalid`; none of them is ever exported or displayed as 0 except an observed 0; `suspect_zero` flags appear without changing values.
7. Synthetic results: 200 W × 10 s gives mean 200 W, work 2 kJ, MMP(5) 200 W; 100/300 W split gives mean 200 W, work 2 kJ, MMP(5) 300 W.
8. A 3 s gap invalidates any MMP window crossing it.
9. A timer stop changes `timer_s` and not `elapsed_s`.
10. Display time zone change alters no computed value.
11. Coverage below 0.95 makes M002 unavailable with a named state; M003 shows `lower_bound`.
12. Every displayed metric opens its full register entry.
13. Production metric code agrees with the oracle on all fixtures and on randomised property tests.
14. Full archive round trip reproduces hashes, counts and values.
15. Deletion marker scan of the data root (including WAL and SHM) finds neither the marker nor the hash.
16. Import, calculation and export pass with outbound networking blocked.
17. Data root is outside the source tree; vault and database paths are gitignored.
17a. Each activity's recording statistics (section 5.3, item 7) are reported, including for irregular interval files, and no file is rejected or labelled inadequate on recording mode alone.
18. Import of a large synthetic history completes without loading all telemetry into the browser; measured time and memory are reported, no target invented.
19. Backend and frontend test suites run offline; any exception listed.

## 10. Decision record

Decisions approved by Jimmy on 2026-10-17 in the project thread. Each is binding until changed through change control (roadmap).

| ID | Decision | Rationale | Spec |
|---|---|---|---|
| D1 | **Report** recorded work at any coverage, labelled `lower_bound` below 0.95 | Mechanical power cannot be negative, so recorded work is a provable lower bound, not an estimate. Mean power stays withheld below 0.95 because missing data may be non random and bias it | M003 |
| D2 | **Strict** gap tolerance, 1.5 × nominal interval, no bridging | Holding a value across a gap is interpolation, which P6 forbids. Known cost: one dropped sample breaks long MMP windows; Phase One measures how often on real files | 5.3 |
| D3 | **Continuous** timer fallback when a file has no timer events, labelled `assumed_continuous`, device reported timer shown alongside | Withholding would blank duration for every Wattbike Hub TCX. The label and the device timer comparison keep the assumption visible | 5.4 |
| D4 | **AppSupport**: data root `~/Library/Application Support/OpenCyclingScience/`, configurable, never in the source tree | A repo relative data folder makes publishing personal rides one `git add` away | 8.1 |
| D5 | **Keep** GPS in original file exports, byte identical, with a warning | Byte identity is the provenance chain; stripping needs a FIT writer. Derived exports carry no location | 8.2 |
| D6 | **Full** export in Phase One: originals, derived data, archive with manifest | Backup, deletion and round trip reproducibility cannot be tested without it | 8.3 |
| D7 | **Manual** duplicate exclusion. The app proposes matches automatically; only the rider's confirmation excludes an activity from aggregates. Every original is preserved. Each channel (timer, power, HR, cadence, speed, distance, temperature) can be taken from a different recording | No device is authoritative for every measurement (P11). Automatic exclusion would make a silent choice about which recording counts. Cost: totals overcount until the rider confirms; the overcount is shown | 5.7, 5.8 |
| D8 | **MIT `fitdecode`** as the FIT decoder | Keeps every runtime dependency under an OSI open source licence. `fitdecode` 0.11.0 is MIT, has no runtime dependencies, and embeds the FIT profile from Garmin SDK 21.171 (Aug 2025). Cost: newer messages decode as unknown raw fields; core record, event and session fields are long established. The Garmin SDK is not a dependency | Arch 2, 7 |

