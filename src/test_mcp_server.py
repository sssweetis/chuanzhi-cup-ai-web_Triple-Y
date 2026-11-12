# -*- coding: utf-8 -*-
"""MCP stdio Server 冒烟测试：initialize / tools/list / tools/call。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SERVER = HERE / "mcp_server.py"


def main():
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "check_date", "arguments": {"due_at": "2026-11-20T18:00:00+08:00",
                                                           "now": "2026-11-12T10:00:00+08:00"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "search_materials",
                    "arguments": {"query": "视频有什么要求",
                                  "documents": ["视频格式为 MP4，时长不超过 3 分钟。",
                                                "请提交报名表和成绩单。"]}}},
    ]
    raw = "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in messages)
    proc = subprocess.run([sys.executable, str(SERVER)], input=raw, text=True,
                          capture_output=True, cwd=str(HERE), timeout=30)
    lines = [json.loads(x) for x in proc.stdout.splitlines() if x.strip()]
    by_id = {x.get("id"): x for x in lines}
    checks = []
    checks.append(("initialize 返回 serverInfo", by_id.get(1, {}).get("result", {}).get("serverInfo", {}).get("name") == "buliuban-ai-tools"))
    tools = by_id.get(2, {}).get("result", {}).get("tools") or []
    checks.append(("tools/list 暴露 2 个工具", len(tools) == 2))
    date_text = by_id.get(3, {}).get("result", {}).get("content", [{}])[0].get("text", "")
    checks.append(("check_date 可调用", "days_left" in date_text))
    search_text = by_id.get(4, {}).get("result", {}).get("content", [{}])[0].get("text", "")
    checks.append(("search_materials 可调用", "视频" in search_text or "hits" in search_text))
    for name, ok in checks:
        print(("✅ " if ok else "❌ ") + name)
    if proc.stderr.strip():
        print("server stderr:", proc.stderr[:500])
    return 0 if all(ok for _n, ok in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
