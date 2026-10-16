# -*- coding: utf-8 -*-
"""
用户情况核对接口自测（POST /api/check）—— 对应 10/18 里程碑

先启动服务，再执行：
    python smoke_test_check.py                    # 默认 http://127.0.0.1:8000
    python smoke_test_check.py http://127.0.0.1:8123

覆盖：只传 matter / 只传 text / 缺项差集 / 全勾选 / 自述冲突 / 参数兜底。
"""

import json
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
results = []
PASS, FAIL = "✅", "❌"


def call(path, payload):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def check(name, ok, detail=""):
    results.append((name, ok))
    print(("%s %s" % (PASS if ok else FAIL, name)) + ("  → %s" % detail if detail else ""))


SAMPLES = {}


def main():
    print("目标服务：%s\n%s" % (BASE, "-" * 60))

    # 1) 先拿一份真实抽取结果
    _, r = call("/api/analyze", {"text": "奖学金报名：10月25日18:00前提交报名表、成绩单，另可提交个人视频介绍。"})
    matter = (r.get("data") or {})
    check("先用 /api/analyze 拿到 Matter", r.get("success") is True and bool(matter), "mode=%s" % matter.get("mode"))

    # 2) 只传 matter（不跑模型）
    _, r2 = call("/api/check", {"matter": matter, "checked_material_ids": []})
    d2 = r2.get("data") or {}
    check("只传 matter 也能核对", r2.get("success") is True and d2.get("matter") == matter,
          "summary=%s" % d2.get("summary"))
    check("返回缺项字段齐全",
          all(k in d2 for k in ("missing_required", "missing_optional", "need_confirm", "profile_issues", "ready", "summary")),
          "ready=%s ratio=%s" % (d2.get("ready"), d2.get("ready_ratio")))

    # 3) 勾选所有必交材料 → 不再缺项
    required_ids = [m.get("material_id") for m in (d2.get("missing_required") or [])]
    all_ids = list(required_ids) + [m.get("material_id") for m in (matter.get("materials") or [])]
    _, r3 = call("/api/check", {"matter": matter, "checked_material_ids": [i for i in all_ids if i]})
    d3 = r3.get("data") or {}
    check("勾选齐全后 missing_required 为空", (d3.get("missing_required") or []) == [], "summary=%s" % d3.get("summary"))

    # 4) 用户自述「没有视频」→ 指出来
    m_video = {
        "mode": "standard",
        "title": "奖学金报名材料提交",
        "materials": [
            {"material_id": "mat_1", "material_name": "报名表", "material_type": "required", "required_by_source": True},
            {"material_id": "mat_2", "material_name": "个人视频介绍", "material_type": "optional"},
        ],
        "sources": [{"quote": "请提交报名表，另可提交个人视频介绍"}],
        "deadline": {"due_at": "2026-10-25T18:00:00+08:00"},
    }
    _, r4 = call("/api/check", {"matter": m_video, "checked_material_ids": ["mat_1"], "profile": {"has_video": False}})
    d4 = r4.get("data") or {}
    hit = [i.get("label") for i in (d4.get("profile_issues") or [])]
    check("自述『没有视频』被指出", "视频材料" in hit, "profile_issues=%s summary=%s" % (hit, d4.get("summary")))

    # 5) 原文没提视频时不能误报
    m_noVideo = {"mode": "standard", "title": "体检通知", "materials": [], "deadline": {"due_at": "2026-11-01T09:00:00+08:00"}}
    _, r5 = call("/api/check", {"matter": m_noVideo, "checked_material_ids": [], "profile": {"has_video": False}})
    check("原文没提视频时不误报", ((r5.get("data") or {}).get("profile_issues") or []) == [])

    # 6) 只传 text（服务端先抽取）
    _, r6 = call("/api/check", {"text": "请于10月25日18:00前提交奖学金报名表。", "checked_material_ids": []})
    check("只传 text 也能核对", r6.get("success") is True and bool((r6.get("data") or {}).get("matter")))

    # 7) 参数兜底
    _, r7 = call("/api/check", {})
    check("都不传 → 明确报错", r7.get("success") is False and bool(r7.get("error")), "error=%s" % r7.get("error"))

    _, r8 = call("/api/check", {"matter": "not-a-dict"})
    check("matter 类型不对 → 统一契约报错", r8.get("success") is False and bool(r8.get("error")), "error=%s" % r8.get("error"))

    _, r9 = call("/api/check", {"text": "关于校园活动的通知内容。" * 300})
    check("超长 text 被拦截", r9.get("success") is False and "3000" in (r9.get("error") or ""), "error=%s" % r9.get("error"))

    failed = [n for n, ok in results if not ok]
    print("-" * 60)
    print("共 %d 项，通过 %d 项%s" % (len(results), len(results) - len(failed), "，全部通过 🎉" if not failed else "，失败：%s" % failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())