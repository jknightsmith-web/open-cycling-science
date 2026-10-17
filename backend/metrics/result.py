from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

VALID = "valid"
LOWER_BOUND = "lower_bound"
INSUFFICIENT_COVERAGE = "insufficient_coverage"
NO_POWER = "no_power"
NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class MetricResult:
    metric_id: str
    version: str
    classification: str
    units: str
    value: Optional[float]
    state: str
    parameters: dict[str, Any] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
