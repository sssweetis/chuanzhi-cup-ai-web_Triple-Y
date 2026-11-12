# -*- coding: utf-8 -*-
"""汇总用户测试记录表（A6）。不编造数据；没有记录时明确提示。"""

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


def main(path: str):
    p = Path(path)
    if not p.exists():
        print("找不到记录表：%s" % p)
        return 2
    with p.open(encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if any((v or "").strip() for v in r.values())]
    if not rows:
        print("暂无数据：请先按 docs/用户测试/任务卡.md 完成真人测试，再填写记录表。")
        return 1

    n = len(rows)
    print("## 用户测试汇总\n")
    print("- 参与人数：%d" % n)
    for key, label in (("task_a_done", "任务 A 完成率"), ("task_b_done", "任务 B 完成率"),
                       ("task_c_done", "任务 C 完成率"), ("error_recovery", "错误恢复率")):
        count = sum(1 for r in rows if truth(r.get(key)))
        print("- %s：%d/%d（%.0f%%）" % (label, count, n, 100 * count / n))
    for key, label in (("task_a_seconds", "任务 A 平均耗时"),
                       ("task_b_seconds", "任务 B 平均耗时"),
                       ("task_c_seconds", "任务 C 平均耗时")):
        vals = [num(r.get(key)) for r in rows]
        vals = [v for v in vals if v is not None]
        print("- %s：%s" % (label, ("%.1f 秒" % (sum(vals) / len(vals))) if vals else "无数据"))
    scores = [num(r.get("ease_score")) for r in rows]
    scores = [v for v in scores if v is not None]
    if scores:
        print("- 易用性均值：%.2f / 5" % (sum(scores) / len(scores)))
    for key, label in (("deadline_correct", "截止时间正确率"),
                       ("materials_correct", "材料正确率"),
                       ("first_step_correct", "第一步正确率")):
        count = sum(1 for r in rows if truth(r.get(key)))
        print("- %s：%d/%d（%.0f%%）" % (label, count, n, 100 * count / n))

    issues = Counter((r.get("top_issue") or "").strip() for r in rows if (r.get("top_issue") or "").strip())
    print("\n**Top 问题**\n")
    for issue, count in issues.most_common(5):
        print("- %s（%d 次）" % (issue, count))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法：python scripts/summarize_user_test.py docs/用户测试/记录表.csv")
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
