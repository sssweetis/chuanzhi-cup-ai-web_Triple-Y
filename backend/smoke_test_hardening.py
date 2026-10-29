# -*- coding: utf-8 -*-
"""10/28–10/31 加固功能验收：双通知、版本历史、导出、日期、会话隔离、限流。"""
import json
import sys
import urllib.error
import urllib.request
import uuid

from rate_limit import SlidingWindowLimiter
from compare_store import compare_matters

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
PASS, FAIL = "✅", "❌"
results = []


def call(method, path, payload=None, headers=None, raw=None):
    data = raw
    hdrs = dict(headers or {})
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(BASE + path, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def jcall(*args, **kwargs):
    status, headers, raw = call(*args, **kwargs)
    try:
        return status, headers, json.loads(raw.decode("utf-8"))
    except Exception:
        return status, headers, {"success": False, "error": raw.decode("utf-8", "replace")}


def header(headers, name):
    wanted = name.lower()
    for key, value in headers.items():
        if key.lower() == wanted:
            return value
    return ""


def check(name, ok, detail=""):
    results.append((name, ok))
    print(("%s %s" % (PASS if ok else FAIL, name)) + ("  → %s" % detail if detail else ""))


def upload(filename, content, session_id):
    boundary = "----hardeningBoundary"
    body = (("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\n"
             "Content-Type: text/plain\r\n\r\n" % (boundary, filename)).encode("utf-8")
            + content + ("\r\n--%s--\r\n" % boundary).encode("utf-8"))
    return jcall("POST", "/api/files", raw=body, headers={
        "Content-Type": "multipart/form-data; boundary=%s" % boundary,
        "X-Session-Id": session_id,
    })


def main():
    print("目标服务：%s\n%s" % (BASE, "-" * 66))

    status, _, d1 = jcall("GET", "/api/tools/check-date?date=2026-10-31")
    data1 = d1.get("data") or {}
    check("日期核对：周末", status == 200 and d1.get("success") is True
          and data1.get("weekday_index") == 6 and data1.get("is_weekend") is True,
          "%s %s" % (data1.get("date"), data1.get("weekday")))

    _, _, d2 = jcall("GET", "/api/tools/check-date?date=2026-11-02")
    check("日期核对：工作日 + 距今", d2.get("success") is True
          and (d2.get("data") or {}).get("is_workday") is True
          and "days_left" in (d2.get("data") or {}), str((d2.get("data") or {}).get("deadline_label")))

    _, _, bad_date = jcall("GET", "/api/tools/check-date?date=not-a-date")
    check("日期核对：错误格式被拦截", bad_date.get("success") is False and bool(bad_date.get("error")))

    _, _, post_date = jcall("POST", "/api/tools/check-date", {
        "deadline": "2026-11-08T18:00:00+08:00",
    })
    post_info = post_date.get("data") or {}
    check("日期核对：兼容前端 POST deadline", post_date.get("success") is True
          and bool(post_info.get("message")) and bool(post_info.get("recommended_date")),
          "days_left=%s" % post_info.get("days_left"))

    session = "smoke-cmp-" + uuid.uuid4().hex[:6]
    left_text = "请于2026年11月2日17:00前提交报名表和成绩单。"
    right_text = "请于2026年11月3日18:00前提交报名表、成绩单和身份证复印件。"
    _, _, cmp = jcall("POST", "/api/compare", {
        "left": {"filename": "旧版通知.txt", "text": left_text},
        "right": {"filename": "新版通知.txt", "text": right_text},
    }, {"X-Session-Id": session})
    cd = cmp.get("data") or {}
    diff = cd.get("diff") or {}
    materials = diff.get("materials") or {}
    check("双通知分别保留名称与 Matter", cmp.get("success") is True
          and (cd.get("left") or {}).get("filename") == "旧版通知.txt"
          and (cd.get("right") or {}).get("filename") == "新版通知.txt"
          and bool(((cd.get("left") or {}).get("matter") or {}).get("id")))
    check("双通知识别截止/材料差异", (diff.get("deadline") or {}).get("changed") is True
          and "身份证复印件" in (materials.get("only_right") or []), str(materials))

    # 真实模型对同一文本重复解析也可能有细微差异；这里用同一个 Matter
    # 做确定性对比，专门验证“无差异”分支，避免把模型非确定性当成产品 bug。
    same_matter = (cd.get("left") or {}).get("matter") or {}
    _, _, same_cmp = jcall("POST", "/api/compare", {
        "left": {"filename": "同一份.txt", "matter": same_matter},
        "right": {"filename": "同一份副本.txt", "matter": same_matter},
    }, {"X-Session-Id": session})
    same_diff = ((same_cmp.get("data") or {}).get("diff") or {})
    check("双通知无差异", same_cmp.get("success") is True and same_diff.get("has_difference") is False,
          "changed=%s" % same_diff.get("has_difference"))

    incremental = compare_matters(
        {"materials": [{"material_name": "A form"}, {"material_name": "B score"}]},
        {"materials": [{"material_name": "C recommendation"}]},
        "original",
        "supplement: add C recommendation",
    )
    check("补充通知增量合并不误报删除",
          incremental["materials"]["only_left"] == []
          and "B score" in incremental["materials"]["common"]
          and incremental["materials"]["only_right"] == ["C recommendation"]
          and bool(incremental.get("changes"))
          and bool(incremental.get("affected_todos")),
          str(incremental["materials"]))
    same_id = (same_cmp.get("data") or {}).get("comparison_id")
    if same_id:
        jcall("DELETE", "/api/compare/%s" % same_id, headers={"X-Session-Id": session})

    comparison_id = cd.get("comparison_id")
    _, _, own = jcall("GET", "/api/compare/%s" % comparison_id, headers={"X-Session-Id": session})
    _, _, other = jcall("GET", "/api/compare/%s" % comparison_id, headers={"X-Session-Id": session + "-other"})
    check("对比记录可读取且跨会话不可见", own.get("success") is True and other.get("success") is False)

    matter_id = "matter_smoke_" + uuid.uuid4().hex[:8]
    session_a = session + "-a"
    session_b = session + "-b"
    v1 = [{"todo_id": "t1", "action": "准备报名表", "status": "pending", "source_ref": {"quote": "报名表"}}]
    v2 = [{"todo_id": "t1", "action": "准备报名表（已修改）", "status": "completed", "source_ref": {"quote": "报名表"}}]
    _, _, s1 = jcall("POST", "/api/prepare-list/save", {
        "matter_id": matter_id, "title": "测试清单", "todo_list": v1}, {"X-Session-Id": session_a})
    _, _, s2 = jcall("POST", "/api/prepare-list/save", {
        "matter_id": matter_id, "title": "测试清单", "todo_list": v2}, {"X-Session-Id": session_a})
    _, _, hist = jcall("GET", "/api/prepare-list/%s/history" % matter_id, headers={"X-Session-Id": session_a})
    hd = hist.get("data") or {}
    check("准备清单版本化并保留修改前内容", s1.get("success") is True and s2.get("success") is True
          and (s2.get("data") or {}).get("version") == 2
          and len(hd.get("history") or []) == 1
          and (hd.get("previous_todo_list") or [{}])[0].get("action") == "准备报名表")

    _, _, cross = jcall("GET", "/api/prepare-list/%s" % matter_id, headers={"X-Session-Id": session_b})
    check("准备清单跨会话隔离", cross.get("success") is False)

    status_csv, head_csv, raw_csv = call("GET", "/api/prepare-list/%s/export?format=csv" % matter_id,
                                         headers={"X-Session-Id": session_a})
    text_csv = raw_csv.decode("utf-8-sig")
    check("服务端导出 CSV", status_csv == 200 and "attachment" in header(head_csv, "Content-Disposition")
          and "准备报名表（已修改）" in text_csv)

    status_md, head_md, raw_md = call("GET", "/api/prepare-list/%s/export?format=md" % matter_id,
                                      headers={"X-Session-Id": session_a})

    _, _, raw_generic = call("GET", "/api/export", headers={"X-Session-Id": session_a})
    generic_text = raw_generic.decode("utf-8-sig")
    check("任务清单通用导出 /api/export", "准备报名表（已修改）" in generic_text,
          "bytes=%d" % len(raw_generic))
    text_md = raw_md.decode("utf-8")
    check("服务端导出 Markdown", status_md == 200 and "text/markdown" in header(head_md, "Content-Type")
          and "# 测试清单" in text_md and "v2" in text_md)

    _, _, file_a = upload("A的材料.txt", "视频要求：时长不超过三分钟。".encode("utf-8"), session_a)
    _, _, file_b = upload("B的材料.txt", "报名截止：十一月二日。".encode("utf-8"), session_b)
    a_id = (file_a.get("data") or {}).get("file_id")
    b_id = (file_b.get("data") or {}).get("file_id")
    _, _, list_a = jcall("GET", "/api/files", headers={"X-Session-Id": session_a})
    _, _, list_b = jcall("GET", "/api/files", headers={"X-Session-Id": session_b})
    names_a = [x.get("filename") for x in ((list_a.get("data") or {}).get("items") or [])]
    names_b = [x.get("filename") for x in ((list_b.get("data") or {}).get("items") or [])]
    check("文件列表按会话隔离", bool(a_id) and bool(b_id)
          and names_a == ["A的材料.txt"] and names_b == ["B的材料.txt"], "%s | %s" % (names_a, names_b))

    _, _, cross_file = jcall("GET", "/api/files/%s" % a_id, headers={"X-Session-Id": session_b})
    _, _, cross_delete = jcall("DELETE", "/api/files/%s" % a_id, headers={"X-Session-Id": session_b})
    _, _, own_delete = jcall("DELETE", "/api/files/%s" % a_id, headers={"X-Session-Id": session_a})
    check("文件不可跨会话读取/删除，可删除自己的", cross_file.get("success") is False
          and cross_delete.get("success") is False and own_delete.get("success") is True)

    _, _, delete_other_prepare = jcall("DELETE", "/api/prepare-list/%s" % matter_id,
                                       headers={"X-Session-Id": session_b})
    _, _, delete_own_prepare = jcall("DELETE", "/api/prepare-list/%s" % matter_id,
                                     headers={"X-Session-Id": session_a})
    check("准备清单删除也按会话隔离", delete_other_prepare.get("success") is False
          and delete_own_prepare.get("success") is True)

    _, _, delete_other_cmp = jcall("DELETE", "/api/compare/%s" % comparison_id,
                                   headers={"X-Session-Id": session + "-other"})
    _, _, delete_own_cmp = jcall("DELETE", "/api/compare/%s" % comparison_id,
                                 headers={"X-Session-Id": session})
    check("对比记录删除也按会话隔离", delete_other_cmp.get("success") is False
          and delete_own_cmp.get("success") is True)

    limiter = SlidingWindowLimiter()
    allowed = [limiter.hit("unit", 2)[0] for _ in range(3)]
    check("限流器窗口计数", allowed == [True, True, False], str(allowed))

    failed = [n for n, ok in results if not ok]
    print("-" * 66)
    print("共 %d 项，通过 %d 项%s" % (len(results), len(results) - len(failed),
                                     "，全部通过 🎉" if not failed else "，失败：%s" % failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
