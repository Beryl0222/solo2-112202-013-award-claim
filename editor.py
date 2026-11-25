"""编辑工作流入口的模块别名。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from exhibition.service import EditorialService  # noqa: E402

Editor = EditorialService

__all__ = ["EditorialService", "Editor"]
