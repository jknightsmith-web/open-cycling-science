# Open Cycling Science: Conflicts and Resolutions Log

| Field | Value |
|---|---|
| Document | 05 Conflicts and resolutions |
| Version | 1.0 (approved for Phase One by Jimmy 2026-10-17) |
| Date | 2026-10-17 |
| Inputs compared | Starter pack (`README`, `CLAUDE.md`, `docs/01` to `07`, `prompts/01`, `reference/metric_oracle.py`); thread "Map the existing platform files" (`inventory/PLATFORM_INVENTORY.md`); thread "Draft a data ownership design" (`design/08_DATA_OWNERSHIP.md`); thread "Build a cited formula register" (`formula-register/FORMULA_REGISTER.md`) |

## 1. Decisions (approved 2026-10-17)

Jimmy approved D1 to D8 on 2026-10-17. The decisions and their rationale are recorded in `01_SPECIFICATION.md` section 10, which is the authoritative record. Summary:

| ID | Question | Approved | Recommended in v0.1 |
|---|---|---|---|
| D1 | Work below 95% power coverage | Report, labelled `lower_bound` | Same |
| D2 | Gap tolerance | Strict, 1.5 × nominal interval | Same |
| D3 | Timer without pause events | Continuous, labelled | Same |
| D4 | Data location | Application Support | Same |
| D5 | GPS in exported originals | Keep, with warning | Same |
| D6 | Phase One export | Full | Same |
| D7 | Duplicate rides in aggregates | Manual: auto proposal, rider confirmation before exclusion, per channel source selection | Auto (changed) |
| D8 | FIT decoder | MIT `fitdecode` | Garmin SDK (changed) |

Additional requirements from the same approval, written into the spec: no device is authoritative for all measurements (P11, 5.8); every original recording preserved (P12); missing, zero and measured values kept distinct end to end (P6, 5.2).

## 2. Conflicts resolved in the specification

