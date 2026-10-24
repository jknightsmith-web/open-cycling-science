"""WP2: data root, vault (acceptance 5) and schema constraints that enforce P6."""
import os
import re
import sqlite3
import stat
from pathlib import Path

import pytest

from backend import config
from backend.storage.db import engine_for, upgrade
from backend.storage.vault import Vault, VaultIntegrityError, sha256_bytes

REPO = Path(__file__).resolve().parents[1]


def test_default_data_root_is_outside_source_tree(monkeypatch):
    monkeypatch.delenv(config.ENV_VAR, raising=False)
    root = config.data_root().resolve()
    assert REPO not in root.parents and root != REPO


def test_data_root_override(monkeypatch, tmp_path):
    monkeypatch.setenv(config.ENV_VAR, str(tmp_path))
    assert config.data_root() == tmp_path


def test_vault_preserves_bytes_and_hash(tmp_path):
    v = Vault(tmp_path)
    data = os.urandom(4096)
    digest, created = v.put(data)
    assert created and digest == sha256_bytes(data)
    p = v.path_for(digest)
    assert p.read_bytes() == data
    assert not (p.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    assert v.put(data) == (digest, False)   # identical bytes stored once


def test_vault_detects_tampering(tmp_path):
    v = Vault(tmp_path)
    digest, _ = v.put(b"original")
    p = v.path_for(digest)
    os.chmod(p, stat.S_IWUSR | stat.S_IRUSR)
    p.write_bytes(b"altered")
    with pytest.raises(VaultIntegrityError):
        v.read(digest)


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "db" / "cycling.db"
    upgrade(path)
    return path


def test_migration_creates_schema_with_pragmas(db):
    eng = engine_for(db)
    with eng.connect() as c:
        tables = {r[0] for r in c.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"source_files", "activities", "samples", "rides", "ride_channel_sources",
                "duplicate_groups", "metric_runs", "metric_values"} <= tables
        assert c.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert c.exec_driver_sql("PRAGMA secure_delete").scalar() == 1
        assert c.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"


def _sample(con, **cols):
    base = {"activity_id": 1, "sample_index": cols.pop("i", 0), "timestamp_utc": 0.0,
            "power_validity": "missing", "hr_validity": "missing", "cadence_validity": "missing",
            "speed_validity": "missing", "distance_validity": "missing", "temp_validity": "missing",
            "suspect_zero": 0}
    base.update(cols)
    keys = ", ".join(base)
    con.execute(f"INSERT INTO samples ({keys}) VALUES ({', '.join('?' * len(base))})", list(base.values()))


def test_schema_keeps_zero_missing_and_invalid_distinct(db):
    con = sqlite3.connect(db)
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("INSERT INTO source_files (id, sha256, byte_length, media_format, imported_at_utc, parser_version,"
                " relative_storage_path, validation_status) VALUES (1, 'x', 1, 'fit', 0, 't', 'p', 'ok')")
    con.execute("INSERT INTO activities (id, source_file_id) VALUES (1, 1)")
    _sample(con, i=0, power_w=0.0, power_validity="observed")       # measured zero
    _sample(con, i=1)                                               # missing
    _sample(con, i=2, power_validity="invalid")                     # invalid
    for bad in ({"power_w": 0.0, "power_validity": "missing"},       # zero standing in for absence
                {"power_validity": "observed"},                      # observed without value
                {"power_w": 5.0, "power_validity": "invalid"}):
        with pytest.raises(sqlite3.IntegrityError):
            _sample(con, i=9, **bad)
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO metric_runs (id, metric_id, metric_version, scope_type, scope_id, parameter_json,"
                    " input_revision, calculated_at_utc, computation_version) VALUES (1,'M002','1.0','activity',1,'{}','r',0,'0.1')")
        con.execute("INSERT INTO metric_values (run_id, numeric_value, state, units) VALUES (1, 0.0, 'insufficient_coverage', 'W')")
    con.execute("DELETE FROM activities WHERE id = 1")
    assert con.execute("SELECT COUNT(*) FROM samples").fetchone()[0] == 0   # cascade (spec 8.4)


def test_migrations_match_the_schema_definition(db, tmp_path):
    """Upgrading through every migration yields the same tables, columns and CHECK constraints as schema.py."""
    from sqlalchemy import create_engine
    from backend.storage.schema import metadata
    fresh = tmp_path / "fresh.db"
    metadata.create_all(create_engine(f"sqlite:///{fresh}"))

    def shape(path):
        con = sqlite3.connect(path)
        out = {}
        for name, sql in con.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name != 'alembic_version'"):
            cols = sorted(r[1] for r in con.execute(f"PRAGMA table_info({name})"))
            checks = sorted(re.findall(r"CONSTRAINT (\w+) CHECK", sql))
            out[name] = (cols, checks)
        return out
    assert shape(db) == shape(fresh)
