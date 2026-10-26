"""Migration 0004 on a library that holds GPS in its stored raw fields (as WP4 to WP8 stored them).

It must remove position keys from `samples.original_field_json` only: the vault
bytes (with GPS), every other column of every table, and every metric run stay
exactly as they were (spec 8.2, P7, P12). Synthetic data only.
"""
import json

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from backend.library import Library
from backend.storage.db import MIGRATIONS_DIR
from ownership_helpers import LAT, build, dump, new_library


def alembic(lib: Library) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{lib.paths['db']}")
    return cfg


def test_0004_strips_position_from_stored_fields_and_changes_nothing_else(tmp_path):
    lib = new_library(tmp_path / "data")
    ids = build(lib)
    with lib.engine.begin() as c:   # put back what the WP4 importer stored for this file
        rows = c.execute(text("SELECT sample_index, original_field_json FROM samples WHERE activity_id = :a"),
                         {"a": ids["gps"]}).all()
        for idx, doc in rows:
            f = json.loads(doc)
            f.update(position_lat=LAT + idx, position_long=-idx)
            c.execute(text("UPDATE samples SET original_field_json = :d WHERE activity_id = :a AND sample_index = :i"),
                      {"d": json.dumps(f, sort_keys=True), "a": ids["gps"], "i": idx})
    vault_before = {d: lib.vault.path_for(d).read_bytes() for d in lib.vault.objects()}
    before = dump(lib)
    lib.engine.dispose()
    command.downgrade(alembic(lib), "0003")
    command.upgrade(alembic(lib), "head")
    lib = Library(tmp_path / "data")
    after = dump(lib)
    gps = [r for r in after["samples"] if r["activity_id"] == ids["gps"]]
    assert len(gps) == len(rows) and all("position" not in r["original_field_json"] for r in gps)
    assert all(str(LAT) not in r["original_field_json"] for r in after["samples"])
    # The original bytes, GPS included, are untouched.
    assert {d: lib.vault.path_for(d).read_bytes() for d in lib.vault.objects()} == vault_before
    assert any(LAT.to_bytes(4, "little", signed=True) in b for b in vault_before.values())
    # Every other table, metric runs and provenance included, and every other sample column are unchanged.
    for t in after:
        if t != "samples":
            assert after[t] == before[t], t
    strip = lambda rs: [{k: v for k, v in r.items() if k != "original_field_json"} for r in rs]
    assert strip(after["samples"]) == strip(before["samples"])
    others = lambda rs: [r for r in rs if r["activity_id"] != ids["gps"]]
    assert others(after["samples"]) == others(before["samples"])
