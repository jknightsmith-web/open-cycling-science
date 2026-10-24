# Open Cycling Science: Phase One Interface Design (WP8)

| Field | Value |
|---|---|
| Document | 06 Interface design, WP8 |
| Version | 0.2 APPROVED by Jimmy 2026-10-24 with three required changes, incorporated here (sections 4.1, 4.5, 6 B3, 7, 8 UI-16 to UI-19). Decisions UI-D1 to UI-D5 approved |
| Date | 2026-10-24 |
| Governs | Roadmap WP8. Normative behaviour stays in `01_SPECIFICATION.md`; where this document seems to disagree, the specification wins |

## 1. Constraints carried from the specification

- Five screens only: Library, Overview, Activity, Science, Settings (spec 3.2 item 5).
- The browser computes no metric. Every number shown comes from the API with its `metric_id`, version, class, state and provenance. The frontend only formats: units, rounding, dates in the display time zone.
- Every displayed value carries its class (P3). Every metric opens its register entry (acceptance 12).
- Missing, invalid, observed zero and observed values look different everywhere (P6, acceptance 6). Unavailable metrics show their named state, never 0 or blank (spec 6.2).
- Works offline on macOS from 127.0.0.1. No CDN, web font, analytics, external link loading or network call beyond the local server (spec 8.5). DOI links are plain links the rider may choose to open.
- No training load, readiness, fitness or fatigue score, no FTP, no zones, no kcal (spec 3.3, register section 3).
- Export and deletion belong to WP9 and are not in this design (section 9).

## 2. Architecture

```
Browser (Safari or Chrome on the Mac)
  React 19 + TypeScript, built by Vite to static files
  ├── routes (react-router 7)           one route per screen, deep links
  ├── data layer (TanStack Query)       fetch + cache API responses, no business logic
  ├── api types (generated)             TypeScript types from the FastAPI OpenAPI schema
  ├── components                        MetricValue, ValidityCell, ClassBadge, StateLabel,
  │                                     RegisterDrawer, TimeSeriesChart, SelectionForm
  └── format/                           units, rounding, time zone display (pure, unit tested)
        │  HTTP, same origin
FastAPI on 127.0.0.1  (existing backend/api/app.py)
  ├── /api/...                          existing endpoints plus section 6 additions
  └── /                                 serves frontend/dist (static), index.html for routes
```

| Choice | Proposal | Licence | Reason | Alternative rejected |
|---|---|---|---|---|
| Framework | React 19, TypeScript, Vite 8 | MIT | Already agreed (architecture 2) | |
| Routing | react-router 7 | MIT | Deep links to an activity, ride or register entry | |
| Data | TanStack Query 5 | MIT | Caching and refetch after a decision, no state framework | Redux (more code, no gain) |
| Charts | uPlot 1.6 | MIT | Canvas, about 50 KB, draws 10k+ points per series quickly; null values break lines natively, which is how gaps must look | ECharts (Apache-2.0, about 1 MB); Recharts (SVG, slow above a few thousand points) |
| Styling | Plain CSS with design tokens, system font stack | | No framework or font download; light and dark from the OS | Tailwind (build step and class noise for five screens) |
| Types | openapi-typescript | MIT | Frontend types generated from the backend schema; CI fails if stale | Hand written types (drift) |
| Tests | Vitest + Testing Library; Playwright | MIT, Apache-2.0 | Component tests and end to end tests against the real backend | |

The charting library was left open at WP7 (architecture 2). uPlot is the recommendation; its licence goes into `DEPENDENCIES.md` before it is added. Every frontend package is pinned in `package-lock.json` and recorded in `DEPENDENCIES.md` with its licence.

Build: `make setup` runs `uv sync` and `npm ci` once (the only step that needs a network). `make run` builds the frontend if needed and serves everything from 127.0.0.1:8765. Built assets are not committed.

Large histories (acceptance 18): lists are paginated on the server; charts request a bounded number of points (section 6, B3); the raw sample table is paged. The browser never holds a full history of samples.

## 3. Navigation

```
┌──────────────────────────────────────────────────────────────────────┐
│ Open Cycling Science   Overview  Library  Science  Settings    ● 2   │  ● = proposed duplicate groups
└──────────────────────────────────────────────────────────────────────┘
```

