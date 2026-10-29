# -*- coding: utf-8 -*-
"""
性能基线（C 侧）：Mock 模式下 /api/analyze 的延迟分布

    python smoke_test_perf.py [BASE] [次数]
"""
import json
import statistics
import sys
import time
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
N = int(sys.argv[2]) if len(sys.argv) > 2 else 100
TEXT = "请于11月2日17:00前提交报名表和成绩单，交至行政楼305。"


def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60) as r:
        body = json.loads(r.read().decode("utf-8"))
    return (time.perf_counter() - t0) * 1000, body


def main():
    print("目标：%s  次数：%d" % (BASE, N))
    lat = []
    ok = 0
    for i in range(N):
        ms, body = post("/api/analyze", {"text": TEXT})
        lat.append(ms)
        if body.get("success"):
            ok += 1
    lat.sort()
    print("成功：%d/%d" % (ok, N))
    print("平均：%.1f ms" % statistics.mean(lat))
    print("P50 ：%.1f ms" % lat[len(lat) // 2])
    print("P95 ：%.1f ms" % lat[min(len(lat) - 1, int(len(lat) * 0.95))])
    print("最大：%.1f ms" % lat[-1])
    return 0 if ok == N else 1


if __name__ == "__main__":
    sys.exit(main())