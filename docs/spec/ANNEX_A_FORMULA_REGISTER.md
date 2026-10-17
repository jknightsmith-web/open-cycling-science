# Cited formula register

Compiled 17 October 2026 for Open Cycling Science. Companion to `docs/03_METRIC_REGISTER.md` (M001 to M011) and `docs/06_RESEARCH_REFERENCES.md` (R01 to R08). IDs here use the prefix `F` so they do not collide with metric IDs.

## How to read this register

**Evidence labels** follow `docs/02_SCIENTIFIC_STANDARD.md`:

| Label | Meaning |
|---|---|
| IDENTITY | Established mathematical identity, valid by definition of the inputs |
| CONTROLLED | Model supported in controlled settings under a defined protocol |
| LIMITED | Predictive evidence limited, small samples or unvalidated in individuals |
| UNVERIFIED | Vendor or book definition with no peer reviewed derivation or validation |

**Source verification status** (column `Ver.` in the bibliography):

* **V**: title, journal and DOI confirmed against a publisher, repository or indexing record during this review.
* **P**: taken from the project's own bibliography (`06_RESEARCH_REFERENCES.md`), not rechecked here.
* **M**: citation given from reviewer knowledge; DOI not confirmed in this review because Crossref, doi.org and PubMed were unreachable from the review environment. Confirm before the metric's evidence record is marked complete.

**Fact vs inference.** Formulas and quoted study results are facts from the cited source. Text marked *Assessment* is the reviewer's inference or recommendation.

## Summary

| ID | Calculation | Class | Evidence | Recommended phase | Key flag |
|---|---|---|---|---|---|
| F01 | Duration weighted mean power | DERIVED | IDENTITY | 1 (M002) | Gap rule is an engineering choice |
| F02 | Mechanical work | DERIVED | IDENTITY | 1 (M003) | Underestimate if gaps |
| F03 | Maximal mean power, power duration curve | DERIVED | IDENTITY | 1 (M004) | Observed, not maximal capability |
| F04 | Power to mass ratio | DERIVED | IDENTITY | 1 or 2 | Mass provenance needed |
| F05 | Crank torque, AEPF, CPV | DERIVED | IDENTITY | 2 | Crank length must be recorded |
| F06 | Mechanical work to metabolic energy | MODELLED | LIMITED | 2, labelled estimate | Gross efficiency varies ~18 to 24% |
| F07 | Two parameter CP and W′ | MODELLED | CONTROLLED | 2 (M005) | Three fitting forms give different CP |
| F08 | Three parameter CP (Morton) | MODELLED | CONTROLLED | 2, optional | Needs Pmax; poorly conditioned |
| F09 | 3 min all out test | MODELLED | CONTROLLED, contested | 2, optional | End power vs CP agreement disputed |
| F10 | Omni domain power duration (OmPD) | MODELLED | LIMITED | 3 | Single validation group |
| F11 | Power law endurance model | MODELLED | LIMITED, contested | 3, comparator only | Active published dispute with CP |
| F12 | Record power profile | DERIVED + reference data | LIMITED | 2 (display only) | Population norms not transferable |
| F13 | W′ balance, integral (Skiba 2012) | MODELLED | LIMITED | 3 | τ equation fitted in small cohort |
| F14 | W′ balance, differential (Skiba 2015) | MODELLED | LIMITED | 3 | Different recovery assumption from F13 |
| F15 | W′ recovery τ for elite cyclists (Bartram) | MODELLED | LIMITED | 3 | R² 0.43 |
| F16 | FTP (95% of 20 min) and variants | MODELLED | UNVERIFIED definition, contested validity | Excluded from 1; configurable input only | Agreement with MLSS disputed |
| F17 | Intensity zones | DERIVED from thresholds | Depends on anchor | 2 (M010) | % FTP zones are conventions |
| F18 | HRmax prediction, HR reserve | MODELLED | LIMITED for individuals | Measured values only | Population SEE large |
| F19 | Normalized Power style weighted power | DERIVED | UNVERIFIED | 3, renamed | Trademarked; no peer reviewed derivation |
| F20 | IF and TSS style session load | DERIVED | UNVERIFIED (formula), LIMITED (validity) | 3, renamed | Trademarked; depends on F16 |
| F21 | HR TRIMP (Banister, Edwards, Lucia, iTRIMP) | DERIVED | LIMITED | 3 | Weighting constants differ by method |
| F22 | Session RPE load | DERIVED | LIMITED | 3 | Subjective input |
| F23 | Banister impulse response | MODELLED | LIMITED | 3 (M007) | Identifiability problems |
| F24 | Variable dose response (Busso) | MODELLED | LIMITED | 3 | More parameters, same data demands |
| F25 | EWMA load (CTL, ATL, TSB style) | MODELLED | UNVERIFIED as predictor | 3, renamed | Fixed 42/7 d constants |
| F26 | Acute to chronic workload ratio | MODELLED | Contested | Do not implement | Mathematical coupling |
| F27 | Power to HR decoupling, efficiency factor | DERIVED ratio | UNVERIFIED interpretation | 2 descriptive (M006) | Heat and hydration confound |
| F28 | Durability | DERIVED | LIMITED | 3 | No agreed operational definition |
| F29 | RMSSD | DERIVED | CONTROLLED (measurement) | 3 (M008) | Requires raw RR intervals |
| F30 | Polarization index | DERIVED | LIMITED | 3 | Defined only for specific zone order |
| F31 | VO2max from power | MODELLED | LIMITED | Excluded (M009) | Population equations |
| F32 | Road cycling power from speed (virtual power) | MODELLED | CONTROLLED | Excluded | Spec forbids inferring power |

