"""中英双语文本的透明规则抽取。

下一届材料若出现新措辞，可在本模块的词典/正则中扩展；所有结论都保留原行 id 与原话。
规则只负责取出可核对结构，不直接决定能否发布。
"""
from __future__ import annotations

import re
from typing import Any

from .models import Claim

ZH_NUM = {
    "零": 0.0,
    "一": 1.0,
    "二": 2.0,
    "两": 2.0,
    "三": 3.0,
    "四": 4.0,
    "五": 5.0,
    "六": 6.0,
    "七": 7.0,
    "八": 8.0,
    "九": 9.0,
    "十": 10.0,
}
EN_NUM = {
    "one": 1.0,
    "two": 2.0,
    "three": 3.0,
    "four": 4.0,
    "five": 5.0,
    "six": 6.0,
    "seven": 7.0,
    "eight": 8.0,
    "nine": 9.0,
    "ten": 10.0,
}

PERCENT = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*(?:%|％)")
PERCENT_PHRASE_ZH = re.compile(r"百分之\s*([0-9]+(?:\.[0-9]+)?|[零一二两三四五六七八九十]+)")
CLAUSE_SPLIT = re.compile(r"[。！？!?；;，,\n]+")

DELTA_ZH = re.compile(
    r"(提升|提高|上升|增长|增加|增多|下降|降低|减少|减|降|回落)"
    r"\s*([0-9]+(?:\.[0-9]+)?|[零一二两三四五六七八九十]+)?"
    r"\s*(个百分点|百分点|％|%|成)?"
)
DELTA_EN = re.compile(
    r"\b(rose|risen|increased?|gained|up|improved|fell|fallen|dropped|declined|decreased|down)\b"
    r"(?:\s+by)?\s*"
    r"([0-9]+(?:\.[0-9]+)?|one|two|three|four|five|six|seven|eight|nine|ten)?"
    r"\s*(percentage points?|pp|percent|%)?",
    re.IGNORECASE,
)
NOUN_DELTA_EN = re.compile(
    r"\b([0-9]+(?:\.[0-9]+)?|one|two|three|four|five|six|seven|eight|nine|ten)\s*(%|percent)?\s*"
    r"([A-Za-z\- ]{0,50}?)\b(increase|rise|gain|improvement|decrease|fall|decline|drop)\b",
    re.IGNORECASE,
)


def lang_of(text: str, declared: str | None = None) -> str:
    if declared in {"zh", "en"}:
        return declared
    return "zh" if re.search(r"[一-鿿]", text or "") else "en"


def parse_number(token: str | None) -> float | None:
    if token is None:
        return None
    token = token.strip()
    if not token:
        return None
    try:
        return float(token)
    except ValueError:
        pass
    low = token.lower()
    if low in EN_NUM:
        return EN_NUM[low]
    if token in ZH_NUM:
        return ZH_NUM[token]
    # 简单支持“十六”“二十”等材料中可能出现的中文数字。
    if token.startswith("十") and len(token) == 2:
        return 10.0 + ZH_NUM.get(token[1], 0.0)
    if token.endswith("十") and len(token) == 2:
        return ZH_NUM.get(token[0], 1.0) * 10.0
    if "十" in token and len(token) == 3:
        left, right = token.split("十")
        return ZH_NUM.get(left, 1.0) * 10.0 + ZH_NUM.get(right, 0.0)
    return None


def split_clauses(text: str) -> list[str]:
    return [part.strip() for part in CLAUSE_SPLIT.split(text or "") if part and part.strip()]


def metric_from_text(text: str) -> str | None:
    if re.search(r"返工率|返工|rework", text, re.IGNORECASE):
        return "rework_rate"
    if re.search(r"良率|合格率|yield", text, re.IGNORECASE):
        return "yield"
    if re.search(r"同名指标|same[- ]named metric", text, re.IGNORECASE):
        return "same_named_metric"
    return None


