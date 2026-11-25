"""兼容性别名：部分接稿脚本可能以 solution 作为项目入口。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from exhibition import EditorialService, cell_width, publish_selected_themes  # noqa: E402
from exhibition.geometry import display_width, text_width  # noqa: E402

ExhibitionEditor = EditorialService
analyze_pack = publish_selected_themes
analyze = publish_selected_themes
run = publish_selected_themes

__all__ = [
    "EditorialService",
    "ExhibitionEditor",
    "publish_selected_themes",
    "analyze_pack",
    "analyze",
    "run",
    "cell_width",
    "display_width",
    "text_width",
]
