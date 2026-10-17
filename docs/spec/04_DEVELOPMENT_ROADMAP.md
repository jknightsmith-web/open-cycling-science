# Open Cycling Science: Development Roadmap

| Field | Value |
|---|---|
| Document | 04 Development roadmap (authoritative) |
| Version | 1.0 PHASE ONE FROZEN (approved by Jimmy 2026-10-17) |
| Date | 2026-10-17 |

No durations are given: none can be estimated honestly before WP1 benchmarks and real files exist. Phases are ordered by dependency and each ends at a gate.

## Gate 0. Specification approval (current)

- Decisions D1 to D8 answered (done 2026-10-17, spec section 10).
- Jimmy gives final approval of the revised set (done 2026-10-17, v1.0 frozen).
- A code repository exists and is attached to the project; the spec set is copied into its `docs/` as the first commit. Status 2026-10-17: no GitHub repository is attached yet. Work proceeds in a local Git repository in the project files (`/mnt/project-files/code/open-cycling-science`) and is pushed unchanged, with history, once a repository is attached.

Not a Gate 0 condition: real files. WP1, 2, 4, 5 and most of 3 run on synthetic data. Real anonymised files (one Fenix 8 FIT with power, one Wattbike Hub TCX, one MyWhoosh FIT, ideally one ride recorded by all three) are needed for the WP3 verification step and Gate 1, kept local and out of Git.

**Exit:** written approval in the project thread. Coding starts only after this.

## Phase One. Own the data and trust the arithmetic

| WP | Content | Depends on | Done when |
|---|---|---|---|
| 1 | Repo, MIT LICENSE, dependency register (fitdecode MIT recorded), offline run script, CI on Linux | Gate 0 | `make test` runs offline |
| 2 | Data root, vault, migrations, storage benchmark on synthetic 20M samples | 1 | Vault hash test passes; size and time measured |
| 3 | FIT (fitdecode) and TCX importers, synthetic FIT encoder for tests, sensor identity per channel; field mapping verified on real files | 1; real files for the verification part only | Mapping table in architecture confirmed or corrected |
| 4 | Timeline builder (spec 5.3 to 5.5), validity states, suspect zero flag, per activity recording statistics | 3 | Edge case and validity state tests pass; item 17a |
| 5 | M001 to M004 production code, oracle agreement, property tests | 4 | Acceptance items 7 to 11, 13 |
| 6 | Idempotent import, duplicate proposals, confirm/reject/reopen, rides, per channel source selection, overcount display | 3, 5 | Items 3, 4, 4a |
| 7 | Registry YAML for M001 to M004, completeness validator, Science catalogue | 5 | Item 12 |
| 8 | Library, Overview, Activity detail screens | 5, 6 | UI smoke tests |
| 9 | Exports, archive round trip, deletion, offline network test | 2, 5 | Items 14 to 17 |
| 10 | Large history benchmark, Phase One report | all | Item 18; full acceptance run recorded |

**Gate 1:** every acceptance criterion in spec section 9 passes on macOS; real file results reported per source; unverified areas listed.

## Phase Two. Measured performance and CP

- Equipment and sensor metadata (`devices` table), cross source power agreement assessment for the rider's own rides (accuracy only if a calibrated reference becomes available).
- Clock alignment method between files of one ride (U8), required before any metric combines channels from different recordings.
- Data quality report per activity and over history.
- Power duration curve over date ranges with source links.
- Test effort marking with protocol fields; M005 with transform comparison, residuals, standard errors, sensitivity.
- Register review for M006 (HR at controlled workload) as a candidate.
- LAN viewing on iPad with authentication; transport choice tested on the actual iPad.
- GPS stripped original copy for sharing (if D5 confirms).

**Gate 2:** synthetic CP test passes; unverified efforts never produce an unlabelled CP; real rider CP results show protocol status.

## Phase Three. Training response research

- Define load input `u` and separately observed performance outcomes (for example repeated test efforts).
- Fit candidate models (M007 impulse response and others in the register) on time ordered training data; evaluate on held out later data against naive baselines (last observed value, moving average).
- Publish out of sample errors and parameter stability in the register.

**Gate 3:** a model is shown only if it beats the naive baselines out of sample, and then only as MODELLED with its error. Failure is an acceptable, documented outcome.

## Phase Four. Workouts and equipment

- Open JSON workout schema, import and export; compliance recording (commanded vs measured power stored separately).
- Wattbike Atom control prototype via a Mac Bluetooth bridge using FTMS (preferred) or a native iPad app; choice after tests on the rider's Atom.
- Safety tests: single controller, stop, manual override, disconnect behaviour, ERG step changes, sleep and reconnect.

**Gate 4:** prescribed sequence executes on the real Atom with correct targets and reliable disconnect recovery.

## Change control

- Any change to a metric definition increments its version and keeps prior runs.
- Any change to these documents increments the document version and adds a line to the conflicts log or a change log.
- A new metric enters only through a complete register entry and the phase gate that approves it.
