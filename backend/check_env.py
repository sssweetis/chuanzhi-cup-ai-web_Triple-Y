# -*- coding: utf-8 -*-
"""
服务端调用环境自检（C 负责）

    python check_env.py

一次性检查：Python 版本 / 依赖包 / .env 配置 / 当前运行模式 / 端口占用 / 抽取链路能否直接跑通。
输出「环境就绪 ✅」报告，可直接截图作为 10/16 的交付证据。
"""

import importlib
import json
import os
import socket
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))

REQUIRED = [
    ("fastapi", "Web 框架"),
    ("uvicorn", "ASGI 服务器"),
    ("pydantic", "请求/响应模型"),
    ("dotenv", "加载 .env"),
    ("openai", "调用大模型 API"),
    ("jsonschema", "Matter Schema 校验"),
]

DIST_NAME = {"dotenv": "python-dotenv"}


def _ver(mod: str) -> str:
    """取包版本（jsonschema 已弃用 __version__，统一走 importlib.metadata）。"""
    try:
        from importlib.metadata import version

        return version(DIST_NAME.get(mod, mod))
    except Exception:
        return ""


problems = []


def line(name, ok, detail=""):
    if not ok:
        problems.append(name)
    print(("✅ " if ok else "❌ ") + name + (f"    {detail}" if detail else ""))


print("=" * 64)
print("通知抽取服务 · 服务端调用环境自检")
print("=" * 64)

# ---------- 1. Python ----------
line(f"Python {sys.version.split()[0]}", sys.version_info >= (3, 10), sys.executable)

# ---------- 2. 依赖 ----------
print("-" * 64)
for mod, desc in REQUIRED:
    try:
        m = importlib.import_module(mod)
        line(f"依赖 {mod:<11} {desc}", True, _ver(mod))
    except ImportError:
        line(f"依赖 {mod:<11} {desc}", False, "未安装 → pip install -r requirements.txt")

# ---------- 3. .env ----------
print("-" * 64)
env_path = os.path.join(HERE, ".env")
line(".env 配置文件", os.path.exists(env_path), env_path if os.path.exists(env_path) else "复制 .env.example 为 .env")

try:
    from dotenv import load_dotenv
    load_dotenv(env_path)
except ImportError:
    pass

api_key = (os.getenv("LLM_API_KEY") or "").strip()
mock_on = (os.getenv("LLM_ENABLE_MOCK") or "0").strip() == "1"
mode = "real" if api_key else ("mock" if mock_on else "real")

if api_key:
    masked = api_key[:6] + "…" + api_key[-4:] if len(api_key) > 12 else "***"
    line("LLM_API_KEY 已配置", True, f"({masked})")
    line("当前模式 = real（走真实大模型）", True, f"model={os.getenv('LLM_MODEL') or 'gpt-4o'}  base_url={os.getenv('LLM_BASE_URL') or 'https://api.openai.com/v1'}")
elif mock_on:
    line("LLM_API_KEY 未配置", True, "LLM_ENABLE_MOCK=1 → 当前模式 = mock（返回虚构数据，用于前端联调）")
else:
    line("LLM_API_KEY 未配置且未开 Mock", False, "真实解析会报错：请跑 configure_env.ps1 配密钥，或 .env 里设 LLM_ENABLE_MOCK=1")

try:
    max_len = int((os.getenv("MAX_TEXT_LENGTH") or "3000").strip())
except ValueError:
    max_len = 3000
line("文本长度上限", True, f"{max_len} 字符" + ("（0 = 不限制）" if max_len <= 0 else ""))

# ---------- 4. 端口 ----------
print("-" * 64)
port = int((os.getenv("PORT") or "8000").strip() or "8000")
with socket.socket() as s:
    s.settimeout(0.6)
    in_use = s.connect_ex(("127.0.0.1", port)) == 0

if in_use:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as r:
            body = json.loads(r.read().decode("utf-8"))
        line(f"端口 {port} 已有服务在跑", True, f"/health → {body}（若 mode 与上面不一致，说明服务是改配置之前启动的，需重启）")
    except Exception as e:
        line(f"端口 {port} 被占用但 /health 不通", False, f"{e}")
else:
    line(f"端口 {port} 空闲", True, "启动命令：python -m uvicorn main:app --reload --port " + str(port))

# ---------- 5. 抽取链路 ----------
print("-" * 64)
try:
    sys.path.insert(0, HERE)
    from service import analyze_notification

    t0 = time.perf_counter()
    result = analyze_notification("请于10月25日18:00前提交奖学金报名表。")
    cost = (time.perf_counter() - t0) * 1000
    data = result.get("data") or {}
    line("抽取链路可用（service.analyze_notification）", bool(result.get("success")),
         f"mode={data.get('mode')} title={data.get('title')} 耗时={cost:.0f} ms")
except Exception as e:
    line("抽取链路可用（service.analyze_notification）", False, f"{type(e).__name__}: {e}")

# ---------- 结论 ----------
print("=" * 64)
if not problems:
    print("环境就绪 ✅  下一步：")
    print(f"  1) 启动服务：python -m uvicorn main:app --reload --host 0.0.0.0 --port {port}")
    print("  2) 自测接口：python smoke_test.py")
    print("  3) 验证密钥：python test_llm.py")
else:
    print("环境未就绪 ❌  待处理：")
    for p in problems:
        print("  - " + p)
    sys.exit(1)