| ID | Sources in conflict | Resolution | Where |
|---|---|---|---|
| C01 | Pack is Mac only; project is open source for others | macOS is the acceptance platform; code stays cross platform, CI on Linux | Spec 4 |
| C02 | Oracle MMP is O(n²) (inventory) vs multi year history | Production uses O(n) prefix sum; oracle kept as reference; property tests require agreement | Arch 6 |
| C03 | Pack M001 "elapsed intervals flagged timer running" has no rule for sample length, last sample, jitter or duplicate timestamps | Sample duration rule written | Spec 5.3 |
| C04 | Jimmy's brief says "must support" MyWhoosh and Wattbike; pack says "deferred" and "do not promise" | "Supported" defined as passing tests on a real file; all three sources are "targeted" until then; Phase One gate requires one real file from each | Spec 3.1, 9 |
| C05 | Pack duplicate rule is qualitative | 80% timer overlap of the shorter activity (engineering parameter) | Spec 5.7 |
| C06 | Fenix 8 Smart Recording gives irregular intervals; v0.2 assumed they would fail the coverage gate | Corrected 2026-10-17: recording coverage is assessed from each file's measured interval and gap statistics, not assumed from the recording mode. Every Second is recommended, not required. `irregular_recording` is a descriptive flag; adequacy is decided only by each metric's data quality rules. Meaning of Smart Recording gaps is evidence question U9 | Spec 3.1, 5.3 item 7, 9 item 17a |
| C07 | MyWhoosh speed and distance are simulated, pack treats speed as a sensor channel | `origin = simulated`, excluded from real world speed metrics | Spec 5.6 |
| C08 | Wattbike claims ±1 to 2% citing Hopker 2010 (older models, agreement with an SRM); the only located calibrated reference study, on the AtomX (R10), found −6.4% in one unit; no Atom accuracy study found | Corrected 2026-10-17: power from different sources is not pooled without an agreement assessment on the rider's own rides. Comparisons between power meters are reported as agreement (bias, limits of agreement), never as absolute accuracy, unless a calibrated reference is used | Spec 6.3, Register 6 |
| C09 | Data ownership: backups inside data root vs recovery | "Delete everything" includes them, stated in the confirmation (accepted from draft) | Spec 8.4 |
| C10 | M005: oracle fits form 3 (P on 1/t); formula register says fix one primary form | Primary form chosen at Phase Two start by test type, others as sensitivity. All forms agree on the noise free acceptance data, so the oracle test stands | Register 2, 4 |
| C11 | Pack excludes FTP; formula register allows a user entered threshold | FTP never computed; a dated user entry with method may exist from Phase Two | Register 3 |
| C12 | NP, IF, TSS are registered TrainingPeaks marks (formula register) | No trademarked names; neutral names only, Phase Three research | Spec 1, Register 3 |
| C13 | ACWR appears in the literature set | Rejected: mathematical coupling (Lolli 2019) | Register 3 |
| C14 | Pack forbids kJ to kcal equivalence; formula register proposes a labelled estimate | None in Phase One; MODELLED candidate M014 with explicit gross efficiency | Spec M003, Register 3 |
| C15 | Formula register suggests power to mass in Phase 1 | Phase Two, because no mass history exists in Phase One | Register 4 |
| C16 | Pack R06, R07, R08 incomplete | Authors and DOIs found and recorded | Register 5 |
| C17 | Pack acceptance used generic "valid FIT and TCX examples" | Stricter: real anonymised files from all three sources plus a three source same ride agreement assessment | Spec 9 |
| C18 | Delete granularity and LAN transport open in draft | Per activity and everything in Phase One; LAN transport decided by a test on the iPad in Phase Two | Spec 8.4, Roadmap |
| C19 | Pack docs, prompt and 08 draft all claim authority | This five document set supersedes them; originals kept as history | Spec header |
| C20 | v0.1 said "telemetry from different files is never mixed"; D7 requires channels from different files in one ride | Each channel comes whole from one file; no splicing within a channel. Cross file channel combinations wait for U8 | Spec 5.6, 5.8 |
| C21 | v0.1 auto primary vs D7 manual confirmation | Proposals change nothing; unconfirmed members all count and the overcount is shown | Spec 5.7 |
| C22 | Physical range rule made HR 0 invalid while principle P6 says zero is a measurement | Zero stays a measurement where it is physically possible (power, cadence). HR 0 cannot occur on a living rider, so it is a sensor artefact and `invalid`. Documented in 5.2 | Spec 5.2 |
| C23 | D8 removes the Garmin SDK, but tests need synthetic FIT files | Small FIT encoder in `tests/` | Arch 2 |
| C24 | Oracle withholds work below 0.95, contradicting D1 | Oracle updated to D1 in WP5 before agreement tests | Register M003 |
| C25 | Per channel selection could let ride power metrics mix one file's timer with another file's power, which needs clock alignment (U8) | Power metrics at ride level use the selected power file with its own timer; the selected timer source sets only reported duration | Spec 5.8 |
| C26 | Deleting an activity that sits in a confirmed group would leave dangling channel selections | Member removed from group, its selections become unselected, ride flagged for review, other members untouched | Spec 8.4 |
| C27 | Gate 0 required real files, yet most Phase One work needs only synthetic data | Real files moved to the WP3 verification step and Gate 1 | Roadmap |

## 3. Evidence questions

These remain open as evidence questions. They do not block development unless a specific implementation depends on one; the dependency column says where that is the case.

| ID | Question | How it gets resolved | Blocks |
|---|---|---|---|
| U1 | Does a Fenix 8 force 1 s recording when a power meter is paired? | Inspect a real file | Nothing (statistics reported either way) |
| U2 | Does MyWhoosh alter trainer power before writing FIT? | Three source agreement assessment ride | Nothing in Phase One |
| U3 | Atom power accuracy | No accuracy study against a calibrated reference found. A rider side comparison against another meter is an agreement assessment only (bias, limits of agreement); accuracy needs a calibrated reference | Nothing in Phase One; pooling across sources in later phases |
| U4 | FIT record power timing (assumption A1) | Garmin documentation or a controlled test | Nothing (cannot change mean or work on regular data) |
| U5 | 24 Annex A DOIs unconfirmed | Confirm before each dependent metric is approved | Phase Two and Three metrics only |
| U6 | ~~Garmin FIT SDK licence~~ | Closed by D8: Garmin SDK not used | Closed |
| U7 | Do recorders write 0 W during dropouts? | `suspect_zero` flag now; real file inspection in WP3 | Nothing (flag only) |
| U8 | Clock offset between devices on one ride | Phase Two method before any cross file channel combination | Cross file channel metrics (not in Phase One) |
| U9 | Do Smart Recording gaps mean the value did not change? | Garmin documentation or a controlled recording in both modes | Nothing (uniform rule D2 applies meanwhile) |
