"""Phase One database schema (architecture section 5).

CHECK constraints enforce spec P6 in storage: a value column is NULL exactly
when its validity is not `observed`, so NULL never means zero and zero never
means absent.
"""
from __future__ import annotations

from sqlalchemy import (Boolean, CheckConstraint, Column, Float, ForeignKey, Integer, MetaData,
                        String, Table, Text, UniqueConstraint)

metadata = MetaData()

VALIDITY = ("observed", "missing", "invalid")
VALUE_STATES = ("valid", "lower_bound", "insufficient_coverage", "no_power", "not_applicable",
                "unconfirmed_duplicates_included")
CHANNEL_COLUMNS = {  # channel -> (value column, validity column)
    "power": ("power_w", "power_validity"),
    "heart_rate": ("heart_rate_bpm", "hr_validity"),
    "cadence": ("cadence_rpm", "cadence_validity"),
    "speed": ("speed_mps", "speed_validity"),
    "distance": ("distance_m", "distance_validity"),
    "temperature": ("temp_c", "temp_validity"),
}


def _fk(target: str) -> ForeignKey:
    return ForeignKey(target, ondelete="CASCADE")


def _validity_checks() -> list[CheckConstraint]:
    allowed = ", ".join(f"'{v}'" for v in VALIDITY)
    checks = []
    for value_col, validity_col in CHANNEL_COLUMNS.values():
        checks.append(CheckConstraint(f"{validity_col} IN ({allowed})", name=f"ck_{validity_col}_enum"))
        checks.append(CheckConstraint(
            f"({value_col} IS NULL) = ({validity_col} <> 'observed')", name=f"ck_{value_col}_null_iff_not_observed"))
    return checks


source_files = Table(
    "source_files", metadata,
    Column("id", Integer, primary_key=True),
    Column("sha256", String(64), nullable=False, unique=True),
    Column("original_filename", Text),
    Column("byte_length", Integer, nullable=False),
    Column("media_format", String(16), nullable=False),
    Column("imported_at_utc", Float, nullable=False),
    Column("parser_version", String(32), nullable=False),
    Column("relative_storage_path", Text, nullable=False),
    Column("validation_status", String(16), nullable=False),
    Column("validation_details", Text),
)

activities = Table(
    "activities", metadata,
    Column("id", Integer, primary_key=True),
    Column("source_file_id", Integer, _fk("source_files.id"), nullable=False),
    Column("original_activity_id", Text),
    Column("source_platform", String(32)),
    Column("device_identity_json", Text),
    Column("sport", String(32)),
    Column("start_utc", Float),
    Column("end_utc", Float),
    Column("utc_offset_s", Float),
    Column("elapsed_s", Float),
    Column("timer_s", Float),
    Column("timer_source", String(32)),
    Column("device_timer_s", Float),
    Column("nominal_interval_s", Float),
    Column("recording_stats_json", Text),
    Column("recording_flags_json", Text),
)

activity_channels = Table(
    "activity_channels", metadata,
    Column("activity_id", Integer, _fk("activities.id"), primary_key=True),
    Column("channel", String(16), primary_key=True),
    Column("present", Boolean, nullable=False),
    Column("sensor_identity_json", Text),
    Column("origin", String(16), nullable=False),
    Column("observed_s", Float, nullable=False),
    Column("invalid_count", Integer, nullable=False),
    Column("suspect_zero_s", Float, nullable=False),
    CheckConstraint("origin IN ('measured', 'simulated')", name="ck_origin_enum"),
)

samples = Table(
    "samples", metadata,
    Column("activity_id", Integer, _fk("activities.id"), primary_key=True),
    Column("sample_index", Integer, primary_key=True),
    Column("timestamp_utc", Float, nullable=False),
    *[c for value_col, validity_col in CHANNEL_COLUMNS.values()
      for c in (Column(value_col, Float), Column(validity_col, String(8), nullable=False))],
    Column("suspect_zero", Boolean, nullable=False, default=False),
    Column("original_field_json", Text),
    *_validity_checks(),
)

timer_events = Table(
    "timer_events", metadata,
    Column("id", Integer, primary_key=True),
    Column("activity_id", Integer, _fk("activities.id"), nullable=False, index=True),
    Column("timestamp_utc", Float, nullable=False),
    Column("event_type", String(16), nullable=False),
    Column("source_field", Text),
)

