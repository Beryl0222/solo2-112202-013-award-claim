"""百分率指标的单位换算与口径比较。"""
from __future__ import annotations

from typing import Any


def rate_change(baseline: float, current: float) -> dict[str, float | None]:
    """给定两个百分率（如 70、80），返回绝对百分点差和相对变化百分比。"""
    percentage_points = float(current) - float(baseline)
    relative_percent: float | None = None
    if baseline:
        relative_percent = percentage_points / float(baseline) * 100.0
    return {
        "percentage_points": percentage_points,
        "absolute_percentage_points": abs(percentage_points),
        "relative_percent": relative_percent,
        "absolute_relative_percent": abs(relative_percent) if relative_percent is not None else None,
    }


def describe_rate_change(baseline: float, current: float, lang: str = "zh") -> str:
    change = rate_change(baseline, current)
    pp = abs(change["percentage_points"])
    rel = change["relative_percent"]
    if lang == "en":
        direction = "rise" if change["percentage_points"] >= 0 else "fall"
        return f"{direction} of {pp:g} percentage points; relative change {rel:.2f}%" if rel is not None else f"{direction} of {pp:g} pp"
    direction = "提升" if change["percentage_points"] >= 0 else "下降"
    return f"{direction}{pp:g}个百分点；相对变化{abs(rel):.2f}%" if rel is not None else f"{direction}{pp:g}个百分点"


def claims_are_same_metric(claim_a: dict[str, Any], claim_b: dict[str, Any], tolerance: float = 0.15) -> bool:
    """判断两个数量说法是否可视为同一口径；pp 与 relative percent 不自动等同。"""
    if claim_a.get("metric") != claim_b.get("metric"):
        return False
    if claim_a.get("delta_unit") != claim_b.get("delta_unit"):
        return False
    if claim_a.get("delta") is not None and claim_b.get("delta") is not None:
        return abs(float(claim_a["delta"]) - float(claim_b["delta"])) <= tolerance
    return True
