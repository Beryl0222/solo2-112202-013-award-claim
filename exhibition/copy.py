"""由结构化事实生成受字格约束的准确短写。"""
from __future__ import annotations

from typing import Any

from .geometry import cell_width

METRIC_ZH = {"yield": "良率", "rework_rate": "返工率"}
METRIC_EN = {"yield": "Yield", "rework_rate": "Rework rate"}
LINE_ZH = {"L1": "一号线", "L2": "二号线"}
LINE_EN = {"L1": "Line1", "L2": "Line2"}


def n(value: float | int | None) -> str:
    if value is None:
        return "?"
    return f"{value:g}"


def zh_number(value: float | int | None) -> str:
    """版面优先使用中文数字；超出简单表时退回阿拉伯数字以保证准确。"""
    if value is None:
        return "?"
    if float(value).is_integer():
        integer = int(value)
        digits = "零一二三四五六七八九"
        if 0 <= integer <= 10:
            return "十" if integer == 10 else digits[integer]
        if 11 <= integer <= 19:
            return "十" + digits[integer - 10]
        if 20 <= integer < 100 and integer % 10 == 0:
            return digits[integer // 10] + "十"
    return n(value)


def line_zh(fact: dict[str, Any]) -> str:
    line = fact.get("scope", {}).get("line")
    if line in LINE_ZH:
        return LINE_ZH[line]
    scale = fact.get("scope", {}).get("scale")
    return {"plant": "全厂", "workshop": "全车间", "overall": "总体"}.get(scale, "该项")


def line_en(fact: dict[str, Any]) -> str:
    line = fact.get("scope", {}).get("line")
    if line in LINE_EN:
        return LINE_EN[line]
    scale = fact.get("scope", {}).get("scale")
    return {"plant": "Plant-wide", "workshop": "Workshop-wide", "overall": "Overall"}.get(scale, "Item")


def comparator_zh(fact: dict[str, Any], short: bool = True) -> str | None:
    code = fact.get("comparator") or ""
    if "prior_month_same_line" in code:
        return "比上月同线"
    if "prior_period" in code:
        return "较上期"
    if "same_week" in code and not short:
        return "同一周对照"
    if "same_period" in code:
        return "同期口径"
    if "same_week" in code:
        return "同周对照"
    return fact.get("time_phrase")


def comparator_en(fact: dict[str, Any]) -> str | None:
    code = fact.get("comparator") or ""
    if "prior_month_same_line" in code and "same_week" in code:
        return "week vs prior-month same line"
    if "prior_month_same_line" in code:
        return "vs prior-month same line"
    if "prior_period" in code:
        return "vs prior period"
    if "same_period" in code:
        return "same period"
    if "same_week" in code:
        return "same-week check"
    return None


def board_comparator_en(fact: dict[str, Any]) -> str:
    code = fact.get("comparator") or ""
    if "prior_month_same_line" in code:
        return "vs prior-month same line"
    if "prior_period" in code:
        return "vs prior period"
    if "same_period" in code:
        return "same period baseline"
    if "same_week" in code:
        return "same-week check"
    return "vs registered baseline"


def board_candidates_zh(fact: dict[str, Any]) -> list[str]:
    title = METRIC_ZH.get(fact.get("metric"), "指标")
    obj = line_zh(fact)
    base, cur, delta = n(fact.get("baseline")), n(fact.get("current")), n(fact.get("delta"))
    sid = fact["source_id"]
    comp = comparator_zh(fact) or "按登记基线"
    direction = "升" if fact.get("direction") != "down" else "降"
    sign = "+" if fact.get("direction") != "down" else "-"
    recalc = "复算" if fact.get("recalculation") else "据"
    return [
        f"{title}：{obj}{base}%至{cur}%，{direction}{zh_number(delta)}个百分点；{recalc}{sid}，{comp}",
        f"{title}:{obj}{base}%-{cur}%,{sign}{delta}个百分点;{recalc}{sid},{comp}",
        f"{title}:{obj}{base}%-{cur}%,{sign}{delta}个百分点;{recalc},{comp}",
        f"{title}:{obj}{base}%-{cur}%,{sign}{delta}pp;{comp}",
    ]


def board_candidates_en(fact: dict[str, Any]) -> list[str]:
    title = METRIC_EN.get(fact.get("metric"), "Metric")
    obj = line_en(fact)
    base, cur, delta = n(fact.get("baseline")), n(fact.get("current")), n(fact.get("delta"))
    sid = fact["source_id"]
    comp = comparator_en(fact) or "against registered baseline"
    board_comp = board_comparator_en(fact)
    sign = "+" if fact.get("direction") != "down" else "-"
    trial = fact.get("trial") or "same trial"
    predecessor = fact.get("withdrawn_predecessor")
    predecessor_note = f" {predecessor} withdrawn;" if predecessor else ""
    parenthetical_parts = [f"{sid} recalc", board_comp]
    if predecessor:
        parenthetical_parts.append(f"{predecessor} withdrawn")
    parenthetical_parts.append("1 trial")
    full_unit = (
        f"{title}: {obj} {base}-{cur}%, {sign}{delta} percentage points "
        f"({'; '.join(parenthetical_parts)})."
    )
    return [
        full_unit,
        f"{title}: {obj} {base}%-{cur}%, {sign}{delta}pp. {sid} recalc,{trial}; {comp}.{predecessor_note} one trial.",
        f"{title}: {obj} {base}-{cur}%, {sign}{delta}pp ({sid}; {comp}; one {trial} trial).",
        f"{title}: {obj} {base}-{cur}%, {sign}{delta}pp ({comp}).",
    ]


def choose_candidate(candidates: list[str], limit: int) -> dict[str, Any] | None:
    for text in candidates:
        width = cell_width(text)
        if width <= limit:
            return {"text": text, "width": width}
    return None


def yield_inner_zh(fact: dict[str, Any]) -> str:
    comp = comparator_zh(fact) or "登记基线"
    return f"一号线{n(fact.get('baseline'))}%-{n(fact.get('current'))}%，+{n(fact.get('delta'))}个百分点（复算{fact['source_id']}；{comp}）。"


def yield_inner_en(fact: dict[str, Any]) -> str:
    comp = comparator_en(fact) or "registered baseline"
    return f"Line1 {n(fact.get('baseline'))}-{n(fact.get('current'))}%,+{n(fact.get('delta'))}pp({fact['source_id']} recalc;{comp})."


def rework_inner_zh(fact: dict[str, Any]) -> str:
    status = "预计" if fact.get("modality") == "expected" else ""
    measured = "，尚未测量" if fact.get("measured") is False else ""
    sign = "-" if fact.get("direction") == "down" else "+"
    return f"返工{status}总体{sign}{n(fact.get('delta'))}%（{fact['source_id']}{measured}）。"


def rework_inner_en(fact: dict[str, Any]) -> str:
    modality = "forecast " if fact.get("modality") == "expected" else ""
    measured = ",unmeasured" if fact.get("measured") is False else ""
    sign = "-" if fact.get("direction") == "down" else "+"
    return f"Rework: {modality}overall {sign}{n(fact.get('delta'))}%({fact['source_id']}{measured})."


def inner_page_text(theme_ids: list[str], facts_by_theme: dict[str, dict[str, Any] | None]) -> str:
    zh = ["中："]
    en = ["EN:"]
    if "T1" in theme_ids and facts_by_theme.get("T1"):
        fact = facts_by_theme["T1"]
        zh.append(yield_inner_zh(fact))
        en.append(yield_inner_en(fact))
    if "T2" in theme_ids and facts_by_theme.get("T2"):
        fact = facts_by_theme["T2"]
        zh.append(rework_inner_zh(fact))
        en.append(rework_inner_en(fact))

    lines = ["".join(zh), " ".join(en)]
    t1 = facts_by_theme.get("T1")
    if "T1" in theme_ids and t1 and t1.get("withdrawn_predecessor"):
        lines.append(f"{t1['withdrawn_predecessor']}初稿撤回；{t1['withdrawn_predecessor']}/{t1['source_id']}同{t1.get('trial')}。")
        lines.append(
            f"{t1['withdrawn_predecessor']} withdrawn; {t1['withdrawn_predecessor']}/{t1['source_id']} same {t1.get('trial')} trial."
        )
    return "\n".join(lines)
