# -*- coding: utf-8 -*-
"""
10/20 端到端验收脚本（C 负责）

先启动服务，再运行：
    python smoke_test_acceptance.py                     # 默认 http://127.0.0.1:8000
    python smoke_test_acceptance.py http://127.0.0.1:8123

做三件事：
    1. 用三套测试通知跑 /api/analyze，对照「期望 mode / 结构 / 字段规范」
    2. 用解析结果调 /api/check，确认缺项核对可用
    3. 输出一张验收表 + 问题清单（可直接发群里 / 挂进验收文档）

说明：Mock 模式下内容为虚构，但结构与模式判定与真实模式一致；
      真实模式下如果 A 的 prompt 有退化，这个脚本会把问题直接抓出来。
"""

import json
import sys
import time
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")

SAMPLES = [
    ("样本1", "simple", "请于10月25日18:00前提交奖学金报名表。"),
    ("样本2", "standard",
     "奖学金报名：10月25日18:00前提交报名表（附件1）、成绩单、身份证复印件，交至行政楼302，需本人签字。"),
    ("样本3", "complex",
     "奖学金报名流程：10月20日-25日在线填写报名表（附件1），上传身份证和成绩单；"
     "10月26-28日王老师审核，审核通过后才能缴费；10月29-30日缴费100元；11月1日打印准考证。"),
]

SIMPLE_BANNED = [
    "owner", "assignees", "participants", "contact", "default_location", "key_points",
    "attachments", "materials", "step_list", "warning_list", "permissions",
    "audit_log", "comments", "recurrence",
]
VALID_MATERIAL_TYPES = {"required", "optional", "unspecified"}

PASS, FAIL, WARN = "✅", "❌", "⚠️"


def call(path, payload=None, timeout=180):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers,
                                 method="POST" if payload is not None else "GET")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8")), (time.perf_counter() - t0) * 1000, r.status
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = {"success": False, "error": "HTTP %s" % e.code}
        return body, (time.perf_counter() - t0) * 1000, e.code


def check_matter(data, expected_mode):
    """返回 (问题列表, 警告列表)"""
    issues, warnings = [], []
    mode = data.get("mode")

    if mode != expected_mode:
        issues.append("mode 期望 %s，实际 %s" % (expected_mode, mode))

    if expected_mode == "simple":
        banned = [k for k in SIMPLE_BANNED if k in data]
        if banned:
            issues.append("simple 模式出现禁字段：%s" % ", ".join(banned))
    else:
        if not data.get("materials"):
            issues.append("%s 模式缺 materials" % expected_mode)
        if not data.get("step_list"):
            issues.append("%s 模式缺 step_list" % expected_mode)

    # 材料字段规范
    for m in data.get("materials") or []:
        mid, name = m.get("material_id"), m.get("material_name")
        mtype = m.get("material_type")
        if not mid:
            issues.append("材料缺 material_id：%r" % name)
        if not name:
            issues.append("材料缺 material_name（id=%s）" % mid)
        if mtype not in VALID_MATERIAL_TYPES:
            issues.append("材料 %s 的 material_type 非法：%r" % (name, mtype))
        if not (m.get("source_ref") or {}).get("quote"):
            warnings.append("材料「%s」没有 source_ref.quote（溯源缺失）" % name)

    # 步骤顺序（前端会按 order 排序，重复/缺失会导致显示错乱）
    steps = data.get("step_list") or []
    if steps:
        orders = [s.get("order") for s in steps]
        if any(o is None for o in orders):
            issues.append("有步骤缺 order 字段")
        elif len(set(orders)) != len(orders):
            issues.append("步骤 order 有重复：%s（前端排序会乱）" % orders)
        elif sorted(orders) != list(range(1, len(orders) + 1)):
            issues.append("步骤 order 不是 1..%d：%s" % (len(steps), orders))
        for s in steps:
            if not s.get("step_id"):
                issues.append("步骤缺 step_id（title=%r）" % s.get("title"))

    # 预警
    for w in data.get("warning_list") or []:
        if not w.get("message"):
            issues.append("预警 %s 缺少 message（前端只能显示空卡片）" % w.get("warning_id"))
        elif w.get("warning_type") not in ("time_conflict", "material_reuse", "deadline_risk", "missing_material"):
            warnings.append("预警类型不在枚举内：%r" % w.get("warning_type"))

    # 截止时间
    dl = data.get("deadline") or {}
    if dl and not dl.get("due_at"):
        issues.append("deadline 存在但缺 due_at")

    # 模式与 enabled_sections 一致性
    sections = data.get("enabled_sections") or []
    if mode == "simple" and sections and sections != ["summary", "schedule", "source"]:
        warnings.append("simple 的 enabled_sections 异常：%s" % sections)

    return issues, warnings