---

## A. Mathematical identities

### F01. Duration weighted mean power

`P_mean = Σ(P_i·Δt_i) / Σ(Δt_i)` over valid observed power intervals.

* **Units:** W.
* **Assumptions:** `P_i` holds over `[t_i, t_i + Δt_i)`. Recorded 0 W is valid; missing is excluded.
* **Valid range:** any duration; reported with coverage fraction. The project's 95% coverage threshold is an engineering rule, not a published threshold (already stated in M002).
* **Source:** definition of time averaged power. No literature source required.
* **Flag:** none on the formula. *Assessment:* the only contestable part is gap handling, which the project already specifies.

### F02. Mechanical work

`W_kJ = Σ(P_i·Δt_i) / 1000`.

* **Assumptions and range:** as F01. This is observed recorded work, an underestimate when intervals are missing.
* **Source:** definition (1 W = 1 J/s).
* **Measurement caveat:** accuracy is bounded by the power meter. See R06 (Sensors 2022 review) and Hopker et al. 2010 for the Wattbike. *Fact:* Hopker 2010 tested earlier Wattbike models; no Atom specific validation was looked up in this review.

### F03. Maximal mean power and the power duration curve

`MMP(T) = max_a (1/T)·∫_a^{a+T} P(t) dt`, window may not cross missing data or timer pauses.

* **Units:** W per duration T (s).
* **Assumptions:** data are duration weighted; a window requires T seconds of valid data (M004).
* **Valid range:** 1 s up to the longest valid continuous segment.
* **Source:** definition. Use in research: Pinot & Grappe 2011 (record power profile); Quod et al. 2010; Leo et al. 2022 review.
* **Flag:** Leo et al. 2022 state that field MMP shows "what a cyclist did, not what the cyclist is capable of"; race MMP values are not necessarily maximal. This supports the M004 limitation as written.

### F04. Power to mass ratio

`P_rel = P / m`, W·kg⁻¹.

* **Assumptions:** body mass measured near the activity date; store source and date of mass.
* **Source:** definition.
* **Flag:** *Assessment:* store mass in `threshold_history`-style history; a single static mass silently corrupts years of history.

### F05. Crank torque, average effective pedal force, circumferential pedal velocity

* `ω = 2π·cadence_rpm / 60` (rad·s⁻¹)
* `τ = P / ω` (N·m)
* `AEPF = P / (ω·L_crank)` (N)
* `CPV = ω·L_crank` (m·s⁻¹)

* **Assumptions:** cadence and power time aligned; `L_crank` in m from equipment record. Undefined at cadence 0 (return null, not infinity).
* **Source:** rotational mechanics. Quadrant analysis (AEPF vs CPV plot) is described in Allen & Coggan's book; no peer reviewed validation of its training interpretation was found in this review.
* **Flag:** IDENTITY for the numbers, UNVERIFIED for any interpretation.

### F06. Mechanical work to metabolic energy

`E_met_kcal = W_kJ / (GE × 4.184)`

* **Inputs:** gross efficiency GE as a fraction.
* **Derived consequence:** the common "1 kJ ≈ 1 kcal" heuristic is exact only at GE = 0.239. At GE 0.18 the ratio is 1.33 kcal per kJ; at 0.23 it is 1.04.
* **Source:** unit conversion (1 kcal = 4.184 kJ). GE range in cycling: Ettema & Lorås 2009 (M).
* **Flag:** LIMITED. GE varies between riders, cadence and intensity. Label any output as an estimate with the GE used. The architecture doc already forbids equating mechanical kJ with dietary kcal.

---

## B. Power duration and critical power models

### F07. Two parameter critical power model

Three algebraically equivalent forms:

1. Hyperbolic: `P = CP + W′/t`, equivalently `t = W′/(P − CP)`
2. Linear work–time: `W = CP·t + W′`
3. Linear power–inverse time: `P = W′·(1/t) + CP`

* **Units:** P, CP in W; W′ in J; t in s.
* **Assumptions:** each point is an exhaustive constant power effort (or time trial) from a rested state; W′ is fully expended at task failure; CP is sustainable indefinitely in theory.
* **Valid range:** severe domain, conventionally efforts of about 2 to 15 min (Chorley & Lamb 2020; Leo et al. 2022). Not valid for sprint or for durations beyond about 15 to 20 min.
* **Primary sources:** Monod & Scherrer 1965 (original, muscle groups); Moritani et al. 1981 (cycle ergometry); Hill 1993 (review); Poole et al. 2016 and Jones et al. 2010 (physiological basis).
* **Disagreement and weak points:**
  * *Fact:* the three forms fitted to the same data give different CP and W′ estimates (Mattioni Maturana et al. 2018; Muniz-Pumares et al. 2019), because each minimises error in a different variable.
  * *Fact:* Leo et al. 2022: the 2 parameter model overestimates power outside the severe domain at both short and long durations.
  * *Fact:* Whether CP marks the maximal metabolic steady state is argued for by Jones et al. 2019 and disputed by Dotan 2022, with a rebuttal by Burnley 2023 and Wong et al. 2023. This is an active dispute, not settled.
  * *Fact:* the project's own acceptance test (CP 250 W, W′ 18000 J at 180, 360, 720 s) is consistent with form 1: 250 + 18000/180 = 350 W.
