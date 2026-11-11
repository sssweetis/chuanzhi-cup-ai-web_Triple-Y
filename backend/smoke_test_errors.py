# -*- coding: utf-8 -*-
"""错误契约 v2 回归：验证 12 类失败都返回统一 error 对象。"""
import json
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
PASS, FAIL = "✅", "❌"
results = []


def call(method, path, payload=None, raw=None, headers=None):
    hdrs = {"X-Session-Id": "error-contract-test"}
    data = raw
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    hdrs.update(headers or {})
    req = urllib.request.Request(BASE + path, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, dict(r.headers), json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, dict(e.headers), json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, dict(e.headers), {"success": False, "error": "HTTP %s" % e.code}


def upload(path, field, filename, content, content_type):
    boundary = "----errorContractBoundary"
    body = (("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
             "Content-Type: %s\r\n\r\n" % (boundary, field, filename, content_type)).encode("utf-8")
            + content + ("\r\n--%s--\r\n" % boundary).encode("utf-8"))
    return call("POST", path, raw=body, headers={
        "Content-Type": "multipart/form-data; boundary=%s" % boundary,
    })


def error_info(body):
    err = body.get("error")
    return err if isinstance(err, dict) else {}


def check(name, body, expected_code=None):
    err = error_info(body)
    ok = (
        body.get("success") is False
        and body.get("data") is None
        and bool(err.get("code"))
        and bool(err.get("message"))
        and isinstance(err.get("retryable"), bool)
        and bool(err.get("stage"))
        and bool(err.get("request_id"))
        and (expected_code is None or err.get("code") == expected_code)
    )
    results.append((name, ok))
    print(("%s %s" % (PASS if ok else FAIL, name)) + "  → " + json.dumps(err, ensure_ascii=False))


def main():
    _, _, body = call("POST", "/api/analyze", {"text": ""})
    check("空文本", body, "TEXT_EMPTY")
    _, _, body = call("POST", "/api/analyze", {"text": "   \n"})
    check("空白文本", body, "TEXT_EMPTY")
    _, _, body = call("POST", "/api/analyze", {"text": "a" * 10001})
    check("超长文本", body, "TEXT_TOO_LONG")
    _, _, body = call("POST", "/api/analyze", raw=b"not-json", headers={"Content-Type": "application/json"})
    check("非法 JSON", body, "REQUEST_INVALID")
    _, _, body = upload("/api/analyze-image", "image", "bad.txt", b"hello", "text/plain")
    check("图片格式错误", body, "IMAGE_TYPE")
    _, _, body = upload("/api/analyze-image", "image", "empty.png", b"", "image/png")
    check("图片空文件", body, "IMAGE_EMPTY")
    _, _, body = upload("/api/analyze-image", "image", "big.png", b"x" * (5 * 1024 * 1024 + 1), "image/png")
    check("图片超限", body, "IMAGE_TOO_LARGE")
    _, _, body = upload("/api/analyze-pdf", "file", "bad.txt", b"hello", "text/plain")
    check("PDF 格式错误", body, "PDF_TYPE")
    _, _, body = upload("/api/analyze-pdf", "file", "empty.pdf", b"", "application/pdf")
    check("PDF 空文件", body, "PDF_EMPTY")
    _, _, body = upload("/api/analyze-pdf", "file", "big.pdf", b"x" * (10 * 1024 * 1024 + 1), "application/pdf")
    check("PDF 超限", body, "PDF_TOO_LARGE")
    _, _, body = call("POST", "/api/check", {"checked_material_ids": []})
    check("缺核对输入", body, "CHECK_INPUT")
    _, _, body = call("POST", "/api/files/search", {"query": ""})
    check("空检索", body, "SEARCH_EMPTY")

    failed = [name for name, ok in results if not ok]
    print("-" * 72)
    print("共 %d 项，通过 %d 项%s" % (len(results), len(results) - len(failed),
                                     "，全部通过 🎉" if not failed else "，失败：%s" % failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
