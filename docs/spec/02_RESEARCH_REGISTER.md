# Open Cycling Science: Scientific Research Register

| Field | Value |
|---|---|
| Document | 02 Scientific research register (authoritative) |
| Version | 1.0 PHASE ONE FROZEN (approved by Jimmy 2026-10-17) |
| Date | 2026-10-17 |
| Annex A | `/mnt/project-files/formula-register/FORMULA_REGISTER.md` (F01 to F32), adopted as the detailed formula and disagreement record. Where Annex A and this document differ, this document wins; differences are listed in section 4. |

## 1. Conventions

**Evidence labels** (project labels, not GRADE): `IDENTITY` (established mathematical identity), `CONTROLLED` (model supported in controlled settings), `LIMITED` (predictive evidence limited), `UNVERIFIED`.

**Source verification status:**

| Code | Meaning |
|---|---|
| V | Title, journal and DOI confirmed against a publisher, repository or index record |
| P | From the starter pack bibliography, not rechecked |
| M | Cited from reviewer knowledge; DOI not confirmed. Must reach V before any metric depending on it is approved |

**Rule:** a metric's `scientific_validation_status` cannot be `approved` while any of its `source_refs` is M.

## 2. Phase One evidence records

All five records below are the machine readable contract from spec 6.2. The normative definition (equation, rules, tests) is in `01_SPECIFICATION.md` section 7 and is not repeated.

### M001 Timer duration, elapsed duration and sample coverage

| Field | Value |
|---|---|
| metric_id, version | M001, 1.0 |
| classification | DERIVED |
| units | s |
| equation | Spec 7, M001 |
| variable_definitions | `t_start`, `t_end`, timer running segments (spec 5.4), sample intervals (spec 5.3) |
| source_refs | D01 (FIT timer event semantics), D07 (recording modes). No exercise science source needed |
| population_scope | Any activity file |
| input_requirements | Timestamped records; timer events if present |
| data_quality_rules | Strictly increasing timestamps after deduplication; `timer_source` recorded |
| algorithm | Interval sums over spec 5.3 and 5.4 structures |
| parameter_set | `gap_tolerance_factor = 1.5` `[D2]` |
| assumptions | Device clock monotonic within a file; FIT timer events complete when present |
| known_limitations | Without events (all TCX) pauses are invisible and `timer_s = elapsed_s`. Not moving time |
| validation_protocol | Synthetic tests (spec 7); real files: compare with `device_timer_s`, flag > max(2 s, 1%) |
| software_test_status | Oracle covers timer pause only; production not built |
| scientific_validation_status | IDENTITY; real file check pending |
| uncertainty_statement | Exact given inputs; error source is file content, not arithmetic |
| last_reviewed | 2026-10-17 |

### M002 Recorded mean power

| Field | Value |
|---|---|
| metric_id, version | M002, 1.0 |
| classification | DERIVED |
| units | W |
| equation | `Σ(P_i Δt_i) / Σ(Δt_i)`, observed power only (Annex A F01) |
| source_refs | Definition of time averaged power. Device measurement evidence: R06, R09 (agreement), R10 (accuracy, calibrated reference) |
| population_scope | Any ride with measured power |
| input_requirements | Measured power (never speed derived, Annex A F32) |
| data_quality_rules | Power coverage ≥ 0.95 of timer time, else `insufficient_coverage` |
| algorithm | Single pass sum |
| parameter_set | `min_coverage = 0.95` (engineering threshold) |
| assumptions | A1 (value applies forward); step function within each interval |
| known_limitations | Accuracy bounded by the power meter: about ±2 to 3% at 150 to 350 W for common meters, with condition dependent errors (R06). Values from different meters are not interchangeable without an agreement assessment. Missing data may be non random (dropouts during sprints), so mean over observed time can be biased even above 95% coverage |
| validation_protocol | Synthetic oracle agreement; cross source agreement assessment (bias, limits of agreement) on one ride recorded by Fenix 8, MyWhoosh and Hub. Not an accuracy validation, since no calibrated reference is available (spec 6.3) |
| software_test_status | Oracle 3 tests pass; production not built |
| scientific_validation_status | IDENTITY |
| uncertainty_statement | Arithmetic exact; measurement uncertainty is the device's, not quantified per ride |
| last_reviewed | 2026-10-17 |

### M003 Recorded mechanical work

