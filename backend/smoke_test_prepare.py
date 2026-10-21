# -*- coding: utf-8 -*-
"""准备清单接口自测（10/21）：生成 → 勾选 → 保存 → 读取 → 参数兜底"""
import json, sys, urllib.error, urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
results = []
PASS, FAIL = "✅", "❌"


def call(method, path, payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"success": False, "error": "HTTP %s" % e.code}


def check(name, ok, detail=""):
    results.append((name, ok))
    print(("%s %s" % (PASS if ok else FAIL, name)) + ("  → %s" % detail if detail else ""))


def main():
    print("目标服务：%s\n%s" % (BASE, "-" * 60))
    r = call("POST", "/api/analyze", {"text": "奖学金报名：10月25日18:00前提交报名表（附件1）、成绩单、身份证复印件，交至行政楼302，需本人签字。"})
    matter = (r.get("data") or {})
    todos = matter.get("todo_list") or []
    check("analyze 返回 todo_list", r.get("success") is True and len(todos) >= 1, "todos=%d" % len(todos))
    if todos:
        t0 = todos[0]
        check("todo 字段规范", bool(t0.get("todo_id")) and bool(t0.get("action")) and bool(t0.get("status")) and bool((t0.get("source_ref") or {}).get("quote")),
              "%s | %s" % (t0.get("todo_id"), t0.get("action")))

    p1 = call("POST", "/api/prepare-list", {"matter": matter, "checked_material_ids": []})
    d1 = p1.get("data") or {}
    check("prepare-list 生成缺项与待办", p1.get("success") is True and len(d1.get("missing_items") or []) >= 1 and len(d1.get("todo_list") or []) >= 1,
          "missing=%d todos=%d | %s" % (len(d1.get("missing_items") or []), len(d1.get("todo_list") or []), d1.get("summary")))

    all_ids = [m.get("material_id") for m in (matter.get("materials") or []) if m.get("material_id")]
    p2 = call("POST", "/api/prepare-list", {"matter": matter, "checked_material_ids": all_ids})
    check("全部勾选后缺项为空", ((p2.get("data") or {}).get("missing_items") or []) == [], "summary=%s" % (p2.get("data") or {}).get("summary"))

    edited = [dict(t, action=(t["action"] + "（已按我改的）")) for t in (d1.get("todo_list") or [])]
    s1 = call("POST", "/api/prepare-list/save", {"matter_id": matter.get("id"), "todo_list": edited})
    check("保存准备清单", s1.get("success") is True and (s1.get("data") or {}).get("saved_at"), "saved_at=%s" % (s1.get("data") or {}).get("saved_at"))
    g1 = call("GET", "/api/prepare-list/%s" % matter.get("id"))
    g1d = g1.get("data") or {}
    check("读取保存的清单", g1.get("success") is True and len(g1d.get("todo_list") or []) == len(edited), "todos=%d" % len(g1d.get("todo_list") or []))
    check("修改内容被保存", any("已按我改的" in t.get("action", "") for t in (g1d.get("todo_list") or [])))

    p3 = call("POST", "/api/prepare-list", {"text": "请于11月2日17:00前提交作品演示视频和报名表。"})
    check("只传 text 也能生成", p3.get("success") is True and bool((p3.get("data") or {}).get("todo_list")))

    p4 = call("POST", "/api/prepare-list", {})
    check("都不传 → 明确报错", p4.get("success") is False and bool(p4.get("error")), "error=%s" % p4.get("error"))
    s2 = call("POST", "/api/prepare-list/save", {"matter_id": "", "todo_list": []})
    check("保存缺 matter_id → 报错", s2.get("success") is False and bool(s2.get("error")), "error=%s" % s2.get("error"))
    g2 = call("GET", "/api/prepare-list/not-exist-id")
    check("读取不存在 → 报错", g2.get("success") is False and bool(g2.get("error")), "error=%s" % g2.get("error"))

    failed = [n for n, ok in results if not ok]
    print("-" * 60)
    print("共 %d 项，通过 %d 项%s" % (len(results), len(results) - len(failed), "，全部通过 🎉" if not failed else "，失败：%s" % failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())