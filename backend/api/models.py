"""Response models (design 06, B7). They define the OpenAPI schema from which the
frontend's TypeScript types are generated, so the two cannot drift silently.

Nested detail that the register or the recording defines (parameters,
recording statistics, evidence) stays a free form mapping.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict

Json = dict[str, Any]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MetricValue(Model):
    metric_id: str
    version: str
    display_name: Optional[str]
    classification: Optional[str]
    units: str
    value: Optional[float]
    state: str
    coverage: Optional[float]
    parameters: Json
    details: Json
    input_revision: str
    computation_version: str
    calculated_at_utc: float
    source_sha256: list[str]
    source_activity_ids: list[int]
    uncertainty: Any
    register_url: str
    catalogue_url: str


class ImportOutcome(Model):
    filename: str
    status: Literal["imported", "duplicate_bytes", "failed"]
    sha256: Optional[str] = None
    source_file_id: Optional[int] = None
    activity_id: Optional[int] = None
    group_id: Optional[int] = None
    error_code: Optional[str] = None
    message: Optional[str] = None


class ImportResponse(Model):
    outcomes: list[ImportOutcome]


class ImportLogRow(Model):
    source_file_id: int
    sha256: str
    original_filename: Optional[str]
    media_format: str
    byte_length: int
    imported_at_utc: float
    validation_status: str
    error: Optional[Json]
    activity_id: Optional[int]


class ImportLogPage(Model):
    total: int
    items: list[ImportLogRow]


class ChannelPresence(Model):
    present: bool
    origin: Literal["measured", "simulated"]


class GroupRef(Model):
    id: int
    status: Literal["proposed", "confirmed", "rejected"]
    membership: Literal["member", "pending", "excluded"]


class ActivityRow(Model):
    id: int
    start_utc: Optional[float]
    end_utc: Optional[float]
    utc_offset_s: Optional[float]
    timer_s: Optional[float]
    elapsed_s: Optional[float]
    timer_source: Optional[str]
    source_platform: Optional[str]
    media_format: str
    original_filename: Optional[str]
    sha256: str
    channels: dict[str, ChannelPresence]
    flags: list[str]
    ride_id: Optional[int]
    group: Optional[GroupRef]


class ActivityPage(Model):
    total: int
    items: list[ActivityRow]


class ChannelInfo(Model):
    channel: str
    present: bool
    origin: str
    observed_s: float
    invalid_count: int
    suspect_zero_s: float
    sensor_identity: Any


class ActivityDetail(ActivityRow):
    device_timer_s: Optional[float]
    nominal_interval_s: Optional[float]
    original_activity_id: Optional[str]
    parser_version: str
    device_identity: Json
    recording_stats: Json
    channel_info: list[ChannelInfo]
    timer_segments: list[list[float]]
    metrics: list[MetricValue]


class ChannelSample(Model):
    value: Optional[float]
    validity: Literal["observed", "missing", "invalid"]


class Sample(Model):
    sample_index: int
    timestamp_utc: float
    suspect_zero: bool
    channels: dict[str, ChannelSample]


class SamplePage(Model):
    total: int
    items: list[Sample]


class SeriesRun(Model):
    t: list[float]
    v: list[float]


class SeriesBreak(Model):
    start: float
    end: float
    reason: Literal["missing", "invalid", "gap", "paused"]


class Series(Model):
    kind: Literal["display_envelope"]
    channel: str
    t_start: Optional[float]
    t_end: Optional[float]
    simulated: bool
    points_requested: int
    points_returned: int
    bucket_width_s: Optional[float]
    runs: list[SeriesRun]
    breaks: list[SeriesBreak]
    suspect_zero: list[list[float]]
    timer_segments: list[list[float]]


class GroupMember(Model):
    group_id: int
    activity_id: int
    membership: str
    added_at_utc: Optional[float]


class GroupEvent(Model):
    id: int
    group_id: int
    action: str
    activity_id: Optional[int]
    at_utc: float
    actor: str
    detail: Optional[Json]


class Prefill(Model):
    activity_id: Optional[int]
    basis: str
    rule: Optional[Json] = None


class DuplicateGroup(Model):
    id: int
    status: str
    rule_version: str
    proposed_at_utc: float
    decided_at_utc: Optional[float]
    evidence: Json
    members: list[GroupMember]
    ride_id: Optional[int]
    selection_prefill: dict[str, Prefill]
    events: list[GroupEvent]


class SelectionBody(Model):
    selection: dict[str, Optional[int]]
    exclude_activity_ids: list[int] = []


class RideId(Model):
    ride_id: int


class StatusOut(Model):
    status: str


class RevisionOut(Model):
    selection_revision: int


class SelectionHistoryRow(Model):
    id: int
    ride_id: int
    selection_revision: int
    channel: str
    activity_id: Optional[int]
    selected_at_utc: float
    selected_by: str
    source_deleted: bool


class Ride(Model):
    id: int
    kind: str
    activity_id: Optional[int]
    group_id: Optional[int]
    needs_review: bool
    active: bool
    selection_revision: int
    members: list[int]
    sources: dict[str, Optional[int]]
    selection_history: list[SelectionHistoryRow]
    metrics: list[MetricValue]


class BestPower(Model):
    value: float
    ride_id: int
    activity_ids: Optional[list[int]]
    source_sha256: Optional[list[str]]
    window_start_s: Optional[float]


class Overcount(Model):
    unconfirmed_group_count: int
    pending_recording_count: int
    ride_count: int
    duration_s: float
    work_kj: float
    activity_ids: list[int]


class Totals(Model):
    ride_count: int
    duration_s: float
    work_kj: float
    work_state: str
    rides_by_work_state: dict[str, int]
    best_mmp_w: dict[str, Optional[BestPower]]
    state: str
    potential_overcount: Overcount


class RangeTotals(Totals):
    range_utc: list[float]


class WeekTotals(Totals):
    week: str
    start_utc: float
    end_utc: float


class Settings(Model):
    display_time_zone: Optional[str] = None   # None: use the Mac's own zone
    week_start: Literal["monday"] = "monday"   # UI-D2


class System(Model):
    data_root: str
    database_bytes: int
    vault_bytes: int
    vault_objects: int
    app_version: str
    computation_version: str
    registry: list[Json]
    host: str


class ScienceRow(Model):
    metric_id: str
    version: str
    display_name: str
    classification: str
    units: str
    complete: bool
    register_url: str


# ---------------------------------------------------------------- WP9: export, restore, deletion

class ExportEntry(Model):
    name: str
    kind: Optional[str]
    bytes: int
    created_at_utc: Optional[float]
    recordings: int
    path: str
    readable: bool


class GroupEffect(Model):
    group_id: int
    status: str
    effect: str
    ride_id: Optional[int]
    fields_unselected: list[str]
    remaining_members: list[int]


class DeletionReport(Model):
    source_file_id: int
    activity_id: Optional[int]
    original_filename: Optional[str]
    groups: list[GroupEffect]
    rides_needing_review: list[int]
    exports_removed: list[str]
    vault_object_removed: bool
    checkpoint: list[int]
    committed: bool


class DataEntry(Model):
    path: str
    bytes: int


class DeleteAllPreview(Model):
    data_root: str
    counts: dict[str, int]
    entries: list[DataEntry]
    exports: list[str]
    kept_not_ours: list[str]
    token: str
    cannot_delete: list[str]


class DeleteAllBody(Model):
    token: str


class DeleteAllResult(Model):
    removed: list[DataEntry]
    counts: dict[str, int]
    kept_not_ours: list[str]


class RestoreReport(Model):
    restored_rows: dict[str, int]
    vault_objects: int
    recompute_check: dict[str, Any]
    archive_created_at_utc: float
    app_version: str
    checkpoint: list[int]
