#!/usr/bin/env python3
"""项目根入口，等价于 python -m exhibition。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from exhibition.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
