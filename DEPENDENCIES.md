# Dependency register

Every dependency is recorded here, with its licence, before it is added (architecture section 7). Versions are pinned in `uv.lock`. Licences were read from installed package metadata on 2026-10-17.

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

Planned, not yet added: FastAPI and Pydantic in WP8.

## Development only (not distributed)

| Package | Version | Licence | Purpose |
|---|---|---|---|
| pytest | 9.1.1 | MIT | Test runner |
| hypothesis | 6.170.1 | MPL-2.0 | Property tests against the oracle |
| sortedcontainers | 2.4.0 | Apache-2.0 | Transitive, hypothesis |
| iniconfig, pluggy | 2.3.1, 1.7.0 | MIT | Transitive, pytest |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | Transitive, pytest |
| Pygments | 2.21.0 | BSD-2-Clause | Transitive, pytest |

MPL-2.0 is file level copyleft and applies only to hypothesis's own files, which are not copied into or distributed with this project.

## Excluded

| Package | Reason |
|---|---|
| Garmin FIT SDK (`garmin-fit-sdk`) | Proprietary FIT SDK licence; decision D8 |
| Any GPL source (for example GoldenCheetah) | Incompatible with MIT distribution |
