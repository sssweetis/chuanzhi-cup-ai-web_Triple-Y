# -*- coding: utf-8 -*-
"""文件片段索引 / 检索 / 追问 自测（10/26–10/27）"""
import json, sys, urllib.error, urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
results = []
PASS, FAIL = "✅", "❌"


def call(method, path, payload=None):
    data, headers = None, {}
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


def upload(filename, content, ctype="text/plain"):
    boundary = "----codexFileBoundary"
    body = (("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\nContent-Type: %s\r\n\r\n"
             % (boundary, filename, ctype)).encode() + content + ("\r\n--%s--\r\n" % boundary).encode())
    req = urllib.request.Request(BASE + "/api/files", data=body,
                                 headers={"Content-Type": "multipart/form-data; boundary=%s" % boundary}, method="POST")
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
    lim = call("GET", "/api/files/limits")
    d = lim.get("data") or {}
    check("文件限制端点", lim.get("success") is True and d.get("max_bytes") == 10 * 1024 * 1024
          and "PDF" in (d.get("formats") or []), "max=%sMB formats=%s" % (d.get("max_mb"), d.get("formats")))

    r1 = upload("报名通知.txt", "报名要求：请提交报名表和成绩单，于11月2日17:00前交至行政楼305。".encode("utf-8"))
    d1 = r1.get("data") or {}
    check("上传 TXT 并切片段", r1.get("success") is True and d1.get("chunk_count", 0) >= 1,
          "file=%s chunks=%s" % (d1.get("file_id"), d1.get("chunk_count")))

    r2 = upload("视频要求.md", "视频要求：作品演示视频不超过3分钟，需包含项目介绍与演示。".encode("utf-8"), "text/markdown")
    d2 = r2.get("data") or {}
    check("上传第二份材料", r2.get("success") is True and bool(d2.get("file_id")), "file=%s" % d2.get("file_id"))

    lst = call("GET", "/api/files")
    items = (lst.get("data") or {}).get("items") or []
    check("文件列表", len(items) >= 2, "count=%d" % len(items))

    g = call("GET", "/api/files/%s" % d1.get("file_id"))
    chunks = (g.get("data") or {}).get("chunks") or []
    check("片段编号", bool(chunks) and all(c.get("chunk_id") for c in chunks), "chunks=%d" % len(chunks))

    s = call("POST", "/api/files/search", {"query": "视频时长", "top_k": 3})
    hits = (s.get("data") or {}).get("hits") or []
    check("检索命中正确材料", bool(hits) and any("视频" in h.get("filename", "") for h in hits),
          "top=%s score=%s" % (hits[0].get("filename") if hits else None, hits[0].get("score") if hits else None))

    a = call("POST", "/api/ask", {"question": "视频有什么要求？"})
    ad = a.get("data") or {}
    check("材料内问题能回答并附出处",
          a.get("success") is True and bool(ad.get("answer")) and bool(ad.get("sources")),
          "mode=%s answer=%s" % (ad.get("mode"), (ad.get("answer") or "")[:40]))

    a2 = call("POST", "/api/ask", {"question": "食堂几点开门？"})
    a2d = a2.get("data") or {}
    check("材料外问题不乱答", a2.get("success") is True and "没有找到" in (a2d.get("answer") or "") and not a2d.get("sources"),
          "answer=%s" % (a2d.get("answer") or "")[:40])

    bad = upload("tool.exe", b"MZ...", "application/octet-stream")
    check("不支持的格式被拦截", bad.get("success") is False and "仅支持" in (bad.get("error") or ""), "error=%s" % bad.get("error"))

    big = upload("big.txt", b"a" * (10 * 1024 * 1024 + 10))
    check("超过 10MB 被拦截", big.get("success") is False and "10 MB" in (big.get("error") or ""), "error=%s" % big.get("error"))

    failed = [n for n, ok in results if not ok]
    print("-" * 60)
    print("共 %d 项，通过 %d 项%s" % (len(results), len(results) - len(failed), "，全部通过 🎉" if not failed else "，失败：%s" % failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())