| Field | Value |
|---|---|
| metric_id, version | M003, 1.0 |
| classification | DERIVED |
| units | kJ |
| equation | `Σ(P_i Δt_i) / 1000` (Annex A F02) |
| source_refs | Definition (1 W = 1 J/s). Device measurement evidence R06, R09 (agreement), R10 (accuracy, calibrated reference) |
| population_scope | As M002 |
| input_requirements | As M002 |
| data_quality_rules | Reported at any coverage > 0; `lower_bound` state below 0.95 `[D1]` |
| algorithm | Single pass sum |
| parameter_set | `lower_bound_label_below = 0.95` |
| assumptions | Mechanical power ≥ 0, so recorded work ≤ true work during timer time |
| known_limitations | Not metabolic energy. Conversion to kcal requires gross efficiency, which varies (Annex A F06, Ettema 2009, M) and is not done in Phase One |
| validation_protocol | As M002 |
| software_test_status | Oracle covered; oracle currently withholds work below 0.95 and must be updated to D1 (approved) before production code is compared with it |
| scientific_validation_status | IDENTITY |
| uncertainty_statement | As M002 |
| last_reviewed | 2026-10-17 |

### M004 Maximal mean power over duration T

| Field | Value |
|---|---|
| metric_id, version | M004, 1.0 |
| classification | DERIVED |
| units | W per T (s) |
| equation | `max_a (1/T) ∫[a,a+T) P dt`, windows inside contiguous observed power (Annex A F03) |
| source_refs | Definition. Use and interpretation: R11 (Leo 2022), R12 (Pinot and Grappe 2011, M) |
| population_scope | Any rider; history level values only as good as the efforts recorded |
| input_requirements | Contiguous observed power of at least T seconds |
| data_quality_rules | No window crosses gap, invalid sample or timer stop |
| algorithm | Prefix sum, two pointer, O(n) per T (architecture 6); oracle O(n²) reference |
| parameter_set | `durations_s = [5, 60, 300, 1200, 3600]` plus user values |
| assumptions | A1; step function |
| known_limitations | Shows what was done, not capability (R11). Strict no bridge rule means one dropped sample breaks long windows; effect to be measured on real files in Phase One. Short T sensitive to sample alignment and recording rate; meters differ in sprint response (R06) |
| validation_protocol | Oracle agreement plus hypothesis property tests; real file gap frequency report |
| software_test_status | Oracle 1 test pass; production not built |
| scientific_validation_status | IDENTITY |
| uncertainty_statement | Arithmetic exact; device and alignment uncertainty not quantified |
| last_reviewed | 2026-10-17 |

### M005 Critical Power and W′, two parameter (Phase Two)

| Field | Value |
|---|---|
| metric_id, version | M005, 0.1 (not approved) |
| classification | MODELLED |
| units | CP W, W′ J |
| equation | `P = CP + W′/t` and equivalent forms (Annex A F07) |
| source_refs | R01 Poole 2016 (P), R02 Chorley and Lamb 2020 (P), Hill 1993 (V), Monod and Scherrer 1965 (V), Mattioni Maturana 2018 (V), Muniz-Pumares 2019 (V), Jones 2019 (V), Dotan 2022 (M), Burnley 2023 (V), Karsten 2015 (V) |
| population_scope | Trained adults performing exhaustive efforts of about 2 to 15 min |
| input_requirements | ≥ 3 protocol efforts, separate sessions, distinct durations |
| data_quality_rules | Unmarked efforts give `protocol_unverified`; CP ≤ 0 or W′ ≤ 0 rejected |
| algorithm | Primary form fixed at Phase Two start `[resolved C10]`; other two forms as sensitivity |
| parameter_set | Fit form, effort IDs, exclusions |
| assumptions | Full W′ depletion at exhaustion; rested state; constant power or TT |
| known_limitations | Forms give different estimates on the same data (Mattioni Maturana 2018; Muniz-Pumares 2019). Overestimates outside the severe domain (R11). Whether CP equals the maximal metabolic steady state is disputed (Jones 2019 vs Dotan 2022). Power law alternative (Drake 2024) disputes the model form. W′ is not a measured energy store |
| validation_protocol | Synthetic recovery test; residuals; leave one out; Phase Two real rider repeat test |
| software_test_status | Oracle synthetic test passes (form 3) |
| scientific_validation_status | CONTROLLED, not approved |
| uncertainty_statement | Parameter standard errors from the fit; not a physiological confidence interval |
| last_reviewed | 2026-10-17 |

## 3. Candidate catalogue and disposition

Every formula in Annex A has a disposition here. Nothing not listed may be implemented.

