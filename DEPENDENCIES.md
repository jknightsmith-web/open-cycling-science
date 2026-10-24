# Dependency register

Every dependency is recorded here, with its licence, before it is added (architecture section 7). Versions are pinned in `uv.lock`. Licences were read from installed package metadata on 2026-10-17 (WP1 to WP3) and 2026-10-24 (WP6, WP7).

## Runtime

| Package | Version | Licence | Purpose | Added in |
|---|---|---|---|---|
| SQLAlchemy | 2.1.5 | MIT | Schema and SQLite access | WP2 |
| alembic | 1.20.0 | MIT | Database migrations | WP2 |
| Mako | 1.4.3 | MIT | Transitive, alembic templates | WP2 |
| MarkupSafe | 3.0.4 | BSD-3-Clause | Transitive, Mako | WP2 |
| typing_extensions | 4.16.0 | PSF-2.0 | Transitive, SQLAlchemy and alembic | WP2 |
| fitdecode | 0.11.0 | MIT | FIT decoding (decision D8). No runtime dependencies. Embedded FIT profile from Garmin SDK 21.171 | WP3 |
| defusedxml | 0.7.1 | PSF-2.0 (PSFL) | Safe TCX XML parsing (no entity expansion or external entities) | WP3 |
| FastAPI | 0.162.0 | MIT | Local API (architecture 2, 8) | WP6/7 |
| Pydantic, pydantic-core | 2.14.1, 2.50.1 | MIT | Transitive, FastAPI | WP6/7 |
| Starlette | 1.9.0 | BSD-3-Clause | Transitive, FastAPI | WP6/7 |
| anyio, idna | 4.15.1, 3.20 | MIT, BSD-3-Clause | Transitive, Starlette | WP6/7 |
| annotated-types, annotated-doc, typing-inspection | 0.8.0, 0.0.5, 0.4.4 | MIT | Transitive, FastAPI and Pydantic | WP6/7 |
| opentelemetry-api | 1.45.1 | Apache-2.0 | Transitive, FastAPI. API package only; with no SDK or exporter installed it records and sends nothing | WP6/7 |
| uvicorn | 0.54.0 | BSD-3-Clause | Local server, bound to 127.0.0.1 | WP6/7 |
| click, h11 | 8.5.0, 0.16.0 | BSD-3-Clause, MIT | Transitive, uvicorn | WP6/7 |
| PyYAML | 6.0.3 | MIT | Registry entries in `registry/` (architecture 3) | WP7 |

## Development only (not distributed)

| Package | Version | Licence | Purpose |
|---|---|---|---|
| pytest | 9.1.1 | MIT | Test runner |
| hypothesis | 6.170.1 | MPL-2.0 | Property tests against the oracle |
| sortedcontainers | 2.4.0 | Apache-2.0 | Transitive, hypothesis |
| iniconfig, pluggy | 2.3.1, 1.7.0 | MIT | Transitive, pytest |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | Transitive, pytest |
| Pygments | 2.21.0 | BSD-2-Clause | Transitive, pytest |
| httpx, httpcore | 0.28.1, 1.0.9 | BSD-3-Clause | FastAPI test client; requests go to the in process app, not the network |
| certifi | 2026.10.23 | MPL-2.0 | Transitive, httpx; not used, since tests make no TLS connections |

MPL-2.0 is file level copyleft and applies only to hypothesis's own files, which are not copied into or distributed with this project.

## Excluded

| Package | Reason |
|---|---|
| Garmin FIT SDK (`garmin-fit-sdk`) | Proprietary FIT SDK licence; decision D8 |
| Any GPL source (for example GoldenCheetah) | Incompatible with MIT distribution |
