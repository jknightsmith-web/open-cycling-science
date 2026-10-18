"""WP2 storage benchmark (not part of the test suite). Usage: python tests/bench_storage.py N_SAMPLES DB_PATH"""
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.storage.db import engine_for, upgrade  # noqa: E402

n, path = int(sys.argv[1]), Path(sys.argv[2])
upgrade(path)
eng = engine_for(path)
raw = eng.raw_connection()
cur = raw.cursor()
cur.execute("INSERT INTO source_files (id, sha256, byte_length, media_format, imported_at_utc, parser_version, "
            "relative_storage_path, validation_status) VALUES (1, 'x', 1, 'fit', 0, 'b', 'p', 'ok')")
per_activity = 3600 * 2
rng = random.Random(1)
t0 = time.perf_counter()
for a in range(n // per_activity):
    cur.execute("INSERT INTO activities (id, source_file_id) VALUES (?, 1)", (a + 1,))
    rows = [(a + 1, i, 1.76e9 + i, float(rng.randint(0, 600)), "observed", float(rng.randint(90, 180)), "observed",
             float(rng.randint(0, 120)), "observed", None, "missing", None, "missing", None, "missing", 0, None)
            for i in range(per_activity)]
    cur.executemany("INSERT INTO samples (activity_id, sample_index, timestamp_utc, power_w, power_validity, "
                    "heart_rate_bpm, hr_validity, cadence_rpm, cadence_validity, speed_mps, speed_validity, distance_m, "
                    "distance_validity, temp_c, temp_validity, suspect_zero, original_field_json) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    raw.commit()
elapsed = time.perf_counter() - t0
cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")
size = path.stat().st_size
t1 = time.perf_counter()
cur.execute("SELECT power_w, power_validity FROM samples WHERE activity_id = ? ORDER BY sample_index", (n // per_activity // 2,))
read_rows = len(cur.fetchall())
read_s = time.perf_counter() - t1
rows = (n // per_activity) * per_activity
print(f"rows={rows} insert_s={elapsed:.1f} rows_per_s={rows / elapsed:.0f} db_bytes={size} "
      f"bytes_per_row={size / rows:.1f} read_one_activity_rows={read_rows} read_s={read_s:.4f}")
