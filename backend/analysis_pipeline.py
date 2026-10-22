# -*- coding: utf-8 -*-
"""
统一的抽取管道（C 侧）：有 Key 走 A 的真实抽取，无 Key 且 LLM_ENABLE_MOCK=1 时走离线 Mock。

main.py（文本/PDF）、image_analyzer.py（截图 OCR 后的文字）都用这里，
保证三条入口的降级行为完全一致。
"""

import logging
import os

from mock_extractor import mock_extract
from service import analyze_notification

logger = logging.getLogger("analysis_pipeline")

LLM_ENABLE_MOCK = (os.getenv("LLM_ENABLE_MOCK") or "0").strip() == "1"


def _has_key() -> bool:
    return bool((os.getenv("LLM_API_KEY") or "").strip())


def analyze_with_fallback(text: str) -> dict:
    """文本 → {success, data, error}。"""
    if LLM_ENABLE_MOCK and not _has_key():
        try:
            return {"success": True, "data": mock_extract(text), "error": None}
        except Exception as e:
            logger.exception("离线 Mock 失败：%s", e)

    result = analyze_notification(text)
    if (not result.get("success") and LLM_ENABLE_MOCK
            and "LLM_API_KEY" in str(result.get("error") or "")):
        try:
            logger.info("真实抽取不可用，降级到离线 Mock")
            return {"success": True, "data": mock_extract(text), "error": None}
        except Exception as e:
            logger.exception("离线 Mock 失败：%s", e)
    return result