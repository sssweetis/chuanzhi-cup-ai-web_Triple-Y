# -*- coding: utf-8 -*-
"""PDF 接口自测（10/25）：文字型 PDF → Matter；大小/格式/扫描件提示"""
import json, sys, urllib.error, urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
results = []
PASS, FAIL = "✅", "❌"


def build_pdf(text, with_text=True):
    content = ("BT /F1 12 Tf 50 760 Td (%s) Tj ET" % text).encode("latin-1") if with_text else b""
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(out))
        out += ("%d 0 obj\n" % i).encode() + o + b"\nendobj\n"
    xref = len(out)
    out += ("xref\n0 %d\n" % (len(objs) + 1)).encode() + b"0000000000 65535 f \n"
    for off in offsets:
        out += ("%010d 00000 n \n" % off).encode()
    out += ("trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)).encode()
    return bytes(out)


def upload(filename, content, content_type, field="file"):
    boundary = "----codexPdfBoundary"
    body = b""
    if filename is not None:
        body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\nContent-Type: %s\r\n\r\n"
                 % (boundary, field, filename, content_type)).encode("utf-8")
        body += content + b"\r\n"
    body += ("--%s--\r\n" % boundary).encode()
    req = urllib.request.Request(BASE + "/api/analyze-pdf", data=body,
                                 headers={"Content-Type": "multipart/form-data; boundary=%s" % boundary}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
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
    with urllib.request.urlopen(BASE + "/api/analyze-pdf/limits", timeout=30) as r:
        lim = json.loads(r.read().decode("utf-8"))
    d = lim.get("data") or {}
    check("limits 端点", lim.get("success") is True and d.get("max_bytes") == 10 * 1024 * 1024
          and d.get("max_pages") == 30 and d.get("field") == "file",
          "max=%sMB pages=%s field=%s" % (d.get("max_mb"), d.get("max_pages"), d.get("field")))

    pdf = build_pdf("Submit the report before Oct 25 18:00")
    r = upload("notice.pdf", pdf, "application/pdf")
    data = r.get("data") or {}
    quote = ((data.get("sources") or [{}])[0]).get("quote", "")
    check("文字型 PDF → 生成 Matter", r.get("success") is True and bool(data.get("title")) and "Submit the report" in quote,
          "title=%s quote=%s" % (data.get("title"), quote[:40]))

    r = upload("note.txt", b"hello", "text/plain")
    check("非 PDF 被拦截", r.get("success") is False and "仅支持 PDF" in (r.get("error") or ""), "error=%s" % r.get("error"))

    big = pdf + b"\0" * (10 * 1024 * 1024)
    r = upload("big.pdf", big, "application/pdf")
    check("超过 10MB 被拦截", r.get("success") is False and "10 MB" in (r.get("error") or ""), "error=%s" % r.get("error"))

    r = upload("scan.pdf", build_pdf("", with_text=False), "application/pdf")
    check("扫描件（无文字）给明确提示", r.get("success") is False and "未从 PDF 中提取到文字" in (r.get("error") or ""), "error=%s" % (r.get("error") or "")[:60])

    r = upload(None, b"", "application/pdf")
    check("没传 file 字段 → 统一信封", r.get("success") is False and bool(r.get("error")), "error=%s" % r.get("error"))

    failed = [n for n, ok in results if not ok]
    print("-" * 60)
    print("共 %d 项，通过 %d 项%s" % (len(results), len(results) - len(failed), "，全部通过 🎉" if not failed else "，失败：%s" % failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())