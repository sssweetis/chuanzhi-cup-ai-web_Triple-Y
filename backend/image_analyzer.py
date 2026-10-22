# -*- coding: utf-8 -*-
"""
图片解析（C 侧 10/23）：截图 →（团队视觉模型）→ 文字 → A 的 analyze_notification → Matter

A 提供的方案（2026-10-21 确认）：
    1. 图片 base64 → 视觉模型（gpt-4o / qwen-vl-max 等）提取纯文字
    2. 把文字交给 service.analyze_notification()
    3. 返回完整 Matter

与她的示例相比，这里做了两处适配：
    · import：`from analysis_pipeline import analyze_with_fallback`（backend 目录下直接可导入）
    · 返回：main.py 约定 `(matter, error)` 元组，而不是直接抛异常
另外：没有配置团队 Key 时返回明确提示，方便前端展示失败态。
"""

import base64
import logging
import os
from typing import Optional, Tuple

from analysis_pipeline import analyze_with_fallback
from service import analyze_notification_from_image

logger = logging.getLogger("image_analyzer")

IMAGE_MAX_BYTES = 5 * 1024 * 1024          # 5 MB
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "JPG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}

VISION_PROMPT = "请精确提取图片中的通知文字，保持原有格式，不要任何解释。"
VISION_TIMEOUT = 90


_ocr_engine = None


def _local_ocr(raw: bytes):
    """本地 OCR 兜底（RapidOCR / onnxruntime），不需要任何 Key。

    返回 (text | None, error | None)。
    """
    global _ocr_engine
    try:
        import cv2
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        return None, ("图片解析暂不可用：未配置 TEAM_LLM_API_KEY，且本地 OCR 未安装"
                      "（pip install -r requirements-ocr.txt）")

    try:
        if _ocr_engine is None:
            _ocr_engine = RapidOCR()
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return None, "图片解析失败：无法解码图片，请换一张 JPG/PNG/WEBP"
        result, _ = _ocr_engine(img)
        if not result:
            return None, "图片解析失败：未识别到文字，请换一张更清晰的通知截图"
        text = "\n".join(line[1] for line in result if len(line) > 1 and line[1])
        text = text.strip()
        if len(text) < 5:
            return None, "图片解析失败：未识别到有效文字，请换一张更清晰的截图"
        return text, None
    except Exception as e:
        logger.exception("本地 OCR 失败：%s", e)
        return None, "图片解析失败（本地 OCR）：%s" % e


def _vision_config():
    """团队视觉模型配置：TEAM_LLM_* 优先，其次回退到 LLM_*。"""
    api_key = (os.getenv("TEAM_LLM_API_KEY") or os.getenv("LLM_API_KEY") or "").strip()
    base_url = (os.getenv("TEAM_LLM_BASE_URL") or os.getenv("LLM_BASE_URL") or "").strip() or None
    model = (os.getenv("TEAM_LLM_MODEL") or "").strip() or os.getenv("LLM_MODEL") or "gpt-4o"
    return api_key, base_url, model


def _call_a_image(data_uri: str):
    """调用 A 的 analyze_notification_from_image（需要可用 Key）。

    A 的函数用 LLM_API_KEY；如果团队 Key 只配在 TEAM_LLM_*，这里临时映射过去。
    """
    team_key, team_base, team_model = _vision_config()
    if not team_key:
        return None
    os.environ["LLM_API_KEY"] = team_key
    if team_base:
        os.environ["LLM_BASE_URL"] = team_base
    if team_model:
        os.environ["LLM_MODEL"] = team_model
    try:
        return analyze_notification_from_image(data_uri)
    except Exception as e:
        logger.exception("A 的图片解析异常：%s", e)
        return {"success": False, "error": "图片解析异常：%s" % e}


def analyze_image_bytes(raw: bytes, filename: str, content_type: str) -> Tuple[Optional[dict], Optional[str]]:
    """返回 (matter_dict | None, error | None)。

    识别顺序：
        1) 有 Key → A 的视觉大模型（analyze_notification_from_image，截图专用规则）
        2) 无 Key / 视觉失败 → 本地 RapidOCR 兜底（不需要 Key）
        3) 都失败 → 可展示的中文错误
    """
    api_key, _base, _model = _vision_config()

    if api_key:
        data_uri = "data:%s;base64,%s" % (content_type, base64.b64encode(raw).decode("utf-8"))
        result = _call_a_image(data_uri) or {}
        if result.get("success") and result.get("data"):
            logger.info("视觉模型解析成功：%s", filename)
            return result["data"], None
        logger.warning("视觉模型不可用（%s），改用本地 OCR 兜底", result.get("error"))

    extracted_text, ocr_err = _local_ocr(raw)
    if ocr_err:
        return None, ocr_err
    logger.info("本地 OCR 识别完成：%s chars=%d", filename, len(extracted_text))

    result = analyze_with_fallback(extracted_text)
    if not result.get("success"):
        return None, result.get("error") or "图片内容解析失败"
    return result.get("data"), None
