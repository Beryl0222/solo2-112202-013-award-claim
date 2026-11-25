"""把编校报告渲染成负责人可读的 Markdown。"""
from __future__ import annotations

from typing import Any


def _width_ok(width: int, limit: int) -> str:
    return "✅" if width <= limit else "❌"


def render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# 参展摘要编校报告")
    lines.append("")
    lines.append(f"选中主题：{', '.join(report['selected_themes'])}")
    lines.append("")

    lines.append("## 一、中英版面与字格")
    for board in report["plan"]["boards"]:
        lines.append(
            f"### {board['surface_id']} · {board['channel']}（{board['language']}） "
            f"{board['used_cells']}/{board['limit']} 格 {_width_ok(board['used_cells'], board['limit'])}"
        )
        for entry in board["entries"]:
            lines.append("")
            lines.append(f"- `{entry['entry_id']}`，{entry['width']} 格，主题 {','.join(entry['theme_ids'])}")
            lines.append("")
            lines.append("```text")
            lines.append(entry["text"])
            lines.append("```")
        for omitted in board["omitted_themes"]:
            lines.append(
                f"- ⚠️ 未覆盖 {omitted['theme_id']}（{omitted['theme']}）：{omitted['reason']}；"
                f"补件请求：{', '.join(omitted.get('request_ids', [])) or '无'}"
            )
        lines.append("")

    check = report["plan"]["shared_sentence_check"]
    lines.append("## 二、一句短写覆盖两项主题校验")
    if check.get("evaluated"):
        lines.append(f"- 结论：{'可行' if check['one_sentence_may_cover_two_themes'] else '当前不可行'}")
        lines.append(f"- 语言支持：{check['language_support']}")
        lines.append(f"- 规则：{check['rule']}")
        if check.get("failure_reason"):
            lines.append(f"- 原因：{check['failure_reason']}")
    else:
        lines.append(f"- {check.get('reason', '未检查')}")
    lines.append("")

    lines.append("## 三、合并会失去的限制与原话")
    for review in report["merge_reviews"]:
        lines.append(f"### {review['review_id']}（试验 {review['trial_id']}）")
        lines.append("- 不建议合并；以下限制必须分别保留：")
        for limit in review["lost_limits_if_merged"]:
            lines.append(f"  - {limit}")
        lines.append(f"- 同试验独立印证数：{review['same_trial_independent_count']}")
        lines.append(f"- 当前有效决定：{review['effective_decision']}")
        lines.append("- 原话：")
        for quote in review["original_quotes"]:
            lines.append(f"  - `{quote['source_id']}`：{quote['quote']}")
        lines.append("")

    lines.append("## 四、展项核对发现")
    for review in report["exhibit_reviews"]:
        if not review["findings"]:
            continue
        lines.append(f"### {review['exhibit_id']} · {review['topic']}（{review['lang']}）")
        lines.append(f"来稿：{review['draft']}")
        for finding in review["findings"]:
            lines.append(f"- [{finding['severity']}] `{finding['code']}` {finding['message']}")
        lines.append("")

    lines.append("## 五、需向展项负责人补交资料的范围")
    for request in report["material_requests"]:
        lines.append(f"### {request['request_id']} · {request['exhibit_id']} · {request['theme']}")
        if request.get("also_exhibit_ids"):
            lines.append(f"- 同时关联：{', '.join(request['also_exhibit_ids'])}")
        lines.append(f"- 需要范围：{request['needed_scope']}")
        lines.append(f"- 可接受证据：{request['acceptable_evidence']}")
        for candidate in request["rejected_candidates"]:
            lines.append(f"- 不能替代：`{candidate['source_id']}` — {candidate['reason']}")
        lines.append("")

    correction = report["correction_release"]
    lines.append("## 六、同步更正签发与实物动作")
    lines.append(f"- 更正签发号：{correction['correction_id']}")
    lines.append(f"- 同步签发时间：{correction['issued_at']}")
    for lang, edition in correction["editions"].items():
        lines.append(f"### {lang} · {edition['surface_id']}")
        if edition.get("corrected_text"):
            lines.append(f"- 字格：{edition['width']}/{edition['limit']}，排得下：{edition['fits']}")
            lines.append("```text")
            lines.append(edition["corrected_text"])
            lines.append("```")
        lines.append(f"- 实物动作：{edition['physical_action']}")
    lines.append("")

    lines.append("## 七、扫码版本响应")
    for code, response in report["scan_responses"].items():
        lines.append(f"### {code} · {response['issuance_id']} · {response['revision_status']}")
        lines.append(f"- 出具时间：{response['issued_at']}；更正时间：{response['correction_issued_at']}")
        lines.append(f"- 适用版本：{response['applicability_notice']}")
        lines.append(f"- 纠正提示：{response['old_board_correction_notice']}")
        lines.append(f"- 换稿动作：{response['physical_replacement_action']}")
        lines.append("- 仍有凭据内容：")
        lines.append("```text")
        lines.append(str(response["still_credentialed_content"]))
        lines.append("```")
    lines.append("")

    lines.append("## 八、编辑主题回查")
    for trace in report["editor_audit"]["theme_to_surface_facts"]:
        status = "已覆盖" if trace["covered"] else "未覆盖"
        lines.append(f"### {trace['theme_id']} · {trace['theme']}（{trace['importance']}）— {status}")
        lines.append(f"- 关联展项：{', '.join(trace.get('exhibit_ids', []))}")
        for surface in trace["surfaces"]:
            lines.append(f"- {surface['channel']}：{surface['status']}")
            for fact in surface.get("expressed_facts", []):
                scope = fact["scope"]
                lines.append(
                    f"  - 事实 `{fact['fact_id']}`：{fact['metric']} "
                    f"{fact['baseline']}→{fact['current']} delta={fact['delta']}{fact['delta_unit']} "
                    f"modality={fact['modality']} comparator={fact['comparator']} trial={fact['trial']} source={fact['source_id']}"
                )
        if trace["material_request_ids"]:
            lines.append(f"- 需补材料：{', '.join(trace['material_request_ids'])}")
    return "\n".join(lines)
