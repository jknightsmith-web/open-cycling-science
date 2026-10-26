# WP9 decisions for review

Prepared 2026-10-26 for Jimmy's review of WP9 (provisionally accepted 2026-10-26). Each decision is set against the text of the frozen specification v1.0 (`docs/spec/01_SPECIFICATION.md`, quoted verbatim) and, where relevant, the architecture (`03_TECHNICAL_ARCHITECTURE.md`). Nothing in the specification has been changed. WP10 has not started.

Classification used below:

- **Required**: the specification text requires this behaviour.
- **Interpretation**: the specification leaves a detail open and this fills it without contradicting any text.
- **Extension**: behaviour the specification does not mention, added to meet an acceptance criterion.
- **Needs your call**: a reasonable reading of the text could reject it.

## Summary

| # | Decision | Classification | Recommendation |
|---|---|---|---|
| 1 | Migration 0004 strips GPS from `samples.original_field_json` | Interpretation (does not breach P7, P12 or 8.2; see analysis) | Approve |
| 2 | Deleting a recording deletes app made exports in `<data root>/exports/` that contain it | Required by acceptance 15 for that folder only; never touches files outside the data root | Approve |
| 3 | JSON form of derived data is JSON Lines | Interpretation | Approve |
| 4 | A group below two members dissolves; its ride, runs and selection history go | Required in substance; history removal is interpretation | Approve |
| 5 | Ride runs that used the deleted file are deleted and recomputed | Required | Approve |
| 6 | A ride whose timer source is deleted has no values and is not counted until reviewed | Interpretation | Approve |
| 7 | Restore only into an empty install with the same schema revision, after a recompute check | Interpretation (stricter than required) | Approve; revisit when the schema changes |
| 8 | `DELETE /api/imports/{id}` for files that failed to parse | Extension | Approve |
| 9 | Delete everything removes the app's folders, keeps other files it did not create, and leaves an empty install | **Needs your call** | Approve, or ask for full removal of the root |
| 10 | No VACUUM on single deletion | Required (VACUUM is specified for full deletion only) | Approve |
| 11 | Recovery on open after an interrupted operation | Extension | Approve |
| 12 | Selection history keeps a "deletion" row with no activity id when a group survives | **Needs your call** (raised in this review, not in the WP9 report) | Approve, or ask for removal |

## 1. GPS stripping in migration 0004

**Specification text**

- P12: "Every original recording is preserved. Duplicate handling and source selection never delete, merge or alter a recording."
- P7: "Source files are immutable. Every calculated value is reproducible from recorded input hashes, metric version and parameters."
- 3.2 (Phase One functional scope) item 1: "Import FIT and TCX files and zip archives of them, preserving original bytes."
- 8.1: "Vault files are written once, set read only, verified by rehash on import and before export."
- 8.2 `[D5]`: "Phase One does not normalise GPS position. Derived exports contain no location." / "Original files in the vault and in original exports keep their GPS bytes unchanged (provenance requires byte identity). The export UI warns that originals may reveal home location." / "A GPS stripped copy for sharing is a Phase Two candidate, produced as a new file with its own hash, never replacing the original."
- 8.3: derived data contains "Activities, samples, …"; the full archive contains "Both plus `manifest.json`"; "Importing a full archive into an empty install MUST reproduce identical vault hashes, row counts and metric values."
- D5: "**Keep** GPS in original file exports, byte identical, with a warning | Byte identity is the provenance chain; stripping needs a FIT writer. Derived exports carry no location."
- Architecture 4 (samples): "keep `original_field_json`. No position columns in Phase One."

**What 0004 does (fact, `migrations/versions/0004_wp9_deletion_and_location.py`)**

It rewrites one column, `samples.original_field_json`, removing keys whose name matches position, lat, long, latitude or longitude. It does not open the vault. From WP9 on, the FIT importer drops the same keys before storing; the TCX importer never stored position (it copies only the five mapped channels).

**Assessment: no breach of the preservation requirement**

