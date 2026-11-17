# -*- coding: utf-8 -*-
"""汇总用户测试记录表（A6）。不编造数据；没有记录时明确提示。

兼容两种表头：
- A: task_a_done / task_a_seconds / ease_score
- B: task1_completed / task1_seconds / satisfaction_1_5
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path


def truth(v: str) -> bool:
    return str(v or "").strip().lower() in {"1", "true", "yes", "y", "是", "完成"}


def num(v: str):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def normalized(row):
    """把 A/B 两种记录表统一成同一结构。"""
    if "task_a_done" in row:
        return {
            "done": [row.get("task_a_done"), row.get("task_b_done"), row.get("task_c_done")],
            "seconds": [row.get("task_a_seconds"), row.get("task_b_seconds"), row.get("task_c_seconds")],
            "error_recovery": row.get("error_recovery"),
            "ease": row.get("ease_score"),
            "deadline": row.get("deadline_correct"),
            "materials": row.get("materials_correct"),
            "first_step": row.get("first_step_correct"),
            "issue": row.get("top_issue"),
        }
    return {
        "done": [row.get("task1_completed"), row.get("task2_completed"), row.get("task3_completed")],
        "seconds": [row.get("task1_seconds"), row.get("task2_seconds"), row.get("task3_seconds")],
        "error_recovery": row.get("task3_completed") or row.get("error_recovery_notes"),
        "ease": row.get("satisfaction_1_5"),
        "deadline": "",
        "materials": "",
        "first_step": "",
        "issue": row.get("raw_feedback") or row.get("error_recovery_notes"),
    }


def main(path: str):
    p = Path(path)
    if not p.exists():
        print("找不到记录表：%s" % p)
        return 2
    with p.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        # participant_id / experience_level 只是行号，不能算“已测试”。
        metric_fields = [k for k in (reader.fieldnames or [])
                         if k not in ("participant", "participant_id", "experience_level")]
        rows = [
            r for r in reader
            if any((r.get(k) or "").strip() for k in metric_fields)
        ]
    if not rows:
        print("暂无数据：请先按 B 的 frontend/docs/frontend/user-testing-kit.md（或 A 的 docs/用户测试/任务卡.md）完成真人测试，再填写记录表。")
        return 1

    rows = [normalized(row) for row in rows]
    n = len(rows)
    print("## 用户测试汇总\n")
    print("- 参与人数：%d" % n)
    for idx, label in enumerate(("任务 1 完成率", "任务 2 完成率", "任务 3 完成率")):
        count = sum(1 for r in rows if truth(r["done"][idx]))
        print("- %s：%d/%d（%.0f%%）" % (label, count, n, 100 * count / n))
    count = sum(1 for r in rows if truth(r["error_recovery"]))
    print("- 错误恢复率：%d/%d（%.0f%%）" % (count, n, 100 * count / n))
    for idx, label in enumerate(("任务 1 平均耗时", "任务 2 平均耗时", "任务 3 平均耗时")):
        vals = [num(r["seconds"][idx]) for r in rows]
        vals = [v for v in vals if v is not None]
        print("- %s：%s" % (label, ("%.1f 秒" % (sum(vals) / len(vals))) if vals else "无数据"))
    scores = [num(r["ease"]) for r in rows]
    scores = [v for v in scores if v is not None]
    if scores:
        print("- 易用性均值：%.2f / 5" % (sum(scores) / len(scores)))
    for key, label in (("deadline", "截止时间正确率"),
                       ("materials", "材料正确率"),
                       ("first_step", "第一步正确率")):
        if not any(r.get(key) not in (None, "") for r in rows):
            continue
        count = sum(1 for r in rows if truth(r.get(key)))
        print("- %s：%d/%d（%.0f%%）" % (label, count, n, 100 * count / n))

    issues = Counter((r.get("issue") or "").strip() for r in rows if (r.get("issue") or "").strip())
    print("\n**Top 问题**\n")
    for issue, count in issues.most_common(5):
        print("- %s（%d 次）" % (issue, count))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法：python scripts/summarize_user_test.py frontend/docs/frontend/user-testing-results.csv")
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