* *Assessment:* fix one primary fitting form in the evidence record (form 1 by nonlinear least squares on P, or form 2), report the other two as a sensitivity analysis, and store which was used in `model_fits`. Field derived CP from training peaks: Karsten et al. 2015 reported acceptable agreement for a field protocol with defined efforts, which is not the same as arbitrary ride history. Keep `protocol_unverified`.

### F08. Three parameter critical power model (Morton)

`t = W′/(P − CP) − W′/(Pmax − CP)`

* **Additional parameter:** Pmax (W), the instantaneous power at t = 0.
* **Assumptions:** as F07, plus the curve reaches a finite Pmax rather than infinity.
* **Valid range:** extends into the extreme domain (short efforts).
* **Source:** Morton 1996, *Ergonomics* 39(4):611–619 (metadata V, DOI M).
* **Flag:** *Fact:* still overestimates moderate domain power (Leo et al. 2022). *Assessment:* three parameters from typically three to five test points is poorly conditioned; reject fits where Pmax is not supported by a measured sprint.

### F09. 3 minute all out test

* `CP_est = EP` = mean power over the final 30 s of a 180 s all out effort.
* `W′_est = WEP` = work done above EP over the 180 s.

* **Assumptions:** truly all out from the start with fixed resistance (linear mode) set from prior testing; W′ fully depleted by about 150 s.
* **Valid range:** single test protocol; requires a controllable ergometer (relevant for the Wattbike in a later phase).
* **Primary sources:** Burnley, Doust & Vanhatalo 2006 (M); Vanhatalo, Doust & Burnley 2007 (title V, DOI M).
* **Disagreement:** *Fact:* Wright et al. 2015 (*J Sci Cycling*) tested reliability and validity in linear and isokinetic modes and cite Karsten et al. (2013) finding the isokinetic version reliable but not a valid measure of CP or W′. Numerical results of Wright 2015 were not retrieved in this review. *Assessment:* treat EP as a separate test type in `test_efforts`, never pooled silently with conventional CP.

### F10. Omni domain power duration model (OmPD)

Structure (M, verify exact form against the paper before coding):

* For t ≤ T_CPmax: `P(t) = (W′/t)·(1 − e^{−t·(Pmax − CP)/W′}) + CP`
* For t > T_CPmax: the same expression minus `A·ln(t/T_CPmax)`, with T_CPmax = 1800 s in the original.

* **Source:** Puchowicz, Baker & Clarke 2020, *J Sports Sci* 38(7):801–813 (metadata V, DOI M).
* **Flag:** LIMITED. *Fact:* Leo et al. 2022 say exponential decay terms (OmPD, Péronnet & Thibault) are the best current options below CP but their physiological basis is uncertain. *Assessment:* candidate for fitting the whole MMP curve descriptively, not for physiological claims.

### F11. Power law endurance model

`P(t) = S·t^(E − 1)` (equivalently `P = A·t^(−b)`), fitted in log–log space.

* **Source:** Drake, Finke & Ferguson 2024, *Eur J Appl Physiol* 124(2):507–526 (V); historic form from Kennelly 1906.
* **Disagreement:** *Fact:* Drake et al. conclude the power law describes the power duration relationship better than the hyperbolic CP model, which fits well only between about 2 and 15 min. Muniz-Pumares et al. replied ("All models are wrong, but the critical power model is useful", 2023/24, V) and Drake et al. responded again. *Assessment:* useful as a comparator for out of range prediction errors; do not pick a winner in the UI.

### F12. Record power profile

MMP at a fixed set of durations (from 1 s to several hours), compared over time or against published group values.

* **Sources:** Pinot & Grappe 2011 (metadata V, DOI M); Quod et al. 2010 (metadata V, DOI M) show laboratory power profile predicts field MMP.
* **Flag:** published norms come from elite cohorts; *Assessment:* show the rider's own history only, no population ranking, in Phase Two.

---

## C. W′ balance (intermittent work capacity)

### F13. Integral model (Skiba 2012)

`W′bal(t) = W′ − ∫₀ᵗ W′exp(u)·e^{−(t − u)/τ} du`

`τ = 546·e^{−0.01·D_CP} + 316` (s), where `D_CP = CP − mean power during recovery below CP`.

* **Inputs:** CP and W′ from F07 (validated), 1 s power.
* **Source:** Skiba, Chidnok, Vanhatalo & Jones 2012, *Med Sci Sports Exerc* 44(8):1526–1532 (existence V, DOI M).
* **Flag:** LIMITED. τ equation fitted in a small laboratory group. Model output inherits all error in CP and W′.

### F14. Differential model (Skiba 2015)

* Above CP: `dW′/dt = −(P − CP)`
* Below CP: `W′bal(t) = W′ − (W′ − W′bal(t₀))·e^{−D_CP·(t − t₀)/W′}`

* **Source:** Skiba, Fulford, Clarke, Vanhatalo & Jones 2015, *Eur J Appl Physiol* 115:703–713 (M); methodological comparison Skiba & Clarke 2021, *IJSPP* (existence V, DOI M).
* **Disagreement:** F13 and F14 make different recovery assumptions and give different W′bal on the same file. *Assessment:* if implemented, store model variant in `model_fits`; never mix variants in one chart.

### F15. Elite recovery time constant (Bartram)

`τ_W′ = 2287.2·D_CP^(−0.688)`

* **Source:** Bartram, Thewlis, Martin & Norton 2018, *IJSPP* 13(6):724–728, DOI 10.1123/ijspp.2017-0034 (V).
* **Flag:** *Fact:* R² = 0.433; authors state it needs validation and individual τ may be necessary. *Fact:* Skiba's τ was derived in non elite subjects and Bartram found it inaccurate in elite cyclists. Neither should be presented as rider specific without individual calibration.

