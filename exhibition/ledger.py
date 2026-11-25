"""来源授权、撤回状态和主张匹配。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .extract import extract_record
from .io import load_pack
from .models import Claim

PUBLIC_CHANNELS = ("现场中文", "现场英文", "扫码内页")
ONLINE_CHANNELS = {"现场中文", "现场英文"}

AUDIENCE_DEFAULT_CHANNELS = {
    "仅审核": set(),
    "审核": set(),
    "扫码公开": {"扫码内页"},
    "现场公开": {"现场中文", "现场英文"},
}

SCALE_RANK = {"line": 1, "workshop": 2, "overall": 3, "plant": 4}


@dataclass
class SourcePolicy:
    source_id: str
    audience: str
    default_channels: set[str]
    granted_channels: set[str] = field(default_factory=set)
    denied_channels: set[str] = field(default_factory=set)
    status: str = "active"  # active | withdrawn | internal_only
    events: list[dict[str, str]] = field(default_factory=list)
    may_explain_withdrawal: bool = False

    def usable(self, channel: str, at: str | None = None) -> tuple[bool, str]:
        if at is not None:
            events = [event for event in self.events if event["at"] <= at]
            status = self._status_from_events(events)
            granted, denied = self._channels_from_events(events)
        else:
            status = self.status
            granted, denied = self.granted_channels, self.denied_channels

        allowed = (self.default_channels | granted) - denied
        if status == "withdrawn":
            return False, "来源已撤回，不能继续作为事实引用"
        if status == "internal_only":
            return False, "来源仅限编辑核查，未获外发授权"
        if channel in denied:
            return False, "该渠道被授权来函明确禁止"
        if channel not in allowed:
            return False, f"来件最高披露范围为{self.audience}，未授权{channel}"
        return True, "可用"

    @staticmethod
    def _status_from_events(events: list[dict[str, str]]) -> str:
        status = "active"
        for event in events:
            effect = event.get("effect")
            if effect == "withdraw":
                status = "withdrawn"
            elif effect == "internal":
                status = "internal_only"
            elif effect == "allow":
                status = "active"
        return status

    @staticmethod
    def _channels_from_events(events: list[dict[str, str]]) -> tuple[set[str], set[str]]:
        grants: set[str] = set()
        denials: set[str] = set()
        for event in events:
            if event.get("effect") == "allow":
                grants |= set(event.get("channels", []))
            elif event.get("effect") in {"withdraw", "internal"}:
                denials |= set(event.get("channels", PUBLIC_CHANNELS))
        return grants, denials


def parse_permission_note(note: str) -> dict[str, Any]:
    channels: set[str] = set()
    if re.search(r"展板", note):
        channels |= {"现场中文", "现场英文"}
    if re.search(r"扫码|内页|页", note):
        channels.add("扫码内页")
    if re.search(r"外发|公众", note) and not channels:
        channels |= set(PUBLIC_CHANNELS)

    if re.search(r"停止|撤回", note):
        # “停止展板和扫码”明确列出两类；若只说停止某渠道，上面的正则已捕获。
        if re.search(r"展板和扫码|展板.*扫码|扫码.*展板", note):
            channels |= set(PUBLIC_CHANNELS)
        return {"effect": "withdraw", "channels": sorted(channels or set(PUBLIC_CHANNELS))}
    if re.search(r"未获外发准许|只供编辑核查|仅审核|不得外发", note):
        return {"effect": "internal", "channels": sorted(set(PUBLIC_CHANNELS))}
    if re.search(r"可以用于|可用于|准许|授权|同意", note):
        if re.search(r"展板和扫码|公众展板和扫码", note):
            channels |= set(PUBLIC_CHANNELS)
        return {"effect": "allow", "channels": sorted(channels or set(PUBLIC_CHANNELS))}
    return {"effect": "note", "channels": sorted(channels)}


class EditorialLedger:
    def __init__(self, directory=None, tables: dict[str, list[dict[str, str]]] | None = None):
        self.tables = tables if tables is not None else load_pack(directory)
        self.sources = {row["id"]: row for row in self.tables["sources.tsv"]}
        self.exhibits = {row["id"]: row for row in self.tables["exhibits.tsv"]}
        self.surfaces = {row["id"]: row for row in self.tables["releases.tsv"]}
        self.print_logs = self.tables["print_log.tsv"]
        self.priorities = {row["id"]: row for row in self.tables["priorities.tsv"]}
        self.issuances = {row["board_code"]: row for row in self.tables["issuances.tsv"]}
        self.issuance_by_id = {row["id"]: row for row in self.tables["issuances.tsv"]}
        self.permissions = self.tables["permissions.tsv"]

        self.source_claims: dict[str, list[Claim]] = {
            sid: extract_record(row, "source") for sid, row in self.sources.items()
        }
        self.exhibit_claims: dict[str, list[Claim]] = {
            eid: extract_record(row, "exhibit") for eid, row in self.exhibits.items()
        }
        self._resolve_related_metrics()
        self.policies = self._build_policies()

    def _resolve_related_metrics(self) -> None:
        """复算件可能只写“仍为70%至80%”，通过 relates 找回指标名。"""
        for source_id, claims in self.source_claims.items():
            related_ids = [x for x in self.sources[source_id].get("relates", "").split("|") if x]
            related_metric = None
            for related_id in related_ids:
                for claim in self.source_claims.get(related_id, []):
                    if claim.metric and claim.metric != "same_named_metric":
                        related_metric = claim.metric
                        break
                if related_metric:
                    break
            if related_metric:
                for claim in claims:
                    if not claim.metric or claim.metric == "same_named_metric":
                        claim.metric = related_metric

        # “同期做了同名指标”这类来源自身不复述指标名；从同时引用它的展项上下文找回。
        for source_id, claims in self.source_claims.items():
            for claim in claims:
                if claim.metric and claim.metric != "same_named_metric":
                    continue
                contextual_metric = None
                for exhibit in self.exhibits.values():
                    if source_id not in [x for x in exhibit.get("refs", "").split("|") if x]:
                        continue
                    for ex_claim in self.exhibit_claims.get(exhibit["id"], []):
                        if ex_claim.metric and ex_claim.metric != "same_named_metric":
                            contextual_metric = ex_claim.metric
                            break
                    if contextual_metric:
                        break
                if contextual_metric:
                    claim.metric = contextual_metric

    def _build_policies(self) -> dict[str, SourcePolicy]:
        policies: dict[str, SourcePolicy] = {}
        for sid, row in self.sources.items():
            audience = row.get("audience", "")
            policy = SourcePolicy(
                source_id=sid,
                audience=audience,
                default_channels=set(AUDIENCE_DEFAULT_CHANNELS.get(audience, set())),
            )
            if audience == "仅审核":
                policy.status = "internal_only"
        for row in self.permissions:
            sid = row["source"]
            note = row["note"]
            parsed = parse_permission_note(note)
            event = {"at": row["at"], "note": note, **parsed}
            policy = policies.setdefault(
                sid,
                SourcePolicy(
                    source_id=sid,
                    audience=self.sources[sid].get("audience", ""),
                    default_channels=set(
                        AUDIENCE_DEFAULT_CHANNELS.get(self.sources[sid].get("audience", ""), set())
                    ),
                ),
            )
            policy.events.append(event)
            if parsed["effect"] == "withdraw":
                policy.status = "withdrawn"
                policy.denied_channels |= set(parsed["channels"])
                policy.may_explain_withdrawal = True
            elif parsed["effect"] == "internal":
                policy.status = "internal_only"
                policy.denied_channels |= set(parsed["channels"])
            elif parsed["effect"] == "allow":
                policy.status = "active"
                policy.granted_channels |= set(parsed["channels"])
                policy.denied_channels -= set(parsed["channels"])
        for policy in policies.values():
            policy.events.sort(key=lambda event: event["at"])
        return policies

    def policy_for(self, source_id: str) -> SourcePolicy:
        if source_id not in self.policies:
            row = self.sources[source_id]
            audience = row.get("audience", "")
            policy = SourcePolicy(source_id, audience, set(AUDIENCE_DEFAULT_CHANNELS.get(audience, set())))
            if audience == "仅审核":
                policy.status = "internal_only"
            self.policies[source_id] = policy
        return self.policies[source_id]

    def usable(self, source_id: str, channel: str, at: str | None = None) -> tuple[bool, str]:
        return self.policy_for(source_id).usable(channel, at)

    def refs(self, exhibit_id: str) -> list[str]:
        return [x for x in self.exhibits[exhibit_id]["refs"].split("|") if x]

    def claims_for_refs(self, source_ids: list[str]) -> list[tuple[str, Claim]]:
        return [(sid, claim) for sid in source_ids for claim in self.source_claims.get(sid, [])]


def scope_issues(exhibit_scope: dict[str, Any], evidence_scope: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    ex_line = exhibit_scope.get("line")
    ev_line = evidence_scope.get("line")
    if ex_line and ev_line and ex_line != ev_line:
        issues.append(f"对象线别不同：主张为{ex_line}，证据为{ev_line}")

    ex_shift = exhibit_scope.get("shift")
    ev_shift = evidence_scope.get("shift")
    if ex_shift and ev_shift and ex_shift != ex_shift:
        pass
    if ex_shift and ev_shift and ex_shift != ev_shift:
        issues.append(f"班次范围不同：主张为{ex_shift}，证据为{ev_shift}")
    elif ex_shift and not ev_shift and exhibit_scope.get("aggregation") != "day_night_total":
        # 没有班次边界的证据不能证明夜班/日班子组。
        if ex_shift in {"night", "day"}:
            issues.append(f"证据缺少{ex_shift}班次边界")

    ex_scale = exhibit_scope.get("scale")
    ev_scale = evidence_scope.get("scale")
    if ex_scale in SCALE_RANK:
        if ev_scale not in SCALE_RANK or SCALE_RANK[ev_scale] < SCALE_RANK[ex_scale]:
            issues.append(f"对象范围过宽：主张为{ex_scale}，证据仅为{ev_scale or '未注明'}")

    if exhibit_scope.get("aggregation") == "day_night_total":
        if evidence_scope.get("aggregation") != "day_night_total" and evidence_scope.get("shift") != "both":
            issues.append("缺少日夜合计口径")

    ex_phase = exhibit_scope.get("phase")
    ev_phase = evidence_scope.get("phase")
    if ex_phase == "after_changeover" and ev_phase != "after_changeover":
        # “首次使用新装备”可作为计划背景，但不能证明“换型后”的实测合计范围。
        issues.append("缺少首次换型后的阶段边界")

    if exhibit_scope.get("collection_boundary") and not evidence_scope.get("collection_boundary"):
        issues.append("缺少相同采集边界")
    return issues


def number_issues(claim: Claim, evidence: Claim) -> list[str]:
    issues: list[str] = []
    tolerance = 0.15
    if claim.baseline is not None and evidence.baseline is not None:
        if abs(claim.baseline - evidence.baseline) > tolerance:
            issues.append(f"基线不符：主张{claim.baseline}%，证据{evidence.baseline}%")
    if claim.current is not None and evidence.current is not None:
        if abs(claim.current - evidence.current) > tolerance:
            issues.append(f"现值不符：主张{claim.current}%，证据{evidence.current}%")

    if claim.delta is not None:
        wanted_unit = claim.delta_unit
        if wanted_unit == "percentage_point":
            actual = abs((evidence.current or 0) - (evidence.baseline or 0)) if evidence.baseline is not None and evidence.current is not None else evidence.delta
            if actual is None or abs(claim.delta - actual) > tolerance:
                issues.append(f"百分点差不符：主张{claim.delta:g}pp，证据{actual}pp")
        elif wanted_unit in {"relative_percent", "percent"}:
            actual = evidence.relative_pct
            if actual is None and evidence.delta_unit in {"percent", "relative_percent"}:
                actual = evidence.delta
            # “10% increase”若实际是 70→80，相对变化约14.3%，不能当作同值。
            if actual is None or abs(claim.delta - actual) > max(0.16, tolerance * claim.delta):
                issues.append(f"相对幅度不符：主张{claim.delta:g}%，证据相对变化{None if actual is None else round(actual, 2)}%")
    if claim.direction and evidence.direction and claim.direction != evidence.direction:
        issues.append("升降方向相反")
    return issues


def match_claim(claim: Claim, evidence: Claim) -> dict[str, Any]:
    if claim.claim_type != "measurement" or evidence.claim_type != "measurement":
        # 验证类主张单独由 lineage/scope 规则审查。
        return {"match": False, "score": 0, "scope_issues": [], "number_issues": ["非数量主张"]}

    metric_ok = True
    if claim.metric and evidence.metric and evidence.metric != "same_named_metric":
        metric_ok = claim.metric == evidence.metric
    if not metric_ok:
        return {"match": False, "score": 0, "scope_issues": [], "number_issues": ["指标不同"]}

    s_issues = scope_issues(claim.scope, evidence.scope)
    n_issues = number_issues(claim, evidence)
    hard_number = any("不符" in item or "相反" in item for item in n_issues)
    hard_scope = any(item.startswith(("对象线别", "班次范围", "对象范围过宽")) for item in s_issues)
    if hard_number or hard_scope:
        return {"match": False, "score": 0, "scope_issues": s_issues, "number_issues": n_issues}

    score = 100 - len(s_issues) * 15 - len(n_issues) * 10
    return {
        "match": True,
        "partial": bool(s_issues or n_issues),
        "score": max(score, 40),
        "scope_issues": s_issues,
        "number_issues": n_issues,
    }