- The "original recording" in P12 and the "source file" in P7 are the vault object. 0004 never reads or writes the vault, the vault is read only, and acceptance 5 (vault SHA256 equals the original file's) is unaffected. Evidence: `tests/test_migration_0004.py` (new) loads a library whose stored fields hold GPS, as WP4 to WP8 stored them, downgrades to 0003, upgrades through 0004 and asserts the vault bytes are identical and still contain the latitude.
- `original_field_json` is a database copy of decoded fields, part of the samples table and therefore part of the derived data export (8.3). Despite its name, it is derived data, not the original.
- P7 reproducibility holds. Metric inputs are hashed as `input_revision`, the canonical timeline digest (`backend/canonical/digest.py`), which covers timer segments and channel readings and not `original_field_json`. The same test asserts every metric run, every provenance record and every other column of every table is unchanged by 0004.
- 8.3 forces a choice. The derived export must contain the samples table and no location (8.2). The full archive must contain the same derived data and restore it with identical row counts and values. If GPS stayed in `original_field_json`, either the derived export would carry location (breaching 8.2) or it would have to filter that column, and then the archive could not restore the database row for row. Stripping at storage is the only option I found that satisfies 8.2 and 8.3 together.
- Nothing is lost from the system. Every position remains in the vault original and in originals exports, and a Phase Two feature can re-parse it from there.

**Correction to the WP9 report**: I wrote that WP4 storing GPS "conflicted with spec 8.2". That was imprecise. Storage alone did not breach any text; the conflict arose only when the samples table became part of the derived export in WP9.

**Residual points**

- Altitude and GPS accuracy fields are kept. They are not position, but altitude can hint at a location. The specification does not require removing them.
- 0004 does not keep the stripped values elsewhere, so a downgrade does not restore them. They remain recoverable from the vault by re-import.
- No real install holds rider data yet (your recordings are still pending), so 0004 has only run on synthetic data.

**Alternative**: keep GPS in the database and filter it out of derived exports only. This would need the archive to carry an unfiltered copy, which contradicts "Derived exports contain no location" for the archive's data files, or the round trip to be relaxed for one column, which contradicts 8.3. Not recommended.

## 2. Deleting exports that contain a deleted recording

**Specification text**

- 8.1: "Layout: `vault/sha256/ab/cd/<sha256>`, `db/cycling.db`, `exports/`, `backups/`, `logs/`."
- 8.4: "\"Delete everything\" removes the data root including internal backups and exports, after one confirmation listing what will go." / "No tombstone keeps hashes, filenames or timestamps of deleted content." / "The app documents what it cannot delete: external copies, Time Machine and APFS snapshots, SSD physical blocks, vendor accounts."
- Acceptance 15: "Deletion marker scan of the data root (including WAL and SHM) finds neither the marker nor the hash."

**What the code deletes (fact, `backend/library/exports.py`, `containing` and `remove_containing`)**

Only files that meet all three conditions:

1. They are in `<data root>/exports/`, the folder 8.1 assigns to the app.
2. Their name matches the app's own pattern `ocs-(originals|derived|archive)-YYYYMMDDTHHMMSSZ.zip`.
3. Their manifest lists the deleted file's SHA256. If such a file cannot be read as a ZIP, it counts when its bytes contain the hash.

It never touches:

- a file the browser downloaded (the download goes wherever you save it, usually `~/Downloads`; the app keeps no record of downloads);
- a copy you moved or made elsewhere;
- any other file in `exports/` whose name does not match the pattern.

The deletion preview lists the exports that will go before you confirm, and you can cancel.

**Assessment**

- For app managed exports the deletion is required. An app export holding the file contains its hash in `manifest.json` and its filename under `originals/`, inside the data root, so keeping it would fail acceptance 15 and be a tombstone under 8.4.
- For files you saved elsewhere, the specification classes them as "external copies" that the app cannot delete and must document. That is what it does: Settings lists them under "What the app cannot delete".
- One edge case: a zip you copy into `exports/` under an app style name is treated as app managed. A file in `exports/` under any other name survives single deletions, but Delete everything removes the whole `exports/` folder, as 8.4 says.

**Alternatives**

- Refuse the deletion until you remove the exports yourself. This complies with the specification but adds a step.
- Keep the exports. This breaches acceptance 15.

I recommend the current behaviour.

## 3 to 12. Other decisions

| # | Specification text | Implementation | Assessment |
|---|---|---|---|
| 3 | 8.3: "One CSV per table (UTF-8, RFC 4180, units in column names, empty = missing, validity columns included, no rounding) plus JSON" | One JSON Lines file per table beside each CSV | "JSON" is not further defined. JSON Lines streams large sample tables and each line is valid JSON. A single JSON array per table would also comply |
| 4 | 8.4: "If the activity belongs to a duplicate group it is removed from the group. … a group left with one member dissolves into a single activity ride. No other member is altered." | The remaining recording's own data are untouched and it counts as its own ride again. The dissolved group's ride, ride runs, events and selection history are deleted | Dissolution is required. Deleting the group's history follows "No tombstone", because that history names the deleted activity |
| 5 | 8.4: "Deleting an activity removes its samples, events, runs and values; aggregates that used it are recomputed or marked stale." | Ride scope runs whose provenance includes the hash are deleted and recomputed from the remaining selection. The commit is refused if any run's provenance still contains the hash | Required |
| 6 | 8.4: "Any ride channel selection that pointed to it becomes unselected and the ride is flagged for the rider to review"; P6 | The field becomes unselected and the ride is flagged. Without a timer source the ride has no duration, so it shows no values and is not counted, rather than counting as zero | Picking a new timer automatically would contradict "becomes unselected" and D7. Counting zero would breach P6 |
| 7 | 8.3: "Importing a full archive into an empty install MUST reproduce identical vault hashes, row counts and metric values." | Restore works only into an empty install with the same schema revision. Every member hash, every original and the metric definitions are checked, and each recording is recomputed before anything is written | The specification defines only the empty install case; merging is not specified. Requiring the same schema revision means an archive from an older version will need a migration step when the schema next changes (not needed in Phase One) |
| 8 | 8.4 covers activities only | A file that failed to parse has a vault object and a filename but no activity, so it gets its own deletion endpoint | Without it such a file could never be deleted, which would fail acceptance 15 |
| 9 | 8.4: "\"Delete everything\" removes the data root including internal backups and exports" | Removes `vault`, `db`, `exports`, `backups` and `logs`, lists any other file in the root and keeps it, removes the root if it is then empty, and opens a fresh empty install (the folders are recreated) | **Needs your call.** The literal text says the data root is removed. I kept files the app did not create, because the root is configurable and could be pointed at a folder holding other files. The recreated install is empty, so the marker scan passes. If you want the literal reading, the change is to remove the root unconditionally and not reopen |
| 10 | 8.4: "SQLite residue is removed (`secure_delete`, WAL checkpoint truncate, `VACUUM` on full deletion)." | Single deletions use `secure_delete` and a WAL truncate. Delete everything removes the database file, so VACUUM is unnecessary | Required. The marker scan passes without VACUUM |
| 11 | Not specified | On open, the app removes orphan vault objects, half written files, `.partial-` exports and exports that hold a file no longer in the library, then truncates the WAL | Keeps acceptance 15 true after a crash between commit and file removal (`tests/test_interruptions.py`) |
| 12 | 8.4: "No tombstone keeps hashes, filenames or timestamps of deleted content." | When a group survives a deletion, its selection history rows keep their place with the activity id cleared and `source_deleted` set; a new selection revision is written, marked `selected_by = "deletion"` with the deletion time; and remaining duplicate decision events show the deleted member's id as "deleted" | **Needs your call.** No hash, filename or recording timestamp survives (the scan proves the first two). The rows do record that a source once existed and when it was deleted. I read that as a ride decision record, not a tombstone of content. The stricter option deletes those rows, at the cost of the ride's audit trail |

## Decisions needed

1. Approve 1 to 8, 10 and 11 as built, or name any to change.
2. Decision 9: keep files the app did not create (as built), or remove the whole data root.
3. Decision 12: keep the anonymised selection history rows (as built), or delete them.
