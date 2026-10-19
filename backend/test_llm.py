# -*- coding: utf-8 -*-
"""
大模型密钥连通性验证（C 负责 · 协助配置密钥）

    python test_llm.py           # 按 .env 真实调用一次大模型（会消耗一点点额度）
    python test_llm.py --mock    # 离线自检，不联网、不消耗额度

验证内容：Key / Base URL / 模型名 是否可用，走的是真实调用还是 Mock 降级，耗时多少。
不会打印完整 Key（只显示脱敏结果）。
"""

import logging
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(HERE, ".env"))
except ImportError:
    print("未安装 python-dotenv：pip install -r requirements.txt")
    sys.exit(1)

from notification_extractor import LLMClient, MatterExtractor  # noqa: E402
from service import SYSTEM_PROMPT  # noqa: E402

TEST_TEXT = "请于10月25日18:00前提交奖学金报名表。"
MOCK_ONLY = "--mock" in sys.argv

api_key = (os.getenv("LLM_API_KEY") or "").strip()
base_url = (os.getenv("LLM_BASE_URL") or "https://api.openai.com/v1").strip()
model = (os.getenv("LLM_MODEL") or "gpt-4o").strip()

print("=" * 64)
print("大模型密钥连通性验证")
print("=" * 64)
print(f"LLM_API_KEY   : {(api_key[:6] + '…' + api_key[-4:]) if len(api_key) > 12 else ('未配置' if not api_key else '***')}")
print(f"LLM_BASE_URL  : {base_url}")
print(f"LLM_MODEL     : {model}")
print(f"LLM_ENABLE_MOCK: {os.getenv('LLM_ENABLE_MOCK') or '0'}")
print("-" * 64)

if MOCK_ONLY:
    os.environ.pop("LLM_API_KEY", None)
    print("模式：离线自检（--mock，不联网）")
elif not api_key:
    print("❌ 没有配置 LLM_API_KEY，无法验证真实调用。")
    print("   配置方法：powershell -ExecutionPolicy Bypass -File .\\configure_env.ps1")
    print("   或者先用离线自检：python test_llm.py --mock")
    sys.exit(1)

# 捕获 A 模块里的日志，用来判断到底走了真实调用还是 Mock 降级
records = []


class Capture(logging.Handler):
    def emit(self, record):
        records.append(record)


logger = logging.getLogger("notification_extractor")
logger.addHandler(Capture(level=logging.INFO))

client = LLMClient()
extractor = MatterExtractor(client, SYSTEM_PROMPT)

t0 = time.perf_counter()
try:
    matter, err = extractor.process(TEST_TEXT)
except Exception as e:
    cost = time.perf_counter() - t0
    print(f"❌ 调用失败（{cost:.1f}s）：{type(e).__name__}: {e}")
    print("-" * 64)
    print("常见原因：")
    print("  · 401 Unauthorized → API Key 不对或已过期")
    print("  · 404 model not found → LLM_MODEL 名称不对，或 LLM_BASE_URL 不匹配该平台")
    print("  · Connection error / timeout → 网络或代理问题（国内直连 OpenAI 通常需要代理）")
    print("  · 若只是想先跑通前后端，可在 .env 里设 LLM_ENABLE_MOCK=1")
    sys.exit(1)

cost = time.perf_counter() - t0
fell_back = any("降级到 mock" in r.getMessage() or "未配置" in r.getMessage() for r in records)

print(f"耗时：{cost * 1000:.0f} ms")
if err:
    print(f"❌ 抽取链路报错：{err}")
    sys.exit(1)

if MOCK_ONLY or fell_back:
    print("⚠️  本次走的是 Mock（虚构数据），不是真实大模型。")
    print("   若目标是真实调用：确认 .env 里 LLM_API_KEY 有值、LLM_BASE_URL / LLM_MODEL 正确，然后重跑。")
else:
    print("✅ 真实大模型调用成功！Key / Base URL / 模型名都可用。")

print(f"抽取结果：mode={matter.mode}  title={matter.title}  sections={matter.enabled_sections}")
print("-" * 64)
print("下一步：重启服务（run.ps1 或 uvicorn main:app --reload），然后打开 /health 应看到 "
      f"{{'status':'ok','mode':{'mock' if (MOCK_ONLY or fell_back) else 'real'}}}")