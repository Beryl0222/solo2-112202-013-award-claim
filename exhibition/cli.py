"""命令行入口：生成 JSON/Markdown 编校报告或解析单个扫码码。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .report import render_markdown
from .service import EditorialService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="制造成果参展摘要与跨展项口径核对")
    parser.add_argument("--directory", type=Path, default=None, help="资料包目录，默认使用 ./materials")
    parser.add_argument(
        "--themes",
        default=None,
        help="编辑当次选中的主题编号或名称，逗号分隔；默认 T1,T2,T3",
    )
    parser.add_argument(
        "--theme",
        action="append",
        help="可重复传入的主题编号或名称，例如 --theme T1 --theme T2",
    )
    parser.add_argument("--out-dir", type=Path, default=Path("out"), help="报告输出目录")
    parser.add_argument("--scan", help="只输出指定 board_code 的扫码版本响应")
    parser.add_argument(
        "--merge-decision",
        action="append",
        default=[],
        help="记录合并/单独保留决定，格式 MRG-ID=drop_external 或 retain_internal_only",
    )
    parser.add_argument("--no-write", action="store_true", help="只打印摘要，不写报告文件")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.theme:
        themes = list(args.theme)
    elif args.themes:
        themes = [item.strip() for item in str(args.themes).split(",") if item.strip()]
    else:
        themes = ["T1", "T2", "T3"]
    service = EditorialService(args.directory)
    for item in args.merge_decision:
        if "=" not in item:
            raise SystemExit("--merge-decision 必须采用 MRG-ID=decision 格式")
        review_id, decision = item.split("=", 1)
        try:
            service.decide_merge(review_id.strip(), decision.strip(), editor="cli")
        except (PermissionError, ValueError) as exc:
            raise SystemExit(f"编校决定未被接受：{exc}") from exc

    if args.scan:
        payload = service.scan_response(args.scan, themes)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    report = service.build_report(themes)
    markdown = render_markdown(report)

    if not args.no_write:
        out_dir = args.out_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "editorial_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (out_dir / "editorial_report.md").write_text(markdown, encoding="utf-8")

    for board in report["plan"]["boards"]:
        status = "OK" if board["used_cells"] <= board["limit"] else "OVER"
        print(f"[{status}] {board['surface_id']} {board['channel']}: {board['used_cells']}/{board['limit']}")
        for entry in board["entries"]:
            print(f"  {entry['entry_id']}: {entry['text']}")
        for omitted in board["omitted_themes"]:
            print(f"  UNCOVERED {omitted['theme_id']}: {omitted['reason']}")
    print("未覆盖主题：", ", ".join(report["editor_audit"]["uncoverable_themes"]) or "无")
    if not args.no_write:
        print(f"报告已写入：{args.out_dir / 'editorial_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
