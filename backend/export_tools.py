# -*- coding: utf-8 -*-
"""准备清单导出（C 侧，10/30）：服务端生成 CSV / Markdown 下载内容。"""
import csv
import io


def _source_text(item):
    ref = item.get("source_ref") or {}
    return ref.get("quote") or ""


def _title(record):
    return record.get("title") or "准备清单"


def export_prepare_list_csv(record: dict) -> str:
    """返回带 UTF-8 BOM 的 CSV 文本，Excel 打开中文不乱码。"""
    record = record or {}
    out = io.StringIO(newline="")
    writer = csv.writer(out)
    writer.writerow(["序号", "事项", "状态", "材料ID", "原文依据"])
    for index, todo in enumerate(record.get("todo_list") or [], 1):
        if not isinstance(todo, dict):
            continue
        writer.writerow([
            index,
            todo.get("action") or "",
            todo.get("status") or "pending",
            todo.get("material_id") or "",
            _source_text(todo),
        ])
    return "\ufeff" + out.getvalue()


def export_prepare_list_markdown(record: dict) -> str:
    record = record or {}
    lines = ["# %s" % _title(record), ""]
    if record.get("summary"):
        lines.extend(["> %s" % record["summary"], ""])
    lines.append("| 序号 | 事项 | 状态 | 原文依据 |")
    lines.append("| ---: | --- | --- | --- |")
    for index, todo in enumerate(record.get("todo_list") or [], 1):
        if not isinstance(todo, dict):
            continue
        quote = _source_text(todo).replace("|", "\\|").replace("\n", " ")
        action = (todo.get("action") or "").replace("|", "\\|").replace("\n", " ")
        lines.append("| %d | %s | %s | %s |" % (
            index, action, todo.get("status") or "pending", quote))
    lines.extend([
        "",
        "---",
        "导出时间：%s" % (record.get("saved_at") or ""),
        "版本：v%s" % (record.get("version") or 1),
    ])
    return "\n".join(lines) + "\n"