| Route | Screen | Reached from |
|---|---|---|
| `/` | Overview | top bar |
| `/library` | Library: Activities tab | top bar |
| `/library/imports` | Library: Imports tab | top bar, after an import |
| `/library/duplicates` and `/library/duplicates/:groupId` | Library: Duplicates tab and confirmation | top bar badge, Overview overcount notice, Activity screen |
| `/activities/:id` | Activity (one recording) | Library, Overview, ride members |
| `/rides/:id` | Activity screen in ride mode (confirmed group) | Library, Overview, best power links |
| `/science` and `/science/:metricId` | Science | top bar, every metric's info button |
| `/settings` | Settings | top bar |

The Activity screen has two modes, recording and ride, so the five screen limit holds while a confirmed group can still be shown with its selected sources. Every metric value has an info button that opens the register drawer in place and links to its Science page.

## 4. Shared conventions

### 4.1 Metric value

Readability first (Jimmy, 2026-10-24): the cycling number is the most prominent element; the science sits one click away and nothing is removed.

```
 ┌───────────────────┐ ┌───────────────────┐ ┌─────────────────────────┐
 │ Mean power     (i)│ │ Work           (i)│ │ Mean power           (i)│
 │ 207 W             │ │ at least 432 kJ   │ │ Not available           │
 │ derived           │ │ derived · 81% data│ │ only 81% of time has    │
 └───────────────────┘ └───────────────────┘ │ power (needs 95%)       │
                                             └─────────────────────────┘
```

- Primary layer, always visible: name, value in large type, units, and a small muted class label (P3 requires every value to carry its class). Any state that changes what the number means stays inline: "at least" for `lower_bound`, the plain reason for an unavailable state, and "simulated" for simulated channels.
- Info control (i), one click or tap: class with its definition, state, coverage, parameters, equation, assumptions, limitations, sources, uncertainty ("not quantified"), source file and SHA256, input revision, computation version, and a link to the Science page.
- Unavailable states show the state's own words from `registry/states.yaml`, never a number.
- `lower_bound` is shown as "at least 432 kJ".
- `uncertainty: not quantified` appears in the drawer, not as a ± figure.
- M004 is labelled "Highest observed", never "maximal" or "capability".
- Class badges: OBSERVED, DERIVED, MODELLED, EXPERIMENTAL. Phase One has only DERIVED metrics and OBSERVED device values (`device_timer_s`, sensor readings). The component supports all four, and EXPERIMENTAL is hidden unless the rider turns it on (none exist in Phase One).

### 4.2 Data validity

| State | Chart | Table cell | Colour is never the only cue |
|---|---|---|---|
| observed value | line | value with units | |
| observed 0 | line at 0 | `0 W` | written zero |
| missing | break in the line plus a hatched band labelled "missing" | `missing` in muted italics | hatch pattern and word |
| invalid | break in the line plus tick marks on a strip under the chart | `invalid` with a tooltip giving the reason (sentinel, out of range, repeated timestamp) | ticks and word |
| suspect zero | line at 0 plus an amber band labelled "suspect zero" | `0 W` plus a "suspect zero" flag | band and label; value unchanged |
| timer paused | grey band labelled "paused" | | |
| simulated channel | series label "simulated (MyWhoosh)" | `simulated` tag | label |

### 4.3 Time and units

