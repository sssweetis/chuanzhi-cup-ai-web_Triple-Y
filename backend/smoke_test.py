# -*- coding: utf-8 -*-
"""
接口自测脚本（只用标准库，先启动服务再运行）：

    python smoke_test.py
    python smoke_test.py http://127.0.0.1:8000     # 指定地址

覆盖：/health、正常文本、空文本、超长文本、边界长度、非法请求体、CORS 预检、Mock 响应时间。
"""

import json
import sys
import time
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
PASS, FAIL = "✅", "❌"
results = []


def call(method, path, payload=None, headers=None, raw=None):
    data = None
    hdrs = dict(headers or {})
    if raw is not None:
        data = raw.encode("utf-8")
    elif payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(BASE + path, data=data, headers=hdrs, method=method)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8"), (time.perf_counter() - t0) * 1000
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8"), (time.perf_counter() - t0) * 1000


def check(name, passed, detail=""):
    results.append((name, passed))
    print(f"{PASS if passed else FAIL} {name}" + (f"  → {detail}" if detail else ""))


def body_json(*args):
    return json.loads(args[2])


print(f"目标服务：{BASE}\n" + "-" * 60)

# 1. /health
try:
    status, _, body, ms = call("GET", "/health")
    h = json.loads(body)
    check("GET /health 可访问", status == 200 and h.get("status") == "ok",
          f"{h}（{ms:.0f} ms，mode 表示当前是 mock 还是真实模型）")
except Exception as e:
    check("GET /health 可访问", False, f"连不上服务：{e}")
    print("\n请先在 backend 目录启动服务：python -m uvicorn main:app --reload --port 8000")
    sys.exit(1)

# 2. 正常文本
_, _, body, ms = call("POST", "/api/analyze", {"text": "请于10月25日18:00前提交奖学金报名表。"},
                      headers={"Origin": "http://localhost:5173"})
r = json.loads(body)
data = r.get("data") or {}
banned = [k for k in ("materials", "step_list", "attachments", "warning_list") if k in data]
check("正常文本返回 Matter", r.get("success") is True and bool(data),
      f"mode={data.get('mode')} title={data.get('title')}（{ms:.0f} ms）")
check("simple 模式无禁字段", not (data.get("mode") == "simple" and banned), f"禁字段：{banned or '无'}")

# 3. 参数校验
_, _, body, _ = call("POST", "/api/analyze", {"text": ""})
r = json.loads(body)
check("空文本被拦截", r.get("success") is False and r.get("error"), f"error={r.get('error')}")

_, _, body, _ = call("POST", "/api/analyze", {"text": "   \n "})
r = json.loads(body)
check("空白文本被拦截", r.get("success") is False and r.get("error"), f"error={r.get('error')}")

_, _, body, _ = call("POST", "/api/analyze", raw="not-a-json")
r = json.loads(body)
check("非法请求体走统一契约", r.get("success") is False and r.get("error"), f"error={r.get('error')}")

# 4. 超长与边界
long_text = "关于校园活动的通知内容。" * 1500
_, _, body, _ = call("POST", "/api/analyze", {"text": long_text})
r = json.loads(body)
check(f"超长文本（{len(long_text)} 字）被拦截",
      r.get("success") is False and "通知过长" in (r.get("error") or ""), f"error={r.get('error')}")

r = json.loads(call("POST", "/api/analyze", {"text": "a" * 3000})[2])
check("3000 字边界正常返回", r.get("success") is True)

# 5. CORS 预检
status, headers, _, _ = call("OPTIONS", "/api/analyze", headers={
    "Origin": "http://localhost:5173",
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "content-type",
})
check("CORS 预检放行 localhost:5173", headers.get("access-control-allow-origin") == "*",
      f"Allow-Origin={headers.get('access-control-allow-origin')}")

# 6. Mock 响应时间
t0 = time.perf_counter()
for _ in range(20):
    call("POST", "/api/analyze", {"text": "请于10月25日18:00前提交奖学金报名表。"})
avg = (time.perf_counter() - t0) / 20 * 1000
check("Mock 模式毫秒级响应", avg < 500, f"20 次平均 {avg:.1f} ms/次")

failed = [n for n, ok in results if not ok]
print("-" * 60)
print(f"共 {len(results)} 项，通过 {len(results) - len(failed)} 项" + ("，全部通过 🎉" if not failed else f"，失败：{failed}"))
sys.exit(1 if failed else 0)