def scope_from_text(text: str) -> dict[str, Any]:
    scope: dict[str, Any] = {}
    if re.search(r"一号线|第一条线|同一条一号线|first[- ]line|Line\s*1\b", text, re.IGNORECASE):
        scope["line"] = "L1"
    elif re.search(r"二号线|第二条线|Line\s*2\b", text, re.IGNORECASE):
        scope["line"] = "L2"

    if re.search(r"夜班|night", text, re.IGNORECASE):
        scope["shift"] = "night"
    elif re.search(r"日班|白班|day shift|days?\b", text, re.IGNORECASE):
        scope["shift"] = "day"
    if re.search(r"两班|日夜合计|日夜|day\s*[+＋]\s*night|both shifts?", text, re.IGNORECASE):
        scope["shift"] = "both"
        scope["aggregation"] = "day_night_total"

    if re.search(r"全厂|plant[- ]wide|plantwide", text, re.IGNORECASE):
        scope["scale"] = "plant"
    elif re.search(r"全车间|全部车间|整个车间|workshop[- ]wide", text, re.IGNORECASE):
        scope["scale"] = "workshop"
    elif re.search(r"总体|整体|overall|total", text, re.IGNORECASE):
        scope["scale"] = "overall"
    elif scope.get("line"):
        scope["scale"] = "line"

    if re.search(r"试件车间", text):
        scope["parent_site"] = "trial_workshop"
    if re.search(r"首次用新装备|新设备|new equipment|first use", text, re.IGNORECASE):
        scope["phase"] = "new_equipment_first_use"
    if re.search(r"首次换型|换型后|转工装|tooling change|changeover", text, re.IGNORECASE):
        scope["phase"] = "after_changeover"
    if re.search(r"工单只在日班采集|day[- ]only (?:collection|work orders)", text, re.IGNORECASE):
        scope["collection_boundary"] = "day_shift_work_orders_only"
    if re.search(r"全部车间没纳入试验|workshops? (?:were )?not included", text, re.IGNORECASE):
        scope["trial_inclusion"] = "all_workshops_not_included"
    return scope


def comparator_from_text(text: str) -> tuple[str | None, str | None, list[dict[str, str]]]:
    codes: list[str] = []
    phrases: list[str] = []
    anaphora: list[dict[str, str]] = []

    patterns = [
        (r"比上月同线|versus? prior[- ]month same line|vs\.? prior[- ]month same line", "prior_month_same_line", "比上月同线"),
        (r"同一周|一周对照|same week|one-week", "same_week", "同一周/一周对照"),
        (r"同期|same period", "same_period", "同期"),
        (r"较上期|上期|prior period|previous period", "prior_period", "较上期"),
        (r"同一试验|same (?:night )?trial", "same_trial", "同一试验"),
        (r"该线|此线|the line", "anaphoric_line", "该线"),
        (r"同名指标|same[- ]named metric", "anaphoric_metric", "同名指标"),
    ]
    for pattern, code, phrase in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if code not in codes:
                codes.append(code)
            phrases.append(match.group(0))
            if code.startswith("anaphoric") or code in {"same_period", "same_trial"}:
                anaphora.append({"phrase": match.group(0), "refers_to": "contextual_reference"})
    comparator = "+".join(codes) if codes else None
    time_phrase = "；".join(phrases) if phrases else None
    return comparator, time_phrase, anaphora


def _direction(word: str | None) -> str | None:
    if not word:
        return None
    word = word.lower()
    if word in {"下降", "降低", "减少", "减", "降", "回落", "fell", "fallen", "dropped", "declined", "decreased", "down", "decrease", "fall", "decline", "drop"}:
        return "down"
    return "up"


def _unit(unit: str | None, number: float | None) -> tuple[float | None, str | None]:
    if unit is None:
        return number, None
    if unit in {"个百分点", "百分点", "percentage point", "percentage points", "pp"}:
        return number, "percentage_point"
    if unit == "成":
        return (number or 0.0) * 10.0, "relative_percent"
    if unit in {"%", "％", "percent"}:
        return number, "percent"
    return number, unit


