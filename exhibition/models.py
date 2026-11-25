"""编校流程使用的透明数据结构。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Claim:
    """从来件中抽出的一项数量主张。"""

    claim_id: str
    record_id: str
    lang: str
    quote: str
    claim_type: str = "measurement"  # measurement | validation | plan | qualitative
    metric: str | None = None
    subject: str | None = None
    scope: dict[str, Any] = field(default_factory=dict)
    baseline: float | None = None
    current: float | None = None
    delta: float | None = None
    delta_unit: str | None = None
    relative_pct: float | None = None
    direction: str | None = None
    modality: str = "unknown"  # observed | expected | unknown
    measured: bool | None = None
    comparator: str | None = None
    time_phrase: str | None = None
    trial: str | None = None
    explicit_refs: list[str] = field(default_factory=list)
    anaphora: list[dict[str, str]] = field(default_factory=list)
    provisional: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Finding:
    code: str
    severity: str  # block | correction | warning | info
    message: str
    record_id: str | None = None
    exhibit_id: str | None = None
    source_ids: list[str] = field(default_factory=list)
    quote: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MaterialRequest:
    request_id: str
    exhibit_id: str
    theme: str | None
    needed_scope: str
    acceptable_evidence: str
    rejected_candidates: list[dict[str, str]] = field(default_factory=list)
    priority: str = "补充"
    formats: list[str] = field(default_factory=list)
    also_exhibit_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BoardEntry:
    entry_id: str
    theme_ids: list[str]
    fact_ids: list[str]
    source_ids: list[str]
    text: str
    width: int
    language: str
    statement_kind: str = "fact"
    supports_shared_themes: bool = False
    components: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BoardPlan:
    surface_id: str
    channel: str
    language: str
    limit: int
    used_cells: int
    entries: list[BoardEntry] = field(default_factory=list)
    notices: list[dict[str, Any]] = field(default_factory=list)
    omitted_themes: list[dict[str, Any]] = field(default_factory=list)
    feasible: bool = True

    @property
    def remaining_cells(self) -> int:
        return self.limit - self.used_cells

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["remaining_cells"] = self.remaining_cells
        return data