def main():
    print("=" * 78)
    print("10/20 端到端验收　目标服务：%s" % BASE)
    print("=" * 78)

    try:
        health, _, _ = call("/health", None, 10)
    except Exception as e:
        print("❌ 连不上服务：%s" % e)
        print("   请先在 backend 目录启动： python -m uvicorn main:app --reload --port 8000")
        return 1
    print("服务状态：%s\n" % json.dumps(health, ensure_ascii=False))

    rows, all_issues, all_warnings = [], [], []
    matters = {}

    for name, expected, text in SAMPLES:
        resp, cost, status = call("/api/analyze", {"text": text})
        if not resp.get("success"):
            rows.append((name, expected, "-", "-", "-", "%.0f" % cost, "%s %s" % (FAIL, resp.get("error"))))
            all_issues.append("%s：分析失败 - %s" % (name, resp.get("error")))
            continue
        data = resp.get("data") or {}
        matters[name] = data
        issues, warns = check_matter(data, expected)
        all_issues += ["%s：%s" % (name, i) for i in issues]
        all_warnings += ["%s：%s" % (name, w) for w in warns]

        mate = "%d" % len(data.get("materials") or [])
        step = "%d" % len(data.get("step_list") or [])
        warn = "%d" % len(data.get("warning_list") or [])
        verdict = PASS if not issues else "%s %d 个问题" % (FAIL, len(issues))
        rows.append((name, expected, data.get("mode"), mate, step, "%.0f" % cost, verdict))

        # 缺项核对
        chk, ccost, _ = call("/api/check", {"matter": data, "checked_material_ids": [], "profile": {"has_video": False}})
        if not chk.get("success"):
            all_issues.append("%s：/api/check 失败 - %s" % (name, chk.get("error")))
        else:
            cd = chk.get("data") or {}
            if not cd.get("summary"):
                all_issues.append("%s：/api/check 没有 summary" % name)

    print("%-6s %-9s %-9s %-6s %-6s %-8s %s" % ("样本", "期望mode", "实际mode", "材料", "步骤", "耗时ms", "结果"))
    print("-" * 78)
    for r in rows:
        print("%-6s %-9s %-9s %-6s %-6s %-8s %s" % r)

    print("\n" + "-" * 78)
    if all_issues:
        print("必须修复的问题（%d）：" % len(all_issues))
        for i in all_issues:
            print("  ❌ " + i)
    else:
        print("结构类问题：无 ✅")

    if all_warnings:
        print("\n建议关注（%d）：" % len(all_warnings))
        for w in all_warnings:
            print("  ⚠️  " + w)

    print("\n提示：")
    print("  · Mock 模式下内容是虚构的，结构与模式判定与真实模式一致")
    print("  · 切真实模式：.env 里 LLM_ENABLE_MOCK=0 + 填 LLM_API_KEY，重启后 /health 应为 mode=real")
    print("  · 真实模式首次请求可能要 10~30 秒，脚本超时已设 180 秒")

    return 1 if all_issues else 0


if __name__ == "__main__":
    sys.exit(main())