timer_segments = Table(
    "timer_segments", metadata,
    Column("id", Integer, primary_key=True),
    Column("activity_id", Integer, _fk("activities.id"), nullable=False, index=True),
    Column("start_utc", Float, nullable=False),
    Column("end_utc", Float, nullable=False),
    Column("source", String(32), nullable=False),
)

duplicate_groups = Table(
    "duplicate_groups", metadata,
    Column("id", Integer, primary_key=True),
    Column("proposed_at_utc", Float, nullable=False),
    Column("rule_version", String(16), nullable=False),
    Column("overlap_json", Text),
    Column("status", String(16), nullable=False),
    Column("decided_at_utc", Float),
    CheckConstraint("status IN ('proposed', 'confirmed', 'rejected')", name="ck_group_status"),
)

duplicate_group_members = Table(
    "duplicate_group_members", metadata,
    Column("group_id", Integer, _fk("duplicate_groups.id"), primary_key=True),
    Column("activity_id", Integer, _fk("activities.id"), primary_key=True),
)

rides = Table(
    "rides", metadata,
    Column("id", Integer, primary_key=True),
    Column("kind", String(8), nullable=False),
    Column("activity_id", Integer, _fk("activities.id"), unique=True),
    Column("group_id", Integer, _fk("duplicate_groups.id"), unique=True),
    Column("needs_review", Boolean, nullable=False, default=False),
    CheckConstraint("(kind = 'single' AND activity_id IS NOT NULL AND group_id IS NULL) OR "
                    "(kind = 'group' AND group_id IS NOT NULL AND activity_id IS NULL)", name="ck_ride_kind"),
)

ride_channel_sources = Table(
    "ride_channel_sources", metadata,
    Column("ride_id", Integer, _fk("rides.id"), primary_key=True),
    Column("channel", String(16), primary_key=True),
    Column("activity_id", Integer, ForeignKey("activities.id", ondelete="SET NULL")),
    Column("selected_at_utc", Float, nullable=False),
    Column("selection_revision", Integer, nullable=False),
)

channel_preferences = Table(
    "channel_preferences", metadata,
    Column("channel", String(16), primary_key=True),
    Column("rank", Integer, primary_key=True),
    Column("rule_json", Text, nullable=False),
)

metric_definitions = Table(
    "metric_definitions", metadata,
    Column("metric_id", String(8), primary_key=True),
    Column("version", String(16), primary_key=True),
    Column("classification", String(16), nullable=False),
    Column("units", String(16), nullable=False),
    Column("formula", Text, nullable=False),
    Column("evidence_status", String(32), nullable=False),
    Column("documentation_path", Text, nullable=False),
    Column("source_ref_json", Text),
)

metric_runs = Table(
    "metric_runs", metadata,
    Column("id", Integer, primary_key=True),
    Column("metric_id", String(8), nullable=False),
    Column("metric_version", String(16), nullable=False),
    Column("scope_type", String(16), nullable=False),
    Column("scope_id", Integer, nullable=False),
    Column("parameter_json", Text, nullable=False),
    Column("input_revision", String(64), nullable=False),
    Column("calculated_at_utc", Float, nullable=False),
    Column("quality_json", Text),
    Column("computation_version", String(32), nullable=False),
    CheckConstraint("scope_type IN ('activity', 'ride', 'aggregate')", name="ck_scope_type"),
    UniqueConstraint("metric_id", "metric_version", "scope_type", "scope_id", "parameter_json",
                     "input_revision", "computation_version", name="uq_run_identity"),
)

metric_values = Table(
    "metric_values", metadata,
    Column("id", Integer, primary_key=True),
    Column("run_id", Integer, _fk("metric_runs.id"), nullable=False, index=True),
    Column("numeric_value", Float),
    Column("state", String(40), nullable=False),
    Column("units", String(16), nullable=False),
    Column("uncertainty_json", Text),
    CheckConstraint("state IN (" + ", ".join(f"'{s}'" for s in VALUE_STATES) + ")", name="ck_value_state"),
    CheckConstraint("(numeric_value IS NULL) = (state NOT IN ('valid', 'lower_bound', "
                    "'unconfirmed_duplicates_included'))", name="ck_value_null_iff_unavailable"),
)
