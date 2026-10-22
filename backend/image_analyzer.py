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


def analyze_image_bytes(raw: bytes, filename: str, content_type: str) -> Tuple[Optional[dict], Optional[str]]:
    """返回 (matter_dict | None, error | None)。

    识别顺序：
        1) 配置了团队视觉模型 Key → 调视觉模型（A 指定的方案）
        2) 没有 Key / 视觉调用失败 → 本地 RapidOCR 兜底（不需要 Key）
        3) 都失败 → 返回可展示的中文错误
    """
    api_key, base_url, model = _vision_config()
    extracted_text = None

    if api_key:
        try:
            from openai import OpenAI

            b64 = base64.b64encode(raw).decode("utf-8")
            client = OpenAI(api_key=api_key, base_url=base_url, timeout=VISION_TIMEOUT)
            response = client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_PROMPT},
                        {"type": "image_url",
                         "image_url": {"url": "data:%s;base64,%s" % (content_type, b64)}},
                    ],
                }],
                temperature=0,
            )
            extracted_text = (response.choices[0].message.content or "").strip()
            logger.info("视觉模型识别完成：%s chars=%d model=%s", filename, len(extracted_text), model)
        except Exception as e:
            logger.warning("视觉模型不可用（%s），改用本地 OCR 兜底", e)

    if not extracted_text:
        extracted_text, ocr_err = _local_ocr(raw)
        if ocr_err:
            return None, ocr_err
        logger.info("本地 OCR 识别完成：%s chars=%d", filename, len(extracted_text))

    if len(extracted_text) < 5:
        return None, "图片解析失败：未识别到有效文字，请换一张更清晰的通知截图"

    result = analyze_with_fallback(extracted_text)
    if not result.get("success"):
        return None, result.get("error") or "图片内容解析失败"
    return result.get("data"), None
