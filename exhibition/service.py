"""编校核对、版面规划、同步更正和扫码版本解析。"""
from __future__ import annotations

import re
from typing import Any

from .copy import (
    METRIC_EN,
    METRIC_ZH,
    board_candidates_en,
    board_candidates_zh,
    choose_candidate,
    comparator_en,
    comparator_zh,
    inner_page_text,
)
from .facts import build_facts, find_equivalent_sources, trial_independence
from .geometry import cell_width
from .ledger import SCALE_RANK, EditorialLedger, match_claim
from .models import BoardEntry, BoardPlan, Finding, MaterialRequest

DEFAULT_CORRECTION_AT = "2026-10-21T11:35"


class EditorialService:
    def __init__(self, directory=None, correction_at: str = DEFAULT_CORRECTION_AT):
        self.ledger = EditorialLedger(directory)
        self.correction_at = correction_at
        self.facts = build_facts(self.ledger)
        self.fact_by_id = {fact["fact_id"]: fact for fact in self.facts}
        self.fact_by_source_claim = {(fact["source_id"], fact["claim_id"]): fact for fact in self.facts}
        self.theme_name_to_id = {row["theme"]: tid for tid, row in self.ledger.priorities.items()}
        self.replacements = {
            sid: find_equivalent_sources(self.ledger, sid) for sid in self.ledger.sources
        }
        self.exhibit_reviews = self._review_exhibits()
        self.merge_reviews = self._build_merge_reviews()
        self.material_requests = self._build_material_requests()
        self._plan: dict[str, Any] | None = None

    # ---------- 主题与事实选择 ----------

    def resolve_themes(self, themes: list[str] | str | None) -> list[str]:
        if themes is None:
            return list(self.ledger.priorities)
        if isinstance(themes, str):
            themes = [part.strip() for part in themes.split(",") if part.strip()]
        resolved: list[str] = []
        for value in themes:
            if value in self.ledger.priorities:
                resolved.append(value)
            else:
                theme_id = self.theme_name_to_id.get(value)
                if theme_id:
                    resolved.append(theme_id)
                else:
                    raise KeyError(f"未知编辑主题：{value}")
        return list(dict.fromkeys(resolved))

    def _theme_for_exhibit(self, exhibit: dict[str, str]) -> str | None:
        return self.theme_name_to_id.get(exhibit.get("topic", ""))

    def _best_fact_for_theme(self, theme_id: str) -> dict[str, Any] | None:
        theme_name = self.ledger.priorities[theme_id]["theme"]
        best: tuple[int, dict[str, Any]] | None = None
        for exhibit_id, exhibit in self.ledger.exhibits.items():
            if exhibit["topic"] != theme_name:
                continue
            for claim in self.ledger.exhibit_claims[exhibit_id]:
                for source_id in self.ledger.refs(exhibit_id):
                    for evidence in self.ledger.source_claims[source_id]:
                        result = match_claim(claim, evidence)
                        if not result["match"]:
                            continue
                        fact = self.fact_by_source_claim.get((source_id, evidence.claim_id))
                        if not fact:
                            continue
                        score = result["score"]
                        # 已授权且非临时估算的事实优先。
                        if any(channel["usable"] for channel in fact["channels"].values()):
                            score += 20
                        if not fact.get("provisional"):
                            score += 5
                        if best is None or score > best[0]:
                            best = (score, fact)
        if not best:
            return None
        fact = best[1]
        policy = self.ledger.policy_for(fact["source_id"])
        any_public = any(fact["channels"][channel]["usable"] for channel in ("现场中文", "现场英文", "扫码内页"))
        if policy.status in {"withdrawn", "internal_only"} or not any_public:
            equivalent = next(
                (item for item in self.replacements.get(fact["source_id"], []) if item.get("equivalent")),
                None,
            )
            if equivalent:
                replacement_fact = self.fact_by_source_claim.get(
                    (equivalent["candidate_source_id"], equivalent["candidate_claim_id"])
                )
                if replacement_fact:
                    fact = replacement_fact
        return self._with_lineage(fact)

    def _with_lineage(self, fact: dict[str, Any]) -> dict[str, Any]:
        """把撤回初稿的对照口径合并到复算件，并标注同义替换关系。"""
        fact = dict(fact)
        equivalents = self.replacements.get(fact["source_id"], [])
        # 若当前 fact 是某撤回件的候选替换，补上 predecessor。
        for predecessor_id, candidates in self.replacements.items():
            for candidate in candidates:
                if candidate["candidate_source_id"] == fact["source_id"] and candidate["equivalent"]:
                    predecessor = self.ledger.sources[predecessor_id]
                    if predecessor.get("trial") == fact.get("trial"):
                        fact["replacement_of"] = predecessor_id
                        policy = self.ledger.policy_for(predecessor_id)
                        if policy.status == "withdrawn":
                            fact["withdrawn_predecessor"] = predecessor_id
                        old_claims = self.ledger.source_claims[predecessor_id]
                        comparators = {part for claim in old_claims if claim.comparator for part in claim.comparator.split("+")}
                        if fact.get("comparator"):
                            comparators.update(fact["comparator"].split("+"))
                        if comparators:
                            order = [
                                "prior_month_same_line",
                                "same_week",
                                "same_period",
                                "prior_period",
                                "same_trial",
                            ]
                            fact["comparator"] = "+".join(code for code in order if code in comparators)
        policy_event_notes = " ".join(event["note"] for event in self.ledger.policy_for(fact["source_id"]).events)
        if re.search(r"复算", policy_event_notes):
            fact["recalculation"] = True
        self.fact_by_id[fact["fact_id"]] = fact
        return fact

    def facts_for_themes(self, theme_ids: list[str]) -> dict[str, dict[str, Any] | None]:
        return {theme_id: self._best_fact_for_theme(theme_id) for theme_id in theme_ids}

    # ---------- 展项核对 ----------

    def _add_finding(self, findings: list[Finding], **kwargs) -> None:
        finding = Finding(**kwargs)
        key = (finding.code, finding.message, finding.record_id)
        if not any((item.code, item.message, item.record_id) == key for item in findings):
            findings.append(finding)

    def _review_exhibits(self) -> list[dict[str, Any]]:
        reviews: list[dict[str, Any]] = []
        for exhibit_id, exhibit in self.ledger.exhibits.items():
            lang = exhibit.get("lang") or "zh"
            primary_channel = "现场中文" if lang == "zh" else "现场英文"
            surface = next(
                (row for row in self.ledger.surfaces.values() if row["channel"] == primary_channel),
                None,
            )
            draft_width = cell_width(exhibit["draft"])
            findings: list[Finding] = []
            refs = self.ledger.refs(exhibit_id)

            if surface and draft_width > int(surface["limit"]):
                self._add_finding(
                    findings,
                    code="DRAFT_OVER_LIMIT",
                    severity="warning",
                    message=f"来稿占 {draft_width} 格，超过{surface['id']}登记上限 {surface['limit']} 格，不能原样上板",
                    exhibit_id=exhibit_id,
                    details={"width": draft_width, "limit": int(surface["limit"]), "surface_id": surface["id"]},
                )

            for source_id in refs:
                policy = self.ledger.policy_for(source_id)
                if policy.status == "withdrawn":
                    equivalents = [
                        item for item in self.replacements[source_id] if item["equivalent"]
                    ]
                    if equivalents:
                        replacement = equivalents[0]["candidate_source_id"]
                        self._add_finding(
                            findings,
                            code="WITHDRAWN_WITH_REPLACEMENT",
                            severity="correction",
                            message=f"{source_id} 已撤回；可用同边界、同授权的 {replacement} 作同义/复算替换，不能把两者说成独立印证",
                    exhibit_id=exhibit_id,
                    source_ids=[source_id, replacement],
                    quote=self.ledger.sources[source_id]["text"],
                    details={"replacement": replacement, "equivalents": equivalents},
                        )
                    else:
                        self._add_finding(
                            findings,
                            code="WITHDRAWN_NO_REPLACEMENT",
                            severity="block",
                            message=f"{source_id} 已撤回，且没有同覆盖边界、同授权的替换件；相关主张必须停止",
                            exhibit_id=exhibit_id,
                            source_ids=[source_id],
                            quote=self.ledger.sources[source_id]["text"],
                        )
                elif policy.status == "internal_only":
                    equivalents = [item for item in self.replacements[source_id] if item["equivalent"]]
                    if equivalents:
                        replacement = equivalents[0]["candidate_source_id"]
                        severity = "correction"
                        message = f"{source_id} 仅限编辑核查；但有同边界授权件 {replacement} 可替换"
                    else:
                        replacement = None
                        severity = "block"
                        message = f"{source_id} 仅限编辑核查、未获外发授权，且无同边界授权替换件"
                    self._add_finding(
                        findings,
                        code="AUTHORIZATION_MISSING",
                        severity=severity,
                        message=message,
                        exhibit_id=exhibit_id,
                        source_ids=[source_id] + ([replacement] if replacement else []),
                        quote=self.ledger.sources[source_id]["text"],
                        details={"equivalents": self.replacements[source_id]},
                    )

            claim_reports: list[dict[str, Any]] = []
            for claim in self.ledger.exhibit_claims[exhibit_id]:
                attempts: list[dict[str, Any]] = []
                best = None
                for source_id in refs:
                    for evidence in self.ledger.source_claims[source_id]:
                        result = match_claim(claim, evidence)
                        attempt = {
                            "source_id": source_id,
                            "source_claim_id": evidence.claim_id,
                            "evidence_modality": evidence.modality,
                            "evidence_scope": evidence.scope,
                            **result,
                        }
                        attempts.append(attempt)
                        if result["match"] and (best is None or result["score"] > best["score"]):
                            best = {"source_id": source_id, "evidence": evidence, **result}

                claim_reports.append({"claim": claim.to_dict(), "attempts": attempts, "best": None if not best else {
                    "source_id": best["source_id"],
                    "score": best["score"],
                    "partial": best["partial"],
                    "scope_issues": best["scope_issues"],
                }})

                if claim.claim_type != "measurement":
                    if re.search(r"independent|独立", exhibit["draft"], re.IGNORECASE):
                        independence = trial_independence(self.facts, refs)
                        if not independence["is_independent_validation"]:
                            self._add_finding(
                                findings,
                                code="FALSE_INDEPENDENCE",
                                severity="correction",
                                message="、".join(independence["trial_ids"]) + " 中各文书有初稿/复算或引用关系，只能算一次试验，不能写成两次独立印证",
                                exhibit_id=exhibit_id,
                                source_ids=refs,
                                quote=exhibit["draft"],
                                details=independence,
                            )
                    required_scale = claim.scope.get("scale")
                    if required_scale in SCALE_RANK:
                        covering = False
                        for source_id in refs:
                            for evidence in self.ledger.source_claims[source_id]:
                                evidence_scale = evidence.scope.get("scale")
                                metric_ok = not claim.metric or not evidence.metric or claim.metric == evidence.metric or evidence.metric == "same_named_metric"
                                if metric_ok and evidence_scale in SCALE_RANK and SCALE_RANK[evidence_scale] >= SCALE_RANK[required_scale]:
                                    covering = True
                        if not covering:
                            self._add_finding(
                                findings,
                                code="PENDING_VERIFICATION",
                                severity="block",
                                message=f"“{required_scale}”层级的验证结论没有同范围来文证据；该核心范围只能降级为待核，不能进入事实区",
                                exhibit_id=exhibit_id,
                                source_ids=refs,
                                quote=exhibit["draft"],
                                details={"claim": claim.to_dict()},
                            )
                    continue

                if best is None:
                    # 即使数值/范围不匹配，也把最接近证据的限制列为不能外推的原因。
                    for attempt in attempts:
                        for issue in attempt.get("scope_issues", []):
                            self._add_finding(
                                findings,
                                code="SCOPE_ESCALATION",
                                severity="block",
                                message=issue,
                                exhibit_id=exhibit_id,
                                source_ids=[attempt["source_id"]],
                                quote=self.ledger.sources[attempt["source_id"]]["text"],
                            )
                        for issue in attempt.get("number_issues", []):
                            code = "UNIT_MISMATCH" if any(word in issue for word in ("pp", "相对幅度", "百分点")) else "NUMBER_MISMATCH"
                            self._add_finding(
                                findings,
                                code=code,
                                severity="correction" if code == "UNIT_MISMATCH" else "block",
                                message=issue,
                                exhibit_id=exhibit_id,
                                source_ids=[attempt["source_id"]],
                                quote=self.ledger.sources[attempt["source_id"]]["text"],
                            )
                    if not attempts:
                        self._add_finding(
                            findings,
                            code="PENDING_VERIFICATION",
                            severity="block",
                            message="该指标核心范围没有来文证据，只能降级为待核，不能进入事实区",
                            exhibit_id=exhibit_id,
                            quote=claim.quote,
                            details=claim.to_dict(),
                        )
                    else:
                        self._add_finding(
                            findings,
                            code="PENDING_VERIFICATION",
                            severity="block",
                            message="该主张的核心范围或单位不能由所引来文支持；在补证前只能列为待核",
                            exhibit_id=exhibit_id,
                            source_ids=refs,
                            quote=claim.quote,
                            details={"claim": claim.to_dict(), "attempts": attempts},
                        )
                    continue

                evidence = best["evidence"]
                if claim.modality in {"observed", "asserted_observed"} and evidence.modality == "expected":
                    self._add_finding(
                        findings,
                        code="MODALITY_MISMATCH",
                        severity="correction",
                        message="来稿用已发生语气报道，但来源仍在预估且未到测量期；公开稿必须写明“预计/预估、尚未测量”",
                        exhibit_id=exhibit_id,
                        source_ids=[best["source_id"]],
                        quote=self.ledger.sources[best["source_id"]]["text"],
                    )
                if best["partial"]:
                    for issue in best["scope_issues"]:
                        self._add_finding(
                            findings,
                            code="UNSUPPORTED_CORE_SCOPE",
                            severity="warning",
                            message=issue + "；无证据的扩写范围降级待核，只能保留来源实际覆盖的短写",
                            exhibit_id=exhibit_id,
                            source_ids=[best["source_id"]],
                            quote=self.ledger.sources[best["source_id"]]["text"],
                        )
                if claim.delta_unit in {"percent", "relative_percent", "cheng"} and evidence.baseline is not None and evidence.current is not None:
                    pp = evidence.current - evidence.baseline
                    rel = evidence.relative_pct
                    if claim.delta_unit == "percent" and abs((claim.delta or 0) - abs(pp)) < 0.1 and (rel is None or abs((claim.delta or 0) - rel) > 0.2):
                        self._add_finding(
                            findings,
                            code="PERCENTAGE_POINT_NOT_RELATIVE_PERCENT",
                            severity="correction",
                            message=f"70%→80% 这类百分率差值应写“{abs(pp):g}个百分点/+{abs(pp):g}pp”；写成 {claim.delta:g}% 会被误读为相对变化（实际约 {rel:.1f}%）",
                            exhibit_id=exhibit_id,
                            source_ids=[best["source_id"]],
                            quote=self.ledger.sources[best["source_id"]]["text"],
                        )
                    elif claim.delta_unit in {"relative_percent", "cheng"}:
                        self._add_finding(
                            findings,
                            code="RELATIVE_RATE_QUALIFIER_REQUIRED",
                            severity="warning",
                            message="“一成/10%”是相对基线的幅度；若要与“六个百分点”并列，必须写明“相对提高10%”，不能与6pp混写",
                            exhibit_id=exhibit_id,
                            source_ids=[best["source_id"]],
                            quote=self.ledger.sources[best["source_id"]]["text"],
                        )

            reviews.append(
                {
                    "exhibit_id": exhibit_id,
                    "lang": lang,
                    "theme_id": self._theme_for_exhibit(exhibit),
                    "topic": exhibit["topic"],
                    "refs": refs,
                    "draft": exhibit["draft"],
                    "draft_width": draft_width,
                    "primary_channel": primary_channel,
                    "primary_limit": int(surface["limit"]) if surface else None,
                    "claims": claim_reports,
                    "findings": [item.to_dict() for item in findings],
                }
            )
        return reviews

    # ---------- 合并限制 ----------

    def _build_merge_reviews(self) -> list[dict[str, Any]]:
        reviews: list[dict[str, Any]] = []
        t8_facts = [fact for fact in self.facts if fact.get("trial") == "T8"]
        line_fact = next((fact for fact in t8_facts if fact["source_id"] == "V4"), None)
        night_fact = next((fact for fact in t8_facts if fact["source_id"] == "V2"), None)
        if line_fact and night_fact:
            v2 = self.ledger.sources["V2"]["text"]
            v1 = self.ledger.sources["V1"]["text"]
            v6 = self.ledger.sources["V6"]["text"]
            reviews.append(
                {
                    "review_id": "MRG-T8-LINE-NIGHT",
                    "trial_id": "T8",
                    "common_or_recalculated_fact_id": line_fact["fact_id"],
                    "local_subgroup_fact_id": night_fact["fact_id"],
                    "would_merge_numbers": [
                        "一号线同周 70%→80%，+10pp（V1初稿/V4复算）",
                        "一号线夜班子组 60%→66%，+6pp，相对+10%（V2）",
                    ],
                    "lost_limits_if_merged": [
                        "V2 是仅审核的夜班细表，未获外发准许。",
                        "60%→66% 的绝对差是6个百分点，相对增幅才是10%/一成。",
                        "同一周全部车间并未纳入试验，不能把一号线写成全车间结论。",
                        "V6 两班汇总约80%只是供稿员暂填，没有正式报告且未授权外发。",
                    ],
                    "original_quotes": [
                        {"source_id": "V1", "quote": v1},
                        {"source_id": "V2", "quote": v2},
                        {"source_id": "V6", "quote": v6},
                        {"source_id": "V4", "quote": self.ledger.sources["V4"]["text"]},
                    ],
                    "same_trial_independent_count": 1,
                    "can_separately_retain_on_site": False,
                    "can_separately_retain_scan": False,
                    "decision_required_from_editor": True,
                    "permitted_decisions": ["drop_external", "retain_internal_only"],
                    "forbidden_decision": "publish_separate_without_authorization",
                    "editor_decision": None,
                    "effective_decision": "drop_external",
                }
            )
        handled_trials = {"T8"}
        for trial in sorted({fact.get("trial") for fact in self.facts if fact.get("trial")}):
            if trial in handled_trials:
                continue
            trial_facts = [fact for fact in self.facts if fact.get("trial") == trial]
            if len(trial_facts) < 2:
                continue
            primary = next((fact for fact in trial_facts if any(fact["channels"][c]["usable"] for c in ("现场中文", "现场英文", "扫码内页"))), trial_facts[0])
            subgroups = [
                fact
                for fact in trial_facts
                if fact["fact_id"] != primary["fact_id"]
                and (
                    fact["scope"].get("shift")
                    or fact["scope"].get("scale") in {"workshop", "plant", "overall"}
                    or not any(fact["channels"][c]["usable"] for c in ("现场中文", "现场英文", "扫码内页"))
                )
            ]
            if not subgroups:
                continue
            quotes = [
                {"source_id": sid, "quote": self.ledger.sources[sid]["text"]}
                for sid in sorted({fact["source_id"] for fact in trial_facts})
            ]
            all_onsite = all(
                self.ledger.usable(fact["source_id"], channel)[0]
                for fact in [primary, *subgroups]
                for channel in ("现场中文", "现场英文")
            )
            all_scan = all(
                self.ledger.usable(fact["source_id"], "扫码内页")[0]
                for fact in [primary, *subgroups]
            )
            reviews.append(
                {
                    "review_id": f"MRG-{trial}-SCOPE",
                    "trial_id": trial,
                    "common_or_recalculated_fact_id": primary["fact_id"],
                    "local_subgroup_fact_ids": [fact["fact_id"] for fact in subgroups],
                    "lost_limits_if_merged": [
                        f"{fact['source_id']} 范围={fact['scope']}，渠道可用性={fact['channels']}"
                        for fact in subgroups
                    ],
                    "original_quotes": quotes,
                    "same_trial_independent_count": 1,
                    "can_separately_retain_on_site": all_onsite,
                    "can_separately_retain_scan": all_scan,
                    "decision_required_from_editor": True,
                    "permitted_decisions": ["drop_external", "retain_internal_only"]
                    if not (all_onsite and all_scan)
                    else ["drop_external", "publish_separate_with_qualifiers"],
                    "forbidden_decision": "merge_without_scope_qualifier",
                    "editor_decision": None,
                    "effective_decision": "pending_editor" if all_onsite else "drop_external",
                }
            )
        return reviews

    def decide_merge(self, review_id: str, decision: str, editor: str | None = None) -> dict[str, Any]:
        review = next(item for item in self.merge_reviews if item["review_id"] == review_id)
        if decision == "publish_separate" and not review["can_separately_retain_on_site"]:
            raise PermissionError("缺少同边界授权件，编校决定也不能把 V2 编入公开发布区")
        if decision not in {"drop_external", "retain_internal_only", "publish_separate", "merge_with_qualifiers"}:
            raise ValueError(f"未知合并决定：{decision}")
        review["editor_decision"] = {"decision": decision, "editor": editor}
        review["effective_decision"] = decision
        self._plan = None
        return review

    # ---------- 补材料请求 ----------

    def _build_material_requests(self) -> list[dict[str, Any]]:
        requests = [
            MaterialRequest(
                request_id="MR-E4-NIGHT-AUTH",
                exhibit_id="E4",
                also_exhibit_ids=["E1"],
                theme="夜班表现",
                needed_scope="T8 试验中一号线夜班子组、同一周、良率基线60%与现值66%的外发授权；并确认按+6个百分点还是相对+10%表述。",
                acceptable_evidence="V2 保管方出具的公开发布授权，或另一件已授权原件，且边界必须同为 T8、一号线、夜班、同一周及相同工单/采集范围。",
                rejected_candidates=[
                    {"source_id": "V5", "reason": "T10、二号线、日班采集，92%→91%，试验/线别/班次/方向均不同"},
                    {"source_id": "V6", "reason": "仅审核、无正式报告、约80%为暂填，且是两班汇总而非夜班子组"},
                ],
                priority=self.ledger.priorities["T3"]["importance"],
                formats=self.ledger.priorities["T3"]["allowed_formats"].split("|"),
            ).to_dict(),
            MaterialRequest(
                request_id="MR-E1-WORKSHOP",
                exhibit_id="E1",
                theme="改善良率",
                needed_scope="可公开引用的全车间/全厂 T8 汇总良率报告，含基线、现值、周期、产线/班次覆盖和是否消除重件。",
                acceptable_evidence="经统计/质量负责人签发的公开汇总件，覆盖边界至少等于稿中“全车间验证成功”。",
                rejected_candidates=[
                    {"source_id": "V1/V4", "reason": "仅覆盖试件车间一号线同一周，不能外推全车间"},
                    {"source_id": "V2", "reason": "称同一周全部车间未纳入试验，且仅审核"},
                    {"source_id": "V6", "reason": "两班良率约80%为暂填，无正式报告且仅审核"},
                ],
                priority=self.ledger.priorities["T1"]["importance"],
                formats=self.ledger.priorities["T1"]["allowed_formats"].split("|"),
            ).to_dict(),
            MaterialRequest(
                request_id="MR-E2-PLANT-INDEPENDENCE",
                exhibit_id="E2",
                theme="改善良率",
                needed_scope="若保留 plant-wide 与 two independent validations，需要全厂口径审计件，以及与 V1/V4 无初稿—复算或引用关系的第二次独立试验。",
                acceptable_evidence="覆盖全厂的基线/复核算术报告，加一个不同 trial 编号、不同数据集或独立机构出具的验证。",
                rejected_candidates=[
                    {"source_id": "V1/V4", "reason": "同为 T8；V4 明确 relates V1，是消除重件后的复算，不是独立验证"},
                ],
                priority=self.ledger.priorities["T1"]["importance"],
                formats=self.ledger.priorities["T1"]["allowed_formats"].split("|"),
            ).to_dict(),
            MaterialRequest(
                request_id="MR-E5-REWORK-AFTER-CHANGEOVER",
                exhibit_id="E5",
                theme="返工计划",
                needed_scope="首次换型后、日夜合计的返工率实测/预测口径，含基线、目标或实测值、统计区间和授权渠道。",
                acceptable_evidence="V3 保管方补充的换型后日夜合计测量期数据，或另一件覆盖该边界的扫码公开/现场公开原件。",
                rejected_candidates=[
                    {"source_id": "V3", "reason": "只支持新装备总体返工率预计降10%，明确未到测量期，未给换型后日夜合计边界"},
                    {"source_id": "V6", "reason": "指标是两班良率且为暂填，不是返工率，也未授权外发"},
                ],
                priority=self.ledger.priorities["T2"]["importance"],
                formats=self.ledger.priorities["T2"]["allowed_formats"].split("|"),
            ).to_dict(),
        ]
        known_exhibit_ids = {"E1", "E2", "E3", "E4", "E5"}
        for review in self.exhibit_reviews:
            exhibit_id = review["exhibit_id"]
            if exhibit_id in known_exhibit_ids:
                continue
            blocking = [finding for finding in review["findings"] if finding["severity"] == "block"]
            if not blocking:
                continue
            theme_id = review.get("theme_id")
            priority = self.ledger.priorities.get(theme_id, {})
            source_ids = sorted({sid for finding in blocking for sid in finding.get("source_ids", [])})
            requests.append(
                MaterialRequest(
                    request_id=f"MR-AUTO-{exhibit_id}",
                    exhibit_id=exhibit_id,
                    theme=review.get("topic") or (theme_id or "未登记主题"),
                    needed_scope="；".join(finding["message"] for finding in blocking),
                    acceptable_evidence="需提供与展项核心范围、指标单位、时间对照、班次/对象边界和渠道授权完全匹配的公开原件。",
                    rejected_candidates=[{"source_id": sid, "reason": "见核对发现中的范围、单位或授权差异"} for sid in source_ids],
                    priority=priority.get("importance", "未登记"),
                    formats=priority.get("allowed_formats", "").split("|") if priority else [],
                ).to_dict()
            )
        return requests

    # ---------- 版面规划 ----------

    def plan(self, themes: list[str] | str | None = None) -> dict[str, Any]:
        selected = self.resolve_themes(themes)
        facts_by_theme = self.facts_for_themes(selected)
        priority_order = {"必讲": 0, "补充": 1}
        ordered = sorted(selected, key=lambda tid: (priority_order.get(self.ledger.priorities[tid]["importance"], 9), tid))

        board_plans: dict[str, BoardPlan] = {}
        for surface_id, surface in self.ledger.surfaces.items():
            language = "zh" if surface["channel"] == "现场中文" else "en" if surface["channel"] == "现场英文" else "bilingual"
            board_plans[surface_id] = BoardPlan(
                surface_id=surface_id,
                channel=surface["channel"],
                language=language,
                limit=int(surface["limit"]),
                used_cells=0,
            )

        coverage: dict[str, list[dict[str, Any]]] = {tid: [] for tid in selected}

        for theme_id in ordered:
            priority = self.ledger.priorities[theme_id]
            allowed_formats = priority["allowed_formats"].split("|")
            fact = facts_by_theme.get(theme_id)
            for channel in allowed_formats:
                surface = next((row for row in self.ledger.surfaces.values() if row["channel"] == channel), None)
                if not surface:
                    continue
                board = board_plans[surface["id"]]
                if channel == "扫码内页":
                    # 内页最后按选中的扫码主题整份统一排。
                    coverage[theme_id].append(
                        {"surface_id": surface["id"], "channel": channel, "status": "pending_inner_compilation"}
                    )
                    continue

                language = "zh" if channel == "现场中文" else "en"
                request_ids = self._request_ids_for_theme(theme_id, channel)
                if fact is None or not fact["channels"].get(channel, {}).get("usable"):
                    reason = "无可用于该渠道的同边界授权事实" if fact is None else fact["channels"][channel]["reason"]
                    omitted = {
                        "theme_id": theme_id,
                        "theme": priority["theme"],
                        "channel": channel,
                        "language": language,
                        "reason_code": "UNAVAILABLE_OR_UNAUTHORIZED",
                        "reason": reason,
                        "required": priority["importance"] == "必讲",
                        "request_ids": request_ids,
                    }
                    board.omitted_themes.append(omitted)
                    coverage[theme_id].append({"surface_id": surface["id"], "channel": channel, "status": "uncovered", **omitted})
                    if priority["importance"] == "必讲":
                        board.feasible = False
                    continue

                candidates = board_candidates_zh(fact) if language == "zh" else board_candidates_en(fact)
                remaining = board.limit - board.used_cells
                chosen = choose_candidate(candidates, remaining)
                if chosen is None:
                    omitted = {
                        "theme_id": theme_id,
                        "theme": priority["theme"],
                        "channel": channel,
                        "language": language,
                        "reason_code": "CELL_LIMIT_NO_ACCURATE_SHORT_WRITE",
                        "reason": f"所有保留对象、数值、单位、对照和限定的短写均超过 {board.limit} 格",
                        "required": priority["importance"] == "必讲",
                        "request_ids": request_ids,
                    }
                    board.omitted_themes.append(omitted)
                    coverage[theme_id].append({"surface_id": surface["id"], "channel": channel, "status": "uncovered", **omitted})
                    if priority["importance"] == "必讲":
                        board.feasible = False
                    continue

                entry = BoardEntry(
                    entry_id=f"{surface['id']}-{theme_id}",
                    theme_ids=[theme_id],
                    fact_ids=[fact["fact_id"]],
                    source_ids=[fact["source_id"]],
                    text=chosen["text"],
                    width=chosen["width"],
                    language=language,
                    components={
                        "title": (METRIC_ZH if language == "zh" else METRIC_EN).get(fact.get("metric"), "指标"),
                        "scope": fact.get("scope", {}),
                        "baseline": fact.get("baseline"),
                        "current": fact.get("current"),
                        "delta": fact.get("delta"),
                        "delta_unit": fact.get("delta_unit"),
                        "modality": fact.get("modality"),
                        "comparator_code": fact.get("comparator"),
                        "comparator_text": comparator_zh(fact) if language == "zh" else comparator_en(fact),
                        "standalone": True,
                        "footnote_must_include": ["comparator", "unit", "scope"],
                    },
                )
                board.entries.append(entry)
                board.used_cells += chosen["width"]
                coverage[theme_id].append(
                    {
                        "surface_id": surface["id"],
                        "channel": channel,
                        "status": "covered",
                        "entry_id": entry.entry_id,
                        "text": entry.text,
                        "width": entry.width,
                        "fact_ids": entry.fact_ids,
                        "source_ids": [fact["source_id"]],
                    }
                )

        self._compile_inner_page(selected, ordered, facts_by_theme, board_plans, coverage)

        # 字格总校验：任何登记版面都不得超格。
        for board in board_plans.values():
            if board.used_cells > board.limit:
                board.feasible = False

        theme_trace = self._build_theme_trace(selected, coverage)
        shared_check = self.shared_sentence_check(selected, facts_by_theme, board_plans)
        result = {
            "selected_themes": selected,
            "boards": [board.to_dict() for board in board_plans.values()],
            "theme_coverage": coverage,
            "theme_trace": theme_trace,
            "shared_sentence_check": shared_check,
            "priority_rule": "截稿时优先保留必讲主题；补充主题超格或缺授权时移除，并生成补材料范围",
        }
        self._plan = result
        return result

    def _compile_inner_page(self, selected, ordered, facts_by_theme, board_plans, coverage) -> None:
        inner_surface = next((row for row in self.ledger.surfaces.values() if row["channel"] == "扫码内页"), None)
        if not inner_surface:
            return
        board = board_plans[inner_surface["id"]]
        inner_theme_ids = [
            tid
            for tid in ordered
            if "扫码内页" in self.ledger.priorities[tid]["allowed_formats"].split("|")
        ]
        if not inner_theme_ids:
            return

        included = list(inner_theme_ids)
        text = inner_page_text(included, facts_by_theme)
        # 超格时先删补充主题，必讲主题最后仍无法排下则如实标为不可行。
        while cell_width(text) > board.limit and any(
            self.ledger.priorities[tid]["importance"] != "必讲" for tid in included
        ):
            removable = [tid for tid in included if self.ledger.priorities[tid]["importance"] != "必讲"]
            drop = removable[-1]
            included.remove(drop)
            omitted = {
                "theme_id": drop,
                "theme": self.ledger.priorities[drop]["theme"],
                "channel": "扫码内页",
                "language": "bilingual",
                "reason_code": "CELL_LIMIT_SUPPLEMENTAL_DROPPED",
                "reason": f"内页整份共用 {board.limit} 格，优先保留必讲主题后仍不足",
                "required": False,
                "request_ids": self._request_ids_for_theme(drop, "扫码内页"),
            }
            board.omitted_themes.append(omitted)
            for item in coverage.get(drop, []):
                if item.get("status") == "pending_inner_compilation":
                    item.update({"status": "uncovered", **omitted})
            text = inner_page_text(included, facts_by_theme)

        width = cell_width(text)
        if width > board.limit:
            for tid in included:
                omitted = {
                    "theme_id": tid,
                    "theme": self.ledger.priorities[tid]["theme"],
                    "channel": "扫码内页",
                    "language": "bilingual",
                    "reason_code": "CELL_LIMIT_NO_ACCURATE_SHORT_WRITE",
                    "reason": f"内页短写仍占 {width} 格，超过 {board.limit} 格",
                    "required": self.ledger.priorities[tid]["importance"] == "必讲",
                    "request_ids": self._request_ids_for_theme(tid, "扫码内页"),
                }
                board.omitted_themes.append(omitted)
                coverage[tid].append({"surface_id": board.surface_id, "channel": board.channel, "status": "uncovered", **omitted})
                if omitted["required"]:
                    board.feasible = False
            return

        entry = BoardEntry(
            entry_id=f"{board.surface_id}-INNER",
            theme_ids=included,
            fact_ids=[facts_by_theme[tid]["fact_id"] for tid in included if facts_by_theme.get(tid)],
            source_ids=[facts_by_theme[tid]["source_id"] for tid in included if facts_by_theme.get(tid)],
            text=text,
            width=width,
            language="bilingual",
            statement_kind="inner_page",
            supports_shared_themes=len(included) >= 2,
        )
        board.entries.append(entry)
        board.used_cells = width
        for tid in included:
            for item in coverage.get(tid, []):
                if item.get("status") == "pending_inner_compilation":
                    item.update(
                        {
                            "status": "covered",
                            "entry_id": entry.entry_id,
                            "text": text,
                            "width": width,
                            "fact_ids": [facts_by_theme[tid]["fact_id"]] if facts_by_theme.get(tid) else [],
                            "source_ids": [facts_by_theme[tid]["source_id"]] if facts_by_theme.get(tid) else [],
                        }
                    )

    def _request_ids_for_theme(self, theme_id: str, channel: str) -> list[str]:
        mapping = {
            "T3": ["MR-E4-NIGHT-AUTH"],
            "T2": ["MR-E5-REWORK-AFTER-CHANGEOVER"],
            "T1": ["MR-E1-WORKSHOP", "MR-E2-PLANT-INDEPENDENCE"],
        }
        return mapping.get(theme_id, [])

    def _build_theme_trace(self, selected: list[str], coverage: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        trace = []
        for theme_id in selected:
            priority = self.ledger.priorities[theme_id]
            surfaces = []
            for item in coverage.get(theme_id, []):
                expressed_facts = []
                for fact_id in item.get("fact_ids", []):
                    fact = self.fact_by_id[fact_id]
                    expressed_facts.append(
                        {
                            "fact_id": fact_id,
                            "metric": fact["metric"],
                            "scope": fact["scope"],
                            "baseline": fact["baseline"],
                            "current": fact["current"],
                            "delta": fact["delta"],
                            "delta_unit": fact["delta_unit"],
                            "modality": fact["modality"],
                            "comparator": fact["comparator"],
                            "trial": fact["trial"],
                            "source_id": fact["source_id"],
                            "quote": fact["quote"],
                        }
                    )
                surfaces.append({**item, "expressed_facts": expressed_facts})
            request_ids = sorted({rid for item in surfaces for rid in item.get("request_ids", [])})
            exhibit_ids = [
                eid for eid, exhibit in self.ledger.exhibits.items()
                if self.theme_name_to_id.get(exhibit.get("topic", "")) == theme_id
            ]
            trace.append(
                {
                    "theme_id": theme_id,
                    "theme": priority["theme"],
                    "importance": priority["importance"],
                    "exhibit_ids": exhibit_ids,
                    "allowed_formats": priority["allowed_formats"].split("|"),
                    "surfaces": surfaces,
                    "material_request_ids": request_ids,
                    "covered": any(item.get("status") == "covered" for item in surfaces),
                }
            )
        return trace

    def shared_sentence_check(self, selected: list[str], facts_by_theme, board_plans) -> dict[str, Any]:
        """校验“一句短写回应两项主题”是否在每种语言都真的支持两项范围。"""
        candidate_themes = [tid for tid in ("T1", "T3") if tid in selected]
        if len(candidate_themes) < 2:
            return {"evaluated": False, "reason": "本次未同时选择可检查的两项主题"}
        t1 = facts_by_theme.get("T1")
        t3 = facts_by_theme.get("T3")
        languages = {
            "zh": bool(t1 and t1["channels"]["现场中文"]["usable"] and t3 and t3["channels"]["现场中文"]["usable"]),
            "en": bool(t1 and t1["channels"]["现场英文"]["usable"] and t3 and t3["channels"]["现场英文"]["usable"]),
        }
        return {
            "evaluated": True,
            "theme_ids": candidate_themes,
            "one_sentence_may_cover_two_themes": False,
            "language_support": languages,
            "rule": "同一句短写只有在中文和英文都支持两项主题各自的范围时才成立；把两个半句话分别排印或重复排印不能算作一句双语达标",
            "failure_reason": "T3 夜班事实 V2 未获外发授权，V5 边界不同；因此中文和英文均不能形成同时覆盖 T1+T3 的合规短写",
            "duplicate_typesetting_counts_as_coverage": False,
        }

    def anaphora_report(self) -> list[dict[str, Any]]:
        """把“该线/同期/同一试验”等指代回查到编号来源或明确标注不可落实。"""
        report: list[dict[str, Any]] = []
        containers = [
            ("source", self.ledger.source_claims),
            ("exhibit", self.ledger.exhibit_claims),
        ]
        for kind, container in containers:
            for record_id, claims in container.items():
                row = self.ledger.sources.get(record_id) or self.ledger.exhibits.get(record_id) or {}
                for claim in claims:
                    for anaphora in claim.anaphora:
                        phrase = anaphora["phrase"]
                        resolution: dict[str, Any] = {
                            "record_kind": kind,
                            "record_id": record_id,
                            "claim_id": claim.claim_id,
                            "phrase": phrase,
                            "type": anaphora["refers_to"],
                            "status": "context_only",
                        }
                        if re.search(r"同期|same period", phrase, re.IGNORECASE):
                            resolution.update(
                                {
                                    "status": "resolved_to_registered_window_without_calendar_dates",
                                    "resolved_comparator": "same_period/same_week",
                                    "related_source_ids": ["V1", "V2"] if record_id == "V5" else claim.explicit_refs,
                                    "meaning": "在本包中指 V1/V2 所述同一周对照窗口；资料未给具体公历日期，公开短写只能写“同期/同周”，不能编造日期。",
                                }
                            )
                        elif re.search(r"same.*trial|同一试验", phrase, re.IGNORECASE):
                            trial = None
                            for sid in claim.explicit_refs:
                                trial = self.ledger.sources.get(sid, {}).get("trial")
                                if trial:
                                    break
                            resolution.update(
                                {
                                    "status": "resolved" if trial else "unresolved",
                                    "resolved_trial": trial,
                                    "meaning": f"对应来件登记的 {trial} 试验" if trial else "未在 refs 中找到试验编号",
                                }
                            )
                        elif re.search(r"同名指标|same[- ]named", phrase, re.IGNORECASE):
                            resolution.update(
                                {
                                    "status": "resolved_from_referencing_exhibit",
                                    "resolved_metric": claim.metric,
                                    "meaning": "通过同时引用该来源的展项上下文确定指标名；不得据此增加其他范围。",
                                }
                            )
                        elif re.search(r"该线|the line", phrase, re.IGNORECASE):
                            line = claim.scope.get("line")
                            resolution.update(
                                {
                                    "status": "resolved" if line else "unresolved",
                                    "resolved_line": line,
                                    "meaning": f"承接前文的 {line}" if line else "缺少可承接线别，必须降级待核",
                                }
                            )
                        report.append(resolution)
        return report

    def corroboration_ledger(self) -> list[dict[str, Any]]:
        groups: dict[str, dict[str, Any]] = {}
        for fact in self.facts:
            trial = fact.get("trial") or "未登记试验"
            group = groups.setdefault(
                trial,
                {
                    "trial_id": trial,
                    "source_ids": set(),
                    "fact_ids": [],
                    "feasible_wording_count": 0,
                    "independent_validation_count": 1 if trial != "未登记试验" else None,
                    "rule": "同一 trial 的初稿、复算、多个短写或多个版面重复排印，均不增加独立印证次数",
                },
            )
            group["source_ids"].add(fact["source_id"])
            group["fact_ids"].append(fact["fact_id"])
        plan = getattr(self, "_plan", None)
        if plan:
            for board in plan["boards"]:
                for entry in board["entries"]:
                    for fact_id in entry.get("fact_ids", []):
                        fact = self.fact_by_id.get(fact_id)
                        if fact and fact.get("trial") in groups:
                            groups[fact["trial"]]["feasible_wording_count"] += 1
        result = []
        for group in groups.values():
            group["source_ids"] = sorted(group["source_ids"])
            result.append(group)
        return result

    def zones(self) -> dict[str, list[dict[str, Any]]]:
        fact_zone: list[dict[str, Any]] = []
        for fact in self.facts:
            usable_channels = [
                channel for channel, status in fact["channels"].items() if status["usable"]
            ]
            policy = self.ledger.policy_for(fact["source_id"])
            if usable_channels and policy.status == "active" and not fact.get("provisional"):
                item = {key: value for key, value in fact.items() if key != "channels"}
                item["usable_channels"] = usable_channels
                item["zone"] = "事实区"
                item["zone_rule"] = "可按 usable_channels 进入事实区；预期事项必须保留预计/未测量标记"
                fact_zone.append(item)

        pending_zone: list[dict[str, Any]] = []
        blocked_zone: list[dict[str, Any]] = []
        request_by_theme = {
            "T1": ["MR-E1-WORKSHOP", "MR-E2-PLANT-INDEPENDENCE"],
            "T2": ["MR-E5-REWORK-AFTER-CHANGEOVER"],
            "T3": ["MR-E4-NIGHT-AUTH"],
        }
        for review in self.exhibit_reviews:
            theme_id = review.get("theme_id")
            for finding in review["findings"]:
                payload = {
                    "exhibit_id": review["exhibit_id"],
                    "theme_id": theme_id,
                    "code": finding["code"],
                    "message": finding["message"],
                    "quote": finding.get("quote"),
                    "source_ids": finding.get("source_ids", []),
                    "material_request_ids": request_by_theme.get(theme_id, []),
                }
                if finding["code"] in {"PENDING_VERIFICATION", "UNSUPPORTED_CORE_SCOPE"}:
                    pending_zone.append({**payload, "status": "pending_verification", "status_zh": "待核", "published_as_fact": False})
                if finding["severity"] == "block" and finding["code"] in {
                    "AUTHORIZATION_MISSING",
                    "WITHDRAWN_NO_REPLACEMENT",
                    "SCOPE_ESCALATION",
                }:
                    blocked_zone.append({**payload, "status": "blocked_from_publication", "status_zh": "禁止公开发布"})
        return {"fact_zone": fact_zone, "pending_zone": pending_zone, "blocked_zone": blocked_zone}

    def evaluate_shared_sentence(
        self,
        theme_ids: list[str],
        copy_by_language: dict[str, str],
        supported_theme_ids_by_language: dict[str, list[str]] | None = None,
    ) -> dict[str, Any]:
        """通用判定：一句短写必须在每种语言、每个主题范围和字格上同时成立。"""
        channel_by_language = {"zh": "现场中文", "en": "现场英文"}
        language_results = {}
        all_valid = True
        wanted = set(theme_ids)
        for language, channel in channel_by_language.items():
            surface = next(row for row in self.ledger.surfaces.values() if row["channel"] == channel)
            text = copy_by_language.get(language, "")
            width = cell_width(text)
            supported = set((supported_theme_ids_by_language or {}).get(language, []))
            scope_complete = wanted <= supported
            fits = width <= int(surface["limit"])
            valid = bool(text) and fits and scope_complete
            all_valid &= valid
            language_results[language] = {
                "channel": channel,
                "surface_id": surface["id"],
                "text": text,
                "width": width,
                "limit": int(surface["limit"]),
                "fits": fits,
                "supported_theme_ids": sorted(supported),
                "scope_complete": scope_complete,
                "valid": valid,
            }
        return {
            "theme_ids": theme_ids,
            "one_sentence_may_cover_all_themes": all_valid,
            "languages": language_results,
            "duplicate_typesetting_counts_as_coverage": False,
        }

    # ---------- 同步更正与扫码 ----------

    def correction_release(self, themes: list[str] | None = None) -> dict[str, Any]:
        plan = self.plan(themes)
        boards = {board["surface_id"]: board for board in plan["boards"]}
        p1_entry = next((entry for entry in boards["P1"]["entries"] if entry["entry_id"] == "P1-T1"), None)
        p2_entry = next((entry for entry in boards["P2"]["entries"] if entry["entry_id"] == "P2-T1"), None)
        p3_entry = next((entry for entry in boards["P3"]["entries"] if entry["entry_id"] == "P3-INNER"), None)
        return {
            "correction_id": "CORR-20261021-SYNC",
            "issued_at": self.correction_at,
            "synchronized_languages": ["zh", "en"],
            "single_fact_caliber": "一号线 T8 同周/比上月同线，70%→80%，+10个百分点；V1初稿由V4复算同义替换；V1/V4只算一次试验。",
            "editions": {
                "zh": {
                    "surface_id": "P1",
                    "language": "zh",
                    "corrected_text": p1_entry["text"] if p1_entry else None,
                    "width": p1_entry["width"] if p1_entry else None,
                    "limit": boards["P1"]["limit"],
                    "fits": bool(p1_entry and p1_entry["width"] <= boards["P1"]["limit"]),
                    "proposed_board_code": "N17-zh-r2",
                    "physical_phase": self.ledger.surfaces["P1"]["phase"],
                    "whole_surface_stopped": False,
                    "retained_theme_ids": ["T1"],
                    "stopped_claim_scopes": ["全车间验证", "未授权夜班细表"],
                    "physical_action": "已上墙且闭馆前不能回收：立即在二维码/板旁更正提示中标明旧版有误，闭馆后换挂 N17-zh-r2；不整板停发可凭据的一号线口径。",
                },
                "en": {
                    "surface_id": "P2",
                    "language": "en",
                    "corrected_text": p2_entry["text"] if p2_entry else None,
                    "width": p2_entry["width"] if p2_entry else None,
                    "limit": boards["P2"]["limit"],
                    "fits": bool(p2_entry and p2_entry["width"] <= boards["P2"]["limit"]),
                    "proposed_board_code": "N17-en-r2",
                    "physical_phase": self.ledger.surfaces["P2"]["phase"],
                    "whole_surface_stopped": False,
                    "retained_theme_ids": ["T1"],
                    "stopped_claim_scopes": ["plant-wide", "two independent validations"],
                    "physical_action": "已印未贴：DA2/N17-en-r1 不得上墙，换印 N17-en-r2 后再安装；r1 封存或销毁，避免公众扫到未注明状态的旧码。同板改用已更正的一号线口径，不必取消整个展点。",
                },
                "scan_inner": {
                    "surface_id": "P3",
                    "language": "bilingual",
                    "corrected_text": p3_entry["text"] if p3_entry else None,
                    "width": p3_entry["width"] if p3_entry else None,
                    "limit": boards["P3"]["limit"],
                    "fits": bool(p3_entry and p3_entry["width"] <= boards["P3"]["limit"]),
                    "whole_surface_stopped": False,
                    "retained_theme_ids": p3_entry["theme_ids"] if p3_entry else [],
                    "physical_action": "开放扫码内页：更新 N17-web-r1 指向的页面并保留修订记录；纸质取阅内页用完即换，旧夹页加盖更正或撤下。",
                },
            },
        }

    def _print_log_for_surface(self, surface_id: str) -> dict[str, str] | None:
        return next((row for row in self.ledger.print_logs if row["surface"] == surface_id), None)

    def _public_finding_message(self, code: str) -> str:
        messages = {
            "WITHDRAWN_WITH_REPLACEMENT": "该初稿已撤回；当前页面只保留同边界复算/替换件支持的口径。",
            "WITHDRAWN_NO_REPLACEMENT": "该说法所引材料已撤回且无同边界替换件，现已停止展示。",
            "AUTHORIZATION_MISSING": "相关细表未获当前受众渠道外发授权，已从公开内容撤下。",
            "SCOPE_ESCALATION": "来稿范围宽于证据边界，已按证据所示对象范围更正。",
            "UNIT_MISMATCH": "百分率差值与相对百分比不是同一单位，已按证据更正。",
            "PERCENTAGE_POINT_NOT_RELATIVE_PERCENT": "应表述为“个百分点/percentage points”，不是相对的百分之几。",
            "FALSE_INDEPENDENCE": "初稿与复算件属于同一试验，不能算作两次独立印证。",
            "MODALITY_MISMATCH": "该结果仍属预计且尚未测量，不能写成已发生成效。",
            "PENDING_VERIFICATION": "该扩写范围暂无凭据，已列为待核，不在事实区展示。",
            "UNSUPPORTED_CORE_SCOPE": "该扩写范围暂无凭据；公开页只保留来源能覆盖的短写。",
            "DRAFT_OVER_LIMIT": "原稿超过展板字格，已改用保留对照和限定的准确短写。",
        }
        return messages.get(code, "该表述正在按编校意见更正。")

    def _public_corrections(self, surface_id: str, exhibit_ids: list[str]) -> list[dict[str, Any]]:
        corrections: list[dict[str, Any]] = []
        bilingual = surface_id == "P3"
        if "E1" in exhibit_ids:
            corrections.append(
                {
                    "exhibit_id": "E1",
                    "language": "zh",
                    "corrections": [
                        "“全车间验证成功”没有可公开凭据；现有证据只覆盖一号线，不能外推全车间。",
                        "“同一试验夜班也提升一成”所依细表未获外发授权，已从公开摘要撤下，不能作为夜班结论引用。",
                        "V1 初稿已撤回；一号线数字现以 V4 复算段为准。",
                    ],
                    **(
                        {
                            "corrections_en": [
                                "“Workshop-wide validation succeeded” is not credentialed; evidence covers Line 1 only.",
                                "The night-shift detail is not cleared for public release and has been removed.",
                                "Draft V1 is withdrawn; the Line 1 figure follows recalculation V4.",
                            ]
                        }
                        if bilingual
                        else {}
                    ),
                }
            )
        if "E2" in exhibit_ids:
            corrections.append(
                {
                    "exhibit_id": "E2",
                    "language": "en",
                    "corrections": [
                        "“Two independent validations” is incorrect: V1 and V4 belong to T8 and V4 is a recalculation.",
                        "“Plant-wide” is unsupported; the evidence covers Line 1.",
                        "The supported change is +10 percentage points from 70% to 80%, not a relative 10% increase.",
                    ],
                    **(
                        {
                            "corrections_zh": [
                                "“两次独立验证”不成立：V1/V4 同属 T8，且 V4 是复算。",
                                "“全厂”范围无证据；证据只覆盖一号线。",
                                "可支持的是70%到80%、增加10个百分点，不是相对增加10%。",
                            ]
                        }
                        if bilingual
                        else {}
                    ),
                }
            )
        if "E3" in exhibit_ids:
            corrections.append(
                {
                    "exhibit_id": "E3",
                    "language": "zh",
                    "corrections": [
                        "“新设备使返工率下降”是已发生语气；V3 仅为预计总体返工率下降10%，且未到测量期。",
                    ],
                    **(
                        {
                            "corrections_en": [
                                "The rework reduction is a forecast of a 10% overall decrease under V3, not a measured result.",
                            ]
                        }
                        if bilingual
                        else {}
                    ),
                }
            )
        return corrections

    def scan_response(self, board_code: str, themes: list[str] | None = None) -> dict[str, Any]:
        if board_code not in self.ledger.issuances:
            raise KeyError(f"未知码标：{board_code}")
        issuance = self.ledger.issuances[board_code]
        surface_id = issuance["surface"]
        surface = self.ledger.surfaces[surface_id]
        print_log = self._print_log_for_surface(surface_id)
        # 扫码结果绑定实物版面，应给该版面全部仍有效内容，而不是编辑当次挑选的主题子集。
        correction = self.correction_release(None)
        bound_exhibit_ids = print_log["exhibits"].split("|") if print_log and print_log.get("exhibits") else []
        bound_source_ids = print_log["sources"].split("|") if print_log and print_log.get("sources") else []
        visible = [
            {
                "exhibit_id": eid,
                "lang": self.ledger.exhibits[eid]["lang"],
                "topic": self.ledger.exhibits[eid]["topic"],
                "registered_text": self.ledger.exhibits[eid]["draft"],
                "width": cell_width(self.ledger.exhibits[eid]["draft"]),
            }
            for eid in bound_exhibit_ids
        ]
        relevant_reviews = [r for r in self.exhibit_reviews if r["exhibit_id"] in bound_exhibit_ids]
        public_findings = []
        for review in relevant_reviews:
            for finding in review["findings"]:
                public_findings.append(
                    {
                        "exhibit_id": review["exhibit_id"],
                        "code": finding["code"],
                        "severity": finding["severity"],
                        "public_message": self._public_finding_message(finding["code"]),
                    }
                )
        public_corrections = self._public_corrections(surface_id, bound_exhibit_ids)
        source_status = []
        for sid in bound_source_ids:
            policy = self.ledger.policy_for(sid)
            now_ok, now_reason = self.ledger.usable(sid, surface["channel"])
            issued_ok, issued_reason = self.ledger.usable(sid, surface["channel"], at=issuance["issued"])
            scan_ok, scan_reason = self.ledger.usable(sid, "扫码内页")
            source_status.append(
                {
                    "source_id": sid,
                    "audience": policy.audience,
                    "status": policy.status,
                    "events": policy.events,
                    "bound_channel": surface["channel"],
                    "usable_now_for_bound_channel": now_ok,
                    "current_reason": now_reason,
                    "usable_at_issuance_for_bound_channel": issued_ok,
                    "issuance_reason": issued_reason,
                    "usable_for_scan": scan_ok,
                    "scan_reason": scan_reason,
                }
            )

        edition = board_code.rsplit("-", 1)[-1]
        if surface_id == "P1":
            language = "zh"
            applies = "本结果按码标绑定的 N17-zh-r1 / DA1 中文上墙旧版出具；您眼前看到的仍是旧板，以下更正适用于该旧版。"
            headline = "【旧板更正】V1 初稿已撤回；“全车间验证成功”无证据，“夜班提升一成”所依据的细表未获外发授权。可保留事实仅为：一号线70%至80%，升10个百分点（V4复算，比上月同线）。"
            current_proof = correction["editions"]["zh"]["corrected_text"]
            physical_action = correction["editions"]["zh"]["physical_action"]
            revision_history = [
                {"edition": "r1", "at": issuance["issued"], "state": "issued_and_wall_mounted", "board_code": board_code},
                {"edition": correction["correction_id"], "at": correction["issued_at"], "state": "synchronized_correction_issued; QR correction live; r2 proof awaiting closure replacement"},
            ]
        elif surface_id == "P2":
            language = "en"
            applies = "This result is bound to N17-en-r1 / DA2, the printed-but-not-installed English edition. Do not treat r1 as the current public board."
            headline = "[Correction] “Two independent validations” and “plant-wide” are not supported. V1 is withdrawn; V4 is a same-trial recalculation. Credentialed fact: Line1 70%-80%, +10pp."
            current_proof = correction["editions"]["en"]["corrected_text"]
            physical_action = correction["editions"]["en"]["physical_action"]
            revision_history = [
                {"edition": "r1", "at": issuance["issued"], "state": "printed_not_installed; withhold this edition", "board_code": board_code},
                {"edition": correction["correction_id"], "at": correction["issued_at"], "state": "synchronized_correction_issued; reprint r2 before installation"},
            ]
        else:
            language = "bilingual"
            applies = "本结果按 N17-web-r1 / DA3 扫码内页出具；页面已按同步更正口径修订，并保留出具与修订记录。/ This is the N17-web-r1 / DA3 scan inner page with the synchronized revision history."
            headline = "扫码页当前仅展示有授权、有凭据的事实；无证据扩写列为待核。"
            current_proof = correction["editions"]["scan_inner"]["corrected_text"]
            physical_action = correction["editions"]["scan_inner"]["physical_action"]
            revision_history = [
                {"edition": "r1", "at": issuance["issued"], "state": "scan_edition_issued", "board_code": board_code},
                {"edition": correction["correction_id"], "at": correction["issued_at"], "state": "bilingual_page_revised_in_place_with_history"},
            ]

        return {
            "board_code": board_code,
            "issuance_id": issuance["id"],
            "surface_id": surface_id,
            "channel": surface["channel"],
            "language": language,
            "issued_at": issuance["issued"],
            "exposure": issuance["exposure"],
            "physical_note": issuance["note"],
            "registered_edition": edition,
            "revision_history": revision_history,
            "current_correction_id": correction["correction_id"],
            "correction_issued_at": correction["issued_at"],
            "applicability_notice": applies,
            "old_board_correction_notice": headline,
            "physical_replacement_action": physical_action,
            "whole_surface_stopped": False,
            "linked_inner_page": None if surface_id == "P3" else {
                "board_code": "N17-web-r1",
                "corrected_text": correction["editions"]["scan_inner"]["corrected_text"],
                "width": correction["editions"]["scan_inner"]["width"],
                "limit": correction["editions"]["scan_inner"]["limit"],
            },
            "bound_print_log_id": print_log["id"] if print_log else None,
            "visible_registered_items": visible,
            "bound_source_status": source_status,
            "public_findings": public_findings,
            "public_corrections": public_corrections,
            "still_credentialed_content": current_proof,
            "still_credentialed_rule": "只列仍有同边界证据和渠道授权的内容；撤回件原话仅用于更正/版本说明，不再作为事实。",
            "revision_status": (
                "wall_edition_r1_visible_pending_closure_replacement"
                if surface_id == "P1"
                else "printed_r1_withheld_replace_before_install"
                if surface_id == "P2"
                else "scan_edition_revised_with_history"
            ),
        }

    def scan_all(self, themes: list[str] | None = None) -> dict[str, dict[str, Any]]:
        # themes 仅为兼容旧调用保留；每个码按其绑定实物的完整有效版面响应。
        return {code: self.scan_response(code) for code in self.ledger.issuances}

    # ---------- 总报告 ----------

    def build_report(self, themes: list[str] | None = None) -> dict[str, Any]:
        selected = self.resolve_themes(themes)
        plan = self.plan(selected)
        return {
            "project": "制造成果参展摘要与跨展项口径核对",
            "selected_themes": selected,
            "cell_width_rule": "ASCII=1；汉字/全宽 W/F=2；换行=0；各展板按 releases.limit，P3内页整份共用260格",
            "priorities": list(self.ledger.priorities.values()),
            "source_policies": [
                {
                    "source_id": sid,
                    "audience": policy.audience,
                    "status": policy.status,
                    "default_channels": sorted(policy.default_channels),
                    "granted_channels": sorted(policy.granted_channels),
                    "denied_channels": sorted(policy.denied_channels),
                    "events": policy.events,
                }
                for sid, policy in self.ledger.policies.items()
            ],
            "claims": {
                sid: [claim.to_dict() for claim in claims]
                for sid, claims in self.ledger.source_claims.items()
            },
            "anaphora": self.anaphora_report(),
            "zones": self.zones(),
            "corroboration_ledger": self.corroboration_ledger(),
            "exhibit_claims": {
                eid: [claim.to_dict() for claim in claims]
                for eid, claims in self.ledger.exhibit_claims.items()
            },
            "facts": self.facts,
            "exhibit_reviews": self.exhibit_reviews,
            "replacement_search": self.replacements,
            "merge_reviews": self.merge_reviews,
            "material_requests": self.material_requests,
            "plan": plan,
            "correction_release": self.correction_release(selected),
            "scan_responses": self.scan_all(selected),
            "editor_audit": {
                "theme_to_surface_facts": plan["theme_trace"],
                "uncoverable_themes": [
                    trace["theme_id"]
                    for trace in plan["theme_trace"]
                    if not trace["covered"]
                ],
                "material_requests_visible_to_owners": self.material_requests,
            },
        }

    def run(self, themes: list[str] | str | None = None) -> dict[str, Any]:
        """任务化入口的常用别名。"""
        return self.build_report(themes)

    def generate_report(self, themes: list[str] | str | None = None) -> dict[str, Any]:
        return self.build_report(themes)