| Annex | Calculation | Maps to | Disposition | Phase |
|---|---|---|---|---|
| F01 to F03 | Mean power, work, MMP | M002 to M004 | Approved | 1 |
| F04 | Power to mass | new M012 | Candidate; needs dated mass history | 2 |
| F05 | Torque, AEPF, CPV | new M013 | Candidate; needs crank length record; numbers only, no interpretation | 2 |
| F06 | Work to kcal | new M014 | Candidate, MODELLED, explicit GE input and range shown | 2 |
| F07 | Two parameter CP | M005 | Conditional | 2 |
| F08, F09 | Three parameter CP, 3 min test | M005 variants | Optional, separate test types | 2 |
| F10, F11 | OmPD, power law | Comparators | Research only, descriptive curve fits | 3 |
| F12 | Record power profile | M004 view | Own history only, no population ranking | 2 |
| F13 to F15 | W′ balance | new M015 | Research only, needs validated CP | 3 |
| F16 | FTP | none | Not computed. A dated user entered threshold with method MAY exist in `threshold_history` | 2 |
| F17 | Zones | M010 | Anchor and method stored; % threshold zones labelled conventions | 2 |
| F18 | HRmax prediction | none | Measured HRmax and resting HR only | 2 |
| F19, F20 | NP, IF, TSS style | none in 1 to 2 | Research only, neutral names, no trademarks | 3 |
| F21, F22 | TRIMP, session RPE | M007 inputs | Research only | 3 |
| F23 to F25 | Impulse response, VDR, EWMA load | M007 | Research only; release only after out of sample gate | 3 |
| F26 | ACWR | none | Rejected (mathematical coupling, Lolli 2019) | never |
| F27 | EF, decoupling | M006 | Descriptive candidate, confounders shown (R08) | 2 review |
| F28 | Durability | new M016 | Research only, definition stated | 3 |
| F29 | RMSSD | M008 | Only from raw RR intervals | 3 |
| F30 | Polarization index | M010 view | Research only | 3 |
| F31 | VO2max from power | M009 | Excluded | never in 1 to 3 |
| F32 | Power from speed | none | Excluded as power input (MyWhoosh speed is simulated) | never as input |
| R07 | 3D impulse response (Kontro 2026) | M007 candidate | Research only; authors state no experimental validation | 3 |

## 4. Differences from Annex A (resolved here)

1. F04 suggests Phase 1 or 2: set to Phase 2, because Phase One has no mass history table.
2. F06 suggests a Phase 2 labelled estimate: accepted as M014 candidate; Phase One UI shows no kcal.
3. F07 primary fitting form: left to the Phase Two start, decided by test type. For constant power time to exhaustion tests, duration carries the error; for time trials, power does. The register will record the reasoning and the choice before M005 code.
4. R06, R07, R08 completed below (authors and DOIs found).

## 5. Bibliography

### 5.1 Exercise science

