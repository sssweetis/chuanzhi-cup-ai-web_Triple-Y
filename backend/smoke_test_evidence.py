# -*- coding: utf-8 -*-
"""查看依据接口自测（10/22）：索引 / 单条 / 无依据→建议 / 参数兜底"""
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
    r = call("POST", "/api/analyze", {"text": "奖学金报名：10月25日18:00前提交报名表（附件1）、成绩单，交至行政楼302，需本人签字。"})
    matter = (r.get("data") or {})

    idx = call("POST", "/api/evidence/index", {"matter": matter})
    d = idx.get("data") or {}
    items = d.get("items") or []
    check("索引返回条目", idx.get("success") is True and len(items) > 0, "total=%s suggestions=%s" % (d.get("total"), d.get("suggestion_count")))
    mats = [i for i in items if i["target_type"] == "material"]
    check("材料条目有原文依据", bool(mats) and all(m["quote"] for m in mats), "materials=%d" % len(mats))

    if mats:
        e = call("POST", "/api/evidence", {"matter": matter, "target_type": "material", "target_id": mats[0]["target_id"]})
        ed = e.get("data") or {}
        check("单条查询返回 quote", e.get("success") is True and ed.get("found") is True and bool(ed.get("quote")),
              "%s → %s" % (ed.get("title"), (ed.get("quote") or "")[:28]))

    e2 = call("POST", "/api/evidence", {"matter": matter, "target_type": "deadline", "target_id": "overall"})
    check("截止时间可查依据", (e2.get("data") or {}).get("found") is True, "quote=%s" % (e2.get("data") or {}).get("quote"))

    e3 = call("POST", "/api/evidence", {"matter": matter, "target_type": "material", "target_id": "not-exist"})
    check("不存在的条目 → found=false", (e3.get("data") or {}).get("found") is False, "note=%s" % (e3.get("data") or {}).get("note"))

    fake = {"id": "matter_x", "title": "无依据测试", "materials": [{"material_id": "mat_9", "material_name": "系统建议材料"}],
            "key_points": ["系统补充的要点"]}
    e4 = call("POST", "/api/evidence", {"matter": fake, "target_type": "material", "target_id": "mat_9"})
    d4 = e4.get("data") or {}
    check("没有来源 → 标为建议", d4.get("is_suggestion") is True and "建议" in (d4.get("note") or ""), "note=%s" % d4.get("note"))

    e5 = call("POST", "/api/evidence", {"matter": matter, "target_type": "bad_type", "target_id": "x"})
    check("非法 target_type → 报错", e5.get("success") is False and bool(e5.get("error")), "error=%s" % e5.get("error"))

    e6 = call("POST", "/api/evidence", {"target_type": "material", "target_id": "x"})
    check("缺 matter → 报错", e6.get("success") is False and bool(e6.get("error")), "error=%s" % e6.get("error"))

    failed = [n for n, ok in results if not ok]
    print("-" * 60)
    print("共 %d 项，通过 %d 项%s" % (len(results), len(results) - len(failed), "，全部通过 🎉" if not failed else "，失败：%s" % failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())