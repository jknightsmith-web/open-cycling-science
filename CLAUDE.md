# Standing instructions

The authoritative specification is `docs/spec/` (v1.0, Phase One frozen). Read `docs/spec/README.md` first. Where any other file disagrees, `docs/spec/` wins.

* Implement only Phase One work packages (`docs/spec/04_DEVELOPMENT_ROADMAP.md`). Anything outside them needs Jimmy's approval through change control.
* Missing, invalid, measured zero and measured values stay distinct everywhere (spec P6, 5.2). Never interpolate or substitute zero.
* No device is authoritative for every channel (P11). Never delete, merge or alter an original recording (P12).
* Metric code is pure and must agree with `reference/metric_oracle.py`. A software test proves implementation, not scientific validity.
* No outbound network traffic. Bind to 127.0.0.1. Never commit rider files, `.db` files or credentials.
* Record every dependency with its licence in `DEPENDENCIES.md` before adding it. No GPL source. No Garmin FIT SDK (decision D8).
* Comparisons between power meters are agreement assessments, not accuracy claims, unless a calibrated reference is used (spec 6.3).
* After each task report what was run, what passed and what is unverified, against work packages and acceptance criteria.