---

## D. Thresholds and intensity anchors

### F16. Functional threshold power

Common definitions (all protocol definitions, not physiological measurements):

* `FTP = 0.95 × mean power of a 20 min maximal test` (Allen & Coggan, book)
* `FTP = MMP(3600 s)` from a maximal 60 min effort (definitional origin)
* Ramp test and 8 min test multipliers (vendor protocols; no primary peer reviewed derivation found)

* **Source:** Allen H, Coggan A. *Training and Racing with a Power Meter*, VeloPress (book, no DOI).
* **Evidence and disagreement (all V):**

| Study | n | Finding |
|---|---|---|
| Borszcz et al. 2019, IJSPP | 15 | FTP vs MLSS bias 1.4% ±9.2% (95% LoA); TEE 4.7%; r = 0.91. Authors: usable as MLSS estimate in trained cyclists |
| Inglis et al. 2020, IJSPP | 18 | MLSS = 93.1 ± 5.1% of FTP95%. MLSS rose 12 ± 8 W after training; FTP did not change. Authors: FTP differs from MLSS |
| Karsten et al. 2021, Front Physiol | 17 | CP − FTP bias 7 ± 13 W, LoA −19 to 33 W, r = 0.969. Authors: not interchangeable. Paper reports inconsistent p values and bias between sections |
| Valenzuela et al. 2018, IJSPP | n/r | FTP as surrogate of lactate threshold (numbers not retrieved) |
| MacInnis et al. 2019, IJSPP | n/r | Reliability of 4 and 20 min TTs vs FTP (numbers not retrieved) |

* **Review position:** Leo et al. 2022 (V) state CP and MLSS are considered estimates of the maximal metabolic steady state but this cannot be confirmed for FTP, and recommend avoiding single effort prediction trials.
* *Assessment:* project docs already prohibit an FTP score in Phase One. Recommend treating FTP only as a user configured, dated threshold with `method` recorded in `threshold_history`, never auto estimated from ride history. Agreement limits of ±9 to ±13% are too wide to label FTP as MLSS for an individual.

### F17. Intensity zones

* Power zones as % of a threshold (Allen & Coggan convention, UNVERIFIED as physiological boundaries).
* Three zone model anchored to LT1/LT2 or VT1/VT2 (Seiler 2010, P).
* Time in zone: `T_z = Σ Δt_i [P_i ∈ zone z]`.

* **Sources:** Seiler 2010 (P); Jamnick et al. 2020, *Sports Med* 50:1729–1756, DOI 10.1007/s40279-020-01322-8 (V); Faude, Kindermann & Meyer 2009 (M) on threshold concept validity.
* **Flag:** *Fact:* Jamnick et al. review a wide range of threshold methods that do not agree with each other. *Assessment:* store the anchor and method with every zone set; % FTP zones must be labelled as conventions.

### F18. HRmax prediction and heart rate reserve

* `HRmax_pred = 208 − 0.7·age` (Tanaka, Monahan & Seals 2001, M)
* `HRR = HRmax − HRrest`; target `HR = HRrest + k·HRR` (Karvonen et al. 1957, M)

* **Flag:** population equations carry large individual error (SEE around ±10 bpm, M). *Assessment:* accept measured HRmax and resting HR only; show predicted values only with explicit labelling.

---

## E. Session training load

### F19. Weighted average power (Normalized Power® style)

`P30(t) = 30 s rolling mean of P`; `NP = (mean(P30⁴))^(1/4)`

* **Source:** Coggan, described in Allen & Coggan (book). TrainingPeaks' own article by Coggan describes NP in words, gives no formula and cites no peer reviewed paper (V, trainingpeaks.com).
* **Flags:**
  * UNVERIFIED. The 30 s window and fourth power exponent have no peer reviewed derivation found in this review.
  * Gap and pause handling are not specified by the originator; the project must define it (consistent with M004 rules).
  * Skiba's xPower variant uses a 25 s exponentially weighted average instead; unpublished, so implementations differ.
  * **Naming:** TrainingPeaks marks "Normalized Power®", "Intensity Factor®" and "Training Stress Score®" as registered marks (V). *Assessment:* use neutral names (for example "fourth power weighted mean power") and cite the definition; get legal confirmation before using the marks.

### F20. Intensity factor and session stress (IF and TSS style)

* `IF = NP / FTP`
* `TSS = (t_s × NP × IF) / (FTP × 3600) × 100 = 100 × t_h × IF²`

* **Source:** Allen & Coggan (book). TrainingPeaks article states TSS is modelled on Banister's TRIMP (V).
* **Evidence:** Sanders et al. 2017, *IJSPP* 12(5):668–675 (V), 15 cyclists over 10 weeks: TSS correlated with fitness changes r = 0.75 and 0.79; iTRIMP r = 0.81 and 0.77; for 8 min TT performance the strongest were luTRIMP r = 0.70 and iTRIMP r = 0.63.
* **Flag:** inherits FTP uncertainty (F16). Small n; correlations of accumulated load with change scores, not prediction in individuals.

### F21. Heart rate training impulse (TRIMP)