| ID | Citation | DOI / link | Ver. |
|---|---|---|---|
| R01 | Poole DC, Burnley M, Vanhatalo A, Rossiter HB, Jones AM (2016). Critical power: an important fatigue threshold in exercise physiology. *Med Sci Sports Exerc* 48(11):2320–2334 | 10.1249/MSS.0000000000000939 | P |
| R02 | Chorley A, Lamb KL (2020). The application of critical power, W′ and its reconstitution: a narrative review. *Sports* 8(9):123 | 10.3390/sports8090123 | P |
| R03 | Hellard P et al. (2006). Assessing the limitations of the Banister model in monitoring training. *J Sports Sci* 24(5):509–520 | 10.1080/02640410500244697 | P |
| R04 | Seiler S (2010). What is best practice for training intensity and duration distribution in endurance athletes? *IJSPP* 5(3):276–291 | 10.1123/ijspp.5.3.276 | P |
| R05 | Manresa-Rocamora A et al. (2021). HRV guided training: systematic review with meta analysis. *IJERPH* 18(19):10299 | 10.3390/ijerph181910299 | P |
| R06 | Bouillod A, Soto-Romero G, Grappe F, Bertucci W, Brunet E, Cassirame J (2022). Caveats and recommendations to assess the validity and reliability of cycling power meters: a systematic scoping review. *Sensors* 22(1):386 | 10.3390/s22010386 | V |
| R07 | Kontro H, Mastracci A, Cheung SS, MacInnis MJ (2026). The three dimensional impulse response model. *PLOS ONE* 21(2):e0341721 | 10.1371/journal.pone.0341721 | V |
| R08 | Heaps CL, González-Alonso J, Coyle EF (1994). Hypohydration causes cardiovascular drift without reducing blood volume. *Int J Sports Med* 15(2):74–79. PMID 8157372 | 10.1055/s-2007-1021023 | V (via author publication list) |
| R09 | Hopker J, Myers S, Jobson SA, Bruce W, Passfield L (2010). Validity and reliability of the Wattbike cycle ergometer. *Int J Sports Med* 31(10):731–736. Earlier Wattbike models, not the Atom. Compared against an SRM, so it is an agreement study unless the SRM was calibrated against a traceable reference (to check in the paper) | 10.1055/s-0030-1261968 | V (Annex A) |
| R10 | Shiraki S, Yamagishi T, Yamashita D (2025). Conversion table and equations for power estimation in Wattbike AtomX. *Sports Engineering* 28:18. One AtomX read −6.4% (−35.6 W mean) against a Lode calibrator; AtomX is a different model from the Atom | 10.1007/s12283-025-00501-y | V |
| R11 | Leo P, Spragg J, Podlogar T, Lawley JS, Mujika I (2022). Power profiling and the power duration relationship in cycling: a narrative review. *Eur J Appl Physiol* 122(2):301–316 | 10.1007/s00421-021-04833-y | V (Annex A) |
| R12 | Pinot J, Grappe F (2011). The record power profile to assess performance in elite cyclists. *Int J Sports Med* 32(11):839–844 | 10.1055/s-0031-1279773 | M |
| Annex A | All further sources (about 45), with their V/M status | see Annex A bibliography | mixed; 24 DOIs unconfirmed (12 M, 12 DOI only M) |

### 5.2 Devices, formats and data access

| ID | Source | Use | Ver. |
|---|---|---|---|
| D01 | Garmin FIT SDK and protocol, developer.garmin.com/fit | Field definitions, events, sentinels | P |
| D02 | Garmin Connect export support pages | Original FIT export | P |
| D03 | Wattbike Hub session export support page | Per session TCX | P |
| D04 | Wattbike Atom product page | FTMS and ANT+ FE-C | P |
| D05 | Wattbike dual channel Bluetooth support page | Competing controllers | P |
| D06 | caniuse.com Web Bluetooth | No Safari iPadOS support | P |
| D07 | Garmin description of Smart vs Every Second recording, quoted at help.trainingpeaks.com/hc/en-us/articles/204070064 | Recording interval | V (secondary quote) |
| D08 | Garmin forum thread "download from mywhoosh" (user report: mywhoosh.com, Profile, Activities, download .fit) | MyWhoosh export path | V (user report only; not an official MyWhoosh document) |
| D09 | `fitdecode` 0.11.0 on PyPI (MIT, released 2025-08-06; embedded profile from FIT SDK 21.171). Garmin FIT SDK current release 21.218.0 (6 Oct 2026) for comparison | Decoder choice D8 | V (package inspected) |

## 6. Known evidence gaps

1. **Wattbike Atom power accuracy:** no accuracy study of the Atom against a calibrated reference was found. Manufacturer's ±1 to 2% claim cites Hopker 2010 (older models, agreement with SRM). The only located calibrated reference study (R10) is on the AtomX and found a −6.4% bias in one unit. Consequence: Atom watts and other meters' watts are not pooled without an agreement assessment on the rider's own rides. That assessment reports bias and limits of agreement between the instruments; it does not establish either one's accuracy unless a calibrated reference is used.
2. **Fenix 8 wrist HR accuracy during cycling:** not searched. HR source (wrist or strap) is recorded per activity; any HR metric (Phase Two) requires this evidence first.
3. **MyWhoosh power processing:** unknown whether MyWhoosh records trainer power unaltered or smoothed. To be examined in the three source agreement assessment ride.
4. **FIT record power timing (assumption A1):** not documented in sources reviewed.
5. **24 Annex A DOIs unconfirmed:** must be confirmed before their metrics are approved. None affect Phase One.
6. **Zero written during dropouts:** not established whether Fenix 8 or MyWhoosh write 0 W when a power signal drops. Handled by the `suspect_zero` flag (spec 5.2) until tested.
7. **Clock offset between devices recording the same ride:** not measured. Needed before cross file channel combinations (spec 5.8).
8. **Meaning of Smart Recording gaps (U9):** not established whether a gap means the recorder saw no change in value. Until it is, the uniform gap rule (D2) applies and each file's recording statistics are reported.
