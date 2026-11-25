"""制造成果参展摘要与跨展项口径核对项目。"""
from .geometry import cell_width, fits
from .io import load_pack
from .metrics import rate_change
from .service import EditorialService


def publish_selected_themes(themes=None, directory=None):
    """便捷入口：接收编辑选中的主题，返回完整编校与发布报告。"""
    return EditorialService(directory).build_report(themes)


__all__ = ["EditorialService", "publish_selected_themes", "cell_width", "fits", "load_pack", "rate_change"]
__version__ = "1.0.0"
