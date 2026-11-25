"""字格计量与短写适配工具。

资料包把 limit 定义为半宽字格：ASCII 字符占 1 格，汉字和全宽字符占 2 格。
换行不构成可见字格；组合记号按 0 格处理。
"""
from __future__ import annotations

from unicodedata import combining, east_asian_width


def cell_width(text: object) -> int:
    """返回一段文本占用的半宽字格数。"""
    if text is None:
        return 0
    total = 0
    for char in str(text):
        if char in "\r\n":
            continue
        if combining(char):
            continue
        total += 2 if east_asian_width(char) in {"W", "F"} else 1
    return total


def fits(text: object, limit: int) -> bool:
    return cell_width(text) <= int(limit)


# 常见命名别名，方便下一届脚本或测试按习惯调用。
display_width = cell_width
text_width = cell_width
width = cell_width


def require_fit(text: object, limit: int) -> None:
    width = cell_width(text)
    if width > int(limit):
        raise ValueError(f"文案占 {width} 格，超过登记上限 {limit} 格")


def shorten_or_none(candidates, limit: int):
    """从按准确度/完整性排序的候选短写中取第一个能排下的。"""
    for candidate in candidates:
        if candidate is not None and fits(candidate, limit):
            return candidate
    return None
