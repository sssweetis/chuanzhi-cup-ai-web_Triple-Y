# -*- coding: utf-8 -*-
"""A 侧统一 AI 失败语义。

目标：
1. 不把 OpenAI/DeepSeek 的原始异常、堆栈、Key 或内部路径返回给前端；
2. 给前端稳定的 code / stage / retryable，便于展示“人话 + 下一步”；
3. 保留日志中的完整异常，方便排查。

注意：不依赖 backend/error_contract.py，A 侧可单独运行。
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger("ai_error")

# 与前端 errors.js 的 error code 对齐；新增 code 时两边一起加。
ERROR_LABELS = {
    "AI_NO_KEY": "AI 服务未配置",
    "AI_AUTH": "AI 服务认证失败",
    "AI_QUOTA": "AI 服务额度不足",
    "AI_RATE_LIMIT": "AI 服务繁忙",
    "AI_TIMEOUT": "解析超时",
    "AI_NETWORK": "网络连接失败",
    "AI_SCHEMA": "结果格式不稳定",
    "AI_EMPTY": "没有识别到有效内容",
    "AI_PARSE_FAILED": "解析失败",
    "AI_UNKNOWN": "AI 处理失败",
}

RETRYABLE_CODES = {"AI_RATE_LIMIT", "AI_TIMEOUT", "AI_NETWORK", "AI_SCHEMA", "AI_PARSE_FAILED", "AI_UNKNOWN"}


def _request_id() -> str:
    return "ai_" + uuid.uuid4().hex[:10]


def ai_error(
    code: str,
    message: str,
    *,
    stage: str = "ai",
    retryable: Optional[bool] = None,
    detail: Optional[str] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """构造可直接放进 {success:false, data:null, error:...} 的错误对象。"""
    code = code or "AI_UNKNOWN"
    if retryable is None:
        retryable = code in RETRYABLE_CODES
    payload: Dict[str, Any] = {
        "code": code,
        "message": str(message or ERROR_LABELS.get(code, "AI 处理失败，请稍后重试")),
        "stage": stage,
        "retryable": bool(retryable),
        "request_id": request_id or _request_id(),
    }
    if detail:
        # detail 只给日志/开发排查，不返回给前端；由调用方显式读取。
        logger.warning("ai_error code=%s stage=%s detail=%s", code, stage, detail)
    return payload


def classify_exception(exc: BaseException, *, stage: str = "ai") -> Dict[str, Any]:
    """把常见异常映射为稳定的用户提示。"""
    name = type(exc).__name__
    text = str(exc or "")
    low = text.lower()

    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
        raise exc

    # 没有 Key：保留 LLM_API_KEY 字样，兼容 C 侧既有 Mock 兜底判断。
    if "llm_api_key" in low or "api key" in low and ("not set" in low or "missing" in low or "未配置" in text):
        return ai_error(
            "AI_NO_KEY",
            "未配置 LLM_API_KEY，当前无法调用真实模型；请使用演示模式或联系管理员",
            stage="config",
            retryable=False,
            detail=text,
        )

    if any(k in low for k in ("401", "unauthorized", "authentication", "authorization",
                              "invalid api key", "bearer", "认证失败")):
        return ai_error("AI_AUTH", "AI 服务认证失败，请联系管理员检查 Key", stage="ai_auth", retryable=False, detail=text)
    if any(k in low for k in ("insufficient_user_quota", "quota", "额度不足", "billing", "余额")):
        return ai_error("AI_QUOTA", "AI 服务额度不足，请稍后重试或切换演示模式", stage="ai_quota", retryable=False, detail=text)
    if any(k in low for k in ("429", "rate limit", "too many requests", "请求过于频繁")):
        return ai_error("AI_RATE_LIMIT", "AI 服务繁忙，请稍后重试", stage="ai_rate_limit", retryable=True, detail=text)
    if any(k in low for k in ("timeout", "timed out", "超时")):
        return ai_error("AI_TIMEOUT", "解析时间较长，请重试；也可以先粘贴文字内容", stage="ai_timeout", retryable=True, detail=text)
    if any(k in low for k in ("connection", "network", "connect", "dns", "ssl", "网络")):
        return ai_error("AI_NETWORK", "暂时连不上 AI 服务，请检查网络后重试", stage="ai_network", retryable=True, detail=text)
    if any(k in text for k in ("Schema 校验失败", "JSON", "json", "格式错误", "无法转为JSON")):
        return ai_error("AI_SCHEMA", "AI 返回格式不稳定，请重试一次", stage="ai_schema", retryable=True, detail=text)
    if any(k in text for k in ("返回了空内容", "结果为空", "没有识别到", "空内容")):
        return ai_error("AI_EMPTY", "没有识别到有效内容，请换一段更完整的通知或更清晰的截图", stage="ai_empty", retryable=True, detail=text)

    if "LLM_API_KEY" in text:
        # 兼容 LLMClient 直接抛出的 RuntimeError。
        return ai_error(
            "AI_NO_KEY",
            "未配置 LLM_API_KEY，当前无法调用真实模型；请使用演示模式或联系管理员",
            stage="config",
            retryable=False,
            detail=text,
        )

    return ai_error(
        "AI_UNKNOWN",
        "AI 处理失败，请稍后重试",
        stage=stage,
        retryable=True,
        detail=f"{name}: {text}",
    )


def failure_payload(exc: BaseException, *, stage: str = "ai") -> Dict[str, Any]:
    """返回 A 侧统一失败信封（data 固定为 None）。"""
    return {"success": False, "data": None, "error": classify_exception(exc, stage=stage)}


def message_of(error: Any, fallback: str = "AI 处理失败，请稍后重试") -> str:
    """兼容字符串错误和错误对象，供旧代码/日志使用。"""
    if isinstance(error, dict):
        return str(error.get("message") or fallback)
    return str(error or fallback)
