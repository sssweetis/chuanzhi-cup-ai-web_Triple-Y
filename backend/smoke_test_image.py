# -*- coding: utf-8 -*-
"""图片解析接口自测（10/23）：大小/格式限制 + 统一信封 + limits 端点"""
import base64, json, sys, urllib.error, urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
results = []
PASS, FAIL = "✅", "❌"


def check(name, ok, detail=""):
    results.append((name, ok))
    print(("%s %s" % (PASS if ok else FAIL, name)) + ("  → %s" % detail if detail else ""))


def upload(filename, content, content_type, field="image"):
    boundary = "----codexBoundary7d3f"
    body = b""
    if filename is not None:
        body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
                 "Content-Type: %s\r\n\r\n" % (boundary, field, filename, content_type)).encode("utf-8")
        body += content + b"\r\n"
    body += ("--%s--\r\n" % boundary).encode("utf-8")
    req = urllib.request.Request(BASE + "/api/analyze-image", data=body,
                                 headers={"Content-Type": "multipart/form-data; boundary=%s" % boundary},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"success": False, "error": "HTTP %s" % e.code}


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    print("目标服务：%s\n%s" % (BASE, "-" * 60))

    lim = get("/api/analyze-image/limits")
    d = lim.get("data") or {}
    check("limits 端点", lim.get("success") is True and d.get("max_bytes") == 5 * 1024 * 1024
          and "PNG" in (d.get("formats") or []) and d.get("field") == "image",
          "max=%sMB formats=%s" % (d.get("max_mb"), d.get("formats")))

    r = upload("shot.png", PNG_1PX, "image/png")
    check("合法 PNG 到达解析层（当前返回接入中提示）",
          r.get("success") is False and "图片解析" in (r.get("error") or ""), "error=%s" % r.get("error"))

    r = upload("shot.txt", b"hello", "text/plain")
    check("非法格式被拦截", r.get("success") is False and "仅支持" in (r.get("error") or ""), "error=%s" % r.get("error"))

    big = PNG_1PX + b"\0" * (5 * 1024 * 1024)
    r = upload("big.png", big, "image/png")
    check("超过 5MB 被拦截", r.get("success") is False and "5 MB" in (r.get("error") or ""), "error=%s" % r.get("error"))

    r = upload("empty.png", b"", "image/png")
    check("空文件被拦截", r.get("success") is False and "为空" in (r.get("error") or ""), "error=%s" % r.get("error"))

    r = upload(None, b"", "image/png")
    check("没传 image 字段 → 统一信封", r.get("success") is False and bool(r.get("error")), "error=%s" % r.get("error"))

    failed = [n for n, ok in results if not ok]
    print("-" * 60)
    print("共 %d 项，通过 %d 项%s" % (len(results), len(results) - len(failed), "，全部通过 🎉" if not failed else "，失败：%s" % failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())