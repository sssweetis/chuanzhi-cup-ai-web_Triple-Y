# -*- coding: utf-8 -*-
"""最小 MCP stdio Server（A 侧可选能力）。

不依赖第三方 MCP SDK：实现 MCP 的 newline-delimited JSON-RPC 子集：
  initialize / notifications/initialized / tools/list / tools/call

暴露只读工具：
  - check_date(due_at, now?)
  - search_materials(query, documents, top_k?)

运行：python src/mcp_server.py
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List

import service

SERVER_INFO = {"name": "buliuban-ai-tools", "version": "1.0.0"}
PROTOCOL_VERSION = "2024-11-05"

TOOLS = [
    {
        "name": "check_date",
        "description": "核对截止日期：剩余天数、星期、是否周末、风险等级和建议完成时间。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "due_at": {"type": "string", "description": "ISO 8601 截止时间"},
                "now": {"type": "string", "description": "可选，当前时间"},
            },
            "required": ["due_at"],
        },
    },
    {
        "name": "search_materials",
        "description": "在给定材料中做混合检索，返回带出处和分数的原文片段；只读、无副作用。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "documents": {"type": "array", "items": {"type": "string"}},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            "required": ["query", "documents"],
        },
    },
]


def _text_result(payload: Any, is_error: bool = False) -> Dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
        "isError": bool(is_error),
    }


def call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if name == "check_date":
        return _text_result(service.check_date(arguments.get("due_at"), arguments.get("now")))
    if name == "search_materials":
        hit = service.search_materials_tool(
            arguments.get("query") or "",
            arguments.get("documents") or [],
            top_k=int(arguments.get("top_k") or 3),
        )
        return _text_result(hit, not bool(hit.get("success")))
    return _text_result({"success": False, "error": "unknown tool: %s" % name}, True)


def handle(message: Dict[str, Any]) -> Dict[str, Any] | None:
    method = message.get("method")
    msg_id = message.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = message.get("params") or {}
        result = call_tool(params.get("name") or "", params.get("arguments") or {})
    else:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": "Method not found: %s" % method},
        }
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            response = {"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32700, "message": "Parse error"}}
        else:
            response = handle(message)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