* **Banister TRIMP:** `TRIMP = t_min × ΔHRr × 0.64·e^(1.92·ΔHRr)` (men), `0.86·e^(1.67·ΔHRr)` (women), `ΔHRr = (HR_ex − HR_rest)/(HR_max − HR_rest)`. Source: Morton, Fitz-Clarke & Banister 1990, *J Appl Physiol* 69:1171–1177 (existence V, DOI M).
* **Edwards TRIMP:** `Σ t_z × z` for five zones of 50–60% … 90–100% HRmax weighted 1 to 5. Source: Edwards 1993, book (M).
* **Lucia TRIMP:** time below VT1 ×1, VT1–VT2 ×2, above VT2 ×3. Source: Lucia et al. 2003 (M).
* **iTRIMP:** individual exponential weighting from the rider's own HR–lactate curve. Source: Manzi et al. 2009 (M).
* **Flag:** the weighting constants are method specific (sex specific constants in Banister derive from a blood lactate relation in small samples). *Assessment:* iTRIMP has the best evidence in cyclists (Sanders 2017) but needs lab lactate data.

### F22. Session RPE load

`Load = RPE_CR10 × duration_min`

* **Source:** Foster et al. 2001, *J Strength Cond Res* 15(1):109–115 (existence V, DOI M).
* **Flag:** subjective input; store as OBSERVED user report.

---

## F. Longitudinal load and performance models

### F23. Banister impulse response (fitness–fatigue)

`p̂(t) = p₀ + k₁·Σ_{s<t} w_s·e^{−(t−s)/τ₁} − k₂·Σ_{s<t} w_s·e^{−(t−s)/τ₂}`

* **Sources:** Banister et al. 1975 (book chapter/journal without DOI, M); Calvert, Banister, Savage & Bach 1976, *IEEE Trans Syst Man Cybern* (existence V, DOI M); Morton et al. 1990.
* **Flag:** *Fact:* Hellard et al. 2006 (P) show parameter estimation and identifiability limits. Five parameters require many repeated performance measurements. Matches M007 restrictions.

### F24. Variable dose response model

As F23 with `k₂(t)` itself a function of recent load (`k₂(t) = k₃·Σ w_s·e^{−(t−s)/τ₃}`).

* **Source:** Busso 2003, *Med Sci Sports Exerc* 35(7):1188–1195, DOI 10.1249/01.MSS.0000074465.13621.37 (V).
* **Flag:** more parameters, same data scarcity. Research only.

### F25. Exponentially weighted load (CTL, ATL, TSB style)

* `CTL_d = CTL_{d−1} + λ_42·(L_d − CTL_{d−1})`, `ATL_d` same with τ = 7 d, `TSB_d = CTL_{d−1} − ATL_{d−1}`
* Two discretisations are in use: `λ = 1/τ` and `λ = 1 − e^{−1/τ}`. They give different values; specify one.

* **Source:** a special case of F23 with k₁ = k₂ = 1 and fixed τ. Popularised by Coggan via TrainingPeaks; no peer reviewed validation as a performance predictor was found in this review.
* **Flag:** UNVERIFIED as predictor. Docs already forbid labelling as fitness or readiness. *Assessment:* if shown, call it "42 day exponentially weighted load" and state the constants are conventions.

### F26. Acute to chronic workload ratio

`ACWR = mean load (7 d) / mean load (28 d)` or EWMA variants.

* **Sources:** Gabbett 2016 (M); critique Lolli et al. 2019, *BJSM* 53(15):921–922, DOI 10.1136/bjsports-2017-098110 (V); Impellizzeri et al. 2020 (M).
* **Flag:** *Fact:* when the acute window is inside the chronic window the ratio is mathematically coupled, producing spurious correlation (Lolli 2019). Evidence base is team sport injury, not cycling performance. *Assessment:* do not implement.

---

## G. Physiological indices

### F27. Power to heart rate decoupling and efficiency factor

* `EF = P_mean / HR_mean` over a steady segment
* `Decoupling = (EF_first_half − EF_second_half) / EF_first_half`

* **Source:** coaching literature (Friel; Allen & Coggan), no peer reviewed validation found. Cardiovascular drift physiology: Coyle & González-Alonso 2001 (M); hydration confounder R08 (P).
* **Flag:** UNVERIFIED interpretation. Heat, hydration, posture and sensor changes confound. Consistent with M006.

### F28. Durability

No single formula. Typical operational form: `ΔMMP(T) = MMP_after_X_kJ·kg⁻¹(T) / MMP_fresh(T) − 1`.

* **Source:** Maunder et al. 2021, *Sports Med* 51:1619–1628, DOI 10.1007/s40279-021-01459-0 (V).
* **Flag:** definitions of prior work, test duration and freshness differ between studies. *Assessment:* only display with the definition and all parameters stated.

### F29. RMSSD

`RMSSD = sqrt( (1/(N−1))·Σ (RR_{i+1} − RR_i)² )`, ms. Often analysed as ln(RMSSD) with a 7 day rolling mean.

* **Sources:** Task Force of ESC and NASPE 1996, *Circulation* 93:1043–1065 (M); Plews et al. 2013 (M) for rolling lnRMSSD; Manresa-Rocamora et al. 2021 (P) for HRV guided training outcomes.
* **Flag:** valid only from raw RR intervals with documented artefact correction. Vendor overnight HRV is a different OBSERVED quantity (M008).

### F30. Polarization index

`PI = log₁₀( (Z1 / Z2) × Z3 × 100 )` with Zi as fractions of time in a three zone model; defined as polarized when Z1 > Z3 > Z2 and PI above a cut point (formula from M, verify before use).

* **Source:** Treff et al. 2019, *Front Physiol* 10:707 (M). A published commentary on the index exists (PMC10639116, not read).
* **Flag:** LIMITED; depends entirely on how zones were anchored (F17). Not a prescription (R04).