def _common_kwargs(row: dict[str, str], text: str, lang: str, refs: list[str]) -> dict[str, Any]:
    comparator, time_phrase, anaphora = comparator_from_text(text)
    modality = "unknown"
    if row.get("plan") == "预估" or re.search(r"预计|预期|预估|有望|expected|forecast|projected", text, re.IGNORECASE):
        modality = "expected"
    elif row.get("plan") == "观察" or re.search(r"观察|observed|measured", text, re.IGNORECASE):
        modality = "observed"
    measured: bool | None = None
    if modality == "expected":
        measured = False
    if re.search(r"未到测量期|没有出正式报告|尚未测量|unmeasured|not yet measured|no formal report", text, re.IGNORECASE):
        measured = False
    provisional = bool(re.search(r"暂填|约\s*\d|没有出正式报告|provisional|no formal report", text))
    return {
        "lang": lang,
        "quote": text,
        "modality": modality,
        "measured": measured,
        "comparator": comparator,
        "time_phrase": time_phrase,
        "anaphora": anaphora,
        "explicit_refs": refs,
        "trial": row.get("trial") or None,
        "provisional": provisional,
    }


def extract_record(row: dict[str, str], kind: str = "source") -> list[Claim]:
    """kind=source 时读取 text/trial/plan；kind=exhibit 时读取 lang/topic/draft/refs。"""
    record_id = row["id"]
    text = row.get("text") if kind == "source" else row.get("draft", "")
    text = text or ""
    declared_lang = row.get("lang") if kind == "exhibit" else None
    lang = lang_of(text, declared_lang)
    refs = [item for item in (row.get("refs") or row.get("relates") or "").split("|") if item]
    common = _common_kwargs(row, text, lang, refs)
    if kind == "exhibit" and common["modality"] == "unknown":
        # 展项稿没有“预计/预期”等标记，却用直陈语气报道数量，编校上按主张已观察处理。
        common["modality"] = "asserted_observed"
    global_scope = scope_from_text(text)
    global_metric = metric_from_text(text)
    clauses = split_clauses(text)
    claims: list[Claim] = []
    last_line: str | None = None
    measurement_clause_count = 0

    # 先统计含数字的分句，便于处理 V5 这类范围落在相邻分句的文本。
    numeric_clauses = [clause for clause in clauses if PERCENT.search(clause) or DELTA_ZH.search(clause) or DELTA_EN.search(clause) or NOUN_DELTA_EN.search(clause)]
    only_one_numeric = len(numeric_clauses) == 1

    for clause_index, clause in enumerate(clauses, start=1):
        clause_scope = scope_from_text(clause)
        if clause_scope.get("line"):
            last_line = clause_scope["line"]
        elif last_line and PERCENT.search(clause):
            clause_scope["line"] = last_line
            clause_scope.setdefault("scale", "line")
        if only_one_numeric and PERCENT.search(clause) and "shift" not in clause_scope and global_scope.get("shift"):
            clause_scope["shift"] = global_scope["shift"]
            if global_scope.get("aggregation"):
                clause_scope["aggregation"] = global_scope["aggregation"]
        metric = metric_from_text(clause) or global_metric

        percentages = [float(value) for value in PERCENT.findall(clause)]
        delta_value = None
        delta_unit = None
        direction = None

        zh_match = DELTA_ZH.search(clause)
        en_match = DELTA_EN.search(clause)
        noun_match = NOUN_DELTA_EN.search(clause)
        percent_phrase_match = PERCENT_PHRASE_ZH.search(clause)
        if zh_match:
            direction = _direction(zh_match.group(1))
            number = parse_number(zh_match.group(2))
            unit = zh_match.group(3)
            if number is None and percent_phrase_match:
                number = parse_number(percent_phrase_match.group(1))
            if unit is None and percent_phrase_match:
                unit = "%"
            delta_value, delta_unit = _unit(unit, number)
        elif en_match and en_match.group(2):
            direction = _direction(en_match.group(1))
            number = parse_number(en_match.group(2))
            delta_value, delta_unit = _unit(en_match.group(3), number)
        elif noun_match:
            number = parse_number(noun_match.group(1))
            delta_value, delta_unit = _unit(noun_match.group(2) or "%", number)
            direction = _direction(noun_match.group(4))

        baseline = current = None
        if len(percentages) >= 2:
            if re.search(r"之前|before", clause, re.IGNORECASE) and re.search(r"之后|after", clause, re.IGNORECASE):
                baseline, current = percentages[0], percentages[1]
            elif re.search(r"由|从|from", clause) and re.search(r"到|至|to", clause):
                baseline, current = percentages[0], percentages[1]
            else:
                baseline, current = percentages[0], percentages[1]
        elif len(percentages) == 1 and delta_value is None and re.search(r"之前|before", clause):
            baseline = percentages[0]
        elif len(percentages) == 1 and delta_value is None and re.search(r"之后|after", clause):
            current = percentages[0]

        relative_pct = None
        if baseline is not None and current is not None:
            computed_pp = current - baseline
            if delta_value is None or delta_unit is None:
                delta_value = computed_pp
                delta_unit = "percentage_point"
            if baseline:
                relative_pct = (current - baseline) / baseline * 100.0
            if direction is None:
                direction = "up" if computed_pp >= 0 else "down"
        elif delta_unit == "relative_percent":
            relative_pct = delta_value

        is_measurement = baseline is not None or current is not None or delta_value is not None
        if is_measurement:
            measurement_clause_count += 1
            claim_id = f"{record_id}-C{len(claims) + 1}"
            claims.append(
                Claim(
                    claim_id=claim_id,
                    record_id=record_id,
                    **common,
                    claim_type="measurement",
                    metric=metric,
                    subject=clause_scope.get("line") or clause_scope.get("scale"),
                    scope=clause_scope,
                    baseline=baseline,
                    current=current,
                    delta=abs(delta_value) if delta_value is not None else None,
                    delta_unit=delta_unit,
                    relative_pct=abs(relative_pct) if relative_pct is not None else None,
                    direction=direction,
                )
            )

        if re.search(r"验证成功|得到验证|validations? confirm|independently confirm|verified", clause, re.IGNORECASE):
            validation_scope = scope_from_text(clause)
            claimed_count = None
            count_match = re.search(r"([0-9]+|[Tt]wo|[Oo]ne)\s+(?:independent\s+)?validations?", clause)
            if count_match:
                claimed_count = int(parse_number(count_match.group(1)) or 0) or None
            if claimed_count:
                validation_scope["claimed_validation_count"] = claimed_count
                validation_scope["claimed_independent"] = bool(re.search(r"independent", clause, re.IGNORECASE))
            claims.append(
                Claim(
                    claim_id=f"{record_id}-C{len(claims) + 1}",
                    record_id=record_id,
                    **common,
                    claim_type="validation",
                    metric=metric or "yield",
                    subject=validation_scope.get("scale") or validation_scope.get("line"),
                    scope=validation_scope,
                )
            )

    if not claims:
        claims.append(Claim(claim_id=f"{record_id}-C1", record_id=record_id, **common, metric=global_metric, scope=global_scope))

    # 逗号会把“之前是92%，之后是91%”拆成两个半句；将相邻的基线/现值合并为一条主张。
    merged_claims: list[Claim] = []
    for claim in claims:
        previous = merged_claims[-1] if merged_claims else None
        can_merge = (
            previous is not None
            and previous.claim_type == "measurement"
            and claim.claim_type == "measurement"
            and previous.baseline is not None
            and previous.current is None
            and claim.baseline is None
            and claim.current is not None
            and previous.scope.get("line") == claim.scope.get("line")
        )
        if can_merge and previous is not None:
            previous.current = claim.current
            computed = previous.current - previous.baseline
            previous.delta = abs(computed)
            previous.delta_unit = "percentage_point"
            previous.direction = "up" if computed >= 0 else "down"
            if previous.baseline:
                previous.relative_pct = abs(computed / previous.baseline * 100.0)
        else:
            merged_claims.append(claim)
    claims = merged_claims

    # 单条数量主张可安全继承全局班次；多条时不能把夜班范围倒灌给白班/总线主张。
    numeric_claims = [claim for claim in claims if claim.claim_type == "measurement"]
    if len(numeric_claims) == 1 and global_scope.get("shift"):
        claim = numeric_claims[0]
        claim.scope.setdefault("shift", global_scope["shift"])
        if global_scope.get("aggregation"):
            claim.scope.setdefault("aggregation", global_scope["aggregation"])
        if global_scope.get("collection_boundary"):
            claim.scope.setdefault("collection_boundary", global_scope["collection_boundary"])
    return claims