- Stored UTC; displayed in the display time zone chosen in Settings (default: the Mac's). Changing it changes labels and week boundaries only (acceptance 10).
- Power W, work kJ, heart rate bpm, cadence rpm, speed km/h (stored m/s), distance km (stored m), temperature °C. Conversions live in one tested formatter module.

### 4.5 Readability rules

- One primary number per card. Coverage, provenance and class detail sit in the info control.
- Body text 15 px, values 28 px or more, at least 4.5:1 contrast in light and dark modes.
- Plain labels on screen ("Highest observed power, 5 min"); register terms ("M004, DERIVED") in the info control.
- Tables use the same layering: values in cells, validity words where a value is absent, detail in a row's info control.
- Layout works down to an 800 px wide window. iPad layout is Phase Two.

### 4.4 Register drawer

Opened from any metric. Shows the entry from `/api/science/metrics/{id}`: display name, class, evidence label, version, equation, variables, outputs, assumptions, known limitations, data quality rules, validation status, uncertainty statement, sources with DOI and verification status (V, P, M). A link goes to the full Science page.

## 5. Screens

### 5.1 Library

```
Library      [ Activities ]  Imports  Duplicates (2)
┌──────────────────────────────────────────────────────────────────────┐
│  Drop FIT, TCX or ZIP files here, or  [Choose files]                │
└──────────────────────────────────────────────────────────────────────┘
 Date (Europe/London)  Source            Timer    Power  HR   Flags            Ride
 Sat 18 Oct 07:02      Garmin Fenix 8    1:58:10  ✓      ✓    irregular rec.   in group 4 (proposed)
 Sat 18 Oct 07:02      Wattbike Hub      1:57:44  ✓      —    assumed timer    in group 4 (proposed)
 Thu 16 Oct 18:30      MyWhoosh          0:59:58  ✓      —    simulated speed  single
 ...                                                    [ 1 2 3 … next ]
```

- **Activities:** paginated, sortable by date. Channel columns show present, absent or simulated. Flags come from the recording flags (spec 5.3 item 7) and are described, not judged. Each row opens the Activity screen.
- **Imports:** the import log, newest first. Each file shows imported, identical bytes (with a link to the existing activity), or failed with its error code and message. Zip members are listed one by one.
- **Duplicates:** proposed groups first, then pending recordings, confirmed and rejected groups.

Confirmation (`/library/duplicates/:groupId`):

```
Possible duplicate ride  ·  proposed 24 Oct 09:41  ·  rule 1.1
 Evidence                      Fenix 8 ↔ Hub      Fenix 8 ↔ MyWhoosh
 Timer overlap                 99.6%              98.9%
 Start offset                  +1 s               +3 s
 Timer durations               1:58:10 / 1:57:44  1:58:10 / 1:57:20
 Same recording identity       no                 no
 Same device                   no                 no

 Members                 [x] Fenix 8 (FIT)   [x] Wattbike Hub (TCX)   [x] MyWhoosh (FIT)

 Source for each field   Choice                   Suggested because
 Timer (duration)        (•) Fenix 8  ( ) Hub ( ) MyWhoosh    device timer events
 Power                   ( ) Fenix 8  (•) Hub ( ) MyWhoosh    your preference: TCX
 Heart rate              (•) Fenix 8  ( ) none                most observed seconds
 Cadence                 ( ) Fenix 8  ( ) Hub (•) MyWhoosh    most observed seconds
 Speed                   ( ) none     (•) MyWhoosh (simulated) only member that recorded it
 Distance                ...
 Temperature             none recorded by any member: missing

 Preview  ride duration from Fenix 8 timer · power metrics from the Hub file with its own coverage
 [ Confirm as one ride ]   [ Not the same ride ]
```

- Every field must be chosen. The form is prefilled from preferences or coverage, and each suggestion shows its reason. Nothing is applied until Confirm.
- Unticking a member excludes it; it stays a separate ride.
- Confirmed groups show Reopen and Change sources. Rejected groups show Reopen. Pending recordings show Accept (with the same form) and Exclude.
- The history list shows every decision with its time, from `events`.
- The preview text describes which file feeds which value. It is generated from the selection, not computed in the browser.

### 5.2 Overview

```
Overview                                  range  [ last 12 weeks ▾ ]
┌ Notice ──────────────────────────────────────────────────────────────┐
│ 2 possible duplicate rides are unconfirmed. Totals may be overcounted │
│ by up to 1:57:44 and 1,410 kJ.                 [ Review duplicates ] │
└──────────────────────────────────────────────────────────────────────┘
 Weekly duration (timer)     ▇ ▅ ▆ ▇ ▃ ...   bars; overcount part hatched
 Weekly work                 ▇ ▅ ▆ ▇ ▃ ...   bars; "at least" marker when a week includes lower bounds;
                                              weeks with rides lacking power say how many
 Highest observed power      5 s 812 W · 1 min 455 W · 5 min 341 W · 20 min 287 W · 60 min —
                             each links to its ride and source file; — means no window long enough
 Recent activities           last 10, as in Library
```

- Weekly totals come from a backend weekly aggregate (section 6, B4). Each bar opens the rides in that week.
- The notice appears only when the aggregate state is `unconfirmed_duplicates_included`.
- Coverage is shown per week: rides with power, rides at lower bound, rides without power.

### 5.3 Activity (recording mode and ride mode)

```
Sat 18 Oct 2025 07:02 (Europe/London)  ·  Garmin Fenix 8  ·  FIT  ·  in proposed group 4 →
 Timer 1:58:10 (device events)  Elapsed 2:04:31  Device timer 1:58:09 OBSERVED
 Metrics   Mean power 207 W DERIVED (i) · Work 1,469 kJ DERIVED (i) · Highest observed 5 s … 60 min (i)

 [ chart: power | heart rate | cadence | speed  — pause, missing, invalid and suspect zero bands ]
 ──────────────────────────────────────────────── time axis (display zone)

 Channels     present  sensor              origin     observed   invalid  suspect zero
 Power        yes      ANT+ power 4521     measured   99.2%      3        12 s
 Heart rate   yes      unknown (2 candidates) measured 97.0%     0        –
 Speed        yes      –                   simulated  100%       0        –

 Recording statistics   nominal interval 1 s · intervals ≤1 s 98% … >30 s 2 · gaps 6, 41 s · irregular: no
 Samples (paged table)  time · power · HR · cadence · speed · distance · temp, each with its validity
 Provenance   file ride.fit · SHA256 59ba…c07 · parser fit-1.0+fitdecode-0.11.0 · input revision 3f1a… · computed by ocs-0.1.0
```

Ride mode (`/rides/:id`) shows the same layout. Each metric names the file it came from, there is a sources table (field → member) with Change sources, and the members are listed with links to each recording. In Phase One the chart shows one recording at a time (a member picker), because aligning clocks between files is U8 and is not done.

### 5.4 Science

- `/science`: table of every register entry (ID, name, class, units, version, entry complete), then the class, validity and value state definitions.
- `/science/:metricId`: the full entry, as in the register drawer, plus source status codes and the documentation path.
- This replaces the server rendered catalogue for normal use. The server rendered pages stay at `/catalogue` as a fallback that needs no JavaScript.

### 5.5 Settings

- Data location (read only, from the backend), database and vault size.
- Display time zone (default: the system's) and week start (Monday, ISO).
- Channel source preferences: an ordered rule list per field, matching on source platform, file format or product, as the backend supports now.
- About: application version, computation version, registry versions, licences (from `DEPENDENCIES.md`), "runs offline on 127.0.0.1".
- Export and deletion arrive with WP9 and are not shown until they work.

## 6. Backend additions needed (no new metrics)

| ID | Endpoint or change | Why |
|---|---|---|
| B1 | `GET /api/imports` paginated import log from `source_files`, including failures | Library Imports tab |
| B2 | `GET /api/activities` pagination, sort, and per row channel presence, flags and group status | Library list, acceptance 18 |
| B3 | `GET /api/activities/{id}/series?channel=…&points=N` returns a display envelope, not a metric, built from the canonical timeline (spec 5.3 and 5.4). The channel is split into runs of contiguous observed intervals inside timer running segments. Each run is reduced separately to min, max and first value per bucket, and a bucket never spans the end of a run. Between runs the response carries an explicit break with its reason (missing, invalid, gap, paused) and extent. The frontend turns every break into a null point, and uPlot is configured with `spanGaps: false`, so no line can join observations across a break | Charts without loading every sample, with gaps preserved (Jimmy's change 2) |
| B4 | `GET /api/aggregates/weekly?tz=…&from=…&to=…` weekly buckets in the display time zone, each from the existing totals | Overview; the browser does no summing |
| B5 | `GET/PUT /api/settings` (display time zone, week start), new `app_settings` table, migration 0003 | Settings persist on the Mac, not in one browser |
| B6 | `GET /api/system` data root, sizes, versions | Settings |
| B7 | Pydantic response models on every endpoint, so OpenAPI types are exact | Generated TypeScript types |
| B8 | Serve `frontend/dist` at `/`; move the server rendered catalogue to `/catalogue` | Single local server |

## 7. Testing

| Level | Tool | Covers |
|---|---|---|
| Formatters | Vitest | Unit conversion, rounding, time zone display; zero never becomes blank, null never becomes 0 |
| Components | Vitest + Testing Library | MetricValue per state, ValidityCell per state, ClassBadge, register drawer, selection form rules (every field required, absent channels not offered) |
| API contract | pytest + generated types check | Every new endpoint; types regenerated in CI and compared |
| Gap preservation | pytest + hypothesis on B3; Vitest on the series to chart transform; Playwright pixel check | B3 property: for random series with gaps, invalid runs and pauses, no output run contains or bridges a non observed interval, and every break in the timeline appears in the response. Transform: a null sits between every pair of runs. Rendered chart: in the canvas columns that fall inside a known gap, no line pixels are drawn |
| End to end | Playwright against the real backend with synthetic Fenix, Hub and MyWhoosh style files, all non loopback requests aborted | Every acceptance item in section 8 |
| Performance | Playwright script `make perf` on a seeded synthetic history | UI-16 to UI-19 |
| Build | CI on Linux runs all of the above | Acceptance 19 |

## 8. Acceptance criteria for WP8

| ID | Criterion | Spec link |
|---|---|---|
| UI-01 | `make run` starts on macOS and serves the interface on 127.0.0.1 only; it loads and works with networking off | 9.1, 9.16, 8.5 |
| UI-02 | No request leaves 127.0.0.1 in any end to end test; the built bundle holds no remote URLs except DOI links | 8.5 |
| UI-03 | Importing files from the Library shows each outcome: imported, identical bytes with a link, or failed with the reason | 3.2 item 1, 9.3 |
| UI-04 | A synthetic two source ride shows as a proposed group with its evidence; before confirmation the Overview shows both rides and the overcount notice | 9.4 |
| UI-05 | Confirming with a source for each field gives one ride whose metrics name their source files; the Overview totals drop accordingly; Reopen and Not the same ride restore the earlier totals | 9.4, 9.4a |
| UI-06 | Power, heart rate and cadence can each come from a different member; the ride page shows the selected file for each value | 9.4a |
| UI-07 | Observed 0, missing, invalid and suspect zero are distinguishable in the chart and table without relying on colour; no missing or invalid value is shown as 0 | 9.6, P6 |
| UI-08 | Every displayed metric shows its class and opens its register entry, with definition, assumptions, limitations and sources | 9.12, P3 |
| UI-09 | Unavailable metrics show their named state, never 0 or blank; lower bounds read "at least" | 6.2, D1 |
| UI-10 | Changing the display time zone changes labels and week grouping only; every metric value stays identical | 9.10 |
| UI-11 | Each activity shows its recording statistics and flags, including for an irregular interval file, with no adequacy verdict | 9.17a |
| UI-12 | With a synthetic history of 1,000 activities, the Library, Overview and an Activity screen load without fetching all samples; load times and browser memory are measured and reported, with no target invented | 9.18 |
| UI-13 | No metric is computed in the frontend: a test fails if the frontend source contains a sum or mean over sample values outside the formatters | Jimmy, 2026-10-24 |
| UI-14 | No screen shows a training load, readiness, fitness, fatigue, FTP, zone or kcal value | 3.3 |
| UI-15 | Frontend tests run offline in CI and locally | 9.19 |

| UI-16 | Library opens with 1,000 activities in at most 2 s (provisional target), from navigation start to the first page of rows rendered | Jimmy, 2026-10-24 |
| UI-17 | Activity screen for a 3 h, 1 Hz recording opens in at most 2 s (provisional target), from navigation start to metrics and the power chart rendered | Jimmy, 2026-10-24 |
| UI-18 | Browser memory (JS heap used, from the Chrome DevTools protocol) is recorded for UI-16 and UI-17; chart responsiveness is recorded as the time to redraw after a zoom and after switching channel | Jimmy, 2026-10-24 |
| UI-19 | Charts never connect observations across a missing, invalid, gap or paused interval, proven by the gap preservation tests in section 7 | Jimmy, 2026-10-24 |

UI-13 is a guard, not proof. Code review backs it up.

Performance targets are provisional. Results are measured on macOS and reported as measured, including any miss. Results from the Linux build container are reported separately and labelled as such, because they do not stand in for the Mac.

## 9. Not in WP8

Export, archive round trip and deletion (WP9). Large history benchmark (WP10, though UI-12 records interim numbers). iPad or LAN viewing (Phase Two). Charts combining files from one ride (needs U8). Any metric outside M001 to M004.

## 10. Decisions for approval

| ID | Question | Recommendation |
|---|---|---|
| UI-D1 | Chart library | uPlot (MIT) |
| UI-D2 | Weekly grouping | Backend groups by ISO week (Monday start) in the display time zone |
| UI-D3 | Display units | km/h and km for speed and distance; SI everywhere else |
| UI-D4 | Ride view | Activity screen in ride mode, not a sixth screen |
| UI-D5 | Settings in WP8 | No export or deletion controls until WP9 delivers them |
