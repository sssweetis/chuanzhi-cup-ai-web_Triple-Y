# -*- coding: utf-8 -*-
"""
演示前 / 验收前 · 一键自检（C 侧）

    python preflight.py                      # 默认 http://127.0.0.1:8000
    python preflight.py http://127.0.0.1:8123

检查：健康状态 → 文本解析 → 准备清单 → 材料上传 → 检索/追问 → 截图 OCR → PDF 解析
输出一张 PASS/FAIL 表，录演示视频或验收前跑一遍即可。
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
KIT = Path(__file__).resolve().parent.parent / "docs" / "demo-kit"
results = []
PASS, FAIL = "✅", "❌"


def check(name, ok, detail=""):
    results.append((name, ok))
    print(("%s %s" % (PASS if ok else FAIL, name)) + ("  → %s" % detail if detail else ""))


def post_json(path, payload, timeout=90, headers=None):
    hdrs = {"Content-Type": "application/json"}
    hdrs.update(headers or {})
    req = urllib.request.Request(BASE + path,
                                 data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                                 headers=hdrs, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def get_json(path, timeout=30, headers=None):
    req = urllib.request.Request(BASE + path, headers=headers or {}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def get_raw(path, timeout=30, headers=None):
    req = urllib.request.Request(BASE + path, headers=headers or {}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, dict(r.headers), r.read()


def delete_json(path, timeout=30, headers=None):
    req = urllib.request.Request(BASE + path, headers=headers or {}, method="DELETE")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def upload(path, file_path, field, ctype=None, timeout=180):
    boundary = "----preflightBoundary"
    raw = Path(file_path).read_bytes()
    filename = Path(file_path).name
    ctype = ctype or ("application/pdf" if filename.endswith(".pdf") else
                      "image/png" if filename.endswith(".png") else "text/plain")
    body = (("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\nContent-Type: %s\r\n\r\n"
             % (boundary, field, filename, ctype)).encode("utf-8") + raw + ("\r\n--%s--\r\n" % boundary).encode())
    req = urllib.request.Request(BASE + path, data=body,
                                 headers={"Content-Type": "multipart/form-data; boundary=%s" % boundary},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    print("=" * 66)
    print("演示前自检　目标：%s" % BASE)
    print("=" * 66)

    try:
        h = get_json("/health")
        check("服务健康 /health", h.get("status") == "ok", "mode=%s" % h.get("mode"))
    except Exception as e:
        check("服务健康 /health", False, "连不上：%s" % e)
        print("\n请先启动后端：python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000")
        return 1

    notice = (KIT / "01-标准通知-奖学金.txt").read_text(encoding="utf-8")
    t0 = time.perf_counter()
    r = post_json("/api/analyze", {"text": notice})
    ms = (time.perf_counter() - t0) * 1000
    data = r.get("data") or {}
    check("文本解析 /api/analyze", r.get("success") is True and bool(data.get("title")),
          "%s | mode=%s | %.0fms" % (data.get("title"), data.get("mode"), ms))

    prep = post_json("/api/prepare-list", {"matter": data, "checked_material_ids": []})
    pd = prep.get("data") or {}
    check("准备清单 /api/prepare-list", prep.get("success") is True and len(pd.get("todo_list") or []) >= 1,
          "%d 条待办 | %s" % (len(pd.get("todo_list") or []), pd.get("summary")))

    session_headers = {"X-Session-Id": "preflight-check"}
    date_check = get_json("/api/tools/check-date?date=2026-11-02")
    dd = date_check.get("data") or {}
    check("日期核对 /api/tools/check-date", date_check.get("success") is True and dd.get("weekday") == "周一",
          "%s | %s" % (dd.get("weekday"), dd.get("deadline_label")))

    cmp = post_json("/api/compare", {
        "left": {"filename": "旧通知.txt", "text": "请于2026年11月2日17:00前提交报名表和成绩单。"},
        "right": {"filename": "新通知.txt", "text": "请于2026年11月3日18:00前提交报名表、成绩单和身份证复印件。"},
    }, headers=session_headers)
    cmp_data = cmp.get("data") or {}
    cmp_diff = cmp_data.get("diff") or {}
    check("双通知对比 /api/compare", cmp.get("success") is True
          and bool(cmp_data.get("comparison_id")) and (cmp_diff.get("deadline") or {}).get("changed") is True,
          "材料差异=%s" % ((cmp_diff.get("materials") or {}).get("only_right") or []))

    matter_id = data.get("id") or "preflight_matter"
    todo_v1 = [{"todo_id": "todo_1", "action": "准备材料（v1）", "status": "pending", "source_ref": {"quote": "准备材料"}}]
    todo_v2 = [{"todo_id": "todo_1", "action": "准备材料（v2）", "status": "completed", "source_ref": {"quote": "准备材料"}}]
    save1 = post_json("/api/prepare-list/save", {"matter_id": matter_id, "title": "演示清单", "todo_list": todo_v1}, headers=session_headers)
    save2 = post_json("/api/prepare-list/save", {"matter_id": matter_id, "title": "演示清单", "todo_list": todo_v2}, headers=session_headers)
    hist = get_json("/api/prepare-list/%s/history" % matter_id, headers=session_headers)
    check("清单版本历史 /api/prepare-list/.../history", save1.get("success") is True and save2.get("success") is True
          and len((hist.get("data") or {}).get("history") or []) >= 1,
          "version=%s" % ((save2.get("data") or {}).get("version")))

    st_export, _, raw_export = get_raw("/api/prepare-list/%s/export?format=csv" % matter_id, headers=session_headers)
    check("清单导出 /api/prepare-list/.../export", st_export == 200
          and "准备材料（v2）" in raw_export.decode("utf-8-sig"), "CSV %d bytes" % len(raw_export))

    if cmp_data.get("comparison_id"):
        delete_json("/api/compare/%s" % cmp_data["comparison_id"], headers=session_headers)
    delete_json("/api/prepare-list/%s" % matter_id, headers=session_headers)

    a = upload("/api/files", KIT / "01-标准通知-奖学金.txt", "file")
    b = upload("/api/files", KIT / "03-材料视频通知.txt", "file")
    check("材料上传 /api/files", a.get("success") is True and b.get("success") is True,
          "%s / %s" % ((a.get("data") or {}).get("file_id"), (b.get("data") or {}).get("file_id")))

    lst = get_json("/api/files")
    items = (lst.get("data") or {}).get("items") or []
    check("材料列表 /api/files", len(items) >= 2, "%d 个文件" % len(items))

    q1 = post_json("/api/ask", {"question": "视频有什么要求？"})
    q1d = q1.get("data") or {}
    check("材料内追问", q1.get("success") is True and bool(q1d.get("answer")) and bool(q1d.get("sources")),
          "mode=%s | %s" % (q1d.get("mode"), (q1d.get("answer") or "")[:36]))

    q2 = post_json("/api/ask", {"question": "食堂几点开门？"})
    q2d = q2.get("data") or {}
    check("材料外拒答", q2.get("success") is True and (
        "没有找到" in (q2d.get("answer") or "") or q2d.get("found_evidence") is False),
          (q2d.get("answer") or "")[:40])

    img = upload("/api/analyze-image", KIT / "04-通知截图.png", "image", "image/png")
    idata = img.get("data") or {}
    check("截图解析 /api/analyze-image", img.get("success") is True and bool(idata.get("title")),
          "title=%s" % idata.get("title"))

    pdf = upload("/api/analyze-pdf", KIT / "05-文字型通知.pdf", "file", "application/pdf")
    pdata = pdf.get("data") or {}
    check("PDF 解析 /api/analyze-pdf", pdf.get("success") is True and bool(pdata.get("title")),
          "title=%s" % pdata.get("title"))

    failed = [n for n, ok in results if not ok]
    print("-" * 66)
    print("共 %d 项，通过 %d 项%s" % (len(results), len(results) - len(failed),
                                     "，可以开始演示 🎉" if not failed else "，请先修：%s" % failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())