### F31. VO2max estimated from power

* ACSM leg cycling equation: `VO2 (mL·kg⁻¹·min⁻¹) = 1.8 × WR(kg·m·min⁻¹)/m + 7`, with 1 W = 6.12 kg·m·min⁻¹ (ACSM Guidelines, M).
* Hawley & Noakes 1992: `VO2max (L·min⁻¹) = 0.01141 × W_peak + 0.435` in trained cyclists (M).

* **Flag:** population regressions; excluded by M009 and product scope. Listed only so the catalogue can explain why it is absent.

### F32. Road cycling power from speed (virtual power)

`P = [½ρ·CdA·v_a²·v_g + Crr·m·g·v_g·cosθ + m·g·v_g·sinθ + ½(m + I/r²)·Δ(v²)/Δt] / E_chain` (plus bearing losses)

* **Source:** Martin et al. 1998, *J Appl Biomech* 14(3):276–291 (existence V, DOI M).
* **Flag:** validated with measured CdA and Crr in controlled conditions. M002 requires measured power, so this is excluded. Possible later use: estimating CdA from measured power.

---

## Cross cutting disagreements

| Topic | Positions | Status | Recommendation |
|---|---|---|---|
| CP as maximal metabolic steady state | Jones et al. 2019 for; Dotan 2022 against; Burnley 2023 and Wong et al. 2023 rebut Dotan | Unresolved | Describe CP as a model parameter; avoid "threshold" claims in UI |
| CP vs power law | Drake et al. 2024 for power law; Muniz-Pumares et al. 2023/24 defend CP | Unresolved | Fit CP per protocol; offer power law as comparator |
| Choice of CP fitting form | Mattioni Maturana 2018; Muniz-Pumares 2019 show different estimates | Methodological | Fix one, report others as sensitivity |
| FTP vs MLSS | Borszcz 2019 acceptable agreement; Inglis 2020 and Karsten 2021 not interchangeable | Contested; LoA ±9 to ±13% | Configurable input only |
| W′ recovery τ | Skiba 2012 vs Bartram 2018 vs Skiba 2015 differential | Model specific | Individual calibration before display |
| TSS style load validity | Sanders 2017 moderate to strong correlations in n = 15 | Limited | Research display only |
| ACWR | Coupling artefact (Lolli 2019) | Rejected for this project | Do not implement |

## Implications for the existing project register

1. **M005 is consistent** with F07; add the fitting form choice and sensitivity analysis explicitly, plus the CP vs MMSS dispute to its limitations.
2. **Naming risk:** NP, IF and TSS are registered marks per TrainingPeaks; any future load metric should use neutral names.
3. **FTP:** keep excluded from automated outputs. If a threshold is needed for zones, accept a dated user entry with method.
4. **Missing from 06_RESEARCH_REFERENCES.md and worth adding for Phase Two:** Leo et al. 2022, Mattioni Maturana 2018, Muniz-Pumares 2019, Hill 1993, Monod & Scherrer 1965, Morton 1996, Jones et al. 2019, Karsten et al. 2015.
5. **Unverified in this review:** all entries marked M below need DOI confirmation; Wattbike Atom specific power accuracy was not searched.

## Bibliography

