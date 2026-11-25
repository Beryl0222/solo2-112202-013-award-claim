"""资料包装载；复用 pack_check 的格式和引用校验。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pack_check import DEFAULT_DATA, read_tables  # noqa: E402

__all__ = ["DEFAULT_DATA", "read_tables", "load_pack"]


def load_pack(directory: Path | str | None = None) -> dict[str, list[dict[str, str]]]:
    target = Path(directory) if directory is not None else DEFAULT_DATA
    return read_tables(target)