| Ref | Citation | DOI | Ver. |
|---|---|---|---|
| Allen & Coggan | Allen H, Coggan A. *Training and Racing with a Power Meter*. VeloPress (2nd ed. 2010) | none (book) | V (via Karsten 2021 ref list) |
| Bartram 2018 | Bartram JC, Thewlis D, Martin DT, Norton KI. Accuracy of W′ recovery kinetics in high performance cyclists: modeling intermittent work capacity. *IJSPP* 13(6):724–728 | 10.1123/ijspp.2017-0034 | V |
| Borszcz 2018 | Borszcz FK et al. *Int J Sports Med* 39:737–742 (FTP vs MLSS) | 10.1055/s-0044-101546 | V (via Karsten 2021 ref list) |
| Borszcz 2019 | Borszcz FK, Tramontin AF, Costa VP. Is the functional threshold power interchangeable with the maximal lactate steady state in trained cyclists? *IJSPP* 14(8):1029–1035 | 10.1123/ijspp.2018-0572 | V |
| Burnley 2006 | Burnley M, Doust JH, Vanhatalo A. A 3-min all-out test to determine peak oxygen uptake and the maximal steady state. *Med Sci Sports Exerc* 38(11):1995–2003 | 10.1249/01.mss.0000232024.06114.a6 | M |
| Burnley 2023 | Burnley M. Flawed analysis and erroneous interpretations of the critical power concept: response to Mr. Dotan. *Eur J Appl Physiol* 123:211–213 | 10.1007/s00421-022-05013-2 | V |
| Busso 2003 | Busso T. Variable dose-response relationship between exercise training and performance. *Med Sci Sports Exerc* 35(7):1188–1195 | 10.1249/01.MSS.0000074465.13621.37 | V |
| Calvert 1976 | Calvert TW, Banister EW, Savage MV, Bach T. A systems model of the effects of training on physical performance. *IEEE Trans Syst Man Cybern* SMC-6(2):94–102 | 10.1109/TSMC.1976.5409179 | M |
| Chorley 2020 | R02 in project bibliography | 10.3390/sports8090123 | P |
| Coyle 2001 | Coyle EF, González-Alonso J. Cardiovascular drift during prolonged exercise. *Exerc Sport Sci Rev* 29(2):88–92 | 10.1097/00003677-200104000-00009 | M |
| Dotan 2022 | Dotan R. A critical review of critical power. *Eur J Appl Physiol* 122:1559–1588 | 10.1007/s00421-022-04922-6 | M |
| Drake 2024 | Drake JP, Finke A, Ferguson RA. Modelling human endurance: power laws vs critical power. *Eur J Appl Physiol* 124(2):507–526 | 10.1007/s00421-023-05274-5 | V |
| Ettema 2009 | Ettema G, Lorås HW. Efficiency in cycling: a review. *Eur J Appl Physiol* 106(1):1–14 | 10.1007/s00421-009-1008-7 | M |
| Foster 2001 | Foster C et al. A new approach to monitoring exercise training. *J Strength Cond Res* 15(1):109–115 | none confirmed | V (existence) |
| Hawley 1992 | Hawley JA, Noakes TD. Peak power output predicts maximal oxygen uptake and performance time in trained cyclists. *Eur J Appl Physiol* 65(1):79–83 | 10.1007/BF00634965 | M |
| Hellard 2006 | R03 in project bibliography | 10.1080/02640410500244697 | P |
| Hill 1993 | Hill DW. The critical power concept: a review. *Sports Med* 16(4):237–254 | 10.2165/00007256-199316040-00003 | V |
| Hopker 2010 | Hopker J, Myers S, Jobson SA, Bruce W, Passfield L. Validity and reliability of the Wattbike cycle ergometer. *Int J Sports Med* 31(10):731–736 | 10.1055/s-0030-1261968 | V |
| Impellizzeri 2020 | Impellizzeri FM et al. Acute:chronic workload ratio: conceptual issues and fundamental pitfalls. *IJSPP* 15(6):907–913 | 10.1123/ijspp.2019-0864 | M |
| Inglis 2020 | Inglis EC, Iannetta D, Passfield L, Murias JM. Maximal lactate steady state versus the 20-minute functional threshold power test in well-trained individuals: "watts" the big deal? *IJSPP* 15(4):541–547 | 10.1123/ijspp.2019-0214 | V |
| Jamnick 2020 | Jamnick NA, Pettitt RW, Granata C, Pyne DB, Bishop DJ. An examination and critique of current methods to determine exercise intensity. *Sports Med* 50:1729–1756 | 10.1007/s40279-020-01322-8 | V |
| Jones 2010 | Jones AM et al. Critical power: implications for determination of VO2max and exercise tolerance. *Med Sci Sports Exerc* 42(10):1876–1890 | 10.1249/MSS.0b013e3181d9cf7f | V (metadata), M (DOI) |
| Jones 2019 | Jones AM, Burnley M, Black MI, Poole DC, Vanhatalo A. The maximal metabolic steady state: redefining the "gold standard". *Physiol Rep* 7(10):e14098 | 10.14814/phy2.14098 | V |
| Karsten 2015 | Karsten B et al. Validity and reliability of critical power field testing. *Eur J Appl Physiol* 115:197–204 | 10.1007/s00421-014-3001-z | V |
| Karsten 2021 | Karsten B, Petrigna L, Klose A, Bianco A, Townsend N, Triska C. Relationship between the critical power test and a 20-min functional threshold power test in cycling. *Front Physiol* 11:613151 | 10.3389/fphys.2020.613151 | V |
| Leo 2022 | Leo P, Spragg J, Podlogar T, Lawley JS, Mujika I. Power profiling and the power-duration relationship in cycling: a narrative review. *Eur J Appl Physiol* 122(2):301–316 | 10.1007/s00421-021-04833-y | V |
| Lolli 2019 | Lolli L, Batterham AM, Hawkins R et al. Mathematical coupling causes spurious correlation within the conventional acute-to-chronic workload ratio calculations. *Br J Sports Med* 53(15):921–922 | 10.1136/bjsports-2017-098110 | V |
| Lucia 2003 | Lucia A, Hoyos J, Santalla A, Earnest C, Chicharro JL. Tour de France versus Vuelta a España: which is harder? *Med Sci Sports Exerc* 35(5):872–878 | 10.1249/01.MSS.0000064999.82036.B4 | V (existence), M (DOI) |
| MacInnis 2019 | MacInnis MJ, Thomas ACQ, Phillips SM. The reliability of 4-minute and 20-minute time trials and their relationships to functional threshold power in trained cyclists. *IJSPP* 14(1):38–45 | 10.1123/ijspp.2018-0100 | V |
| Manzi 2009 | Manzi V et al. Dose-response relationship of autonomic nervous system responses to individualized training impulse in marathon runners. *Am J Physiol Heart Circ Physiol* 296:H1733–H1740 | 10.1152/ajpheart.00054.2009 | M |
| Martin 1998 | Martin JC, Milliken DL, Cobb JE, McFadden KL, Coggan AR. Validation of a mathematical model for road cycling power. *J Appl Biomech* 14(3):276–291 | 10.1123/jab.14.3.276 | V (existence), M (DOI) |
| Mattioni Maturana 2018 | Mattioni Maturana F et al. Critical power: how different protocols and models affect its determination. *J Sci Med Sport* 21(7):742–747 | 10.1016/j.jsams.2017.11.015 | V |
| Maunder 2021 | Maunder E, Seiler S, Mildenhall MJ, Kilding AE, Plews DJ. The importance of "durability" in the physiological profiling of endurance athletes. *Sports Med* 51:1619–1628 | 10.1007/s40279-021-01459-0 | V |
| Monod 1965 | Monod H, Scherrer J. The work capacity of a synergic muscular group. *Ergonomics* 8(3):329–338 | 10.1080/00140136508930810 | V |
| Moritani 1981 | Moritani T, Nagata A, deVries HA, Muro M. Critical power as a measure of physical work capacity and anaerobic threshold. *Ergonomics* 24(5):339–350 | 10.1080/00140138108924856 | V (metadata), M (DOI) |
| Morton 1990 | Morton RH, Fitz-Clarke JR, Banister EW. Modeling human performance in running. *J Appl Physiol* 69(3):1171–1177 | 10.1152/jappl.1990.69.3.1171 | V (existence), M (DOI) |
| Morton 1996 | Morton RH. A 3-parameter critical power model. *Ergonomics* 39(4):611–619 | 10.1080/00140139608964484 | V (metadata), M (DOI) |
| Muniz-Pumares 2019 | Muniz-Pumares D et al. Methodological approaches and related challenges associated with the determination of critical power and curvature constant. *J Strength Cond Res* 33(2):584–596 | 10.1519/JSC.0000000000002977 | V |
| Muniz-Pumares 2023/24 | Muniz D, Maunder E, Brazier J, Hunter B. All models are wrong, but the critical power model is useful. *Eur J Appl Physiol* (letter) | 10.1007/s00421-023-05359-1 | V |
| Pinot 2011 | Pinot J, Grappe F. The record power profile to assess performance in elite cyclists. *Int J Sports Med* 32(11):839–844 | 10.1055/s-0031-1279773 | V (metadata), M (DOI) |
| Plews 2013 | Plews DJ, Laursen PB, Stanley J, Kilding AE, Buchheit M. Training adaptation and heart rate variability in elite endurance athletes. *Sports Med* 43(9):773–781 | 10.1007/s40279-013-0071-8 | M |
| Poole 2016 | R01 in project bibliography | 10.1249/MSS.0000000000000939 | P |
| Puchowicz 2020 | Puchowicz MJ, Baker J, Clarke DC. Development and field validation of an omni-domain power-duration model. *J Sports Sci* 38(7):801–813 | 10.1080/02640414.2020.1735609 | V (metadata), M (DOI) |
| Quod 2010 | Quod MJ, Martin DT, Martin JC, Laursen PB. The power profile predicts road cycling MMP. *Int J Sports Med* 31(6):397–401 | not confirmed | V (metadata) |
| Sanders 2017 | Sanders D, Abt G, Hesselink MKC, Myers T, Akubat I. Methods of monitoring training load and their relationships to changes in fitness and performance in competitive road cyclists. *IJSPP* 12(5):668–675 | 10.1123/ijspp.2016-0454 | V |
| Seiler 2010 | R04 in project bibliography | 10.1123/ijspp.5.3.276 | P |
| Skiba 2012 | Skiba PF, Chidnok W, Vanhatalo A, Jones AM. Modeling the expenditure and reconstitution of work capacity above critical power. *Med Sci Sports Exerc* 44(8):1526–1532 | 10.1249/MSS.0b013e3182517a80 | V (existence), M (DOI) |
| Skiba 2015 | Skiba PF, Fulford J, Clarke DC, Vanhatalo A, Jones AM. Intramuscular determinants of the ability to recover work capacity above critical power. *Eur J Appl Physiol* 115(4):703–713 | 10.1007/s00421-014-3050-3 | M |
| Skiba 2021 | Skiba PF, Clarke DC. The W′ balance model: mathematical and methodological considerations. *IJSPP* 16(11):1561–1572 | 10.1123/ijspp.2021-0205 | V (existence), M (DOI) |
| Tanaka 2001 | Tanaka H, Monahan KD, Seals DR. Age-predicted maximal heart rate revisited. *J Am Coll Cardiol* 37(1):153–156 | 10.1016/S0735-1097(00)01054-8 | M |
| Task Force 1996 | Task Force of the ESC and NASPE. Heart rate variability: standards of measurement, physiological interpretation and clinical use. *Circulation* 93(5):1043–1065 | 10.1161/01.CIR.93.5.1043 | M |
| Treff 2019 | Treff G et al. The polarization-index: a simple calculation to distinguish polarized from non-polarized training intensity distributions. *Front Physiol* 10:707 | 10.3389/fphys.2019.00707 | V (existence), M (DOI) |
| Valenzuela 2018 | Valenzuela PL, Morales JS, Foster C, Lucia A, de la Villa P. Is the functional threshold power a valid surrogate of the lactate threshold? *IJSPP* 13(10):1293–1298 | 10.1123/ijspp.2018-0008 | V |
| Vanhatalo 2007 | Vanhatalo A, Doust JH, Burnley M. Determination of critical power using a 3-min all-out cycling test. *Med Sci Sports Exerc* 39(3):548–555 | 10.1249/mss.0b013e31802dd3e6 | V (existence), M (DOI) |
| Wong 2023 | Wong S, Burnley M, Mauger AR, Sun F, Hopker J. Functional threshold power and the (manufactured) critical power controversy. *J Sports Sci* 41(17):1643–1644 | 10.1080/02640414.2023.2288757 | V |
| Wright 2015 | Wright J, Jobson S, Bruce-Low S, Jessop D. The reliability and validity of the 3-minute critical power test in linear and isokinetic mode. *J Sci Cycling* 4(2) | 10.28985/jsc.v4i2.206 | V |
| TrainingPeaks | Coggan A. Normalized Power, Intensity Factor and Training Stress Score. trainingpeaks.com/learn/articles/normalized-power-intensity-factor-training-stress/ | web | V |
